#!/usr/bin/env python3
"""Enforce kernel-owned paths for native file writes by Guild subagents.

Claude Code sends PreToolUse payloads on stdin. Main-thread writes and agents
outside this Guild are left alone. Guild agents in an active delivery may write
only while their stage is running and only below that stage's owned paths.
Direct single-specialist work remains the documented fast path when no active
delivery contains that agent.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


class PolicyStateError(Exception):
    pass


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_root(payload: dict) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).resolve()


def _agent_name(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    return raw.rsplit(":", 1)[-1].strip()


def _load_policy() -> tuple[dict, dict]:
    path = _plugin_root() / "config" / "agent-harness.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        profiles = payload["agents"]
        policy = payload["shared"]["nativeWritePolicy"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PolicyStateError(f"invalid agent harness registry at {path}") from exc
    if not isinstance(profiles, dict) or not isinstance(policy, dict):
        raise PolicyStateError(f"invalid agent harness registry at {path}")
    documentation_paths = policy.get("documentationPaths")
    if not isinstance(documentation_paths, list) or not documentation_paths:
        raise PolicyStateError(f"invalid agent harness registry at {path}")
    if policy.get("directFastPath") is not True:
        raise PolicyStateError(f"invalid agent harness registry at {path}")
    return profiles, policy


def _write_path(payload: dict, root: Path) -> Path | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
    )
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve(strict=False)


def _active_agent_stages(root: Path, agent: str) -> tuple[list[dict], list[dict]]:
    delivery_root = (root / "docs" / "delivery").resolve(strict=False)
    if not delivery_root.is_dir():
        return [], []
    try:
        delivery_root.relative_to(root)
    except ValueError as exc:
        raise PolicyStateError("delivery state directory escapes the project") from exc
    planned: list[dict] = []
    running: list[dict] = []
    for state_path in sorted(delivery_root.glob("*/kernel.json")):
        resolved = state_path.resolve(strict=False)
        try:
            resolved.relative_to(delivery_root)
        except ValueError as exc:
            raise PolicyStateError(f"delivery state escapes the project: {state_path}") from exc
        try:
            delivery = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PolicyStateError(f"invalid delivery state: {state_path}") from exc
        if not isinstance(delivery, dict):
            raise PolicyStateError(f"invalid delivery state: {state_path}")
        if delivery.get("status") not in ("running", "interrupted"):
            continue
        stages = delivery.get("stages")
        if not isinstance(stages, list):
            raise PolicyStateError(f"invalid delivery stages: {state_path}")
        for stage in stages:
            if not isinstance(stage, dict):
                raise PolicyStateError(f"invalid delivery stage: {state_path}")
            if _agent_name(stage.get("agent")) != agent:
                continue
            record = {**stage, "delivery_state": str(state_path)}
            planned.append(record)
            if stage.get("status") == "running":
                running.append(record)
    return planned, running


def _owned_roots(stage: dict, root: Path) -> list[Path]:
    raw_paths = stage.get("owned_paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise PolicyStateError(
            f"running stage {stage.get('id', '<unknown>')} has no owned paths"
        )
    owned = []
    for raw in raw_paths:
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            raise PolicyStateError(
                f"running stage {stage.get('id', '<unknown>')} has invalid owned paths"
            )
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            raise PolicyStateError(
                f"running stage {stage.get('id', '<unknown>')} has invalid owned paths"
            )
        resolved = (root / path).resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PolicyStateError(
                f"running stage {stage.get('id', '<unknown>')} owns a path outside the project"
            ) from exc
        owned.append(resolved)
    return owned


def _inside(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _documentation_roots(policy: dict, root: Path) -> list[Path]:
    roots = []
    for raw in policy["documentationPaths"]:
        if not isinstance(raw, str) or not raw.strip():
            raise PolicyStateError("invalid documentation path policy")
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            raise PolicyStateError("invalid documentation path policy")
        resolved = (root / path).resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PolicyStateError("documentation path policy escapes the project") from exc
        roots.append(resolved)
    return roots


def _block(agent: str, reason: str, path: Path | None = None) -> int:
    print(f"blocked: agent path policy denied a native file write for {agent}.", file=sys.stderr)
    print(f"reason: {reason}", file=sys.stderr)
    if path is not None:
        print(f"path: {path}", file=sys.stderr)
    print(
        "claim the stage before editing and keep writes inside its owned_paths; "
        "direct point-work remains available only when no active delivery contains this agent.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        print("blocked: agent path policy received invalid hook JSON.", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("blocked: agent path policy received invalid hook JSON.", file=sys.stderr)
        return 2

    agent = _agent_name(payload.get("agent_type"))
    if not agent:
        return 0

    try:
        profiles, policy = _load_policy()
        profile = profiles.get(agent)
        if profile is None:
            return 0
        if not isinstance(profile, dict):
            raise PolicyStateError(f"invalid harness profile for {agent}")
        mutation = profile.get("mutation")
        if mutation == "deny":
            return _block(agent, "the shared harness marks this agent read-only")
        if mutation not in {"task-owned", "docs-only"}:
            raise PolicyStateError(f"invalid mutation policy for {agent}")

        root = _project_root(payload)
        target = _write_path(payload, root)
        if target is None:
            return _block(agent, "the write tool did not provide a valid file path")
        try:
            target.relative_to(root)
        except ValueError:
            return _block(agent, "the target is outside the project", target)
        if mutation == "docs-only" and not _inside(
            target, _documentation_roots(policy, root)
        ):
            return _block(agent, "the docs-only profile cannot write this path", target)

        planned, running = _active_agent_stages(root, agent)
        if not planned:
            return 0
        if not running:
            return _block(agent, "the agent has an active delivery stage, but it is not claimed")
        if len(running) != 1:
            return _block(agent, "more than one running stage makes ownership ambiguous")

        owned = _owned_roots(running[0], root)
        if not _inside(target, owned):
            return _block(
                agent,
                f"the target is outside stage {running[0].get('id', '<unknown>')} owned_paths",
                target,
            )
        return 0
    except PolicyStateError as exc:
        return _block(agent, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
