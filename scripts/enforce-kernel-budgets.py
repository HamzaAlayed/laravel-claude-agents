#!/usr/bin/env python3
"""Meter kernel-planned Guild stages at tool and subagent boundaries.

PreToolUse counts every tool call made by a claimed Guild subagent and denies
the next call after the stage reaches its time or tool-call ceiling. A
synchronous Agent/Task PostToolUse records completion totals for time, tool
calls, turns, tokens, and cost. Missing completion telemetry fails closed so a
stage cannot quietly pass an unmeasured budget.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "guild-kernel"))

import kernel  # noqa: E402


_BUDGET_RECORD = re.compile(r"guild\.py\b.*\bbudget\s+record\b", re.DOTALL)


def _agent_name(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    return raw.rsplit(":", 1)[-1].strip()


def _root(payload: dict) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(raw).resolve()


def _event_id(payload: dict, phase: str, agent: str) -> str:
    raw = payload.get("tool_use_id") or payload.get("toolUseId")
    if isinstance(raw, str) and raw:
        return f"{phase}:{raw}"
    stable = {
        "session": payload.get("session_id"),
        "phase": phase,
        "agent": agent,
        "tool": payload.get("tool_name"),
        "input": payload.get("tool_input"),
    }
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    # Dual plugin/project hook registrations receive the same payload together.
    # The short bucket suppresses that twin while still counting later repeats.
    return f"{phase}:fallback:{digest}:{int(time.time() // 2)}"


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _integer(value: object) -> int | None:
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _first(mapping: dict, *keys: str):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _completion_metrics(response: dict) -> tuple[dict | None, list[str]]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    duration_ms = _number(
        _first(response, "totalDurationMs", "duration_ms", "durationMs")
    )
    tool_calls = _integer(
        _first(response, "totalToolUseCount", "tool_uses", "toolUseCount")
    )
    tokens = _integer(_first(response, "totalTokens", "total_tokens"))
    if tokens is None and usage:
        try:
            tokens = kernel.usage_tokens(usage)
        except kernel.PlanError:
            tokens = None
    turns = _integer(_first(response, "numTurns", "num_turns", "turns"))
    if turns is None:
        iterations = usage.get("iterations")
        if isinstance(iterations, list) and iterations:
            turns = len(iterations)
    exact_cost = _number(
        _first(response, "totalCostUsd", "total_cost_usd", "cost_usd")
    )
    cost = exact_cost
    if cost is None and usage:
        try:
            cost = kernel.usage_cost(
                usage,
                _first(response, "resolvedModel", "model", "model_name"),
            )
        except kernel.PlanError:
            cost = None
    values = {
        "seconds": None if duration_ms is None else duration_ms / 1000.0,
        "tool_calls": tool_calls,
        "turns": turns,
        "tokens": tokens,
        "cost_usd": cost,
    }
    missing = [key for key, value in values.items() if value is None]
    return (None if missing else values), missing


def _block(reason: str) -> int:
    print("blocked: kernel budget policy denied this tool boundary.", file=sys.stderr)
    print(f"reason: {reason}", file=sys.stderr)
    print(
        "inspect `guild budget list`; a budget-exceeded stage requires a new "
        "human decision rather than silent continuation.",
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

    root = _root(payload)
    event_name = payload.get("hook_event_name")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if event_name == "PostToolUse" and tool_name in {"Agent", "Task"}:
        agent = _agent_name(tool_input.get("subagent_type"))
        if not agent or agent not in kernel.AGENTS:
            return 0
        response = payload.get("tool_response")
        response = response if isinstance(response, dict) else {}
        if response.get("status") == "async_launched":
            return 0
        event_id = _event_id(payload, "completion", agent)
        metrics, missing = _completion_metrics(response)
        try:
            if missing:
                stopped = kernel.stop_stage_for_budget(
                    root,
                    agent,
                    "missing_budget_telemetry:" + ",".join(missing),
                    event_id=event_id,
                )
                if stopped is None:
                    return 0
                return _block(
                    f"completed {agent} stage omitted budget telemetry: "
                    + ", ".join(missing)
                )
            kernel.record_stage_usage(
                root, agent, metrics, event_id=event_id
            )
            return 0
        except kernel.PlanError as exc:
            return _block(str(exc))

    agent = _agent_name(payload.get("agent_type"))
    if not agent or agent not in kernel.AGENTS:
        return 0
    command = tool_input.get("command")
    if isinstance(command, str) and _BUDGET_RECORD.search(command):
        return _block("subagents cannot record their own aggregate usage")
    try:
        kernel.meter_tool_call(
            root,
            agent,
            event_id=_event_id(payload, "tool", agent),
        )
        return 0
    except kernel.PlanError as exc:
        return _block(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
