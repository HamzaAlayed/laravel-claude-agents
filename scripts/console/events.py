"""Normalizes raw Claude Agent SDK messages into the flat event stream the
console UI consumes.

Deliberately operates on plain dicts, not SDK objects, so the whole reducer is
testable from recorded fixtures at zero API spend. The engine adapts SDK
objects to dicts before calling in.

The subagent tree is rebuilt from `parent_tool_use_id`: an Agent tool call
records its tool_use_id, every later message carrying that id belongs to the
spawned agent's lane, and the matching tool_result closes it.
"""

from __future__ import annotations

import time

AGENT_TOOLS = ("Agent", "Task")  # Task is the pre-2.1.63 alias


class RunState:
    """Mutable per-run bookkeeping. One instance per run, never shared."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.seq = 0
        self.agent_by_tool_use: dict[str, str] = {}
        self.open_lanes: set[str] = set()

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def agent_for(self, parent_tool_use_id: str | None) -> str | None:
        if not parent_tool_use_id:
            return None
        return self.agent_by_tool_use.get(parent_tool_use_id)


def _strip_namespace(value: str) -> str:
    return value.split(":")[-1]


def normalize(raw: dict, state: RunState) -> list[dict]:
    """One raw message -> zero or more events. Never raises on unknown shapes."""
    if not isinstance(raw, dict):
        return []
    kind = raw.get("type")
    if kind == "system":
        return _system(raw, state)
    if kind == "assistant":
        return _assistant(raw, state)
    if kind == "user":
        return _user(raw, state)
    if kind == "result":
        return [_event(state, "result", None,
                       subtype=raw.get("subtype"),
                       result=raw.get("result"),
                       duration_ms=raw.get("duration_ms"),
                       total_cost_usd=raw.get("total_cost_usd"),
                       usage=raw.get("usage") or {})]
    return []


def _event(state: RunState, type_: str, agent: str | None, **fields) -> dict:
    event = {
        "seq": state.next_seq(),
        "run_id": state.run_id,
        "ts": int(time.time() * 1000),
        "type": type_,
        "agent": agent,
    }
    event.update(fields)
    return event


def _system(raw: dict, state: RunState) -> list[dict]:
    subtype = raw.get("subtype")
    if subtype == "init":
        return [_event(state, "init", None,
                       model=raw.get("model"),
                       plugins=[p.get("name") for p in raw.get("plugins") or []],
                       plugin_errors=raw.get("plugin_errors") or [],
                       mcp_servers=[s.get("name") for s in raw.get("mcp_servers") or []],
                       mcp_server_errors=raw.get("mcp_server_errors") or [],
                       capabilities=raw.get("capabilities") or [])]
    if subtype == "api_retry":
        return [_event(state, "api_retry", None,
                       attempt=raw.get("attempt"),
                       max_retries=raw.get("max_retries"),
                       retry_delay_ms=raw.get("retry_delay_ms"),
                       error=raw.get("error"))]
    return []


def _assistant(raw: dict, state: RunState) -> list[dict]:
    parent = raw.get("parent_tool_use_id")
    lane = state.agent_for(parent)
    blocks = ((raw.get("message") or {}).get("content")) or []
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]
    out: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            out.append(_event(state, "text", lane, text=block.get("text", "")))
        elif btype == "thinking":
            out.append(_event(state, "thinking", lane, text=block.get("thinking", "")))
        elif btype == "tool_use":
            out.extend(_tool_use(block, state, lane))
    return out


def _tool_use(block: dict, state: RunState, lane: str | None) -> list[dict]:
    tool_use_id = block.get("id") or ""
    name = block.get("name") or ""
    tool_input = block.get("input") or {}
    out = [_event(state, "tool_use", lane,
                  tool=name,
                  tool_use_id=tool_use_id,
                  input=tool_input)]
    if name in AGENT_TOOLS:
        spawned = _strip_namespace(str(tool_input.get("subagent_type") or "unknown"))
        state.agent_by_tool_use[tool_use_id] = spawned
        state.open_lanes.add(tool_use_id)
        out.append(_event(state, "agent_start", spawned,
                          tool_use_id=tool_use_id,
                          task=tool_input.get("description") or "",
                          model=tool_input.get("model"),
                          parent_agent=lane))
    return out


def _user(raw: dict, state: RunState) -> list[dict]:
    parent = raw.get("parent_tool_use_id")
    lane = state.agent_for(parent)
    blocks = ((raw.get("message") or {}).get("content")) or []
    out: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        tool_use_id = block.get("tool_use_id") or ""
        out.append(_event(state, "tool_result", lane,
                          tool_use_id=tool_use_id,
                          is_error=bool(block.get("is_error")),
                          content=block.get("content")))
        if tool_use_id in state.open_lanes:
            state.open_lanes.discard(tool_use_id)
            out.append(_event(state, "agent_end", state.agent_by_tool_use.get(tool_use_id),
                              tool_use_id=tool_use_id,
                              is_error=bool(block.get("is_error"))))
    return out
