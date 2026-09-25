from __future__ import annotations

import json
import hashlib
import fcntl
import pathlib
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field

_LABELS = ("STATUS", "DID", "VERIFIED", "NOT-CHECKED", "FLAGS", "NEXT")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_VERIFICATION_RUNNERS = {
    "artisan-test": ("php", "artisan", "test"),
    "artisan-route-list": ("php", "artisan", "route:list"),
    "composer-audit": ("composer", "audit"),
    "git-diff-check": ("git", "diff", "--check"),
    "git-status": ("git", "status", "--short"),
    "npm-build": ("npm", "run", "build"),
    "npm-lint": ("npm", "run", "lint"),
    "npm-test": ("npm", "test", "--"),
    "phpstan": ("vendor/bin/phpstan",),
    "phpunit": ("vendor/bin/phpunit",),
    "pint-test": ("vendor/bin/pint", "--test"),
    "pnpm-build": ("pnpm", "build"),
    "pnpm-lint": ("pnpm", "lint"),
    "pnpm-test": ("pnpm", "test"),
    "pest": ("vendor/bin/pest",),
    "python-unittest": ("python3", "-m", "unittest"),
    "sail-artisan-test": ("./vendor/bin/sail", "artisan", "test"),
    "sail-artisan-route-list": ("./vendor/bin/sail", "artisan", "route:list"),
    "sail-phpstan": ("./vendor/bin/sail", "bin", "phpstan"),
    "sail-phpunit": ("./vendor/bin/sail", "bin", "phpunit"),
    "sail-pint-test": ("./vendor/bin/sail", "bin", "pint", "--test"),
    "sail-pest": ("./vendor/bin/sail", "bin", "pest"),
}
_INTERNAL_VERIFICATION_RUNNERS = {"file-exists", "file-has-lines"}
_CRITERION_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_CHECKPOINT_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_TOOL_SIGNATURE = re.compile(r"^[0-9a-f]{64}$")
_BUDGET_KEYS = (
    "max_seconds",
    "max_tool_calls",
    "max_turns",
    "max_tokens",
    "max_usd",
)
_BUDGET_POLICY = {
    "stageField": "budget",
    "usageField": "usage",
    "requiredBeforeClaim": True,
    "preToolDimensions": ["max_seconds", "max_tool_calls"],
    "completionDimensions": ["max_turns", "max_tokens", "max_usd"],
    "onBreach": "budget_exceeded",
}
_CRITERION_POLICY = {
    "idsField": "criterion_ids",
    "evidenceField": "verified",
    "waiversField": "criterion_waivers",
    "requiredCoverage": "all",
    "waiverAuthority": "user",
}
_CHECKPOINT_POLICY = {
    "recordField": "checkpoints",
    "stageField": "checkpoint_id",
    "pausedStatus": "paused",
    "answerAuthority": "user",
    "optionActions": ["continue", "stop"],
}
_LOOP_POLICY = {
    "historyField": "loop_history",
    "eventField": "loop_events",
    "repeatThreshold": 3,
    "maxCycleLength": 4,
    "historyLimit": 24,
    "terminalStageStatus": "failed",
    "terminalDeliveryStatus": "stopped",
}
_EMPTY_USAGE = {
    "seconds": 0.0,
    "tool_calls": 0,
    "turns": 0,
    "tokens": 0,
    "cost_usd": 0.0,
}
_BOARD_MARK = {
    "done": "✔",
    "running": "▶",
    "queued": "·",
    "failed": "✖",
    "paused": "⏸",
    "budget_exceeded": "⛔",
    "skipped": "·",
}
AGENTS = frozenset(
    {
        "backend-developer",
        "business-analyst",
        "database-developer",
        "delivery-coordinator",
        "devops-engineer",
        "frontend-developer",
        "mobile-developer",
        "package-developer",
        "peer-router",
        "performance-engineer",
        "product-owner",
        "qa-engineer",
        "scrum-master",
        "security-engineer",
        "solution-architect",
        "tech-lead",
        "technical-writer",
        "ui-ux-designer",
    }
)


class ReportError(Exception):
    pass


class PlanError(Exception):
    pass


@dataclass
class StageSpec:
    id: str
    agent: str
    role: str
    success_criteria: list
    depends_on: list
    status: str = "queued"
    did: list = field(default_factory=list)
    verified: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    pair: str = ""
    awaiting_pair: bool = False
    reopens: int = 0
    owned_paths: list = field(default_factory=list)
    approval_categories: list = field(default_factory=list)
    approvals: list = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    claimed_at: str = ""
    claim_usage: dict = field(default_factory=dict)
    budget_events: list = field(default_factory=list)
    budget_exceeded_reason: str = ""
    criterion_ids: list = field(default_factory=list)
    criterion_waivers: list = field(default_factory=list)
    criterion_contract: int = 2
    checkpoint_id: str = ""
    loop_history: list = field(default_factory=list)
    loop_detected_reason: str = ""


@dataclass
class Delivery:
    name: str
    done_when: str
    cap: int
    status: str
    stages: list
    spawns: int = 0
    sprint: str = ""
    rules_printed: list = field(default_factory=list)
    issue: dict = field(default_factory=dict)
    pr: dict = field(default_factory=dict)
    repo: str = ""
    seen_checks: list = field(default_factory=list)
    seen_comments: list = field(default_factory=list)
    max_parallel: int = 3
    checkpoints: list = field(default_factory=list)
    loop_events: list = field(default_factory=list)


def _state_path(root, name):
    return pathlib.Path(root) / "docs" / "delivery" / name / "kernel.json"


