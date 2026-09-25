#!/usr/bin/env python3
"""Protect kernel control-plane decisions and require a claimed lane before Bash.

Claude Code sends PreToolUse payloads on stdin. The kernel is the only writer
of docs/delivery/*/kernel.json, and only the main thread may grant approvals,
waive criteria, open or resolve checkpoints, or request retries. Guild subagents participating
in an active delivery must have exactly one claimed stage whose declared
approvals are complete.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


class ApprovalStateError(Exception):
    pass


_KERNEL_PATH = re.compile(r"(?:^|/)docs/delivery/[^/]+/kernel\.json$")
_KERNEL_TEXT = re.compile(r"(?:^|[\s'\"])(?:[^\s'\"]*/)?docs/delivery/[^\s'\"]+/kernel\.json(?:$|[\s'\"])")
_CONTROL_PLANE_ACTION = re.compile(
    r"guild\.py\b.*\b(?:approval\s+grant|criterion\s+waive|"
    r"checkpoint\s+(?:open|resolve)|retry\s+request)\b",
    re.DOTALL,
)
_SHELL_MUTATION = re.compile(
    r">|\btee\b|\b(?:sed|perl)\b[^;&|]*\s-i\b|"
    r"\b(?:rm|mv|cp|truncate|install|rsync)\b|\bdd\b[^;&|]*\bof=|"
    r"\b(?:python|python3|ruby|node|php)\b",
    re.IGNORECASE,
)


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_root(payload: dict) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).resolve()


def _agent_name(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    return raw.rsplit(":", 1)[-1].strip()


def _guild_agents() -> set[str]:
    path = _plugin_root() / "config" / "agent-harness.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        profiles = payload["agents"]
        approval_policy = payload["shared"]["approvalPolicy"]
        criterion_policy = payload["shared"]["criterionPolicy"]
        checkpoint_policy = payload["shared"]["checkpointPolicy"]
        retry_policy = payload["shared"]["retryPolicy"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ApprovalStateError(f"invalid agent harness registry at {path}") from exc
    if not isinstance(profiles, dict):
        raise ApprovalStateError(f"invalid agent harness registry at {path}")
    if approval_policy != {
        "stageField": "approval_categories",
        "recordField": "approvals",
        "authority": "user",
        "requiredBeforeClaim": True,
    }:
        raise ApprovalStateError(f"invalid agent harness registry at {path}")
    if criterion_policy != {
        "idsField": "criterion_ids",
        "evidenceField": "verified",
        "waiversField": "criterion_waivers",
        "requiredCoverage": "all",
        "waiverAuthority": "user",
    }:
        raise ApprovalStateError(f"invalid agent harness registry at {path}")
    if checkpoint_policy != {
        "recordField": "checkpoints",
        "stageField": "checkpoint_id",
        "pausedStatus": "paused",
        "answerAuthority": "user",
        "optionActions": ["continue", "stop"],
    }:
        raise ApprovalStateError(f"invalid agent harness registry at {path}")
    if retry_policy != {
        "attemptField": "attempts",
        "reasonField": "retry_reason",
        "eventField": "retry_events",
        "transitionField": "transition_events",
        "maxRetries": 1,
        "requestAuthority": "main",
        "retryStatus": "queued",
        "exhaustedStageStatus": "failed",
        "exhaustedDeliveryStatus": "stopped",
    }:
        raise ApprovalStateError(f"invalid agent harness registry at {path}")
    return set(profiles)


def _tool_input(payload: dict) -> dict:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}


def _native_target(payload: dict, root: Path) -> Path | None:
    tool_input = _tool_input(payload)
    raw = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
        or tool_input.get("absolute_path")
    )
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve(strict=False)


def _is_kernel_state(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return bool(_KERNEL_PATH.search(relative))


def _pending(stage: dict) -> list[str]:
    categories = stage.get("approval_categories", [])
    approvals = stage.get("approvals", [])
    if not isinstance(categories, list) or not all(
        isinstance(item, str) and item.strip() for item in categories
    ):
        raise ApprovalStateError("delivery stage has invalid approval_categories")
    if not isinstance(approvals, list):
        raise ApprovalStateError("delivery stage has invalid approvals")
    approved = {
        record.get("category")
        for record in approvals
        if isinstance(record, dict)
        and record.get("by") == "user"
        and isinstance(record.get("at"), str)
        and record.get("at")
    }
    return [category for category in categories if category not in approved]


def _active_agent_stages(root: Path, agent: str) -> tuple[list[dict], list[dict]]:
    delivery_root = (root / "docs" / "delivery").resolve(strict=False)
    if not delivery_root.is_dir():
        return [], []
    try:
        delivery_root.relative_to(root)
    except ValueError as exc:
        raise ApprovalStateError("delivery state directory escapes the project") from exc
    planned = []
    running = []
    for state_path in sorted(delivery_root.glob("*/kernel.json")):
        resolved = state_path.resolve(strict=False)
        try:
            resolved.relative_to(delivery_root)
        except ValueError as exc:
            raise ApprovalStateError(
                f"delivery state escapes the project: {state_path}"
            ) from exc
        try:
            delivery = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApprovalStateError(f"invalid delivery state: {state_path}") from exc
        if not isinstance(delivery, dict):
            raise ApprovalStateError(f"invalid delivery state: {state_path}")
        if delivery.get("status") != "running":
            continue
        stages = delivery.get("stages")
        if not isinstance(stages, list):
            raise ApprovalStateError(f"invalid delivery stages: {state_path}")
        for stage in stages:
            if not isinstance(stage, dict):
                raise ApprovalStateError(f"invalid delivery stage: {state_path}")
            if _agent_name(stage.get("agent")) != agent:
                continue
            record = {**stage, "delivery_state": str(state_path)}
            planned.append(record)
            if stage.get("status") == "running":
                running.append(record)
    return planned, running


def _block(reason: str) -> int:
    print("blocked: kernel control-plane policy denied this tool call.", file=sys.stderr)
    print(f"reason: {reason}", file=sys.stderr)
    print(
        "use the main thread for user-authoritative decisions; declare sensitive "
        "categories, persist checkpoints, then claim the stage.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return _block("the hook payload is invalid JSON")
    if not isinstance(payload, dict):
        return _block("the hook payload is not an object")

    root = _project_root(payload)
    tool_input = _tool_input(payload)
    command = tool_input.get("command")
    agent = _agent_name(payload.get("agent_type"))

    target = _native_target(payload, root)
    if target is not None and _is_kernel_state(target, root):
        return _block("kernel.json is kernel-owned and cannot be edited directly")

    if isinstance(command, str) and command.strip():
        if _CONTROL_PLANE_ACTION.search(command) and agent:
            return _block(
                "subagents cannot grant approvals, create criterion waivers, "
                "mutate checkpoints, or request retries"
            )
        if _KERNEL_TEXT.search(command) and _SHELL_MUTATION.search(command):
            return _block("Bash cannot mutate kernel.json directly")

    if not agent:
        return 0

    try:
        if agent not in _guild_agents():
            return 0
        planned, running = _active_agent_stages(root, agent)
        if not planned:
            return 0
        if len(running) > 1:
            return _block("more than one running stage makes approval state ambiguous")
        if not running:
            pending = []
            for stage in planned:
                pending.extend(_pending(stage))
            if pending:
                return _block(
                    "user approval is pending: " + ", ".join(dict.fromkeys(pending))
                )
            return _block("the agent has an active delivery stage, but it is not claimed")
        pending = _pending(running[0])
        if pending:
            return _block(
                "the running stage is missing user approval: " + ", ".join(pending)
            )
        return 0
    except ApprovalStateError as exc:
        return _block(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
