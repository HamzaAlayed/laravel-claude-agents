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
_BOARD_MARK = {
    "done": "✔",
    "running": "▶",
    "queued": "·",
    "failed": "✖",
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
    stages = []
    for stage in data.pop("stages"):
        stage.setdefault("flags", [])
        stage.setdefault("pair", "")
        stage.setdefault("awaiting_pair", False)
        stage.setdefault("reopens", 0)
        stage.setdefault("owned_paths", [])
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
        mark = _BOARD_MARK.get(stage.status, "·")
        label = f"pair:{stage.pair}" if stage.awaiting_pair and stage.pair else stage.agent
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


def write_views(root, delivery, *, verified="none", not_checked="none"):
    folder = pathlib.Path(root) / "docs" / "delivery" / delivery.name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "close.md").write_text(
        render_close(delivery, verified=verified, not_checked=not_checked)
    )
    (folder / "graph.md").write_text(render_graph(delivery))


def _has_criteria(stage):
    return any(str(item).strip() for item in stage.success_criteria)


def _agent_mutations():
    path = pathlib.Path(__file__).resolve().parents[2] / "config" / "agent-harness.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            name: profile["mutation"]
            for name, profile in payload["agents"].items()
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PlanError(f"cannot load agent mutation policy from {path}") from exc


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
    if not all(stage.status in ("done", "skipped") for stage in delivery.stages):
        return False
    return all(
        stage.status == "skipped"
        or any(entry.get("exit") == 0 for entry in stage.verified)
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
    if delivery.status in ("stopped", "done"):
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
        or delivery.status in ("stopped", "done")
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
        save(root, delivery)
        write_views(root, delivery, not_checked=delivery.done_when or "none")
        return stage


def next_agent(root, name):
    delivery = load(root, name)
    if _dod_met(delivery):
        return "STOP"
    if delivery.status in ("stopped", "done") or _cap_hit(delivery):
        if _cap_hit(delivery) and delivery.status not in ("stopped", "done"):
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
            '{"runner":"artisan-test","args":["--filter=TagTest"]}'
        ) from exc
    if not isinstance(spec, dict) or set(spec) - {"runner", "args"}:
        raise ReportError("VERIFIED JSON accepts only runner and args")
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
    return {"runner": runner, "args": args}


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


def report(root, name, path, runner):
    fields = _parse_labels(pathlib.Path(path).read_text())
    verifications = []
    for raw in fields["VERIFIED"]:
        verifications.append(_parse_verification(raw))
    if not verifications:
        raise ReportError("VERIFIED must contain a structured verification record")

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
        if stage.awaiting_pair and stage.pair == agent:
            matched = True
            for criterion in stage.success_criteria:
                if criterion and criterion in not_checked:
                    raise ReportError(f"NOT-CHECKED names success criterion: {criterion}")
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
        for criterion in stage.success_criteria:
            if criterion and criterion in not_checked:
                raise ReportError(f"NOT-CHECKED names success criterion: {criterion}")
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