@contextmanager
def _file_lock(path):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def _write_text_atomic(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            handle.write(text)
            temporary = pathlib.Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save(root, delivery):
    path = _state_path(root, delivery.name)
    _write_text_atomic(path, json.dumps(asdict(delivery), indent=2) + "\n")


def load(root, name):
    data = json.loads(_state_path(root, name).read_text())
    data.setdefault("sprint", "")
    data.setdefault("rules_printed", [])
    data.setdefault("issue", {})
    data.setdefault("pr", {})
    data.setdefault("repo", "")
    data.setdefault("seen_checks", [])
    data.setdefault("seen_comments", [])
    data.setdefault("max_parallel", 1)
    data.setdefault("checkpoints", [])
    data.setdefault("loop_events", [])
    stages = []
    for stage in data.pop("stages"):
        stage.setdefault("flags", [])
        stage.setdefault("pair", "")
        stage.setdefault("awaiting_pair", False)
        stage.setdefault("reopens", 0)
        stage.setdefault("owned_paths", [])
        stage.setdefault("approval_categories", [])
        stage.setdefault("approvals", [])
        stage["budget"] = _normalize_budget(stage.get("budget", {}))
        stage["usage"] = _normalize_usage(stage.get("usage", {}))
        stage.setdefault("claimed_at", "")
        claim_usage = stage.get("claim_usage", {})
        stage["claim_usage"] = (
            _normalize_usage(claim_usage) if claim_usage else {}
        )
        stage.setdefault("budget_events", [])
        stage.setdefault("budget_exceeded_reason", "")
        stage.setdefault("criterion_contract", 1)
        stage["criterion_ids"] = _normalize_criterion_ids(
            stage.get("success_criteria", []), stage.get("criterion_ids", [])
        )
        stage.setdefault("criterion_waivers", [])
        stage.setdefault("checkpoint_id", "")
        stage.setdefault("loop_history", [])
        stage.setdefault("loop_detected_reason", "")
        stages.append(StageSpec(**stage))
    return Delivery(stages=stages, **data)


def _norm_flag(text):
    return " ".join(text.strip().lower().split())


def _lesson_id(norm):
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


def _lessons_path(root):
    return pathlib.Path(root) / "docs" / "team" / "lessons.json"


def _load_lessons(root):
    path = _lessons_path(root)
    if not path.is_file():
        return {"lessons": []}
    data = json.loads(path.read_text())
    for lesson in data.get("lessons", []):
        norm = lesson.setdefault("norm", _norm_flag(lesson.get("text", "")))
        lesson.setdefault("id", _lesson_id(norm))
        lesson.setdefault("kind", "learned_hypothesis")
        deliveries = lesson.setdefault("deliveries", [])
        scope = lesson.setdefault("scope", [])
        provenance = lesson.setdefault(
            "provenance",
            {
                "source": "stage_flag",
                "observations": [
                    {"delivery": delivery, "agent": "unknown"}
                    for delivery in deliveries
                ],
            },
        )
        provenance.setdefault("source", "stage_flag")
        provenance.setdefault("observations", [])
        # Pre-provenance stores used `taught` as an automatic promotion. They
        # are hypotheses, not human instructions, until explicitly approved.
        status = lesson.get("status", "observed")
        if status == "seen":
            status = "candidate" if len(deliveries) >= 2 else "observed"
        elif status == "taught":
            approval = provenance.get("approval")
            status = "approved" if approval and approval.get("by") == "user" else "candidate"
        lesson["status"] = status
        if status == "approved" and not provenance.get("approval"):
            lesson["status"] = "candidate"
        if not scope:
            lesson["scope"] = ["unknown"]
    return data


def _save_lessons(root, data):
    path = _lessons_path(root)
    _write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def render_lessons(data):
    lessons = data.get("lessons", [])
    if not lessons:
        return "LESSONS: none\n"
    lines = ["LESSONS:"]
    for lesson in lessons:
        scope = ", ".join(lesson.get("scope", []))
        observations = lesson.get("provenance", {}).get("observations", [])
        approval = lesson.get("provenance", {}).get("approval") or {}
        lines.append(f"ID: {lesson['id']}")
        lines.append(f"RULE: {lesson['text']}")
        lines.append(f"SCOPE: {scope}")
        lines.append(f"STATUS: {lesson['status']}")
        lines.append(f"PROVENANCE: stage_flag ({len(observations)} observations)")
        if lesson["status"] == "approved":
            lines.append(
                f"APPROVED-BY: {approval['by']} at {approval['at']}"
            )
    return "\n".join(lines) + "\n"


def write_lessons_view(root, data):
    path = pathlib.Path(root) / "docs" / "team" / "lessons.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_lessons(data))


def _record_lesson(root, delivery_name, agent, text):
    norm = _norm_flag(text)
    if not norm or norm == "none":
        return
    with _file_lock(_lessons_path(root).with_suffix(".lock")):
        _record_lesson_unlocked(root, delivery_name, agent, text, norm)


def _record_lesson_unlocked(root, delivery_name, agent, text, norm):
    data = _load_lessons(root)
    for lesson in data["lessons"]:
        if lesson.get("norm") != norm:
            continue
        if delivery_name in lesson.get("deliveries", []):
            _save_lessons(root, data)
            write_lessons_view(root, data)
            return
        lesson["deliveries"].append(delivery_name)
        if agent not in lesson["scope"]:
            lesson["scope"].append(agent)
        lesson["provenance"]["observations"].append(
            {"delivery": delivery_name, "agent": agent}
        )
        if len(lesson["deliveries"]) >= 2 and lesson["status"] != "approved":
            lesson["status"] = "candidate"
        _save_lessons(root, data)
        write_lessons_view(root, data)
        return
    data["lessons"].append(
        {
            "id": _lesson_id(norm),
            "kind": "learned_hypothesis",
            "norm": norm,
            "text": text,
            "status": "observed",
            "scope": [agent],
            "deliveries": [delivery_name],
            "provenance": {
                "source": "stage_flag",
                "observations": [{"delivery": delivery_name, "agent": agent}],
            },
        }
    )
    _save_lessons(root, data)
    write_lessons_view(root, data)


def approve_lesson(root, lesson_id, *, approved_by="user"):
    if approved_by != "user":
        raise PlanError("learned rules can only be approved by the user")
    with _file_lock(_lessons_path(root).with_suffix(".lock")):
        data = _load_lessons(root)
        for lesson in data.get("lessons", []):
            if lesson.get("id") != lesson_id:
                continue
            lesson["status"] = "approved"
            lesson["provenance"]["approval"] = {
                "by": "user",
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            _save_lessons(root, data)
            write_lessons_view(root, data)
            return lesson
    raise PlanError(f"unknown lesson id: {lesson_id}")


def _approved_rules(root, stages):
    with _file_lock(_lessons_path(root).with_suffix(".lock")):
        data = _load_lessons(root)
    agents = {stage.agent for stage in stages}
    rules = []
    for lesson in data.get("lessons", []):
        approval = lesson.get("provenance", {}).get("approval") or {}
        if lesson.get("status") != "approved" or approval.get("by") != "user":
            continue
        if agents.intersection(lesson.get("scope", [])):
            rules.append(lesson["text"])
    return rules


def board_line(delivery):
    header = (
        f"{len(delivery.stages)} stages · cap: {delivery.cap} spawns · "
        f"done when: {delivery.done_when}"
    )
    lanes = []
    for stage in delivery.stages:
        pending = _pending_approvals(stage)
        mark = "⏸" if stage.status == "queued" and pending else _BOARD_MARK.get(stage.status, "·")
        label = f"pair:{stage.pair}" if stage.awaiting_pair and stage.pair else stage.agent
        if pending:
            label += f" approval:{','.join(pending)}"
        if stage.budget_exceeded_reason:
            label += f" budget:{stage.budget_exceeded_reason}"
        if stage.checkpoint_id:
            label += f" checkpoint:{stage.checkpoint_id}"
        if stage.loop_detected_reason:
            label += f" loop:{stage.loop_detected_reason}"
        matrix = ",".join(
            f"{row['id']}:{row['mark']}" for row in criterion_rows_for_stage(stage)
        )
        label += f" criteria[{matrix}]"
        lanes.append(f"{stage.id} {mark} {label}")
    return " · ".join([header, *lanes]) if lanes else header


def render_close(delivery, *, verified="none", not_checked="none"):
    issue_url = delivery.issue.get("url") or "none"
    pr_url = delivery.pr.get("url") or "none"
    return (
        f"VERIFIED: {verified}\n"
        f"NOT-CHECKED: {not_checked}\n"
        f"STATUS: {delivery.status}\n"
        f"BOARD: {board_line(delivery)}\n"
        f"ISSUE: {issue_url}\n"
        f"PR: {pr_url}\n"
    )


def render_graph(delivery):
    nodes = ", ".join(stage.agent for stage in delivery.stages)
    by_id = {stage.id: stage for stage in delivery.stages}
    edges = []
    for stage in delivery.stages:
        for dep in stage.depends_on:
            upstream = by_id.get(dep)
            if upstream:
                edges.append(f"{upstream.agent} -> {stage.agent}")
    levels = {}
    remaining = list(delivery.stages)
    while remaining:
        progressed = False
        for stage in list(remaining):
            if all(dep in levels for dep in stage.depends_on):
                levels[stage.id] = (
                    max((levels[dep] for dep in stage.depends_on), default=-1) + 1
                )
                remaining.remove(stage)
                progressed = True
        if not progressed:
            break
    parallel = []
    for level in sorted(set(levels.values())):
        agents = [stage.agent for stage in delivery.stages if levels.get(stage.id) == level]
        if len(agents) > 1:
            parallel.append(" + ".join(agents))
    return (
        f"NODES: {nodes}\n"
        f"EDGES: {', '.join(edges) if edges else 'none'}\n"
        f"PARALLEL: {'; '.join(parallel) if parallel else 'none'}\n"
        f"MAX-PARALLEL: {delivery.max_parallel}\n"
        f"ON-FAIL: stop\n"
    )


def render_checkpoints(delivery):
    lines = ["# Human checkpoints", ""]
    if not delivery.checkpoints:
        return "\n".join([*lines, "None.", ""])
    for checkpoint in delivery.checkpoints:
        lines.extend(
            [
                f"## {checkpoint['id']} — {checkpoint['status']}",
                "",
                f"- Stage: `{checkpoint['stage']}`",
                f"- Question: {checkpoint['question']}",
                f"- Risk: {checkpoint['risk']}",
                f"- Opened: {checkpoint['opened_at']} by {checkpoint['opened_by']}",
                "- Options:",
            ]
        )
        for index, option in enumerate(checkpoint["options"], start=1):
            recommended = " (recommended)" if option["id"] == checkpoint["recommended"] else ""
            lines.append(
                f"  {index}. `{option['id']}`{recommended} [{option['action']}] — "
                f"{option['label']}"
            )
        answer = checkpoint.get("answer") or {}
        if answer:
            note = f" — {answer['note']}" if answer.get("note") else ""
            lines.append(
                f"- Answer: `{answer['option']}` by {answer['by']} at {answer['at']}{note}"
            )
        else:
            lines.append("- Answer: pending")
        lines.append("")
    return "\n".join(lines)


def render_loops(delivery):
    lines = ["# Unproductive loops", ""]
    if not delivery.loop_events:
        return "\n".join([*lines, "None.", ""])
    for event in delivery.loop_events:
        tools = " → ".join(f"`{tool}`" for tool in event["tools"])
        lines.extend(
            [
                f"## {event['stage']} — stopped",
                "",
                f"- Detected: {event['at']}",
                f"- Pattern: {event['cycle_length']}-step cycle repeated "
                f"{event['repeats']} times",
                f"- Tools: {tools}",
                f"- Fingerprint: `{event['fingerprint']}`",
                "- Inputs: SHA-256 digests only; raw tool input is not persisted.",
                "",
            ]
        )
    return "\n".join(lines)


def write_views(root, delivery, *, verified="none", not_checked="none"):
    folder = pathlib.Path(root) / "docs" / "delivery" / delivery.name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "close.md").write_text(
        render_close(delivery, verified=verified, not_checked=not_checked)
    )
    (folder / "graph.md").write_text(render_graph(delivery))
    (folder / "checkpoints.md").write_text(render_checkpoints(delivery))
    (folder / "loops.md").write_text(render_loops(delivery))


def _has_criteria(stage):
    return bool(stage.success_criteria) and all(
        isinstance(item, str) and item.strip() for item in stage.success_criteria
    )


def _normalize_criterion_ids(criteria, raw_ids):
    if not isinstance(criteria, list):
        raise PlanError("success_criteria must be a list")
    if raw_ids in (None, []):
        raw_ids = [f"criterion-{index}" for index in range(1, len(criteria) + 1)]
    if not isinstance(raw_ids, list) or len(raw_ids) != len(criteria):
        raise PlanError("criterion_ids must match success_criteria one-to-one")
    if any(not isinstance(item, str) or not _CRITERION_ID.fullmatch(item) for item in raw_ids):
        raise PlanError("criterion_ids must be unique lowercase kebab-case identifiers")
    if len(raw_ids) != len(set(raw_ids)):
        raise PlanError("criterion_ids must be unique lowercase kebab-case identifiers")
    return list(raw_ids)


def _valid_waivers(stage):
    valid = {}
    for waiver in stage.criterion_waivers:
        if not isinstance(waiver, dict):
            continue
        criterion = waiver.get("criterion")
        if (
            criterion in stage.criterion_ids
            and waiver.get("by") == "user"
            and isinstance(waiver.get("reason"), str)
            and waiver["reason"].strip()
            and isinstance(waiver.get("at"), str)
            and waiver["at"]
        ):
            valid[criterion] = waiver
    return valid


def _verified_criterion_ids(stage):
    verified = {
        entry.get("criterion")
        for entry in stage.verified
        if isinstance(entry, dict)
        and entry.get("exit") == 0
        and entry.get("criterion") in stage.criterion_ids
    }
    if (
        stage.criterion_contract < 2
        and stage.status in ("done", "skipped")
        and any(
            isinstance(entry, dict) and entry.get("exit") == 0
            for entry in stage.verified
        )
    ):
        verified.update(stage.criterion_ids)
    return verified


def criterion_rows_for_stage(stage):
    verified = _verified_criterion_ids(stage)
    waived = _valid_waivers(stage)
    rows = []
    for criterion_id, text in zip(stage.criterion_ids, stage.success_criteria):
        status = (
            "verified" if criterion_id in verified
            else "waived" if criterion_id in waived
            else "pending"
        )
        rows.append(
            {
                "id": criterion_id,
                "text": text,
                "status": status,
                "mark": {"verified": "✓", "waived": "~", "pending": "·"}[status],
                "waiver": waived.get(criterion_id),
            }
        )
    return rows


def _criterion_coverage_complete(stage):
    return all(row["status"] in ("verified", "waived") for row in criterion_rows_for_stage(stage))


def _validate_criteria(stages):
    for stage in stages:
        if not _has_criteria(stage):
            raise PlanError(f"stage {stage.id} requires nonempty success criteria")
        if len(stage.success_criteria) != len(set(stage.success_criteria)):
            raise PlanError(f"stage {stage.id} success criteria must be unique")
        stage.criterion_ids = _normalize_criterion_ids(
            stage.success_criteria, stage.criterion_ids
        )
        if stage.criterion_waivers:
            raise PlanError(f"new stage {stage.id} cannot start with criterion waivers")
        stage.criterion_contract = 2


def _harness_registry():
    path = pathlib.Path(__file__).resolve().parents[2] / "config" / "agent-harness.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        profiles = payload["agents"]
        shared = payload["shared"]
        approval_policy = shared["approvalPolicy"]
        budget_policy = shared["budgetPolicy"]
        criterion_policy = shared["criterionPolicy"]
        checkpoint_policy = shared["checkpointPolicy"]
        loop_policy = shared["loopPolicy"]
        budgets = shared["budgets"]
        if not isinstance(profiles, dict):
            raise TypeError("agent profiles must be an object")
        if approval_policy != {
            "stageField": "approval_categories",
            "recordField": "approvals",
            "authority": "user",
            "requiredBeforeClaim": True,
        }:
            raise TypeError("approval policy is invalid")
        if budget_policy != _BUDGET_POLICY:
            raise TypeError("budget policy is invalid")
        if criterion_policy != _CRITERION_POLICY:
            raise TypeError("criterion policy is invalid")
        if checkpoint_policy != _CHECKPOINT_POLICY:
            raise TypeError("checkpoint policy is invalid")
        if loop_policy != _LOOP_POLICY:
            raise TypeError("loop policy is invalid")
        defaults = budgets["defaults"]
        ceilings = budgets["hardCeilings"]
        if set(defaults) != set(_BUDGET_KEYS) or set(ceilings) != set(_BUDGET_KEYS):
            raise TypeError("budget dimensions are invalid")
        return payload
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PlanError(f"cannot load agent harness policy from {path}") from exc


def _agent_profiles():
    return _harness_registry()["agents"]


def _normalize_budget(value):
    budgets = _harness_registry()["shared"]["budgets"]
    defaults = budgets["defaults"]
    ceilings = budgets["hardCeilings"]
    if value in (None, {}):
        value = {}
    if not isinstance(value, dict) or set(value) - set(_BUDGET_KEYS):
        raise PlanError(f"budget accepts only {', '.join(_BUDGET_KEYS)}")
    normalized = dict(defaults)
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
            raise PlanError(f"budget {key} must be a positive number")
        if key != "max_usd" and not isinstance(raw, int):
            raise PlanError(f"budget {key} must be a positive integer")
        if raw > ceilings[key]:
            raise PlanError(
                f"budget {key} exceeds hard ceiling {ceilings[key]}"
            )
        normalized[key] = raw
    for key in _BUDGET_KEYS:
        raw = normalized[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
            raise PlanError(f"invalid default budget {key}")
        if raw > ceilings[key]:
            raise PlanError(f"default budget {key} exceeds hard ceiling")
        if key != "max_usd" and not isinstance(raw, int):
            raise PlanError(f"default budget {key} must be an integer")
    normalized["max_usd"] = float(normalized["max_usd"])
    return normalized


def _normalize_usage(value):
    if value in (None, {}):
        return dict(_EMPTY_USAGE)
    if not isinstance(value, dict) or set(value) != set(_EMPTY_USAGE):
        raise PlanError("stage usage has invalid dimensions")
    normalized = {}
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
            raise PlanError(f"stage usage {key} must be nonnegative")
        if key in {"tool_calls", "turns", "tokens"} and not isinstance(raw, int):
            raise PlanError(f"stage usage {key} must be an integer")
        normalized[key] = float(raw) if key in {"seconds", "cost_usd"} else raw
    return normalized


def usage_tokens(usage):
    if not isinstance(usage, dict):
        raise PlanError("usage telemetry must be an object")
    total = 0
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        raw = usage.get(key, 0)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
            raise PlanError(f"usage telemetry {key} must be nonnegative")
        total += raw
    return int(total)


def usage_cost(usage, model):
    registry = _harness_registry()
    pricing = registry["shared"]["budgets"].get("pricing")
    if not isinstance(pricing, dict):
        raise PlanError("budget pricing policy is missing")
    rates_by_model = pricing.get("models")
    fallback = pricing.get("unknownModel")
    if not isinstance(rates_by_model, dict) or not isinstance(fallback, dict):
        raise PlanError("budget pricing policy is invalid")
    model_name = str(model or "")
    rates = None
    for alias, candidate in rates_by_model.items():
        if (
            model_name == alias
            or model_name.startswith(alias + "-")
            or model_name.startswith(alias + "[")
        ):
            rates = candidate
            break
    rates = rates or fallback
    try:
        input_rate = float(rates["input"])
        output_rate = float(rates["output"])
        cache_read_multiplier = float(pricing["cacheReadMultiplier"])
        cache_write_multiplier = float(pricing["cacheWriteMultiplier"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError("budget pricing policy is invalid") from exc
    tokens = {}
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        raw = usage.get(key, 0) if isinstance(usage, dict) else None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
            raise PlanError(f"usage telemetry {key} must be nonnegative")
        tokens[key] = float(raw)
    return (
        tokens["input_tokens"] * input_rate
        + tokens["output_tokens"] * output_rate
        + tokens["cache_read_input_tokens"] * input_rate * cache_read_multiplier
        + tokens["cache_creation_input_tokens"]
        * input_rate
        * cache_write_multiplier
    ) / 1_000_000


def _validate_budgets(stages):
    for stage in stages:
        stage.budget = _normalize_budget(stage.budget)
        stage.usage = _normalize_usage(stage.usage)
        if (
            stage.claimed_at
            or stage.claim_usage
            or stage.budget_events
            or stage.budget_exceeded_reason
            or stage.loop_history
            or stage.loop_detected_reason
        ):
            raise PlanError(f"new stage {stage.id} cannot start with runtime state")


def _agent_mutations():
    try:
        return {
            name: profile["mutation"]
            for name, profile in _agent_profiles().items()
        }
    except (KeyError, TypeError) as exc:
        raise PlanError("cannot load agent mutation policy") from exc


def _validate_approval_categories(stages):
    profiles = _agent_profiles()
    for stage in stages:
        categories = stage.approval_categories
        if not isinstance(categories, list):
            raise PlanError(
                f"approval_categories for stage {stage.id} must be a list"
            )
        if not all(
            isinstance(category, str) and category.strip()
            for category in categories
        ):
            raise PlanError(
                f"approval_categories for stage {stage.id} must contain strings"
            )
        if len(categories) != len(set(categories)):
            raise PlanError(
                f"duplicate approval category for stage {stage.id}"
            )
        allowed = profiles.get(stage.agent, {}).get("approvalCategories")
        if not isinstance(allowed, list):
            raise PlanError(
                f"cannot load approval categories for agent {stage.agent}"
            )
        for category in categories:
            if category not in allowed:
                raise PlanError(
                    f"unknown approval category for {stage.agent}: {category}"
                )
        if stage.approvals:
            raise PlanError(f"new stage {stage.id} cannot start with approval records")


def _pending_approvals(stage):
    if not isinstance(stage.approval_categories, list) or not all(
        isinstance(category, str) and category.strip()
        for category in stage.approval_categories
    ):
        raise PlanError(f"stage {stage.id} has invalid approval_categories")
    if not isinstance(stage.approvals, list):
        raise PlanError(f"stage {stage.id} has invalid approval records")
    approved = {
        record.get("category")
        for record in stage.approvals
        if isinstance(record, dict)
        and record.get("by") == "user"
        and isinstance(record.get("at"), str)
        and record.get("at")
    }
    return [
        category for category in stage.approval_categories
        if category not in approved
    ]


def approval_rows(root, name):
    delivery = load(root, name)
    rows = []
    for stage in delivery.stages:
        pending = set(_pending_approvals(stage))
        for category in stage.approval_categories:
            rows.append(
                {
                    "stage": stage.id,
                    "agent": stage.agent,
                    "category": category,
                    "status": "pending" if category in pending else "approved",
                }
            )
    return rows


def approve_stage_action(
    root, name, stage_id, category, *, approved_by="user"
):
    if approved_by != "user":
        raise PlanError("stage actions can only be approved by the user")
    lock_path = _state_path(root, name).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next((item for item in delivery.stages if item.id == stage_id), None)
        if stage is None:
            raise PlanError(f"stage {stage_id} is missing")
        if stage.status != "queued":
            raise PlanError(f"stage {stage_id} is {stage.status}")
        if category not in stage.approval_categories:
            raise PlanError(
                f"approval category {category} was not declared for stage {stage_id}"
            )
        for record in stage.approvals:
            if (
                isinstance(record, dict)
                and record.get("category") == category
                and record.get("by") == "user"
                and isinstance(record.get("at"), str)
                and record.get("at")
            ):
                return record
        approval = {
            "category": category,
            "by": "user",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        stage.approvals.append(approval)
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return approval


def criterion_rows(root, name):
    delivery = load(root, name)
    return [
        {
            "stage": stage.id,
            "agent": stage.agent,
            "criteria": criterion_rows_for_stage(stage),
        }
        for stage in delivery.stages
    ]


def waive_stage_criterion(
    root,
    name,
    stage_id,
    criterion_id,
    reason,
    *,
    waived_by="user",
):
    if waived_by != "user":
        raise PlanError("criterion waivers can only be granted by the user")
    if not isinstance(reason, str) or not reason.strip():
        raise PlanError("criterion waiver requires a nonempty reason")
    reason = " ".join(reason.split())
    if len(reason) > 500:
        raise PlanError("criterion waiver reason exceeds 500 characters")
    lock_path = _state_path(root, name).with_suffix(".lock")
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next((item for item in delivery.stages if item.id == stage_id), None)
        if stage is None:
            raise PlanError(f"stage {stage_id} is missing")
        if stage.status not in ("queued", "running", "paused"):
            raise PlanError(f"stage {stage_id} is {stage.status}")
        if criterion_id not in stage.criterion_ids:
            raise PlanError(
                f"criterion {criterion_id} was not declared for stage {stage_id}"
            )
        for waiver in stage.criterion_waivers:
            if (
                isinstance(waiver, dict)
                and waiver.get("criterion") == criterion_id
                and waiver.get("by") == "user"
                and waiver.get("at")
            ):
                return waiver
        waiver = {
            "criterion": criterion_id,
            "reason": reason,
            "by": "user",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        stage.criterion_waivers.append(waiver)
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return waiver


def _checkpoint_text(raw, label, *, limit, required=True):
    if not isinstance(raw, str):
        raise PlanError(f"checkpoint {label} must be text")
    normalized = " ".join(raw.split())
    if required and not normalized:
        raise PlanError(f"checkpoint {label} is required")
    if len(normalized) > limit:
        raise PlanError(f"checkpoint {label} exceeds {limit} characters")
    return normalized


def _normalize_checkpoint_options(options):
    if not isinstance(options, list) or not 2 <= len(options) <= 5:
        raise PlanError("checkpoint requires between 2 and 5 options")
    normalized = []
    for option in options:
        if not isinstance(option, dict) or set(option) != {"id", "label", "action"}:
            raise PlanError("checkpoint options require exactly id, label, and action")
        option_id = option.get("id")
        if not isinstance(option_id, str) or not _CHECKPOINT_ID.fullmatch(option_id):
            raise PlanError("checkpoint option ids must be lowercase kebab-case")
        action = option.get("action")
        if action not in _CHECKPOINT_POLICY["optionActions"]:
            raise PlanError("checkpoint option action must be continue or stop")
        normalized.append(
            {
                "id": option_id,
                "label": _checkpoint_text(
                    option.get("label"), "option label", limit=200
                ),
                "action": action,
            }
        )
    ids = [option["id"] for option in normalized]
    if len(ids) != len(set(ids)):
        raise PlanError("checkpoint option ids must be unique")
    return normalized


def _pending_checkpoint(delivery, stage_id=None):
    return next(
        (
            checkpoint
            for checkpoint in delivery.checkpoints
            if isinstance(checkpoint, dict)
            and checkpoint.get("status") == "pending"
            and (stage_id is None or checkpoint.get("stage") == stage_id)
        ),
        None,
    )


def checkpoint_rows(root, name):
    delivery = load(root, name)
    return list(delivery.checkpoints)


def loop_rows(root, name):
    delivery = load(root, name)
    return list(delivery.loop_events)


def open_checkpoint(
    root,
    name,
    stage_id,
    checkpoint_id,
    question,
    risk,
    options,
    recommended,
):
    if not isinstance(checkpoint_id, str) or not _CHECKPOINT_ID.fullmatch(checkpoint_id):
        raise PlanError("checkpoint id must be a lowercase kebab-case identifier")
    question = _checkpoint_text(question, "question", limit=500)
    risk = _checkpoint_text(risk, "risk", limit=500)
    options = _normalize_checkpoint_options(options)
    option_ids = {option["id"] for option in options}
    if recommended not in option_ids:
        raise PlanError("checkpoint recommended option must name a declared option")
    expected = {
        "id": checkpoint_id,
        "stage": stage_id,
        "question": question,
        "risk": risk,
        "options": options,
        "recommended": recommended,
    }
    lock_path = _state_path(root, name).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next((item for item in delivery.stages if item.id == stage_id), None)
        if stage is None:
            raise PlanError(f"stage {stage_id} is missing")
        existing = next(
            (
                item for item in delivery.checkpoints
                if isinstance(item, dict) and item.get("id") == checkpoint_id
            ),
            None,
        )
        if existing is not None:
            actual = {key: existing.get(key) for key in expected}
            if existing.get("status") == "pending" and actual == expected:
                return existing
            raise PlanError(f"checkpoint id {checkpoint_id} already exists")
        pending = _pending_checkpoint(delivery, stage_id)
        if pending is not None:
            raise PlanError(
                f"stage {stage_id} already has pending checkpoint {pending['id']}"
            )
        if stage.status not in ("queued", "running"):
            raise PlanError(f"stage {stage_id} is {stage.status}")
        if stage.claimed_at:
            raise PlanError(
                f"stage {stage_id} requires completion telemetry before checkpoint"
            )
        checkpoint = {
            **expected,
            "status": "pending",
            "opened_by": "main",
            "opened_at": _now_utc().isoformat(timespec="seconds"),
            "answer": {},
        }
        delivery.checkpoints.append(checkpoint)
        stage.checkpoint_id = checkpoint_id
        stage.status = "paused"
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return checkpoint


def resolve_checkpoint(
    root,
    name,
    checkpoint_id,
    option_id,
    *,
    note="",
    answered_by="user",
):
    if answered_by != "user":
        raise PlanError("checkpoints can only be answered by the user")
    note = _checkpoint_text(note, "answer note", limit=500, required=False)
    lock_path = _state_path(root, name).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        delivery = load(root, name)
        checkpoint = next(
            (
                item for item in delivery.checkpoints
                if isinstance(item, dict) and item.get("id") == checkpoint_id
            ),
            None,
        )
        if checkpoint is None:
            raise PlanError(f"checkpoint {checkpoint_id} is missing")
        if checkpoint.get("status") == "resolved":
            answer = checkpoint.get("answer", {})
            if answer.get("option") == option_id and answer.get("note", "") == note:
                return checkpoint
            raise PlanError(f"checkpoint {checkpoint_id} is already resolved")
        if checkpoint.get("status") != "pending":
            raise PlanError(f"checkpoint {checkpoint_id} is invalid")
        option = next(
            (
                item for item in checkpoint.get("options", [])
                if isinstance(item, dict) and item.get("id") == option_id
            ),
            None,
        )
        if option is None:
            raise PlanError(
                f"checkpoint {checkpoint_id} option {option_id} is not declared"
            )
        stage = next(
            (item for item in delivery.stages if item.id == checkpoint.get("stage")),
            None,
        )
        if stage is None or stage.checkpoint_id != checkpoint_id or stage.status != "paused":
            raise PlanError(f"checkpoint {checkpoint_id} stage state is inconsistent")
        checkpoint["status"] = "resolved"
        checkpoint["answer"] = {
            "option": option["id"],
            "label": option["label"],
            "action": option["action"],
            "note": note,
            "by": "user",
            "at": _now_utc().isoformat(timespec="seconds"),
        }
        stage.checkpoint_id = ""
        if option["action"] == "stop":
            stage.status = "failed"
            delivery.status = "stopped"
        else:
            stage.status = "queued"
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return checkpoint


def _now_utc():
    return datetime.now(timezone.utc)


def _parse_utc_timestamp(raw, *, label):
    if not isinstance(raw, str) or not raw:
        raise PlanError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise PlanError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise PlanError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _active_budget_targets(root, agent):
    base = pathlib.Path(root) / "docs" / "delivery"
    if not base.is_dir():
        return []
    targets = []
    for state_path in sorted(base.glob("*/kernel.json")):
        delivery = load(root, state_path.parent.name)
        if delivery.status != "running":
            continue
        for stage in delivery.stages:
            if stage.agent == agent and stage.status == "running":
                targets.append((delivery.name, stage.id))
    return targets


def _budget_target(root, agent):
    targets = _active_budget_targets(root, agent)
    if len(targets) > 1:
        raise PlanError(f"more than one running stage exists for agent {agent}")
    return targets[0] if targets else None


def _budget_event_seen(stage, event_id):
    return bool(event_id) and event_id in stage.budget_events


def _remember_budget_event(stage, event_id):
    if not event_id:
        return
    stage.budget_events.append(str(event_id))
    stage.budget_events = stage.budget_events[-128:]


def _active_seconds(stage, now):
    elapsed = float(stage.usage["seconds"])
    if stage.claimed_at:
        started = _parse_utc_timestamp(
            stage.claimed_at, label=f"stage {stage.id} claimed_at"
        )
        elapsed += max(0.0, (now - started).total_seconds())
    return elapsed


def _usage_budget_reason(stage):
    dimensions = (
        ("max_seconds", "seconds"),
        ("max_tool_calls", "tool_calls"),
        ("max_turns", "turns"),
        ("max_tokens", "tokens"),
        ("max_usd", "cost_usd"),
    )
    for budget_key, usage_key in dimensions:
        if stage.usage[usage_key] > stage.budget[budget_key]:
            return budget_key
    return ""


def _mark_budget_exceeded(root, delivery, stage, reason, *, now):
    if stage.claimed_at:
        stage.usage["seconds"] = _active_seconds(stage, now)
    stage.claimed_at = ""
    stage.status = "budget_exceeded"
    stage.budget_exceeded_reason = reason
    delivery.status = "budget_exceeded"
    save(root, delivery)
    write_views(root, delivery, not_checked=delivery.done_when or "none")


def tool_call_signature(tool_name, tool_input):
    """Return a deterministic digest without persisting raw tool input."""
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise PlanError("loop detection requires a tool name")
    if not isinstance(tool_input, dict):
        raise PlanError("loop detection requires an object tool input")
    canonical = json.dumps(
        {"tool": tool_name, "input": tool_input},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _repeated_tool_cycle(history):
    signatures = [entry["signature"] for entry in history]
    repeats = _LOOP_POLICY["repeatThreshold"]
    max_cycle = min(
        _LOOP_POLICY["maxCycleLength"],
        len(signatures) // repeats,
    )
    for cycle_length in range(1, max_cycle + 1):
        width = cycle_length * repeats
        tail = signatures[-width:]
        pattern = tail[:cycle_length]
        if tail == pattern * repeats:
            return cycle_length
    return 0


def _mark_loop_detected(root, delivery, stage, history, cycle_length, *, now):
    repeats = _LOOP_POLICY["repeatThreshold"]
    pattern = history[-cycle_length:]
    fingerprint = hashlib.sha256(
        ":".join(entry["signature"] for entry in pattern).encode("ascii")
    ).hexdigest()[:16]
    reason = f"{cycle_length}-step-cycle-x{repeats}"
    if stage.claimed_at:
        stage.usage["seconds"] = _active_seconds(stage, now)
    stage.claimed_at = ""
    stage.status = _LOOP_POLICY["terminalStageStatus"]
    stage.loop_history = history[-_LOOP_POLICY["historyLimit"]:]
    stage.loop_detected_reason = reason
    delivery.status = _LOOP_POLICY["terminalDeliveryStatus"]
    delivery.loop_events.append(
        {
            "stage": stage.id,
            "cycle_length": cycle_length,
            "repeats": repeats,
            "tools": [entry["tool"] for entry in pattern],
            "fingerprint": fingerprint,
            "at": now.isoformat(timespec="seconds"),
        }
    )
    save(root, delivery)
    write_views(root, delivery, not_checked=delivery.done_when or "none")


def meter_tool_call(
    root,
    agent,
    *,
    event_id="",
    tool_name="",
    signature="",
    now=None,
):
    """Persist budgets and stop repeated exact tool-call cycles pre-execution."""
    if bool(tool_name) != bool(signature):
        raise PlanError("loop detection requires both tool name and signature")
    if signature and not _TOOL_SIGNATURE.fullmatch(signature):
        raise PlanError("loop detection signature must be a SHA-256 digest")
    if tool_name and (
        len(tool_name) > 100 or any(char in tool_name for char in "\r\n")
    ):
        raise PlanError("loop detection tool name is invalid")
    target = _budget_target(root, agent)
    if target is None:
        return None
    name, stage_id = target
    lock_path = _state_path(root, name).with_suffix(".lock")
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next(
            (
                item for item in delivery.stages
                if item.id == stage_id
                and item.agent == agent
                and item.status == "running"
            ),
            None,
        )
        if stage is None or delivery.status != "running":
            raise PlanError(f"running budget stage disappeared for agent {agent}")
        if _budget_event_seen(stage, event_id):
            return stage
        observed_at = now or _now_utc()
        elapsed = _active_seconds(stage, observed_at)
        if elapsed >= stage.budget["max_seconds"]:
            _mark_budget_exceeded(
                root, delivery, stage, "max_seconds", now=observed_at
            )
            raise PlanError(f"stage {stage.id} exceeded budget max_seconds")
        if stage.usage["tool_calls"] >= stage.budget["max_tool_calls"]:
            _mark_budget_exceeded(
                root, delivery, stage, "max_tool_calls", now=observed_at
            )
            raise PlanError(f"stage {stage.id} exceeded budget max_tool_calls")
        if signature:
            history = [
                *stage.loop_history,
                {
                    "signature": signature,
                    "tool": tool_name,
                    "at": observed_at.isoformat(timespec="seconds"),
                },
            ]
            cycle_length = _repeated_tool_cycle(history)
            if cycle_length:
                _remember_budget_event(stage, event_id)
                _mark_loop_detected(
                    root,
                    delivery,
                    stage,
                    history,
                    cycle_length,
                    now=observed_at,
                )
                raise PlanError(
                    f"stage {stage.id} stopped: unproductive {cycle_length}-step "
                    f"tool cycle repeated {_LOOP_POLICY['repeatThreshold']} times"
                )
            stage.loop_history = history[-_LOOP_POLICY["historyLimit"]:]
        stage.usage["tool_calls"] += 1
        _remember_budget_event(stage, event_id)
        save(root, delivery)
        return stage


def stop_stage_for_budget(root, agent, reason, *, event_id="", now=None):
    """Fail closed when required runtime budget evidence is unavailable."""
    target = _budget_target(root, agent)
    if target is None:
        return None
    name, stage_id = target
    lock_path = _state_path(root, name).with_suffix(".lock")
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next(
            (
                item for item in delivery.stages
                if item.id == stage_id
                and item.agent == agent
                and item.status == "running"
            ),
            None,
        )
        if stage is None or delivery.status != "running":
            raise PlanError(f"running budget stage disappeared for agent {agent}")
        if _budget_event_seen(stage, event_id):
            return stage
        _remember_budget_event(stage, event_id)
        _mark_budget_exceeded(
            root, delivery, stage, str(reason), now=now or _now_utc()
        )
        return stage


def record_stage_usage(
    root,
    agent,
    metrics,
    *,
    event_id="",
    now=None,
    expected_target=None,
):
    """Record completion telemetry and stop a stage that crossed a ceiling."""
    required = {"seconds", "tool_calls", "turns", "tokens", "cost_usd"}
    if not isinstance(metrics, dict) or set(metrics) != required:
        raise PlanError("budget telemetry must contain all five usage dimensions")
    normalized = _normalize_usage(metrics)
    target = _budget_target(root, agent)
    if expected_target is not None and target != expected_target:
        return None
    if target is None:
        return None
    name, stage_id = target
    lock_path = _state_path(root, name).with_suffix(".lock")
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next(
            (
                item for item in delivery.stages
                if item.id == stage_id
                and item.agent == agent
                and item.status == "running"
            ),
            None,
        )
        if stage is None or delivery.status != "running":
            raise PlanError(f"running budget stage disappeared for agent {agent}")
        if _budget_event_seen(stage, event_id):
            return stage
        observed_at = now or _now_utc()
        current_seconds = 0.0
        if stage.claimed_at:
            current_seconds = max(
                0.0,
                (
                    observed_at
                    - _parse_utc_timestamp(
                        stage.claimed_at,
                        label=f"stage {stage.id} claimed_at",
                    )
                ).total_seconds(),
            )
        stage.usage["seconds"] += max(current_seconds, normalized["seconds"])
        claim_usage = stage.claim_usage or dict(_EMPTY_USAGE)
        metered_calls = max(
            0, stage.usage["tool_calls"] - claim_usage["tool_calls"]
        )
        stage.usage["tool_calls"] = (
            claim_usage["tool_calls"]
            + max(metered_calls, normalized["tool_calls"])
        )
        stage.usage["turns"] += normalized["turns"]
        stage.usage["tokens"] += normalized["tokens"]
        stage.usage["cost_usd"] += normalized["cost_usd"]
        stage.claimed_at = ""
        _remember_budget_event(stage, event_id)
        reason = _usage_budget_reason(stage)
        if reason:
            _mark_budget_exceeded(root, delivery, stage, reason, now=observed_at)
            raise PlanError(f"stage {stage.id} exceeded budget {reason}")
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return stage


def budget_rows(root, name):
    delivery = load(root, name)
    return [
        {
            "stage": stage.id,
            "agent": stage.agent,
            "status": stage.status,
            "budget": stage.budget,
            "usage": stage.usage,
            "reason": stage.budget_exceeded_reason or None,
        }
        for stage in delivery.stages
    ]


def _validate_owned_paths(stages):
    mutations = _agent_mutations()
    for stage in stages:
        if not isinstance(stage.owned_paths, list):
            raise PlanError(f"owned_paths for stage {stage.id} must be a list")
        if mutations.get(stage.agent) != "deny" and not stage.owned_paths:
            raise PlanError(
                f"stage {stage.id} for mutation-capable agent {stage.agent} "
                "requires at least one owned path"
            )
        seen = set()
        for owned_path in stage.owned_paths:
            if not isinstance(owned_path, str):
                raise PlanError(f"invalid owned path for stage {stage.id}: {owned_path!r}")
            path = pathlib.PurePosixPath(owned_path)
            if path.is_absolute() or ".." in path.parts or not owned_path.strip():
                raise PlanError(f"invalid owned path for stage {stage.id}: {owned_path}")
            normalized = path.as_posix()
            if normalized in seen:
                raise PlanError(f"duplicate owned path for stage {stage.id}: {owned_path}")
            seen.add(normalized)


def _validate_stages(stages):
    if not stages:
        raise PlanError("plan requires at least one stage")
    ids = [stage.id for stage in stages]
    if any(not isinstance(stage_id, str) or not stage_id.strip() for stage_id in ids):
        raise PlanError("stage ids must be nonempty strings")
    if len(ids) != len(set(ids)):
        raise PlanError("stage ids must be unique")
    by_id = {stage.id: stage for stage in stages}
    for stage in stages:
        if stage.agent not in AGENTS:
            raise PlanError(f"unknown stage agent {stage.agent}")
        missing = [dep for dep in stage.depends_on if dep not in by_id]
        if missing:
            raise PlanError(f"stage {stage.id} has unknown dependency {missing[0]}")

    visiting = set()
    visited = set()

    def visit(stage_id):
        if stage_id in visiting:
            raise PlanError("stage dependency graph contains a cycle")
        if stage_id in visited:
            return
        visiting.add(stage_id)
        for dependency in by_id[stage_id].depends_on:
            visit(dependency)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in ids:
        visit(stage_id)
    _validate_criteria(stages)
    _validate_approval_categories(stages)
    _validate_budgets(stages)


def _wip_count(root, sprint):
    count = 0
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            continue
        if load(root, name).status == "running":
            count += 1
    return count


def running_sprints(root):
    base = pathlib.Path(root) / "docs" / "sprints"
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.glob("*/sprint.json")):
        sprint = Sprint(**json.loads(path.read_text()))
        if sprint.status == "running":
            found.append(sprint)
    return found


def _resolve_sprint(root, sprint_id):
    running = running_sprints(root)
    if len(running) > 1:
        raise PlanError("two or more sprints are running")
    if sprint_id:
        path = _sprint_dir(root, sprint_id) / "sprint.json"
        if not path.is_file():
            raise PlanError(f"sprint {sprint_id} is missing")
        chosen = load_sprint(root, sprint_id)
        if chosen.status != "running":
            raise PlanError(f"sprint {sprint_id} is {chosen.status}")
        if any(sprint.id != chosen.id for sprint in running):
            raise PlanError("two or more sprints are running")
        return chosen
    if len(running) == 1:
        return running[0]
    return None


def _attach_sprint(root, name, sprint_id):
    chosen = _resolve_sprint(root, sprint_id)
    if chosen is None:
        return ""
    if _wip_count(root, chosen) >= chosen.wip:
        raise PlanError("sprint WIP is full")
    return chosen.id


def _remember_story(root, sprint_id, name):
    if not sprint_id:
        return
    sprint = load_sprint(root, sprint_id)
    if name not in sprint.stories:
        sprint.stories.append(name)
        save_sprint(root, sprint)
    write_sprint_view(root, sprint)


def plan(
    *, root, name, done_when, stages, sprint="", issue=0, runner=None,
    max_parallel=3
):
    if _state_path(root, name).is_file():
        existing = load(root, name)
        existing.rules_printed = _approved_rules(root, existing.stages)
        save(root, existing)
        write_views(root, existing, not_checked=existing.done_when or "none")
        return existing
    _validate_stages(stages)
    if not done_when.strip() or any(not _has_criteria(stage) for stage in stages):
        raise PlanError("plan requires nonempty done_when and success criteria")
    if not isinstance(max_parallel, int) or not 1 <= max_parallel <= 8:
        raise PlanError("max_parallel must be between 1 and 8")
    _validate_owned_paths(stages)
    issue_data = {}
    if issue:
        if runner is None or not hasattr(runner, "capture"):
            raise PlanError("plan --issue requires a runner with capture")
        cmd = ["gh", "issue", "view", str(int(issue)), "--json", "number,title,url"]
        code, out = runner.capture(root, cmd)
        if code != 0:
            raise PlanError(f"gh issue view exited {code}")
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            raise PlanError("gh issue view returned malformed JSON") from exc
        if int(payload["number"]) != int(issue):
            raise PlanError("gh issue number does not match")
        issue_data = {
            "number": int(payload["number"]),
            "title": payload["title"],
            "url": payload["url"],
        }
    sprint_id = _attach_sprint(root, name, sprint)
    delivery = Delivery(
        name=name,
        done_when=done_when,
        cap=len(stages) + 2,
        status="running",
        stages=list(stages),
        spawns=0,
        sprint=sprint_id,
        issue=issue_data,
        max_parallel=max_parallel,
    )
    delivery.rules_printed = _approved_rules(root, delivery.stages)
    save(root, delivery)
    write_views(root, delivery, not_checked=done_when or "none")
    _remember_story(root, sprint_id, name)
    return delivery


def _dod_met(delivery):
    if _pending_checkpoint(delivery) is not None:
        return False
    if not all(stage.status in ("done", "skipped") for stage in delivery.stages):
        return False
    return all(
        stage.status == "skipped"
        or _criterion_coverage_complete(stage)
        for stage in delivery.stages
    )


def record_pr(root, name, number, runner):
    delivery = load(root, name)
    if not delivery.issue:
        raise PlanError("record_pr requires a delivery issue")
    repo_cmd = ["gh", "repo", "view", "--json", "nameWithOwner"]
    code, out = runner.capture(root, repo_cmd)
    if code != 0:
        raise PlanError(f"gh repo view exited {code}")
    try:
        repo_payload = json.loads(out)
        repo = repo_payload["nameWithOwner"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PlanError("gh repo view returned malformed JSON") from exc
    pr_cmd = ["gh", "pr", "view", str(int(number)), "--json", "number,url,state"]
    code, out = runner.capture(root, pr_cmd)
    if code != 0:
        raise PlanError(f"gh pr view exited {code}")
    try:
        pr_payload = json.loads(out)
        pr_data = {
            "number": int(pr_payload["number"]),
            "url": pr_payload["url"],
            "state": str(pr_payload["state"]).lower(),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise PlanError("gh pr view returned malformed JSON") from exc
    delivery.repo = repo
    delivery.pr = pr_data
    if pr_data["state"] == "open" and _dod_met(delivery):
        delivery.status = "done"
    save(root, delivery)
    write_views(root, delivery, not_checked=delivery.done_when or "none")
    return delivery


def _reopen(root, delivery, stage):
    if stage.reopens >= 1:
        delivery.status = "stopped"
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return delivery
    if stage.status != "done":
        raise PlanError(f"stage {stage.id} is {stage.status}")
    stage.status = "running"
    stage.claimed_at = _now_utc().isoformat(timespec="seconds")
    stage.claim_usage = dict(stage.usage)
    stage.loop_history = []
    stage.loop_detected_reason = ""
    stage.reopens = 1
    delivery.status = "running"
    delivery.cap = max(delivery.cap, delivery.spawns + 1)
    save(root, delivery)
    write_views(root, delivery, not_checked=delivery.done_when or "none")
    return delivery


def ingest(root, name, *, kind, stage_id, runner, check="", comment=""):
    delivery = load(root, name)
    if not delivery.issue or not delivery.pr.get("number"):
        raise PlanError("ingest requires issue and recorded PR")
    stage = next((item for item in delivery.stages if item.id == stage_id), None)
    if stage is None:
        raise PlanError(f"stage {stage_id} is missing")
    if kind not in ("check", "review"):
        raise PlanError(f"unknown ingest kind {kind}")
    try:
        number = int(delivery.pr["number"])
    except (TypeError, ValueError) as exc:
        raise PlanError("pr number must be an integer") from exc
    if kind == "check":
        cmd = ["gh", "pr", "checks", str(number), "--json", "name,bucket,link"]
        code, out = runner.capture(root, cmd)
        if code != 0:
            raise PlanError(f"gh pr checks exited {code}")
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            raise PlanError("gh pr checks returned malformed JSON") from exc
        if not isinstance(payload, list):
            raise PlanError("gh pr checks returned malformed JSON")
        match = next((item for item in payload if item.get("name") == check), None)
        if match is None:
            raise PlanError(f"check {check} not found")
        if match.get("bucket") != "fail":
            return delivery
        return _reopen(root, delivery, stage)
    if not _REPO_RE.fullmatch(delivery.repo or ""):
        raise PlanError("repo must be owner/name")
    cmd = [
        "gh", "api", f"repos/{delivery.repo}/pulls/{number}/comments",
        "--jq", ".[].id",
    ]
    code, out = runner.capture(root, cmd)
    if code != 0:
        raise PlanError(f"gh api comments exited {code}")
    ids = {line.strip() for line in out.splitlines() if line.strip()}
    if str(comment) not in ids:
        raise PlanError(f"review comment {comment} not found")
    return _reopen(root, delivery, stage)


def _watch_target(delivery):
    writers = [
        stage
        for stage in delivery.stages
        if stage.role == "writer" and stage.status in ("done", "running")
    ]
    if writers:
        return writers[-1]
    done = [stage for stage in delivery.stages if stage.status == "done"]
    if done:
        return done[-1]
    return None


def watch_once(root, name, runner):
    delivery = load(root, name)
    if delivery.status in ("stopped", "done", "budget_exceeded"):
        return {"action": "skip"}
    if not delivery.pr.get("number"):
        return {"action": "skip"}
    stage = _watch_target(delivery)
    if stage is None:
        return {"action": "skip"}
    if stage.status == "running":
        return {"action": "wait"}
    try:
        number = int(delivery.pr["number"])
    except (TypeError, ValueError) as exc:
        raise PlanError("pr number must be an integer") from exc
    cmd = ["gh", "pr", "checks", str(number), "--json", "name,bucket,link"]
    code, out = runner.capture(root, cmd)
    if code != 0:
        raise PlanError(f"gh pr checks exited {code}")
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        raise PlanError("gh pr checks returned malformed JSON") from exc
    if not isinstance(payload, list):
        raise PlanError("gh pr checks returned malformed JSON")
    check = next(
        (
            item.get("name")
            for item in payload
            if item.get("bucket") == "fail"
            and item.get("name") not in delivery.seen_checks
        ),
        None,
    )
    if check is not None:
        _reopen(root, delivery, stage)
        delivery.seen_checks.append(check)
        save(root, delivery)
        if delivery.status == "stopped":
            return {"action": "stopped", "check": check}
        return {"action": "reopen", "check": check}
    if not _REPO_RE.fullmatch(delivery.repo or ""):
        raise PlanError("repo must be owner/name")
    review_cmd = [
        "gh", "api", f"repos/{delivery.repo}/pulls/{number}/comments",
        "--jq", ".[].id",
    ]
    code, out = runner.capture(root, review_cmd)
    if code != 0:
        raise PlanError(f"gh api comments exited {code}")
    for line in out.splitlines():
        comment = line.strip()
        if not comment or comment in delivery.seen_comments:
            continue
        _reopen(root, delivery, stage)
        delivery.seen_comments.append(str(comment))
        save(root, delivery)
        if delivery.status == "stopped":
            return {"action": "stopped", "comment": comment}
        return {"action": "reopen", "comment": comment}
    return {"action": "noop"}


def _did_on_disk(root, stage):
    root = pathlib.Path(root)
    return any((root / path).is_file() for path in stage.did if path)


def _cap_hit(delivery):
    return delivery.spawns >= delivery.cap and delivery.status != "done"


def _paths_overlap(left, right):
    left_parts = pathlib.PurePosixPath(left).parts
    right_parts = pathlib.PurePosixPath(right).parts
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def _path_is_within(candidate, owned):
    candidate_parts = pathlib.PurePosixPath(candidate).parts
    owned_parts = pathlib.PurePosixPath(owned).parts
    return candidate_parts[:len(owned_parts)] == owned_parts


def _validate_reported_paths(stage, did_paths):
    if _agent_mutations().get(stage.agent) == "deny" or not stage.owned_paths:
        return
    for did_path in did_paths:
        if not isinstance(did_path, str):
            raise ReportError(f"invalid DID path for stage {stage.id}: {did_path!r}")
        path = pathlib.PurePosixPath(did_path)
        if path.is_absolute() or ".." in path.parts or not did_path.strip():
            raise ReportError(f"invalid DID path for stage {stage.id}: {did_path}")
        if not any(_path_is_within(did_path, owned) for owned in stage.owned_paths):
            raise ReportError(
                f"DID path {did_path} is outside stage {stage.id} owned paths"
            )


def _ownership_collision(stage, others):
    for other in others:
        for owned in stage.owned_paths:
            if any(_paths_overlap(owned, active) for active in other.owned_paths):
                return other
    return None


def ready_stages(root, name):
    """Return a deterministic, bounded wave of dependency-ready stages."""
    delivery = load(root, name)
    return _ready_for_delivery(delivery)


def _ready_for_delivery(delivery):
    if (
        _dod_met(delivery)
        or delivery.status in ("stopped", "done", "budget_exceeded")
        or _cap_hit(delivery)
    ):
        return []
    active = [stage for stage in delivery.stages if stage.status == "running"]
    free = max(0, delivery.max_parallel - len(active))
    if not free:
        return []
    by_id = {stage.id: stage for stage in delivery.stages}
    selected = []
    for stage in delivery.stages:
        if stage.status != "queued":
            continue
        if _pending_approvals(stage):
            continue
        if not all(
            dep in by_id and by_id[dep].status in ("done", "skipped")
            for dep in stage.depends_on
        ):
            continue
        if _ownership_collision(stage, [*active, *selected]):
            continue
        selected.append(stage)
        if len(selected) >= free:
            break
    return selected


def claim_stage(root, name, stage_id):
    """Atomically claim one ready lane before dispatching its agent."""
    lock_path = _state_path(root, name).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(lock_path):
        delivery = load(root, name)
        stage = next((item for item in delivery.stages if item.id == stage_id), None)
        if stage is None:
            raise PlanError(f"stage {stage_id} is missing")
        if stage.status == "paused" and stage.checkpoint_id:
            raise PlanError(
                f"stage {stage_id} is paused at checkpoint {stage.checkpoint_id}"
            )
        pending = _pending_approvals(stage)
        if pending:
            raise PlanError(
                f"stage {stage_id} requires user approval before claim: "
                f"{', '.join(pending)}"
            )
        ready_ids = {item.id for item in _ready_for_delivery(delivery)}
        if stage_id not in ready_ids:
            active = [item for item in delivery.stages if item.status == "running"]
            collision = _ownership_collision(stage, active)
            if collision:
                raise PlanError(
                    f"stage {stage_id} path ownership collides with running stage {collision.id}"
                )
            raise PlanError(f"stage {stage_id} is not ready or parallel capacity is full")
        stage.status = "running"
        stage.claimed_at = _now_utc().isoformat(timespec="seconds")
        stage.claim_usage = dict(stage.usage)
        stage.loop_history = []
        stage.loop_detected_reason = ""
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return stage


def next_agent(root, name):
    delivery = load(root, name)
    if _dod_met(delivery):
        return "STOP"
    if delivery.status in ("stopped", "done", "budget_exceeded") or _cap_hit(delivery):
        if _cap_hit(delivery) and delivery.status not in (
            "stopped", "done", "budget_exceeded"
        ):
            delivery.status = "stopped"
            save(root, delivery)
            write_views(root, delivery)
        return "STOP"
    by_id = {stage.id: stage for stage in delivery.stages}
    for stage in delivery.stages:
        deps_met = all(
            by_id[dep].status in ("done", "skipped") for dep in stage.depends_on
        )
        if not deps_met:
            continue
        if stage.awaiting_pair and stage.pair:
            return stage.pair
        if stage.status == "paused" and stage.checkpoint_id:
            return f"CHECKPOINT_REQUIRED: {stage.checkpoint_id}"
        pending = _pending_approvals(stage)
        if stage.status == "queued" and pending:
            return f"APPROVAL_REQUIRED: {stage.id}: {', '.join(pending)}"
        if stage.status in ("queued", "running"):
            return stage.agent
        if (
            stage.role == "writer"
            and stage.status == "done"
            and not _did_on_disk(root, stage)
        ):
            return stage.agent
    return "STOP"


def pair(root, name, stage_id, *, reviewer="tech-lead"):
    delivery = load(root, name)
    stage = next((item for item in delivery.stages if item.id == stage_id), None)
    if stage is None:
        raise PlanError(f"stage {stage_id} is missing")
    if stage.status not in ("queued", "running"):
        raise PlanError(f"stage {stage_id} is {stage.status}")
    if reviewer not in AGENTS:
        raise PlanError(f"unknown reviewer {reviewer}")
    if reviewer == stage.agent:
        raise PlanError(f"reviewer cannot be the stage agent {reviewer}")
    if stage.pair and stage.pair != reviewer:
        raise PlanError(f"stage {stage_id} already paired with {stage.pair}")
    if stage.pair == reviewer:
        return delivery
    stage.pair = reviewer
    save(root, delivery)
    return delivery


def _parse_labels(text):
    fields = {label: [] for label in _LABELS}
    for line in text.splitlines():
        for label in _LABELS:
            prefix = f"{label}:"
            if line.startswith(prefix):
                fields[label].append(line[len(prefix):].strip())
                break
    return fields


def _parse_verification(raw):
    payload = raw.split(" →", 1)[0].strip()
    try:
        spec = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReportError(
            "VERIFIED must be JSON: "
            '{"criterion":"criterion-1","runner":"artisan-test",'
            '"args":["--filter=TagTest"]}'
        ) from exc
    if not isinstance(spec, dict) or set(spec) != {"criterion", "runner", "args"}:
        raise ReportError("VERIFIED JSON requires exactly criterion, runner, and args")
    criterion = spec.get("criterion")
    if not isinstance(criterion, str) or not _CRITERION_ID.fullmatch(criterion):
        raise ReportError("VERIFIED criterion must be a lowercase kebab-case identifier")
    runner = spec.get("runner")
    args = spec.get("args", [])
    allowed_runners = set(_VERIFICATION_RUNNERS) | _INTERNAL_VERIFICATION_RUNNERS
    if runner not in allowed_runners:
        allowed = ", ".join(sorted(allowed_runners))
        raise ReportError(f"unknown verification runner {runner!r}; choose one of: {allowed}")
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        raise ReportError("VERIFIED args must be a JSON array of strings")
    if len(args) > 32:
        raise ReportError("VERIFIED args exceeds the 32-argument limit")
    for arg in args:
        if not arg or len(arg) > 512 or any(char in arg for char in ("\x00", "\n", "\r")):
            raise ReportError("VERIFIED args must be nonempty single-line strings up to 512 characters")
    if runner == "file-exists" and not args:
        raise ReportError("file-exists requires at least one project-relative path")
    if runner == "file-has-lines" and len(args) < 2:
        raise ReportError("file-has-lines requires a project-relative path and at least one prefix")
    return {"criterion": criterion, "runner": runner, "args": args}


def _verification_argv(spec):
    return [*_VERIFICATION_RUNNERS[spec["runner"]], *spec["args"]]


def _verification_text(spec):
    return json.dumps(spec, separators=(",", ":"), sort_keys=True)


def _project_file(root, raw_path):
    root = pathlib.Path(root).resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReportError("verification paths must stay inside the project") from exc
    return candidate


def _run_verification(root, spec, runner):
    if spec["runner"] == "file-exists":
        return 0 if all(_project_file(root, path).is_file() for path in spec["args"]) else 1
    if spec["runner"] == "file-has-lines":
        path = _project_file(root, spec["args"][0])
        if not path.is_file():
            return 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return 1
        return 0 if all(any(line.startswith(prefix) for line in lines) for prefix in spec["args"][1:]) else 1
    return runner.run(root, _verification_argv(spec))


def _validate_verification_criteria(stage, verifications):
    unknown = [
        spec["criterion"]
        for spec in verifications
        if spec["criterion"] not in stage.criterion_ids
    ]
    if unknown:
        raise ReportError(
            f"unknown criterion {unknown[0]!r} for stage {stage.id}; "
            f"choose one of: {', '.join(stage.criterion_ids)}"
        )


def _validate_criterion_coverage(stage, verifications):
    _validate_verification_criteria(stage, verifications)
    covered = _verified_criterion_ids(stage) | {
        spec["criterion"] for spec in verifications
    }
    covered.update(_valid_waivers(stage))
    missing = [item for item in stage.criterion_ids if item not in covered]
    if missing:
        raise ReportError(
            f"stage {stage.id} lacks verification or user waiver for criteria: "
            + ", ".join(missing)
        )


def _validate_not_checked(stage, not_checked):
    waived = _valid_waivers(stage)
    for criterion_id, criterion in zip(stage.criterion_ids, stage.success_criteria):
        if criterion_id in waived:
            continue
        if criterion_id in not_checked or criterion in not_checked:
            raise ReportError(
                f"NOT-CHECKED names unwaived success criterion: {criterion_id}"
            )


def report(root, name, path, runner):
    fields = _parse_labels(pathlib.Path(path).read_text())
    verifications = []
    for raw in fields["VERIFIED"]:
        verifications.append(_parse_verification(raw))
    if not verifications:
        raise ReportError("VERIFIED must contain a structured verification record")

    delivery = load(root, name)
    agent = pathlib.Path(path).stem
    matching = [
        stage
        for stage in delivery.stages
        if stage.agent == agent or (stage.awaiting_pair and stage.pair == agent)
    ]
    if not matching:
        raise ReportError(f"no stage matched report agent {agent}")
    for stage in matching:
        if stage.status == "paused" or _pending_checkpoint(delivery, stage.id):
            raise ReportError(
                f"stage {stage.id} is paused at checkpoint {stage.checkpoint_id}"
            )
        _validate_verification_criteria(stage, verifications)

    for spec in verifications:
        if _run_verification(root, spec, runner) != 0:
            raise ReportError(f"verification failed: {_verification_text(spec)}")

    with _file_lock(_state_path(root, name).with_suffix(".lock")):
        return _commit_report(root, name, path, fields, verifications)


def _commit_report(root, name, path, fields, verifications):
    delivery = load(root, name)
    agent = pathlib.Path(path).stem
    not_checked = " ".join(fields["NOT-CHECKED"])
    did_paths = [item for item in fields["DID"] if item and item != "none"]
    flag_texts = [
        raw
        for raw in fields["FLAGS"]
        if _norm_flag(raw) and _norm_flag(raw) != "none"
    ]
    matched = False
    for stage in delivery.stages:
        if (stage.agent == agent or stage.pair == agent) and (
            stage.status == "paused" or _pending_checkpoint(delivery, stage.id)
        ):
            raise ReportError(
                f"stage {stage.id} is paused at checkpoint {stage.checkpoint_id}"
            )
        if stage.status == "budget_exceeded" and (
            stage.agent == agent or stage.pair == agent
        ):
            raise ReportError(
                f"stage {stage.id} exceeded budget {stage.budget_exceeded_reason}"
            )
        if stage.awaiting_pair and stage.pair == agent:
            matched = True
            _validate_not_checked(stage, not_checked)
            _validate_criterion_coverage(stage, verifications)
            stage.verified = list(stage.verified) + [
                {**spec, "exit": 0} for spec in verifications
            ]
            stage.awaiting_pair = False
            stage.status = "done"
            for flag_text in flag_texts:
                _record_lesson(root, name, agent, flag_text)
            continue
        if stage.agent != agent:
            continue
        if stage.awaiting_pair:
            raise ReportError(f"stage {stage.id} is awaiting pair {stage.pair}")
        matched = True
        if stage.claimed_at:
            raise ReportError(
                f"stage {stage.id} requires budget telemetry before report"
            )
        _validate_not_checked(stage, not_checked)
        _validate_criterion_coverage(stage, verifications)
        _validate_reported_paths(stage, did_paths)
        stage.did = did_paths
        stage.verified = [{**spec, "exit": 0} for spec in verifications]
        stage.flags = list(flag_texts)
        if stage.pair:
            stage.awaiting_pair = True
            stage.status = "running"
        else:
            stage.status = "done"
        for flag_text in flag_texts:
            _record_lesson(root, name, agent, flag_text)
    if not matched:
        raise ReportError(f"no stage matched report agent {agent}")
    delivery.spawns += 1
    if all(stage.status in ("done", "skipped") for stage in delivery.stages):
        if not _dod_met(delivery):
            raise ReportError("DoD requires verified exit 0 on every done stage")
        if not (delivery.issue and delivery.pr.get("state") != "open"):
            delivery.status = "done"
    elif _cap_hit(delivery):
        delivery.status = "stopped"
    save(root, delivery)
    write_views(
        root,
        delivery,
        verified=" ".join(_verification_text(spec) for spec in verifications),
        not_checked=not_checked or "none",
    )
    if delivery.sprint and (_sprint_dir(root, delivery.sprint) / "sprint.json").is_file():
        write_sprint_view(root, load_sprint(root, delivery.sprint))
    return delivery


@dataclass
class Sprint:
    id: str
    goal: str
    wip: int
    stories: list
    status: str


def _sprint_dir(root, sprint_id):
    return pathlib.Path(root) / "docs" / "sprints" / sprint_id


def save_sprint(root, sprint):
    folder = _sprint_dir(root, sprint.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sprint.json").write_text(json.dumps(asdict(sprint), indent=2) + "\n")


def load_sprint(root, sprint_id):
    data = json.loads((_sprint_dir(root, sprint_id) / "sprint.json").read_text())
    return Sprint(**data)


def _running_sprint(root):
    found = running_sprints(root)
    return found[0] if found else None


def render_sprint(root, sprint):
    lanes = []
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            lanes.append(f"· {name}")
            continue
        mark = _BOARD_MARK.get(load(root, name).status, "·")
        lanes.append(f"{mark} {name}")
    board = " ".join(lanes) if lanes else "none"
    return (
        f"GOAL: {sprint.goal}\n"
        f"WIP: {_wip_count(root, sprint)}/{sprint.wip}\n"
        f"BOARD: {board}\n"
        f"STATUS: {sprint.status}\n"
    )


def write_sprint_view(root, sprint):
    folder = _sprint_dir(root, sprint.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sprint.md").write_text(render_sprint(root, sprint))


def sprint_start(root, *, id, goal, wip):
    existing = _running_sprint(root)
    if existing is not None:
        write_sprint_view(root, existing)
        return existing
    sprint = Sprint(id=id, goal=goal, wip=wip, stories=[], status="running")
    save_sprint(root, sprint)
    write_sprint_view(root, sprint)
    return sprint


def _sprint_blocked(root, sprint):
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            return True
        if load(root, name).status == "running":
            return True
    return False


def sprint_close(root, sprint_id, *, force=False):
    sprint = load_sprint(root, sprint_id)
    blocked = _sprint_blocked(root, sprint)
    if blocked and not force:
        raise PlanError("sprint close rejected: a story is still running")
    sprint.status = "stopped" if blocked else "done"
    save_sprint(root, sprint)
    write_sprint_view(root, sprint)
    return sprint


def sprint_text(root, sprint_id):
    sprint = load_sprint(root, sprint_id)
    write_sprint_view(root, sprint)
    return (_sprint_dir(root, sprint_id) / "sprint.md").read_text()
