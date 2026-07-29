# Guild Web Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ship a localhost web console that launches, streams, steers, and interrupts Guild agent runs in the current Laravel project, replacing the terminal as the place the developer works.

**Architecture:** A python entry script serves a committed React bundle plus a JSON/SSE API from `http.server`; a single background asyncio thread owns one `claude-agent-sdk` `ClaudeSDKClient` per run. SDK messages are normalized to flat events by a pure function, persisted to a per-run JSONL, and fanned out over SSE. The browser reduces those events into a pipeline board and resolves approval prompts by POSTing back to an awaiting `asyncio.Future`.

**Tech Stack:** python3 stdlib (`http.server`, `asyncio`, `queue`, `json`, `re`, `secrets`, `unittest`) + `claude-agent-sdk`; React 19, TypeScript, Vite, Tailwind v4, shadcn/ui, `motion`, `lucide-react`, vitest.

**Spec:** [2026-07-29-guild-web-console-design.md](../specs/2026-07-29-guild-web-console-design.md)

## Global Constraints

- **Python floor: 3.10+.** The plan uses `X | Y` union syntax and the SDK requires it.
- **Canonical test command: `python3 -m unittest discover -s tests/console -t tests/console`.**
  `-t .` fails on Python 3.14 with `ImportError: Start directory is not importable`, because
  `tests/console` has no `__init__.py`. Do **not** add one to make `-t .` work: the absence of
  package files is load-bearing for how `scripts/console` modules resolve via `sys.path`
  insertion in each test file.
- **`claude-agent-sdk` is the only pip dependency**, installed into `.claude/console/venv`. Everything else is python stdlib. No pytest — tests are `unittest`.
- **Node is build-time only.** `scripts/console/dist/` is committed; installing users never run npm.
- **Never offer `bypassPermissions` in the UI** — subagents inherit it and cannot override it. **Never use `dontAsk`** — it denies `AskUserQuestion`.
- **`PermissionResultAllow` must always echo `updated_input`.** An allow result omitting it was rejected before Claude Code v2.1.207.
- **`ClaudeSDKClient.connect()` is called with no prompt**, then `query()` per message. A finite prompt generator closes the input stream before `can_use_tool` can fire.
- **Bind `127.0.0.1` only.** Every `/api` route requires the per-start token; `Origin` is rejected unless absent or localhost.
- **Do not modify** `agents/*.md`, `scripts/board.html`, or `scripts/emit-agent-events.sh`.
- **Any new `.sh` must pass** `shellcheck` at default (strict, info-level fails) severity.
- **Commands go 12 → 13.** `scripts/check_inventory_sync.py`, the four manifests, and README counts move in the same commit as `commands/console.md`.
- **Gemini/Codex skip the console**, so `GEMINI_SKIP_COMMANDS` and `GEMINI_SKIPPED_COMMANDS` both gain `console.md`, keeping the Gemini command count at 11.

---

## File Structure

**Created — python engine (`scripts/console/`):**

| File | Responsibility |
| --- | --- |
| `catalog.py` | Parse `agents/`, `commands/`, `skills/` into the catalog; role→stage map; card colours. Pure reads. |
| `events.py` | `RunState` + `normalize()`: one raw SDK message dict → list of flat event dicts. Pure. |
| `engine.py` | Asyncio loop thread, one client per run, `can_use_tool`, interrupt, subscribe/fan-out, JSONL persistence. |
| `server.py` | `ThreadingHTTPServer` request routing, token + `Origin` checks, SSE, static assets. No SDK knowledge. |
| `serve.py` | CLI entry: venv bootstrap, token mint, port selection, browser open. |

**Created — frontend source (`console-ui/`, not installed):** `src/lib/reducer.ts`, `src/lib/api.ts`, `src/App.tsx`, `src/components/` (`Launcher`, `Board`, `StageColumn`, `AgentCard`, `ApprovalBar`, `DecisionSheet`, `FocusRun`, `Transcript`), plus `components/ui/` from shadcn.

**Created — tests:** `tests/console/test_catalog.py`, `test_events.py`, `test_engine.py`, `test_server.py`; `console-ui/src/lib/reducer.test.ts`.

**Created — other:** `commands/console.md`, `scripts/console/dist/**` (built).

**Modified:** `install.sh` (new `install_console`), `.github/workflows/ci.yml` (python-unit + console-ui jobs), `tests/guardrails.test.sh` (static ratchets), `scripts/check_inventory_sync.py`, `scripts/build-gemini-extension.py`, `README.md`, `.gitignore`, `VERSION` + 4 manifests.

---

### Task 1: Catalog — parse the pack

**Files:**
- Create: `scripts/console/catalog.py`
- Test: `tests/console/test_catalog.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_catalog(root: Path) -> dict` with keys `agents` (list of dicts: `slug`, `name`, `description`, `model`, `tools` list, `color`, `stage`), `commands` (`slug`, `description`, `argument_hint`), `skills` (`slug`, `description`). Also `STAGES: list[str]`, `stage_for(slug: str) -> str`, `COORDINATOR: str`.

- [ ] **Step 1: Write the failing test**

Create `tests/console/test_catalog.py`:

```python
import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import catalog  # noqa: E402


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.load_catalog(REPO)
        cls.agents = {a["slug"]: a for a in cls.cat["agents"]}

    def test_parses_every_agent_on_disk(self):
        self.assertEqual(len(self.cat["agents"]), len(list((REPO / "agents").glob("*.md"))))

    def test_backend_developer_fields(self):
        a = self.agents["backend-developer"]
        self.assertEqual(a["name"], "Adam")
        self.assertEqual(a["model"], "sonnet")
        self.assertEqual(a["stage"], "Build")
        self.assertIn("Read", a["tools"])
        self.assertIn("mcp__laravel-boost", a["tools"])

    def test_name_lifted_from_description_prefix(self):
        self.assertEqual(self.agents["qa-engineer"]["name"], "Dina")
        self.assertEqual(self.agents["security-engineer"]["name"], "Felix")

    def test_pinned_model_ids_survive(self):
        self.assertEqual(self.agents["solution-architect"]["model"], "claude-opus-5")

    def test_coordinator_is_not_a_column(self):
        self.assertIsNone(self.agents[catalog.COORDINATOR]["stage"])

    def test_unknown_agent_falls_back_to_working(self):
        self.assertEqual(catalog.stage_for("brand-new-agent"), "Working")

    def test_every_agent_gets_a_distinct_colour(self):
        colours = [a["color"] for a in self.cat["agents"]]
        self.assertEqual(len(set(colours)), len(colours))

    def test_colour_is_stable_across_calls(self):
        again = {a["slug"]: a["color"] for a in catalog.load_catalog(REPO)["agents"]}
        self.assertEqual(again["scrum-master"], self.agents["scrum-master"]["color"])

    def test_commands_and_skills_parsed(self):
        self.assertEqual(len(self.cat["commands"]), len(list((REPO / "commands").glob("*.md"))))
        board = next(c for c in self.cat["commands"] if c["slug"] == "board")
        self.assertEqual(board["argument_hint"], "[port]")
        self.assertTrue(all(s["description"] for s in self.cat["skills"]))

    def test_skill_description_quotes_stripped(self):
        testing = next(s for s in self.cat["skills"] if s["slug"] == "laravel-testing")
        self.assertFalse(testing["description"].startswith('"'))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.console.test_catalog -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'catalog'`

- [ ] **Step 3: Write the implementation**

Create `scripts/console/catalog.py`:

```python
"""Parses the Guild pack into the catalog the console needs.

Single source of truth is the pack itself: agent slug, human name, model, tools
and colour all come from `agents/*.md` frontmatter. Deliberately introduces no
new registry — a sixth place to register an agent would fight
scripts/check_inventory_sync.py. Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path

COORDINATOR = "delivery-coordinator"
FALLBACK_STAGE = "Working"
STAGES = ["Discover", "Design", "Build", "Review", "Test", "Ship", "Docs", FALLBACK_STAGE]

# Role home, not a claim about the run's phase. The coordinator is the board's
# own header and deliberately absent.
STAGE_BY_AGENT = {
    "business-analyst": "Discover",
    "product-owner": "Discover",
    "scrum-master": "Discover",
    "solution-architect": "Design",
    "ui-ux-designer": "Design",
    "database-developer": "Build",
    "backend-developer": "Build",
    "frontend-developer": "Build",
    "mobile-developer": "Build",
    "package-developer": "Build",
    "tech-lead": "Review",
    "security-engineer": "Review",
    "performance-engineer": "Review",
    "qa-engineer": "Test",
    "devops-engineer": "Ship",
    "technical-writer": "Docs",
}

# Eight declared hue families cover seventeen agents, so families collide. Each
# member of a family takes a distinct shade, indexed by its position in the
# family's alphabetically sorted membership.
COLOR_RAMPS = {
    "green": ["#22c55e", "#15803d", "#4ade80", "#065f46"],
    "blue": ["#3b82f6", "#1d4ed8", "#60a5fa", "#1e3a8a"],
    "yellow": ["#eab308", "#a16207", "#fde047", "#713f12"],
    "red": ["#ef4444", "#b91c1c", "#f87171", "#7f1d1d"],
    "cyan": ["#06b6d4", "#0e7490", "#67e8f9", "#164e63"],
    "orange": ["#f97316", "#c2410c", "#fdba74", "#7c2d12"],
    "purple": ["#a855f7", "#7e22ce", "#d8b4fe", "#581c87"],
    "pink": ["#ec4899", "#be185d", "#f9a8d4", "#831843"],
}
UNKNOWN_COLOR = "#64748b"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_NAME_PREFIX = re.compile(r"^\s*([A-Z][\w'-]*)\s+—")


def _frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs only. Values may be wrapped in quotes."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def stage_for(slug: str) -> str:
    """Column for an agent. Unknown agents land in Working rather than vanishing."""
    return STAGE_BY_AGENT.get(slug, FALLBACK_STAGE)


def _human_name(description: str, slug: str) -> str:
    match = _NAME_PREFIX.match(description)
    if match:
        return match.group(1)
    return slug.replace("-", " ").title()


def _assign_colors(agents: list[dict]) -> None:
    families: dict[str, list[str]] = {}
    for agent in agents:
        families.setdefault(agent["_family"], []).append(agent["slug"])
    for slugs in families.values():
        slugs.sort()
    for agent in agents:
        ramp = COLOR_RAMPS.get(agent["_family"])
        if not ramp:
            agent["color"] = UNKNOWN_COLOR
        else:
            index = families[agent["_family"]].index(agent["slug"]) % len(ramp)
            agent["color"] = ramp[index]
        del agent["_family"]


def load_catalog(root: Path) -> dict:
    agents = []
    for path in sorted((root / "agents").glob("*.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        slug = fields.get("name") or path.stem
        description = fields.get("description", "")
        agents.append(
            {
                "slug": slug,
                "name": _human_name(description, slug),
                "description": description,
                "model": fields.get("model", ""),
                "tools": [t.strip() for t in fields.get("tools", "").split(",") if t.strip()],
                "stage": None if slug == COORDINATOR else stage_for(slug),
                "_family": fields.get("color", ""),
            }
        )
    _assign_colors(agents)

    commands = []
    for path in sorted((root / "commands").glob("*.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        commands.append(
            {
                "slug": path.stem,
                "description": fields.get("description", ""),
                "argument_hint": fields.get("argument-hint", ""),
            }
        )

    skills = []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        skills.append(
            {
                "slug": fields.get("name") or path.parent.name,
                "description": fields.get("description", ""),
            }
        )

    return {"agents": agents, "commands": commands, "skills": skills, "stages": STAGES}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.console.test_catalog -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/console/catalog.py tests/console/test_catalog.py
git commit -m "feat(console): parse the pack into a catalog with stage + colour"
```

---

### Task 2: Event normalization

**Files:**
- Create: `scripts/console/events.py`
- Test: `tests/console/test_events.py`

**Interfaces:**
- Consumes: nothing (operates on plain dicts so it is testable without the SDK).
- Produces: `RunState(run_id: str)` with attribute `seq: int`, and `normalize(raw: dict, state: RunState) -> list[dict]`. Every emitted event has `seq`, `run_id`, `ts`, `type`, `agent` (slug or `None` for the main thread). Types: `init`, `text`, `thinking`, `tool_use`, `tool_result`, `agent_start`, `agent_end`, `api_retry`, `result`, `error`. (`prompt` and `prompt_resolved` are minted by the engine, not here.)

Rules the tests pin down: an `Agent`/`Task` tool call emits **both** `tool_use` and `agent_start`, and records `tool_use_id → subagent slug` so the matching `tool_result` also emits `agent_end`; any message carrying `parent_tool_use_id` is attributed to that agent's lane.

- [ ] **Step 1: Write the failing test**

Create `tests/console/test_events.py`:

```python
import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import events  # noqa: E402


def init_msg():
    return {
        "type": "system",
        "subtype": "init",
        "model": "claude-sonnet-5",
        "plugins": [{"name": "laravel-team", "path": "/p"}],
        "capabilities": ["interrupt_receipt_v1"],
    }


def spawn_msg(tool_use_id="tu_1", subagent="backend-developer", desc="Add Action"):
    return {
        "type": "assistant",
        "parent_tool_use_id": None,
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Delegating."},
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Agent",
                    "input": {"subagent_type": f"laravel-team:{subagent}", "description": desc},
                },
            ],
        },
    }


def tool_result_msg(tool_use_id="tu_1", parent=None, text="done"):
    return {
        "type": "user",
        "parent_tool_use_id": parent,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": text}],
        },
    }


class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.state = events.RunState("run_1")

    def emit(self, raw):
        return events.normalize(raw, self.state)

    def test_init_reports_plugins_and_capabilities(self):
        out = self.emit(init_msg())
        self.assertEqual([e["type"] for e in out], ["init"])
        self.assertEqual(out[0]["plugins"], ["laravel-team"])
        self.assertEqual(out[0]["plugin_errors"], [])
        self.assertIn("interrupt_receipt_v1", out[0]["capabilities"])

    def test_init_surfaces_plugin_errors(self):
        raw = init_msg()
        raw["plugin_errors"] = [{"plugin": "laravel-team", "type": "missing", "message": "nope"}]
        self.assertEqual(self.emit(raw)[0]["plugin_errors"][0]["plugin"], "laravel-team")

    def test_seq_increases_monotonically(self):
        first = self.emit(init_msg())
        second = self.emit(spawn_msg())
        seqs = [e["seq"] for e in first + second]
        self.assertEqual(seqs, sorted(set(seqs)))

    def test_agent_spawn_emits_tool_use_and_agent_start(self):
        out = self.emit(spawn_msg())
        self.assertEqual([e["type"] for e in out], ["text", "tool_use", "agent_start"])
        start = out[-1]
        self.assertEqual(start["agent"], "backend-developer")
        self.assertEqual(start["task"], "Add Action")
        self.assertEqual(start["tool_use_id"], "tu_1")

    def test_matching_tool_result_closes_the_lane(self):
        self.emit(spawn_msg())
        out = self.emit(tool_result_msg())
        self.assertEqual([e["type"] for e in out], ["tool_result", "agent_end"])
        self.assertEqual(out[-1]["agent"], "backend-developer")

    def test_unrelated_tool_result_does_not_close_a_lane(self):
        out = self.emit(tool_result_msg(tool_use_id="tu_other"))
        self.assertEqual([e["type"] for e in out], ["tool_result"])

    def test_subagent_text_attributed_to_its_lane(self):
        self.emit(spawn_msg())
        raw = {
            "type": "assistant",
            "parent_tool_use_id": "tu_1",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "reading"}]},
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["agent"], "backend-developer")

    def test_nested_spawn_tracks_depth(self):
        self.emit(spawn_msg())
        nested = spawn_msg(tool_use_id="tu_2", subagent="qa-engineer", desc="write tests")
        nested["parent_tool_use_id"] = "tu_1"
        out = self.emit(nested)
        start = next(e for e in out if e["type"] == "agent_start")
        self.assertEqual(start["agent"], "qa-engineer")
        self.assertEqual(start["parent_agent"], "backend-developer")

    def test_thinking_block(self):
        raw = {
            "type": "assistant",
            "parent_tool_use_id": None,
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hm"}]},
        }
        self.assertEqual(self.emit(raw)[0]["type"], "thinking")

    def test_api_retry(self):
        raw = {
            "type": "system",
            "subtype": "api_retry",
            "attempt": 2,
            "max_retries": 5,
            "retry_delay_ms": 800,
            "error": "overloaded",
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["type"], "api_retry")
        self.assertEqual(out[0]["attempt"], 2)

    def test_result_carries_cost_and_duration(self):
        raw = {
            "type": "result",
            "subtype": "success",
            "result": "all done",
            "duration_ms": 4200,
            "total_cost_usd": 0.12,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["type"], "result")
        self.assertEqual(out[0]["subtype"], "success")
        self.assertEqual(out[0]["duration_ms"], 4200)

    def test_unknown_message_type_is_ignored_not_crashed(self):
        self.assertEqual(self.emit({"type": "who_knows"}), [])

    def test_malformed_message_is_ignored(self):
        self.assertEqual(self.emit({}), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.console.test_events -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'events'`

- [ ] **Step 3: Write the implementation**

Create `scripts/console/events.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.console.test_events -v`
Expected: PASS, 13 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/console/events.py tests/console/test_events.py
git commit -m "feat(console): normalize SDK messages into a flat event stream"
```

---

### Task 3: Engine — runs, approvals, interrupt

**Files:**
- Create: `scripts/console/engine.py`
- Test: `tests/console/test_engine.py`

**Interfaces:**
- Consumes: `events.RunState`, `events.normalize`.
- Produces:
  - `RunManager(root: Path, client_factory)` with `start(spec: dict) -> str`, `send(run_id, text)`, `answer(run_id, prompt_id, payload) -> bool`, `interrupt(run_id)`, `set_mode(run_id, mode=None, model=None)`, `subscribe(run_id, since_seq=0) -> Iterator[dict]`, `snapshot(run_id) -> list[dict]`, `list_runs() -> list[dict]`, `shutdown()`.
  - `build_prompt(spec: dict) -> str` — turns a launch spec into the text sent to the main thread.
  - `client_factory(options: dict) -> client` protocol: awaitable `connect()`, `query(text)`, `interrupt()`, `set_permission_mode(mode)`, `set_model(model)`, `disconnect()`, and async-iterator `receive_messages()`. The real factory wraps `ClaudeSDKClient`; tests inject a fake.
- `spec` keys: `kind` (`"command" | "specialist" | "prompt"`), `target` (command slug or agent slug; empty for `prompt`), `text`, `mode`, `model`.

- [ ] **Step 1: Write the failing test**

Create `tests/console/test_engine.py`:

```python
import asyncio
import pathlib
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import engine  # noqa: E402


class FakeClient:
    """Stands in for ClaudeSDKClient. Scripted messages, recorded calls."""

    def __init__(self, options):
        self.options = options
        self.queries = []
        self.interrupts = 0
        self.modes = []
        self.models = []
        self._outbox = asyncio.Queue()
        self.can_use_tool = options.get("can_use_tool")

    async def connect(self):
        self.connected = True

    async def query(self, text):
        self.queries.append(text)

    async def interrupt(self):
        self.interrupts += 1

    async def set_permission_mode(self, mode):
        self.modes.append(mode)

    async def set_model(self, model):
        self.models.append(model)

    async def disconnect(self):
        await self._outbox.put(None)

    async def push(self, message):
        await self._outbox.put(message)

    async def receive_messages(self):
        while True:
            message = await self._outbox.get()
            if message is None:
                return
            yield message


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.clients = []

        def factory(options):
            client = FakeClient(options)
            self.clients.append(client)
            return client

        self.mgr = engine.RunManager(self.root, factory)

    def tearDown(self):
        self.mgr.shutdown()
        self.tmp.cleanup()

    def run_coro(self, coro):
        return self.mgr.submit(coro).result(timeout=5)

    def drain(self, run_id, expected_types, timeout=5.0):
        seen = []
        for event in self.mgr.subscribe(run_id, since_seq=0):
            seen.append(event)
            if len(seen) >= len(expected_types):
                break
        self.assertEqual([e["type"] for e in seen], expected_types)
        return seen


class TestPromptBuilding(unittest.TestCase):
    def test_command_kind_prefixes_slash_command(self):
        text = engine.build_prompt({"kind": "command", "target": "review-pr", "text": "HEAD~1"})
        self.assertEqual(text, "/review-pr HEAD~1")

    def test_command_with_no_args(self):
        self.assertEqual(
            engine.build_prompt({"kind": "command", "target": "ship-checklist", "text": ""}),
            "/ship-checklist",
        )

    def test_specialist_kind_delegates_by_slug(self):
        text = engine.build_prompt(
            {"kind": "specialist", "target": "backend-developer", "text": "add idempotency key"}
        )
        self.assertEqual(
            text, "Use the backend-developer subagent to: add idempotency key"
        )

    def test_prompt_kind_passes_through(self):
        self.assertEqual(
            engine.build_prompt({"kind": "prompt", "target": "", "text": "why is /admin slow?"}),
            "why is /admin slow?",
        )


class TestRunLifecycle(EngineTestCase):
    def test_start_connects_and_queries(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "hello"})
        client = self.clients[0]
        self.assertEqual(client.queries, ["hello"])
        self.assertEqual(client.options["cwd"], str(self.root))
        self.assertEqual(client.options["permission_mode"], "default")
        self.assertTrue(run_id)

    def test_bypass_permissions_is_refused(self):
        with self.assertRaises(ValueError):
            self.mgr.start({"kind": "prompt", "target": "", "text": "x",
                            "mode": "bypassPermissions"})

    def test_dont_ask_is_refused(self):
        with self.assertRaises(ValueError):
            self.mgr.start({"kind": "prompt", "target": "", "text": "x", "mode": "dontAsk"})

    def test_messages_become_events_on_the_stream(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "hi"})
        self.run_coro(self.clients[0].push(
            {"type": "assistant", "parent_tool_use_id": None,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "yo"}]}}
        ))
        self.drain(run_id, ["text"])

    def test_events_persist_to_run_jsonl(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "hi"})
        self.run_coro(self.clients[0].push(
            {"type": "assistant", "parent_tool_use_id": None,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "yo"}]}}
        ))
        self.drain(run_id, ["text"])
        path = self.root / ".claude" / "console" / "runs" / f"{run_id}.jsonl"
        self.assertTrue(path.exists())
        self.assertIn('"raw"', path.read_text())

    def test_subscribe_replays_from_since_seq(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "hi"})
        for word in ("one", "two"):
            self.run_coro(self.clients[0].push(
                {"type": "assistant", "parent_tool_use_id": None,
                 "message": {"role": "assistant", "content": [{"type": "text", "text": word}]}}
            ))
        self.drain(run_id, ["text", "text"])
        later = []
        for event in self.mgr.subscribe(run_id, since_seq=1):
            later.append(event)
            break
        self.assertEqual(later[0]["text"], "two")

    def test_send_queries_the_same_client(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "first"})
        self.mgr.send(run_id, "second")
        self.assertEqual(self.clients[0].queries, ["first", "second"])

    def test_set_mode_and_model(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.mgr.set_mode(run_id, mode="acceptEdits", model="opus")
        self.assertEqual(self.clients[0].modes, ["acceptEdits"])
        self.assertEqual(self.clients[0].models, ["opus"])

    def test_set_mode_refuses_bypass(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        with self.assertRaises(ValueError):
            self.mgr.set_mode(run_id, mode="bypassPermissions")

    def test_list_runs_reports_persisted_runs(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        rows = self.mgr.list_runs()
        self.assertEqual([r["run_id"] for r in rows], [run_id])


class TestApprovals(EngineTestCase):
    def ask(self, tool_name="Bash", tool_input=None):
        client = self.clients[0]
        return self.mgr.submit(
            client.can_use_tool(tool_name, tool_input or {"command": "ls"}, _FakeContext())
        )

    def test_prompt_event_emitted_and_allow_resolves(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        event = self.drain(run_id, ["prompt"])[0]
        self.assertEqual(event["tool"], "Bash")
        ok = self.mgr.answer(run_id, event["prompt_id"], {"behavior": "allow"})
        self.assertTrue(ok)
        result = pending.result(timeout=5)
        self.assertEqual(result["behavior"], "allow")
        self.assertEqual(result["updated_input"], {"command": "ls"})

    def test_deny_carries_message_back(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        event = self.drain(run_id, ["prompt"])[0]
        self.mgr.answer(run_id, event["prompt_id"],
                        {"behavior": "deny", "message": "not on prod"})
        result = pending.result(timeout=5)
        self.assertEqual(result["behavior"], "deny")
        self.assertEqual(result["message"], "not on prod")

    def test_allow_can_modify_input(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        event = self.drain(run_id, ["prompt"])[0]
        self.mgr.answer(run_id, event["prompt_id"],
                        {"behavior": "allow", "updated_input": {"command": "ls -la"}})
        self.assertEqual(pending.result(timeout=5)["updated_input"], {"command": "ls -la"})

    def test_second_answer_is_rejected(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        event = self.drain(run_id, ["prompt"])[0]
        self.assertTrue(self.mgr.answer(run_id, event["prompt_id"], {"behavior": "allow"}))
        pending.result(timeout=5)
        self.assertFalse(self.mgr.answer(run_id, event["prompt_id"], {"behavior": "deny"}))

    def test_ask_user_question_answers_pass_through(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        questions = [{"question": "Which?", "header": "Which", "options": [], "multiSelect": False}]
        pending = self.ask("AskUserQuestion", {"questions": questions})
        event = self.drain(run_id, ["prompt"])[0]
        self.assertTrue(event["is_question"])
        self.mgr.answer(run_id, event["prompt_id"],
                        {"behavior": "allow", "answers": {"Which?": "Hash"}})
        result = pending.result(timeout=5)
        self.assertEqual(result["updated_input"]["questions"], questions)
        self.assertEqual(result["updated_input"]["answers"], {"Which?": "Hash"})

    def test_interrupt_while_prompt_pending_denies_it_first(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        self.drain(run_id, ["prompt"])
        self.mgr.interrupt(run_id)
        result = pending.result(timeout=5)
        self.assertEqual(result["behavior"], "deny")
        self.assertIn("interrupt", result["message"].lower())
        self.assertEqual(self.clients[0].interrupts, 1)


class _FakeContext:
    suggestions = []


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.console.test_engine -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine'`

- [ ] **Step 3: Write the implementation**

Create `scripts/console/engine.py`:

```python
"""Owns Guild runs: one Claude Agent SDK client per run on a single asyncio
loop thread, with approvals bridged to HTTP via awaitable futures.

Why one loop thread: the SDK is asyncio-native while http.server is threaded.
Keeping every client in one loop means interrupt and answer routing never
crosses supervision contexts, and the HTTP side only ever does
run_coroutine_threadsafe + queue.get.

Approvals: can_use_tool mints a prompt_id, emits a `prompt` event and awaits a
Future. The docs guarantee the callback may pend indefinitely, so there is no
timeout — a parked run is the honest state. Interrupting a run resolves any
pending prompt with a deny FIRST, otherwise the agent loop parks forever behind
a card nobody can answer.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import events as events_mod

# bypassPermissions is inherited by subagents and cannot be overridden per
# subagent; dontAsk denies AskUserQuestion, which is how checkpoints arrive.
ALLOWED_MODES = ("default", "acceptEdits", "plan")
FORBIDDEN_MODES = ("bypassPermissions", "dontAsk", "auto")
SENTINEL = object()


def build_prompt(spec: dict) -> str:
    kind = spec.get("kind")
    target = (spec.get("target") or "").strip()
    text = (spec.get("text") or "").strip()
    if kind == "command":
        return f"/{target} {text}".strip()
    if kind == "specialist":
        return f"Use the {target} subagent to: {text}"
    return text


def _check_mode(mode: str | None) -> str:
    mode = mode or "default"
    if mode in FORBIDDEN_MODES or mode not in ALLOWED_MODES:
        raise ValueError(
            f"permission mode {mode!r} is not offered by the console; "
            f"choose one of {', '.join(ALLOWED_MODES)}"
        )
    return mode


class Run:
    def __init__(self, run_id: str, spec: dict, path: Path):
        self.run_id = run_id
        self.spec = spec
        self.path = path
        self.state = events_mod.RunState(run_id)
        self.client = None
        self.buffer: list[dict] = []
        self.subscribers: list[queue.SimpleQueue] = []
        self.pending: dict[str, asyncio.Future] = {}
        self.status = "running"
        self.started_at = int(time.time() * 1000)
        self.lock = threading.Lock()


class RunManager:
    def __init__(self, root: Path, client_factory):
        self.root = Path(root)
        self.client_factory = client_factory
        self.runs_dir = self.root / ".claude" / "console" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.runs: dict[str, Run] = {}
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, name="guild-engine", daemon=True)
        self.thread.start()

    # ---- loop plumbing -----------------------------------------------------

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        """Schedule a coroutine on the engine loop; returns concurrent.Future."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def shutdown(self):
        for run in list(self.runs.values()):
            if run.client is not None:
                try:
                    self.submit(run.client.disconnect()).result(timeout=2)
                except Exception:
                    pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=3)

    # ---- run lifecycle -----------------------------------------------------

    def start(self, spec: dict) -> str:
        mode = _check_mode(spec.get("mode"))
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = Run(run_id, spec, self.runs_dir / f"{run_id}.jsonl")
        self.runs[run_id] = run
        options = {
            "cwd": str(self.root),
            "permission_mode": mode,
            "can_use_tool": self._make_can_use_tool(run),
        }
        if spec.get("model"):
            options["model"] = spec["model"]
        run.client = self.client_factory(options)
        self.submit(self._boot(run, build_prompt(spec))).result(timeout=30)
        return run_id

    async def _boot(self, run: Run, text: str):
        await run.client.connect()
        asyncio.create_task(self._pump(run))
        if text:
            await run.client.query(text)

    async def _pump(self, run: Run):
        try:
            async for message in run.client.receive_messages():
                for event in events_mod.normalize(_as_dict(message), run.state):
                    self._publish(run, event, raw=_as_dict(message))
        except Exception as exc:  # never let a dead client kill the loop
            self._publish(run, {
                "seq": run.state.next_seq(), "run_id": run.run_id,
                "ts": int(time.time() * 1000), "type": "error",
                "agent": None, "message": str(exc),
            })
        finally:
            run.status = "finished"

    def _publish(self, run: Run, event: dict, raw: dict | None = None):
        with run.lock:
            run.buffer.append(event)
            subscribers = list(run.subscribers)
        with run.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, "raw": raw}, separators=(",", ":")) + "\n")
        for sub in subscribers:
            sub.put(event)

    def send(self, run_id: str, text: str):
        run = self.runs[run_id]
        self.submit(run.client.query(text)).result(timeout=30)

    def set_mode(self, run_id: str, mode: str | None = None, model: str | None = None):
        run = self.runs[run_id]
        if mode is not None:
            self.submit(run.client.set_permission_mode(_check_mode(mode))).result(timeout=10)
        if model is not None:
            self.submit(run.client.set_model(model)).result(timeout=10)

    def interrupt(self, run_id: str):
        run = self.runs[run_id]
        self.submit(self._interrupt(run)).result(timeout=15)

    async def _interrupt(self, run: Run):
        # Deny pending prompts FIRST — otherwise the loop stays parked.
        for prompt_id, future in list(run.pending.items()):
            if not future.done():
                future.set_result({"behavior": "deny",
                                   "message": "Run interrupted by the user."})
            run.pending.pop(prompt_id, None)
        await run.client.interrupt()
        run.status = "interrupted"

    # ---- approvals ---------------------------------------------------------

    def _make_can_use_tool(self, run: Run):
        async def can_use_tool(tool_name, input_data, context):
            prompt_id = f"p_{uuid.uuid4().hex[:10]}"
            future: asyncio.Future = asyncio.get_running_loop().create_future()
            run.pending[prompt_id] = future
            suggestions = []
            for suggestion in getattr(context, "suggestions", None) or []:
                suggestions.append({
                    "destination": getattr(suggestion, "destination", None),
                    "repr": repr(suggestion),
                })
            self._publish(run, {
                "seq": run.state.next_seq(),
                "run_id": run.run_id,
                "ts": int(time.time() * 1000),
                "type": "prompt",
                "agent": None,
                "prompt_id": prompt_id,
                "tool": tool_name,
                "input": input_data,
                "is_question": tool_name == "AskUserQuestion",
                "suggestions": suggestions,
            })
            decision = await future
            run.pending.pop(prompt_id, None)
            self._publish(run, {
                "seq": run.state.next_seq(),
                "run_id": run.run_id,
                "ts": int(time.time() * 1000),
                "type": "prompt_resolved",
                "agent": None,
                "prompt_id": prompt_id,
                "behavior": decision.get("behavior"),
            })
            return _to_permission_result(decision, input_data)

        return can_use_tool

    def answer(self, run_id: str, prompt_id: str, payload: dict) -> bool:
        """Resolve a pending prompt. False when it is unknown or already answered."""
        run = self.runs.get(run_id)
        if run is None:
            return False
        future = run.pending.get(prompt_id)
        if future is None or future.done():
            return False
        self.loop.call_soon_threadsafe(_safe_set, future, payload)
        return True

    # ---- reads -------------------------------------------------------------

    def subscribe(self, run_id: str, since_seq: int = 0) -> Iterator[dict]:
        run = self.runs[run_id]
        sub: queue.SimpleQueue = queue.SimpleQueue()
        with run.lock:
            backlog = [e for e in run.buffer if e["seq"] > since_seq]
            run.subscribers.append(sub)
        try:
            for event in backlog:
                yield event
            while True:
                event = sub.get()
                if event is SENTINEL:
                    return
                if event["seq"] > since_seq:
                    yield event
        finally:
            with run.lock:
                if sub in run.subscribers:
                    run.subscribers.remove(sub)

    def snapshot(self, run_id: str) -> list[dict]:
        run = self.runs.get(run_id)
        if run is not None:
            with run.lock:
                return list(run.buffer)
        path = self.runs_dir / f"{run_id}.jsonl"
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line)["event"])
            except (ValueError, KeyError):
                continue
        return out

    def list_runs(self) -> list[dict]:
        rows = []
        for path in sorted(self.runs_dir.glob("run_*.jsonl")):
            run_id = path.stem
            live = self.runs.get(run_id)
            rows.append({
                "run_id": run_id,
                # A run this process does not own cannot be running: the SDK
                # child died with whatever process started it.
                "status": live.status if live else "interrupted",
                "spec": live.spec if live else None,
                "started_at": live.started_at if live else int(path.stat().st_mtime * 1000),
            })
        return rows


def _safe_set(future: asyncio.Future, value):
    if not future.done():
        future.set_result(value)


def _to_permission_result(decision: dict, input_data: dict):
    """Shape the callback's return value. Allow ALWAYS echoes updated_input."""
    behavior = decision.get("behavior", "deny")
    if behavior != "allow":
        return {"behavior": "deny", "message": decision.get("message") or "Denied by the user."}
    updated = decision.get("updated_input")
    if updated is None and "answers" in decision:
        updated = {"questions": (input_data or {}).get("questions", []),
                   "answers": decision["answers"]}
        if decision.get("response"):
            updated["response"] = decision["response"]
    if updated is None:
        updated = input_data
    return {"behavior": "allow", "updated_input": updated}


def _as_dict(message) -> dict:
    """SDK objects -> plain dicts so events.normalize stays fixture-testable."""
    if isinstance(message, dict):
        return message
    if hasattr(message, "to_dict"):
        return message.to_dict()
    try:
        import dataclasses
        if dataclasses.is_dataclass(message):
            return dataclasses.asdict(message)
    except Exception:
        pass
    return {k: v for k, v in vars(message).items() if not k.startswith("_")}
```

Note: `_to_permission_result` returns dicts here so the engine stays importable without the SDK. Task 5 adds the adapter that converts them to `PermissionResultAllow` / `PermissionResultDeny`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.console.test_engine -v`
Expected: PASS, 20 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/console/engine.py tests/console/test_engine.py
git commit -m "feat(console): run engine with approval futures and safe interrupt"
```

---

### Task 4: HTTP + SSE server

**Files:**
- Create: `scripts/console/server.py`
- Test: `tests/console/test_server.py`

**Interfaces:**
- Consumes: `RunManager` (Task 3), `load_catalog` (Task 1).
- Produces: `make_server(host, port, token, manager, catalog_root, dist_dir) -> ThreadingHTTPServer`. Routes exactly as the spec table. Every `/api` request requires `X-Guild-Token` header **or** `?token=`; `Origin`, when present, must be `http://localhost:*` or `http://127.0.0.1:*`.

- [ ] **Step 1: Write the failing test**

Create `tests/console/test_server.py`:

```python
import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import server  # noqa: E402

TOKEN = "test-token"


class FakeManager:
    def __init__(self):
        self.started = []
        self.answered = []
        self.interrupted = []
        self.sent = []

    def start(self, spec):
        self.started.append(spec)
        return "run_abc"

    def send(self, run_id, text):
        self.sent.append((run_id, text))

    def answer(self, run_id, prompt_id, payload):
        self.answered.append((run_id, prompt_id, payload))
        return prompt_id == "p_1"

    def interrupt(self, run_id):
        self.interrupted.append(run_id)

    def set_mode(self, run_id, mode=None, model=None):
        self.mode = (run_id, mode, model)

    def list_runs(self):
        return [{"run_id": "run_abc", "status": "running"}]

    def snapshot(self, run_id):
        return [{"seq": 1, "type": "text", "text": "hi"}]

    def subscribe(self, run_id, since_seq=0):
        yield {"seq": 2, "type": "text", "text": "streamed"}


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dist = pathlib.Path(cls.tmp.name)
        (cls.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
        (cls.dist / "app.js").write_text("console.log(1)", encoding="utf-8")
        cls.manager = FakeManager()
        cls.httpd = server.make_server("127.0.0.1", 0, TOKEN, cls.manager, REPO, cls.dist)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, token=TOKEN, origin=None):
        request = urllib.request.Request(self.url(path))
        if token:
            request.add_header("X-Guild-Token", token)
        if origin:
            request.add_header("Origin", origin)
        return urllib.request.urlopen(request, timeout=5)

    def post(self, path, body, token=TOKEN, origin=None):
        request = urllib.request.Request(
            self.url(path), data=json.dumps(body).encode(), method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Guild-Token", token)
        if origin:
            request.add_header("Origin", origin)
        return urllib.request.urlopen(request, timeout=5)

    def test_api_without_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", token=None)
        self.assertEqual(ctx.exception.code, 401)

    def test_api_with_wrong_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", token="nope")
        self.assertEqual(ctx.exception.code, 401)

    def test_token_may_arrive_as_query_param(self):
        response = self.get(f"/api/catalog?token={TOKEN}", token=None)
        self.assertEqual(response.status, 200)

    def test_cross_origin_is_403(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", origin="https://evil.example")
        self.assertEqual(ctx.exception.code, 403)

    def test_localhost_origin_allowed(self):
        response = self.get("/api/catalog", origin=f"http://localhost:{self.port}")
        self.assertEqual(response.status, 200)

    def test_catalog_returns_agents(self):
        payload = json.loads(self.get("/api/catalog").read())
        self.assertTrue(payload["agents"])
        self.assertIn("stages", payload)

    def test_post_runs_starts_a_run(self):
        payload = json.loads(
            self.post("/api/runs", {"kind": "prompt", "target": "", "text": "hi"}).read()
        )
        self.assertEqual(payload["run_id"], "run_abc")
        self.assertEqual(self.manager.started[-1]["text"], "hi")

    def test_post_runs_rejects_missing_kind(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs", {"text": "hi"})
        self.assertEqual(ctx.exception.code, 400)

    def test_answer_returns_409_when_already_resolved(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs/run_abc/answer", {"prompt_id": "p_2", "behavior": "allow"})
        self.assertEqual(ctx.exception.code, 409)

    def test_answer_ok(self):
        response = self.post(
            "/api/runs/run_abc/answer", {"prompt_id": "p_1", "behavior": "allow"}
        )
        self.assertEqual(response.status, 200)

    def test_interrupt(self):
        self.post("/api/runs/run_abc/interrupt", {})
        self.assertIn("run_abc", self.manager.interrupted)

    def test_message(self):
        self.post("/api/runs/run_abc/message", {"text": "more"})
        self.assertIn(("run_abc", "more"), self.manager.sent)

    def test_run_snapshot(self):
        payload = json.loads(self.get("/api/runs/run_abc").read())
        self.assertEqual(payload["events"][0]["text"], "hi")

    def test_events_stream_is_sse(self):
        response = self.get("/api/runs/run_abc/events")
        self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
        first = response.readline() + response.readline()
        self.assertIn(b"streamed", first)
        response.close()

    def test_index_served_at_root_without_token(self):
        response = urllib.request.urlopen(self.url("/"), timeout=5)
        self.assertIn(b"console", response.read())

    def test_unknown_client_route_falls_back_to_index(self):
        response = urllib.request.urlopen(self.url("/runs/run_abc"), timeout=5)
        self.assertIn(b"console", response.read())

    def test_asset_served_with_mime_type(self):
        response = urllib.request.urlopen(self.url("/app.js"), timeout=5)
        self.assertIn("javascript", response.headers["Content-Type"])

    def test_path_traversal_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/../../VERSION"), timeout=5)
        self.assertIn(ctx.exception.code, (400, 403, 404))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.console.test_server -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write the implementation**

Create `scripts/console/server.py`:

```python
"""HTTP + SSE surface for the Guild console. Holds no SDK knowledge.

Security posture: this process can execute arbitrary tools, so /api requires a
per-start token and rejects any cross-origin request. A hostile page on another
origin must not be able to launch agents against the developer's checkout, and
`Origin` checking is what stops fetch() and DNS rebinding from doing that.
"""

from __future__ import annotations

import json
import mimetypes
import posixpath
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalog import load_catalog

LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")
RUN_ROUTE = re.compile(r"^/api/runs/(?P<run_id>[A-Za-z0-9_]+)(?P<rest>/[a-z]+)?$")


def make_server(host: str, port: int, token: str, manager, catalog_root: Path,
                dist_dir: Path) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GuildConsole/1.0"
        protocol_version = "HTTP/1.1"

        # ---- helpers ----
        def log_message(self, fmt, *args):  # quiet by default
            pass

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or bool(LOCAL_ORIGIN.match(origin))

        def _token_ok(self, query: dict) -> bool:
            supplied = self.headers.get("X-Guild-Token") or (query.get("token") or [None])[0]
            return supplied == token

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return {}

        def _guard(self, query: dict) -> bool:
            if not self._origin_ok():
                self._json(403, {"error": "cross-origin requests are refused"})
                return False
            if not self._token_ok(query):
                self._json(401, {"error": "missing or invalid token"})
                return False
            return True

        # ---- GET ----
        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if not parsed.path.startswith("/api/"):
                return self._static(parsed.path)
            if not self._guard(query):
                return
            if parsed.path == "/api/catalog":
                return self._json(200, load_catalog(catalog_root))
            if parsed.path == "/api/runs":
                return self._json(200, {"runs": manager.list_runs()})
            match = RUN_ROUTE.match(parsed.path)
            if match and match.group("rest") is None:
                return self._json(200, {"events": manager.snapshot(match.group("run_id"))})
            if match and match.group("rest") == "/events":
                return self._sse(match.group("run_id"), query)
            return self._json(404, {"error": "no such route"})

        def _sse(self, run_id: str, query: dict):
            since = self.headers.get("Last-Event-ID") or (query.get("since") or ["0"])[0]
            try:
                since_seq = int(since)
            except ValueError:
                since_seq = 0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for event in manager.subscribe(run_id, since_seq=since_seq):
                    chunk = f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            except KeyError:
                return

        # ---- POST ----
        def do_POST(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if not self._guard(query):
                return
            body = self._read_body()
            if parsed.path == "/api/runs":
                if body.get("kind") not in ("command", "specialist", "prompt"):
                    return self._json(400, {"error": "kind must be command, specialist or prompt"})
                if not (body.get("text") or body.get("target")):
                    return self._json(400, {"error": "text or target is required"})
                try:
                    return self._json(200, {"run_id": manager.start(body)})
                except ValueError as exc:
                    return self._json(400, {"error": str(exc)})
            match = RUN_ROUTE.match(parsed.path)
            if not match:
                return self._json(404, {"error": "no such route"})
            run_id, rest = match.group("run_id"), match.group("rest")
            try:
                if rest == "/message":
                    manager.send(run_id, body.get("text") or "")
                    return self._json(200, {"ok": True})
                if rest == "/interrupt":
                    manager.interrupt(run_id)
                    return self._json(200, {"ok": True})
                if rest == "/mode":
                    manager.set_mode(run_id, mode=body.get("mode"), model=body.get("model"))
                    return self._json(200, {"ok": True})
                if rest == "/answer":
                    prompt_id = body.pop("prompt_id", "")
                    if manager.answer(run_id, prompt_id, body):
                        return self._json(200, {"ok": True})
                    return self._json(409, {"error": "prompt unknown or already answered"})
            except KeyError:
                return self._json(404, {"error": "no such run"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(404, {"error": "no such route"})

        # ---- static ----
        def _static(self, path: str):
            clean = posixpath.normpath(path)
            if clean.startswith(".."):
                return self._json(403, {"error": "refused"})
            candidate = (dist_dir / clean.lstrip("/")).resolve()
            index = (dist_dir / "index.html").resolve()
            try:
                candidate.relative_to(dist_dir.resolve())
            except ValueError:
                return self._json(403, {"error": "refused"})
            if not candidate.is_file():
                candidate = index  # SPA fallback
            if not candidate.is_file():
                return self._json(404, {"error": "console bundle missing"})
            data = candidate.read_bytes()
            ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer((host, port), Handler)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.console.test_server -v`
Expected: PASS, 18 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/console/server.py tests/console/test_server.py
git commit -m "feat(console): token- and origin-guarded HTTP/SSE server"
```

---

### Task 5: Entry script, SDK adapter, and the `/console` command

**Files:**
- Create: `scripts/console/serve.py`, `commands/console.md`
- Test: manual (the SDK is a real dependency and a billed process — automated coverage stops at Task 4)

**Interfaces:**
- Consumes: `make_server` (Task 4), `RunManager` (Task 3).
- Produces: `sdk_client_factory(options) -> ClaudeSDKClient` wrapper, and a `python3 scripts/console/serve.py [--port N]` entry point that prints the tokenized URL.

- [ ] **Step 1: Write the entry script**

Create `scripts/console/serve.py`:

```python
#!/usr/bin/env python3
"""Entry point for the Guild web console.

  python3 scripts/console/serve.py [--port 8378] [--no-open]

Bootstraps a venv holding claude-agent-sdk (the only pip dependency), mints a
per-start token, and serves the committed React bundle plus the JSON/SSE API on
loopback. Re-execs itself inside the venv so the SDK import succeeds.
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
PACK_ROOT = HERE.parent.parent
VENV = ROOT / ".claude" / "console" / "venv"
DEFAULT_PORT = 8378
MIN_PYTHON = (3, 10)


def die(message: str) -> None:
    print(f"guild-console: {message}", file=sys.stderr)
    raise SystemExit(1)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> Path:
    python = venv_python()
    if python.exists():
        return python
    print("guild-console: creating venv and installing claude-agent-sdk…")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--upgrade",
                        "pip", "claude-agent-sdk"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        die(f"could not create the venv ({exc}). Install python3-venv and pip, then retry.")
    return python


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 40):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    die(f"no free port in {preferred}-{preferred + 39}")
    return 0


def pack_root() -> Path:
    """Where the Guild pack lives, for the SDK's `plugins` option."""
    if (PACK_ROOT / ".claude-plugin" / "plugin.json").is_file():
        return PACK_ROOT
    for candidate in sorted(Path.home().glob(".claude/plugins/**/laravel-team")):
        if (candidate / ".claude-plugin" / "plugin.json").is_file():
            return candidate
    return PACK_ROOT


def sdk_client_factory(options: dict):
    """Wrap ClaudeSDKClient so the engine speaks dicts and never imports the SDK."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

    engine_callback = options.pop("can_use_tool")

    async def can_use_tool(tool_name, input_data, context):
        decision = await engine_callback(tool_name, input_data, context)
        if decision.get("behavior") == "allow":
            # Allow MUST echo updated_input — an omitted one was rejected
            # outright before Claude Code v2.1.207.
            return PermissionResultAllow(updated_input=decision["updated_input"])
        return PermissionResultDeny(message=decision.get("message") or "Denied by the user.")

    sdk_options = ClaudeAgentOptions(
        cwd=options["cwd"],
        permission_mode=options["permission_mode"],
        can_use_tool=can_use_tool,
        plugins=[{"type": "local", "path": str(pack_root())}],
        **({"model": options["model"]} if options.get("model") else {}),
    )
    return ClaudeSDKClient(options=sdk_options)


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        die(f"python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {sys.version.split()[0]}")

    parser = argparse.ArgumentParser(prog="guild-console")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--in-venv", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not args.in_venv:
        python = ensure_venv()
        os.execv(str(python), [str(python), str(Path(__file__).resolve()),
                               "--port", str(args.port),
                               *(["--no-open"] if args.no_open else []), "--in-venv"])

    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        die("claude-agent-sdk is missing from the venv. Delete "
            f"{VENV} and rerun to rebuild it.")

    sys.path.insert(0, str(HERE))
    from engine import RunManager
    from server import make_server

    # Subagent text and thinking blocks, at every nesting depth — without this
    # the board can show that a subagent ran but not what it did.
    os.environ.setdefault("CLAUDE_CODE_FORWARD_SUBAGENT_TEXT", "1")

    dist = HERE / "dist"
    if not (dist / "index.html").is_file():
        die(f"console bundle missing at {dist}/index.html — "
            "run: cd console-ui && npm ci && npm run build")

    token = secrets.token_urlsafe(24)
    port = free_port(args.port)
    manager = RunManager(ROOT, sdk_client_factory)
    httpd = make_server("127.0.0.1", port, token, manager, pack_root(), dist)
    url = f"http://127.0.0.1:{port}/?token={token}"

    print(f"guild-console: serving {ROOT}")
    print(f"guild-console: {url}")
    print("guild-console: stop with Ctrl-C")
    if not args.no_open:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nguild-console: shutting down")
    finally:
        httpd.shutdown()
        manager.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify the guardrails and diagnostics fire without the SDK installed**

Run: `python3 scripts/console/serve.py --in-venv --no-open`
Expected: exits 1 with `guild-console: claude-agent-sdk is missing from the venv` (proves the diagnostic path, since the ambient python has no SDK).

- [ ] **Step 3: Write the `/console` command**

Create `commands/console.md`:

```markdown
---
description: Open the Guild web console — a browser UI that launches, streams, and steers agent runs in this project.
argument-hint: [port]
allowed-tools: Bash, Read, Glob
---

# Guild console

Serve the web console for this project. It launches runs (a slash command, a
named specialist, or a freeform task), streams every agent onto a pipeline
board, and surfaces approvals and checkpoint questions as real UI. Claude Code
only — it drives the Claude Agent SDK, which the other runtimes don't ship.

## What you do

1. **Locate the entry script.** `scripts/console/serve.py` in this repo or the
   installed pack; find the plugin copy via
   `~/.claude/plugins/**/laravel-team/scripts/console/serve.py` if needed.

2. **Start it in the background**, from the project root so the console serves
   the right working tree:
   `python3 <path>/scripts/console/serve.py --port ${1:-8378}`
   First run creates `.claude/console/venv` and installs `claude-agent-sdk`
   there — that takes a few seconds and only happens once. Port busy →
   it increments on its own.

3. **Report the tokenized URL it prints.** The token is minted per start and is
   required on every API call; a URL without it will not work.

4. **Don't babysit it.** The page streams over SSE. Your job ends once the URL
   is out. Tell the user to stop it with Ctrl-C in that shell.

## Notes for the user (include in your reply)

- Runs persist to `.claude/console/runs/*.jsonl`; add `.claude/console/` to
  `.gitignore` if `.claude/` is committed.
- A run **parks** until you answer an approval or a checkpoint question — the
  amber bar at the top of the board is the signal.
- The five guardrail hooks still apply. A hook deny outranks every permission
  mode, so the console cannot be used to route around them.
- `/board` is unchanged and still covers runs you start in the terminal.
```

- [ ] **Step 4: Verify frontmatter validates**

Run: `python3 scripts/validate-frontmatter.py && grep -c '^description:' commands/console.md`
Expected: exits 0, prints `1`

- [ ] **Step 5: Commit**

```bash
git add scripts/console/serve.py commands/console.md
git commit -m "feat(console): serve entry point, SDK adapter, and /console command"
```

---

### Task 6: Frontend scaffold and the event reducer

**Files:**
- Create: `console-ui/package.json`, `console-ui/vite.config.ts`, `console-ui/tsconfig.json`, `console-ui/index.html`, `console-ui/src/main.tsx`, `console-ui/src/index.css`, `console-ui/src/lib/types.ts`, `console-ui/src/lib/reducer.ts`, `console-ui/src/lib/reducer.test.ts`, `console-ui/src/lib/api.ts`
- Test: `console-ui/src/lib/reducer.test.ts`

**Interfaces:**
- Consumes: the event shapes from Task 2 plus `prompt` / `prompt_resolved` from Task 3.
- Produces:
  - `types.ts`: `GuildEvent`, `Lane` (`{slug, task, stage, status: "running"|"done"|"error", startedAt, endedAt, parent, events}`), `RunView` (`{lanes: Lane[], mode: "board"|"focus", pending: PendingPrompt|null, result, init, retry}`).
  - `reducer.ts`: `emptyRun(kind: string): RunView` and `reduce(view: RunView, event: GuildEvent): RunView`.
  - `api.ts`: `createRun`, `sendMessage`, `answerPrompt`, `interruptRun`, `setMode`, `fetchCatalog`, `streamRun(runId, sinceSeq, onEvent)`.

- [ ] **Step 1: Scaffold the project**

```bash
mkdir -p console-ui/src/lib console-ui/src/components
cd console-ui
npm init -y
npm install react react-dom motion lucide-react clsx tailwind-merge class-variance-authority
npm install -D typescript @types/react @types/react-dom @vitejs/plugin-react vite vitest jsdom tailwindcss @tailwindcss/vite
npx shadcn@latest init -d
npx shadcn@latest add button card sheet badge dialog textarea input tooltip scroll-area
```

Then set `console-ui/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: { outDir: "../scripts/console/dist", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8378" } },
  test: { environment: "jsdom" },
});
```

and add scripts to `console-ui/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run"
  }
}
```

`npm run build` runs `tsc --noEmit`, which resolves `@/…` imports through tsconfig rather than Vite, so confirm `shadcn init` wrote the path alias into `console-ui/tsconfig.json` and add it if not:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

- [ ] **Step 2: Write the failing reducer test**

Create `console-ui/src/lib/reducer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { emptyRun, reduce } from "./reducer";
import type { GuildEvent } from "./types";

let seq = 0;
const ev = (partial: Partial<GuildEvent> & { type: string }): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: null, ...partial }) as GuildEvent;

const play = (kind: string, events: GuildEvent[]) => events.reduce(reduce, emptyRun(kind));

describe("reduce", () => {
  it("starts a specialist run in focus mode", () => {
    expect(emptyRun("specialist").mode).toBe("focus");
    expect(emptyRun("command").mode).toBe("board");
  });

  it("opens a lane on agent_start", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "Add Action", tool_use_id: "t1" }),
    ]);
    expect(view.lanes).toHaveLength(1);
    expect(view.lanes[0].slug).toBe("backend-developer");
    expect(view.lanes[0].status).toBe("running");
    expect(view.lanes[0].task).toBe("Add Action");
  });

  it("closes the lane on agent_end", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "agent_end", agent: "qa-engineer", tool_use_id: "t1", is_error: false }),
    ]);
    expect(view.lanes[0].status).toBe("done");
    expect(view.lanes[0].endedAt).toBeGreaterThan(0);
  });

  it("marks an errored lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "agent_end", agent: "qa-engineer", tool_use_id: "t1", is_error: true }),
    ]);
    expect(view.lanes[0].status).toBe("error");
  });

  it("promotes focus to board when a second agent appears", () => {
    const view = play("specialist", [
      ev({ type: "agent_start", agent: "performance-engineer", task: "profile", tool_use_id: "t1" }),
      ev({ type: "agent_start", agent: "backend-developer", task: "fix", tool_use_id: "t2" }),
    ]);
    expect(view.mode).toBe("board");
  });

  it("never demotes board back to focus", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
    ]);
    expect(view.mode).toBe("board");
  });

  it("attributes tool_use to its lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "x", tool_use_id: "t1" }),
      ev({ type: "tool_use", agent: "backend-developer", tool: "Edit", tool_use_id: "t9" }),
    ]);
    expect(view.lanes[0].events.map((e) => e.type)).toContain("tool_use");
  });

  it("keeps main-thread text out of every lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "x", tool_use_id: "t1" }),
      ev({ type: "text", agent: null, text: "coordinating" }),
    ]);
    expect(view.lanes[0].events.some((e) => e.type === "text")).toBe(false);
    expect(view.main.some((e) => e.type === "text")).toBe(true);
  });

  it("records a pending prompt and clears it on resolution", () => {
    const withPrompt = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: { command: "ls" }, is_question: false }),
    ]);
    expect(withPrompt.pending?.prompt_id).toBe("p1");
    const resolved = reduce(withPrompt, ev({ type: "prompt_resolved", prompt_id: "p1", behavior: "allow" }));
    expect(resolved.pending).toBeNull();
  });

  it("ignores a resolution for a different prompt", () => {
    const withPrompt = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {}, is_question: false }),
    ]);
    const other = reduce(withPrompt, ev({ type: "prompt_resolved", prompt_id: "p2", behavior: "allow" }));
    expect(other.pending?.prompt_id).toBe("p1");
  });

  it("captures init warnings", () => {
    const view = play("command", [
      ev({ type: "init", plugins: ["laravel-team"], plugin_errors: [{ plugin: "x", message: "bad" }] }),
    ]);
    expect(view.init?.plugin_errors).toHaveLength(1);
  });

  it("captures api_retry and clears it on the next event", () => {
    const retrying = play("command", [
      ev({ type: "api_retry", attempt: 2, max_retries: 5, error: "overloaded" }),
    ]);
    expect(retrying.retry?.attempt).toBe(2);
    expect(reduce(retrying, ev({ type: "text", text: "back" })).retry).toBeNull();
  });

  it("stores the final result", () => {
    const view = play("command", [
      ev({ type: "result", subtype: "success", result: "done", duration_ms: 10, total_cost_usd: 1 }),
    ]);
    expect(view.result?.result).toBe("done");
  });

  it("is idempotent for replayed events", () => {
    const start = ev({ type: "agent_start", agent: "qa-engineer", task: "t", tool_use_id: "t1" });
    const once = reduce(emptyRun("command"), start);
    const twice = reduce(once, start);
    expect(twice.lanes).toHaveLength(1);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd console-ui && npx vitest run src/lib/reducer.test.ts`
Expected: FAIL — cannot resolve `./reducer`

- [ ] **Step 4: Write types, reducer, and api client**

Create `console-ui/src/lib/types.ts`:

```ts
export type GuildEvent = {
  seq: number;
  run_id: string;
  ts: number;
  type: string;
  agent: string | null;
  [key: string]: unknown;
};

export type LaneStatus = "running" | "done" | "error";

export type Lane = {
  slug: string;
  task: string;
  toolUseId: string;
  parent: string | null;
  status: LaneStatus;
  startedAt: number;
  endedAt: number;
  events: GuildEvent[];
};

export type PendingPrompt = {
  prompt_id: string;
  tool: string;
  input: Record<string, unknown>;
  is_question: boolean;
  suggestions: unknown[];
};

export type RunView = {
  mode: "board" | "focus";
  lanes: Lane[];
  main: GuildEvent[];
  pending: PendingPrompt | null;
  init: { plugins: string[]; plugin_errors: unknown[] } | null;
  retry: { attempt: number; max_retries: number; error: string } | null;
  result: { subtype: string; result: string; duration_ms: number; total_cost_usd: number } | null;
};

export type Agent = {
  slug: string;
  name: string;
  description: string;
  model: string;
  tools: string[];
  color: string;
  stage: string | null;
};

export type Catalog = {
  agents: Agent[];
  commands: { slug: string; description: string; argument_hint: string }[];
  skills: { slug: string; description: string }[];
  stages: string[];
};
```

Create `console-ui/src/lib/reducer.ts`:

```ts
import type { GuildEvent, Lane, RunView } from "./types";

export const emptyRun = (kind: string): RunView => ({
  // specialist and freeform runs open focused; commands open on the board.
  mode: kind === "command" ? "board" : "focus",
  lanes: [],
  main: [],
  pending: null,
  init: null,
  retry: null,
  result: null,
});

const withLane = (lanes: Lane[], toolUseId: string, patch: Partial<Lane>): Lane[] =>
  lanes.map((lane) => (lane.toolUseId === toolUseId ? { ...lane, ...patch } : lane));

export function reduce(view: RunView, event: GuildEvent): RunView {
  const next: RunView = { ...view, retry: event.type === "api_retry" ? view.retry : null };

  switch (event.type) {
    case "init":
      return {
        ...next,
        init: {
          plugins: (event.plugins as string[]) ?? [],
          plugin_errors: (event.plugin_errors as unknown[]) ?? [],
        },
      };

    case "api_retry":
      return {
        ...next,
        retry: {
          attempt: event.attempt as number,
          max_retries: event.max_retries as number,
          error: event.error as string,
        },
      };

    case "agent_start": {
      const toolUseId = event.tool_use_id as string;
      if (next.lanes.some((lane) => lane.toolUseId === toolUseId)) return next;
      const lane: Lane = {
        slug: (event.agent as string) ?? "unknown",
        task: (event.task as string) ?? "",
        toolUseId,
        parent: (event.parent_agent as string) ?? null,
        status: "running",
        startedAt: event.ts,
        endedAt: 0,
        events: [],
      };
      const lanes = [...next.lanes, lane];
      // Promotion is one-way: a board run never demotes to focus.
      return { ...next, lanes, mode: lanes.length > 1 ? "board" : next.mode };
    }

    case "agent_end":
      return {
        ...next,
        lanes: withLane(next.lanes, event.tool_use_id as string, {
          status: event.is_error ? "error" : "done",
          endedAt: event.ts,
        }),
      };

    case "prompt":
      return {
        ...next,
        pending: {
          prompt_id: event.prompt_id as string,
          tool: event.tool as string,
          input: (event.input as Record<string, unknown>) ?? {},
          is_question: Boolean(event.is_question),
          suggestions: (event.suggestions as unknown[]) ?? [],
        },
      };

    case "prompt_resolved":
      return next.pending?.prompt_id === event.prompt_id ? { ...next, pending: null } : next;

    case "result":
      return {
        ...next,
        result: {
          subtype: event.subtype as string,
          result: (event.result as string) ?? "",
          duration_ms: (event.duration_ms as number) ?? 0,
          total_cost_usd: (event.total_cost_usd as number) ?? 0,
        },
      };

    default: {
      if (!event.agent) return { ...next, main: [...next.main, event] };
      const lanes = next.lanes.map((lane) =>
        lane.slug === event.agent && lane.status === "running"
          ? { ...lane, events: [...lane.events, event] }
          : lane,
      );
      return { ...next, lanes };
    }
  }
}
```

Create `console-ui/src/lib/api.ts`:

```ts
import type { Catalog, GuildEvent } from "./types";

const token = new URLSearchParams(window.location.search).get("token") ?? "";

const headers = { "Content-Type": "application/json", "X-Guild-Token": token };

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
  if (!response.ok) throw new Error((await response.json()).error ?? response.statusText);
  return response.json();
}

export const fetchCatalog = async (): Promise<Catalog> => {
  const response = await fetch("/api/catalog", { headers });
  if (!response.ok) throw new Error("could not load the catalog");
  return response.json();
};

export const createRun = (spec: {
  kind: string;
  target: string;
  text: string;
  mode?: string;
  model?: string;
}) => post<{ run_id: string }>("/api/runs", spec);

export const sendMessage = (runId: string, text: string) =>
  post(`/api/runs/${runId}/message`, { text });

export const answerPrompt = (runId: string, payload: Record<string, unknown>) =>
  post(`/api/runs/${runId}/answer`, payload);

export const interruptRun = (runId: string) => post(`/api/runs/${runId}/interrupt`, {});

export const setMode = (runId: string, mode?: string, model?: string) =>
  post(`/api/runs/${runId}/mode`, { mode, model });

/** SSE with resume: EventSource cannot send headers, so the token rides the query. */
export function streamRun(runId: string, sinceSeq: number, onEvent: (e: GuildEvent) => void) {
  const source = new EventSource(
    `/api/runs/${runId}/events?since=${sinceSeq}&token=${encodeURIComponent(token)}`,
  );
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as GuildEvent);
  return () => source.close();
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd console-ui && npx vitest run src/lib/reducer.test.ts`
Expected: PASS, 14 tests

- [ ] **Step 6: Commit**

```bash
git add console-ui/package.json console-ui/package-lock.json console-ui/vite.config.ts \
        console-ui/tsconfig.json console-ui/index.html console-ui/components.json \
        console-ui/src
git commit -m "feat(console-ui): scaffold Vite/Tailwind/shadcn app and event reducer"
```

---

### Task 7: The pipeline board

**Files:**
- Create: `console-ui/src/components/Board.tsx`, `StageColumn.tsx`, `AgentCard.tsx`, `console-ui/src/lib/useElapsed.ts`
- Modify: `console-ui/src/App.tsx`

**Interfaces:**
- Consumes: `RunView`, `Lane`, `Catalog` (Task 6).
- Produces: `<Board view={RunView} catalog={Catalog} onSelect={(lane: Lane) => void} />`, `<StageColumn stage={string} lanes={Lane[]} …/>`, `<AgentCard lane={Lane} agent={Agent} onSelect={…} />`, `useElapsed(startedAt, endedAt): string`.

- [ ] **Step 1: Write the elapsed-time hook**

Create `console-ui/src/lib/useElapsed.ts`:

```ts
import { useEffect, useState } from "react";

const format = (ms: number) => {
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
};

/** Ticks once a second while running; freezes at the final duration when done. */
export function useElapsed(startedAt: number, endedAt: number): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (endedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [endedAt]);
  if (!startedAt) return "";
  return format((endedAt || now) - startedAt);
}
```

- [ ] **Step 2: Write the agent card**

Create `console-ui/src/components/AgentCard.tsx`:

```tsx
import { motion } from "motion/react";
import { AlertTriangle, Check, Loader2, Pause } from "lucide-react";
import { useElapsed } from "@/lib/useElapsed";
import type { Agent, Lane } from "@/lib/types";

type Props = { lane: Lane; agent?: Agent; parked: boolean; onSelect: () => void };

export function AgentCard({ lane, agent, parked, onSelect }: Props) {
  const elapsed = useElapsed(lane.startedAt, lane.endedAt);
  const color = agent?.color ?? "#64748b";
  const Icon = parked ? Pause : lane.status === "running" ? Loader2 : lane.status === "error" ? AlertTriangle : Check;

  return (
    <motion.button
      layout
      layoutId={lane.toolUseId}
      onClick={onSelect}
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: lane.status === "done" ? 0.7 : 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 380, damping: 30 }}
      className="w-full rounded-lg border bg-card p-2.5 text-left focus-visible:ring-2"
      style={{ borderColor: parked ? color : undefined, borderWidth: parked ? 2 : 1 }}
      aria-label={`${agent?.name ?? lane.slug}: ${lane.task || "working"}`}
    >
      <div className="flex items-center gap-2">
        <span
          className="grid size-6 shrink-0 place-items-center rounded text-[10px] font-bold text-white"
          style={{ background: color }}
        >
          {(agent?.name ?? lane.slug).slice(0, 2)}
        </span>
        <span className="truncate text-sm font-medium">{agent?.name ?? lane.slug}</span>
        <Icon
          className={`ml-auto size-3.5 shrink-0 ${lane.status === "running" && !parked ? "animate-spin" : ""}`}
          aria-hidden
        />
      </div>
      <p className="mt-1 truncate text-xs text-muted-foreground">{lane.task || "working…"}</p>
      <p className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
        {parked ? "needs you" : elapsed}
      </p>
    </motion.button>
  );
}
```

- [ ] **Step 3: Write the column and board**

Create `console-ui/src/components/StageColumn.tsx`:

```tsx
import { AnimatePresence } from "motion/react";
import { AgentCard } from "./AgentCard";
import type { Agent, Lane } from "@/lib/types";

type Props = {
  stage: string;
  lanes: Lane[];
  agents: Record<string, Agent>;
  parkedLane: string | null;
  onSelect: (lane: Lane) => void;
};

export function StageColumn({ stage, lanes, agents, parkedLane, onSelect }: Props) {
  return (
    <section className="flex min-w-[150px] flex-1 flex-col rounded-xl border bg-muted/30 p-2">
      <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {stage}
        <span className="ml-1.5 tabular-nums opacity-60">{lanes.length || ""}</span>
      </h2>
      <div className="flex flex-col gap-2">
        <AnimatePresence mode="popLayout">
          {lanes.map((lane) => (
            <AgentCard
              key={lane.toolUseId}
              lane={lane}
              agent={agents[lane.slug]}
              parked={parkedLane === lane.toolUseId}
              onSelect={() => onSelect(lane)}
            />
          ))}
        </AnimatePresence>
        {lanes.length === 0 && (
          <p className="rounded-lg border border-dashed px-2 py-3 text-center text-[11px] text-muted-foreground">
            idle
          </p>
        )}
      </div>
    </section>
  );
}
```

Create `console-ui/src/components/Board.tsx`:

```tsx
import { LayoutGroup } from "motion/react";
import { StageColumn } from "./StageColumn";
import type { Agent, Catalog, Lane, RunView } from "@/lib/types";

type Props = {
  view: RunView;
  catalog: Catalog;
  onSelect: (lane: Lane) => void;
};

export function Board({ view, catalog, onSelect }: Props) {
  const agents: Record<string, Agent> = Object.fromEntries(
    catalog.agents.map((agent) => [agent.slug, agent]),
  );
  const stageOf = (slug: string) => agents[slug]?.stage ?? "Working";
  // Working only earns a column when something actually lands in it.
  const stages = catalog.stages.filter(
    (stage) => stage !== "Working" || view.lanes.some((lane) => stageOf(lane.slug) === "Working"),
  );
  const parkedLane =
    view.pending && view.lanes.find((lane) => lane.status === "running")?.toolUseId;

  return (
    <LayoutGroup>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {stages.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            lanes={view.lanes.filter((lane) => stageOf(lane.slug) === stage)}
            agents={agents}
            parkedLane={parkedLane ?? null}
            onSelect={onSelect}
          />
        ))}
      </div>
    </LayoutGroup>
  );
}
```

- [ ] **Step 4: Respect reduced motion globally**

Append to `console-ui/src/index.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Verify it compiles and tests still pass**

Run: `cd console-ui && npx tsc --noEmit && npx vitest run`
Expected: no type errors; 14 tests pass

- [ ] **Step 6: Commit**

```bash
git add console-ui/src
git commit -m "feat(console-ui): pipeline board with animated agent lanes"
```

---

### Task 8: Approval bar, decision sheet, and question cards

**Files:**
- Create: `console-ui/src/components/ApprovalBar.tsx`, `console-ui/src/components/DecisionSheet.tsx`
- Test: `console-ui/src/components/DecisionSheet.test.tsx`

**Interfaces:**
- Consumes: `PendingPrompt` (Task 6), `answerPrompt` (Task 6).
- Produces: `<ApprovalBar pending={PendingPrompt|null} onOpen={() => void} />` and `<DecisionSheet pending={PendingPrompt} open={boolean} onClose={…} onAnswer={(payload: Record<string, unknown>) => void} />`. `buildAnswers(questions, selections) -> Record<string, string | string[]>` is exported from `DecisionSheet.tsx` and unit-tested.

- [ ] **Step 1: Write the failing test for answer shaping**

Create `console-ui/src/components/DecisionSheet.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { buildAnswers } from "./DecisionSheet";

const questions = [
  {
    question: "How should I partition?",
    header: "Partition",
    multiSelect: false,
    options: [{ label: "Hash", description: "" }, { label: "Range", description: "" }],
  },
  {
    question: "Which suites?",
    header: "Suites",
    multiSelect: true,
    options: [{ label: "Unit", description: "" }, { label: "Feature", description: "" }],
  },
];

describe("buildAnswers", () => {
  it("maps a single select to its label", () => {
    expect(buildAnswers(questions, { "How should I partition?": ["Hash"] })).toEqual({
      "How should I partition?": "Hash",
    });
  });

  it("keeps a multi-select as an array", () => {
    const out = buildAnswers(questions, { "Which suites?": ["Unit", "Feature"] });
    expect(out["Which suites?"]).toEqual(["Unit", "Feature"]);
  });

  it("uses free text verbatim rather than the word Other", () => {
    const out = buildAnswers(questions, { "How should I partition?": ["by tenant id, hashed"] });
    expect(out["How should I partition?"]).toBe("by tenant id, hashed");
  });

  it("omits unanswered questions", () => {
    expect(buildAnswers(questions, {})).toEqual({});
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd console-ui && npx vitest run src/components/DecisionSheet.test.tsx`
Expected: FAIL — cannot resolve `./DecisionSheet`

- [ ] **Step 3: Write the approval bar**

Create `console-ui/src/components/ApprovalBar.tsx`:

```tsx
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PendingPrompt } from "@/lib/types";

/** Always on top of the board: a parked run must never be silent. */
export function ApprovalBar({
  pending,
  onOpen,
}: {
  pending: PendingPrompt | null;
  onOpen: () => void;
}) {
  return (
    <AnimatePresence>
      {pending && (
        <motion.div
          role="alert"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ type: "spring", stiffness: 420, damping: 32 }}
          className="sticky top-0 z-30 mb-3 flex items-center gap-3 rounded-lg border-2 border-amber-500 bg-amber-500/10 px-3 py-2"
        >
          <AlertTriangle className="size-4 shrink-0 text-amber-600" aria-hidden />
          <p className="truncate text-sm font-semibold">
            {pending.is_question
              ? "The Guild needs a decision from you"
              : `Approval needed — ${pending.tool}`}
          </p>
          <Button size="sm" className="ml-auto" onClick={onOpen}>
            Review
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 4: Write the decision sheet**

Create `console-ui/src/components/DecisionSheet.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import type { PendingPrompt } from "@/lib/types";

export type Question = {
  question: string;
  header: string;
  multiSelect: boolean;
  options: { label: string; description: string }[];
};

/** Answers map question text -> chosen label(s), or the user's own words. */
export function buildAnswers(
  questions: Question[],
  selections: Record<string, string[]>,
): Record<string, string | string[]> {
  const answers: Record<string, string | string[]> = {};
  for (const question of questions) {
    const chosen = selections[question.question];
    if (!chosen || chosen.length === 0) continue;
    answers[question.question] = question.multiSelect ? chosen : chosen[0];
  }
  return answers;
}

export function DecisionSheet({
  pending,
  open,
  onClose,
  onAnswer,
}: {
  pending: PendingPrompt;
  open: boolean;
  onClose: () => void;
  onAnswer: (payload: Record<string, unknown>) => void;
}) {
  const [selections, setSelections] = useState<Record<string, string[]>>({});
  const [other, setOther] = useState<Record<string, string>>({});
  const [denyReason, setDenyReason] = useState("");
  const questions = (pending.input.questions as Question[]) ?? [];

  const toggle = (question: Question, label: string) =>
    setSelections((prev) => {
      const current = prev[question.question] ?? [];
      if (!question.multiSelect) return { ...prev, [question.question]: [label] };
      return {
        ...prev,
        [question.question]: current.includes(label)
          ? current.filter((entry) => entry !== label)
          : [...current, label],
      };
    });

  const submitQuestions = () => {
    const merged = { ...selections };
    for (const [question, text] of Object.entries(other)) {
      if (text.trim()) merged[question] = [text.trim()];
    }
    onAnswer({
      prompt_id: pending.prompt_id,
      behavior: "allow",
      answers: buildAnswers(questions, merged),
    });
  };

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="bottom" className="max-h-[80vh] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            {pending.is_question ? "The Guild has questions" : `Allow ${pending.tool}?`}
          </SheetTitle>
        </SheetHeader>

        {pending.is_question ? (
          <div className="space-y-5 py-4">
            {questions.map((question) => (
              <fieldset key={question.question}>
                <legend className="mb-2 text-sm font-medium">{question.question}</legend>
                <div className="flex flex-wrap gap-2">
                  {question.options.map((option) => (
                    <Button
                      key={option.label}
                      type="button"
                      variant={
                        (selections[question.question] ?? []).includes(option.label)
                          ? "default"
                          : "outline"
                      }
                      size="sm"
                      onClick={() => toggle(question, option.label)}
                      title={option.description}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
                <Input
                  className="mt-2"
                  placeholder="Other — type your own answer"
                  value={other[question.question] ?? ""}
                  onChange={(e) =>
                    setOther((prev) => ({ ...prev, [question.question]: e.target.value }))
                  }
                />
              </fieldset>
            ))}
            <div className="flex gap-2">
              <Button onClick={submitQuestions}>Send answers</Button>
              <Button
                variant="outline"
                onClick={() =>
                  onAnswer({
                    prompt_id: pending.prompt_id,
                    behavior: "allow",
                    answers: {},
                    response: denyReason || "Do what you judge best.",
                  })
                }
              >
                Reply in my own words
              </Button>
            </div>
            <Textarea
              placeholder="…or write a freeform reply instead of choosing"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs">
              {JSON.stringify(pending.input, null, 2)}
            </pre>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => onAnswer({ prompt_id: pending.prompt_id, behavior: "allow" })}
              >
                Allow once
              </Button>
              {pending.suggestions.length > 0 && (
                <Button
                  variant="secondary"
                  onClick={() =>
                    onAnswer({
                      prompt_id: pending.prompt_id,
                      behavior: "allow",
                      remember: true,
                    })
                  }
                >
                  Allow always
                </Button>
              )}
              <Button
                variant="destructive"
                onClick={() =>
                  onAnswer({
                    prompt_id: pending.prompt_id,
                    behavior: "deny",
                    message: denyReason || "The user denied this action.",
                  })
                }
              >
                Deny
              </Button>
            </div>
            <Textarea
              placeholder="Tell the agent why, or what to do instead"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 5: Wire "allow always" through the engine**

Replace the whole `_to_permission_result` function in `scripts/console/engine.py` with this version, which carries the `remember` flag through:

```python
def _to_permission_result(decision: dict, input_data: dict):
    """Shape the callback's return value. Allow ALWAYS echoes updated_input."""
    behavior = decision.get("behavior", "deny")
    if behavior != "allow":
        return {"behavior": "deny", "message": decision.get("message") or "Denied by the user."}
    updated = decision.get("updated_input")
    if updated is None and "answers" in decision:
        updated = {"questions": (input_data or {}).get("questions", []),
                   "answers": decision["answers"]}
        if decision.get("response"):
            updated["response"] = decision["response"]
    if updated is None:
        updated = input_data
    result = {"behavior": "allow", "updated_input": updated}
    if decision.get("remember"):
        # Ask the SDK adapter to echo back the localSettings suggestion so
        # matching calls stop prompting in future sessions.
        result["persist"] = "localSettings"
    return result
```

Then replace the `can_use_tool` closure inside `sdk_client_factory` in `scripts/console/serve.py` with:

```python
    async def can_use_tool(tool_name, input_data, context):
        decision = await engine_callback(tool_name, input_data, context)
        if decision.get("behavior") != "allow":
            return PermissionResultDeny(message=decision.get("message") or "Denied by the user.")
        # Allow MUST echo updated_input — an omitted one was rejected outright
        # before Claude Code v2.1.207.
        if decision.get("persist") == "localSettings":
            persist = [
                suggestion
                for suggestion in (getattr(context, "suggestions", None) or [])
                if getattr(suggestion, "destination", None) == "localSettings"
            ]
            if persist:
                return PermissionResultAllow(
                    updated_input=decision["updated_input"], updated_permissions=persist
                )
        return PermissionResultAllow(updated_input=decision["updated_input"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd console-ui && npx vitest run` then `cd .. && python3 -m unittest discover -s tests/console -t tests/console -v`
Expected: 19 frontend tests pass; all python tests still pass

- [ ] **Step 7: Commit**

```bash
git add console-ui/src scripts/console/engine.py scripts/console/serve.py
git commit -m "feat(console): unmissable approval bar, decision sheet, question cards"
```

---

### Task 9: Launcher, focus mode, transcript, and app wiring

**Files:**
- Create: `console-ui/src/components/Launcher.tsx`, `FocusRun.tsx`, `Transcript.tsx`
- Modify: `console-ui/src/App.tsx`, `console-ui/src/main.tsx`

**Interfaces:**
- Consumes: everything from Tasks 6–8.
- Produces: `<App />` mounting at `#root`; `<Launcher catalog onLaunch={(spec) => void} />`; `<FocusRun view catalog />`; `<Transcript events={GuildEvent[]} />`.

- [ ] **Step 1: Write the transcript**

Create `console-ui/src/components/Transcript.tsx`:

```tsx
import type { GuildEvent } from "@/lib/types";

const label = (event: GuildEvent) => {
  if (event.type === "tool_use") {
    const input = (event.input as Record<string, unknown>) ?? {};
    const detail = input.command ?? input.file_path ?? input.pattern ?? "";
    return `${event.tool} ${String(detail)}`.trim();
  }
  if (event.type === "text" || event.type === "thinking") return String(event.text ?? "");
  if (event.type === "tool_result") return event.is_error ? "→ error" : "→ ok";
  return event.type;
};

export function Transcript({ events }: { events: GuildEvent[] }) {
  if (events.length === 0) {
    return <p className="text-xs text-muted-foreground">Nothing yet.</p>;
  }
  return (
    <ol className="space-y-1.5 text-xs">
      {events.map((event) => (
        <li key={event.seq} className="flex gap-2">
          <span className="w-16 shrink-0 tabular-nums text-muted-foreground">
            {new Date(event.ts).toLocaleTimeString()}
          </span>
          <span
            className={`min-w-0 flex-1 break-words ${
              event.type === "thinking" ? "italic text-muted-foreground" : ""
            }`}
          >
            {label(event)}
          </span>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 2: Write focus mode**

Create `console-ui/src/components/FocusRun.tsx`:

```tsx
import { motion } from "motion/react";
import { useElapsed } from "@/lib/useElapsed";
import { Transcript } from "./Transcript";
import type { Catalog, RunView } from "@/lib/types";

export function FocusRun({ view, catalog }: { view: RunView; catalog: Catalog }) {
  const lane = view.lanes[0];
  const agent = catalog.agents.find((candidate) => candidate.slug === lane?.slug);
  const elapsed = useElapsed(lane?.startedAt ?? 0, lane?.endedAt ?? 0);
  const events = lane ? lane.events : view.main;

  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <motion.aside
        layout
        className="rounded-xl border p-3 md:w-56"
        style={{ borderColor: agent?.color }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          {agent?.name ?? "Main thread"}
        </p>
        <p className="mt-1 text-sm">{lane?.task || view.result?.subtype || "working…"}</p>
        <p className="mt-1 text-xs tabular-nums text-muted-foreground">{elapsed}</p>
        {agent && <p className="mt-2 text-[11px] text-muted-foreground">{agent.model}</p>}
      </motion.aside>
      <section className="min-w-0 flex-1 rounded-xl border p-3">
        <Transcript events={events} />
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Write the launcher**

Create `console-ui/src/components/Launcher.tsx`:

```tsx
import { useState } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Catalog } from "@/lib/types";

export type LaunchSpec = { kind: string; target: string; text: string; mode: string };

export function Launcher({
  catalog,
  busy,
  onLaunch,
}: {
  catalog: Catalog;
  busy: boolean;
  onLaunch: (spec: LaunchSpec) => void;
}) {
  const [kind, setKind] = useState("prompt");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState("default");

  const targets =
    kind === "command"
      ? catalog.commands.map((command) => ({ value: command.slug, label: `/${command.slug}` }))
      : kind === "specialist"
        ? catalog.agents
            .filter((agent) => agent.stage !== null)
            .map((agent) => ({ value: agent.slug, label: `${agent.name} — ${agent.slug}` }))
        : [];

  return (
    <form
      className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        onLaunch({ kind, target, text, mode });
      }}
    >
      <select
        aria-label="Run kind"
        className="h-9 rounded-md border bg-background px-2 text-sm"
        value={kind}
        onChange={(event) => {
          setKind(event.target.value);
          setTarget("");
        }}
      >
        <option value="prompt">Freeform</option>
        <option value="command">Command</option>
        <option value="specialist">Specialist</option>
      </select>

      {targets.length > 0 && (
        <select
          aria-label="Target"
          className="h-9 max-w-56 rounded-md border bg-background px-2 text-sm"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          required
        >
          <option value="">Choose…</option>
          {targets.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}

      <Input
        className="min-w-56 flex-1"
        placeholder={kind === "command" ? "arguments (optional)" : "describe the task"}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />

      <select
        aria-label="Permission mode"
        className="h-9 rounded-md border bg-background px-2 text-sm"
        value={mode}
        onChange={(event) => setMode(event.target.value)}
      >
        <option value="default">Ask me</option>
        <option value="acceptEdits">Accept edits</option>
        <option value="plan">Plan only</option>
      </select>

      <Button type="submit" disabled={busy}>
        <Play className="mr-1 size-4" aria-hidden /> Run
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Wire the app**

Create `console-ui/src/App.tsx`:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApprovalBar } from "@/components/ApprovalBar";
import { Board } from "@/components/Board";
import { DecisionSheet } from "@/components/DecisionSheet";
import { FocusRun } from "@/components/FocusRun";
import { Launcher, type LaunchSpec } from "@/components/Launcher";
import { Transcript } from "@/components/Transcript";
import * as api from "@/lib/api";
import { emptyRun, reduce } from "@/lib/reducer";
import type { Catalog, GuildEvent, Lane, RunView } from "@/lib/types";

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView>(() => emptyRun("prompt"));
  const [selected, setSelected] = useState<Lane | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    api.fetchCatalog().then(setCatalog).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const onEvent = useCallback((event: GuildEvent) => {
    lastSeq.current = Math.max(lastSeq.current, event.seq);
    setView((current) => reduce(current, event));
    if (event.type === "prompt") setSheetOpen(true);
  }, []);

  useEffect(() => {
    if (!runId) return;
    return api.streamRun(runId, lastSeq.current, onEvent);
  }, [runId, onEvent]);

  const launch = async (spec: LaunchSpec) => {
    setError(null);
    lastSeq.current = 0;
    setView(emptyRun(spec.kind));
    try {
      const { run_id } = await api.createRun(spec);
      setRunId(run_id);
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  const answer = async (payload: Record<string, unknown>) => {
    if (!runId) return;
    setSheetOpen(false);
    try {
      await api.answerPrompt(runId, payload);
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  if (!catalog) {
    return (
      <main className="mx-auto max-w-md p-8 text-sm">
        {error ? `Could not reach the console API: ${error}` : "Loading the Guild…"}
      </main>
    );
  }

  // The init event reports plugins, not agent counts — so "did the pack load"
  // is exactly: no plugin errors, and laravel-team present among the plugins.
  const packBroken =
    view.init !== null &&
    (view.init.plugin_errors.length > 0 || !view.init.plugins.includes("laravel-team"));

  return (
    <main className="mx-auto max-w-6xl p-4 md:p-6">
      <header className="mb-4 flex items-baseline gap-3">
        <h1 className="text-lg font-semibold">Laravel Guild Console</h1>
        {runId && (
          <Button size="sm" variant="outline" className="ml-auto" onClick={() => api.interruptRun(runId)}>
            <Square className="mr-1 size-3.5" aria-hidden /> Interrupt
          </Button>
        )}
      </header>

      <Launcher catalog={catalog} busy={false} onLaunch={launch} />

      {packBroken && (
        <p role="alert" className="mb-3 flex items-center gap-2 rounded-lg border-2 border-destructive px-3 py-2 text-sm">
          <AlertTriangle className="size-4" aria-hidden />
          The Guild pack did not load cleanly — agents may be missing.
        </p>
      )}
      {error && <p role="alert" className="mb-3 text-sm text-destructive">{error}</p>}
      {view.retry && (
        <p className="mb-3 text-xs text-muted-foreground">
          Retrying after {view.retry.error} — attempt {view.retry.attempt} of {view.retry.max_retries}
        </p>
      )}

      <ApprovalBar pending={view.pending} onOpen={() => setSheetOpen(true)} />

      {view.mode === "board" ? (
        <Board view={view} catalog={catalog} onSelect={setSelected} />
      ) : (
        <FocusRun view={view} catalog={catalog} />
      )}

      {selected && (
        <section className="mt-4 rounded-xl border p-3">
          <h2 className="mb-2 text-sm font-medium">
            {catalog.agents.find((a) => a.slug === selected.slug)?.name ?? selected.slug}
          </h2>
          <Transcript events={view.lanes.find((l) => l.toolUseId === selected.toolUseId)?.events ?? []} />
        </section>
      )}

      {view.result && (
        <section className="mt-4 rounded-xl border bg-muted/30 p-3">
          <h2 className="mb-1 text-sm font-medium">Final answer</h2>
          <p className="whitespace-pre-wrap text-sm">{view.result.result}</p>
        </section>
      )}

      {view.pending && (
        <DecisionSheet
          pending={view.pending}
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          onAnswer={answer}
        />
      )}
    </main>
  );
}
```

Create `console-ui/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 5: Build and verify**

Run: `cd console-ui && npm run build && npx vitest run`
Expected: build writes `../scripts/console/dist/index.html`; 18 tests pass

- [ ] **Step 6: Commit source and the built bundle**

```bash
git add console-ui/src scripts/console/dist
git commit -m "feat(console-ui): launcher, focus mode, transcript, app wiring + built bundle"
```

---

### Task 10: Ship it — installer, CI, ratchets, and counts

**Files:**
- Modify: `install.sh`, `.github/workflows/ci.yml`, `tests/guardrails.test.sh`, `scripts/check_inventory_sync.py`, `scripts/build-gemini-extension.py`, `README.md`, `.gitignore`
- Modify: `VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`

**Interfaces:**
- Consumes: everything above.
- Produces: a green `./tests/guardrails.test.sh`, a green CI, and `python3 scripts/check_inventory_sync.py` exiting 0 with `commands` at 13.

- [ ] **Step 1: Add the console to the installer**

`install_dir` skips directories (`[ -d "$f" ] && continue`), so `scripts/console/` would be silently dropped. Add a dedicated function after `install_dir`'s closing brace in `install.sh`:

```bash
# scripts/console/ is a tree (python modules + the built dist/), which
# install_dir deliberately skips — it copies files only. Recurse here instead.
install_console() {
  local src="$SCRIPT_DIR/scripts/console"
  local dest="$TARGET/scripts/console"
  if [ ! -d "$src" ]; then
    echo "  console: source missing — skipped"
    return 0
  fi
  if [ ! -f "$src/dist/index.html" ]; then
    echo "  console: bundle not built — skipped (run: cd console-ui && npm ci && npm run build)"
    return 0
  fi
  mkdir -p "$dest"
  cp -R "$src/." "$dest/"
  echo "  console: installed -> $dest"
}
```

Then call it immediately after the existing `install_dir "$SCRIPT_DIR/scripts" "$SCRIPTS_DEST" "guardrail scripts"` line:

```bash
  install_console
```

- [ ] **Step 2: Add the static ratchets to the guardrail suite**

Append to `tests/guardrails.test.sh`, immediately before the final `echo` / totals block:

```bash
echo "console (static ratchets)"
# bypassPermissions is inherited by subagents and cannot be overridden per
# subagent — offering it in the UI would grant 17 agents unattended access.
expect "console never offers bypassPermissions" "0" \
  "$(grep -rl 'bypassPermissions' "$SCRIPT_DIR"/scripts/console/dist "$SCRIPT_DIR"/console-ui/src 2>/dev/null | wc -l | tr -d ' ')"
# dontAsk denies AskUserQuestion, which is how checkpoint prompts arrive.
expect "console never selects dontAsk" "0" \
  "$(grep -rl "'dontAsk'\|\"dontAsk\"" "$SCRIPT_DIR"/console-ui/src 2>/dev/null | wc -l | tr -d ' ')"
expect "console server binds loopback only" "1" \
  "$(grep -q 'make_server("127\.0\.0\.1"' "$SCRIPT_DIR"/scripts/console/serve.py && echo 1 || echo 0)"
expect "console never binds a public interface" "0" \
  "$(grep -c '0\.0\.0\.0' "$SCRIPT_DIR"/scripts/console/serve.py "$SCRIPT_DIR"/scripts/console/server.py | awk -F: '{s+=$2} END{print s}')"
expect "console API is token-guarded" "1" \
  "$(grep -q 'X-Guild-Token' "$SCRIPT_DIR"/scripts/console/server.py && echo 1 || echo 0)"
expect "console rejects non-local Origin" "1" \
  "$(grep -q 'LOCAL_ORIGIN' "$SCRIPT_DIR"/scripts/console/server.py && echo 1 || echo 0)"
expect "console bundle is committed" "1" \
  "$([ -f "$SCRIPT_DIR/scripts/console/dist/index.html" ] && echo 1 || echo 0)"
# The board and its observer are deliberately untouched by the console work.
expect "emit-agent-events.sh still wired three ways" "3" \
  "$(grep -c 'emit-agent-events.sh' "$SCRIPT_DIR/hooks/hooks.json" | tr -d ' ')"
```

- [ ] **Step 3: Run the guardrail suite**

Run: `./tests/guardrails.test.sh`
Expected: `ALL GREEN`, 100 passed (92 existing + 8 new)

Then negative-control two of them, per the repo's habit of proving a new test can fail: temporarily add `bypassPermissions` to a file under `console-ui/src/`, re-run, confirm FAIL, revert. Do the same by changing `127.0.0.1` to `0.0.0.0` in `serve.py`.

- [ ] **Step 4: Update the inventory checker and Gemini skip lists**

In `scripts/check_inventory_sync.py`:

```python
GEMINI_SKIPPED_COMMANDS = {"board.md", "console.md"}  # kept in sync with build-gemini-extension.py
```

In `scripts/build-gemini-extension.py` (line ~153), and extend the comment above it:

```python
# board.md reads the feed written by emit-agent-events.sh, a PreToolUse/
# PostToolUse observer Gemini has no equivalent for. console.md drives the
# Claude Agent SDK, which Gemini does not ship.
GEMINI_SKIP_COMMANDS = {"board.md", "console.md"}
```

Both skips mean the Gemini command count stays at 11 (13 − 2), so no README Gemini claim moves.

- [ ] **Step 5: Bump the command count everywhere it is claimed**

Replace `12 workflow commands` with `13 workflow commands` in all four manifests:

```bash
sed -i '' 's/12 workflow commands/13 workflow commands/' \
  .claude-plugin/plugin.json .claude-plugin/marketplace.json \
  .cursor-plugin/plugin.json .cursor-plugin/marketplace.json
sed -i '' 's/the 12 slash commands/the 13 slash commands/' README.md
```

Then add the row to README's command table, immediately after the `/board [port]` row:

```markdown
| `/console [port]`                         | Opens the Guild web console — a browser UI that launches runs (command, specialist, or freeform), streams every agent onto a pipeline board, and surfaces approvals and checkpoint questions as real UI. Claude Code only. |
```

and add `console.md` to the commands tree listing near line 46:

```markdown
    ├── console.md                # Open the Guild web console (React board, approvals, interrupt)
```

- [ ] **Step 6: Verify the counts and generators**

Run:
```bash
python3 scripts/check_inventory_sync.py
python3 scripts/check_body_budget.py
python3 scripts/build-gemini-extension.py && git diff --stat -- gemini/
python3 scripts/build-codex-extension.py && git diff --stat -- codex/
```
Expected: both checkers exit 0; the generators produce **no** diff (`console.md` is skipped for Gemini, and Codex ships no commands).

- [ ] **Step 7: Add the CI jobs**

Append two jobs to `.github/workflows/ci.yml`:

```yaml
  console-python:
    name: console python units
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Run console unit tests (stdlib unittest, no SDK required)
        run: python3 -m unittest discover -s tests/console -t tests/console -v

  console-ui:
    name: console ui
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: console-ui/package-lock.json
      - name: Install
        working-directory: console-ui
        run: npm ci
      - name: Typecheck + unit tests
        working-directory: console-ui
        run: npx tsc --noEmit && npx vitest run
      - name: Built bundle is in sync with source
        working-directory: console-ui
        run: npm run build
      - name: Fail if dist/ is stale
        run: |
          git diff --exit-code -- scripts/console/dist \
            || { echo "::error::scripts/console/dist is stale — run: cd console-ui && npm run build and commit"; exit 1; }
```

- [ ] **Step 8: Ignore local console state**

Add to `.gitignore`:

```
# Console local state (venv + run transcripts)
.claude/console/
# Brainstorming companion screens
.superpowers/
```

- [ ] **Step 9: Bump the version**

```bash
echo "1.27.0" > VERSION
sed -i '' 's/"version": "1.26.0"/"version": "1.27.0"/' \
  .claude-plugin/plugin.json .cursor-plugin/plugin.json .claude-plugin/marketplace.json
python3 scripts/build-gemini-extension.py
```

Then add the `[1.27.0]` entry to `CHANGELOG.md` in Keep-a-Changelog voice, under `### Added`, describing the console, the two new CI jobs, and the 13th command.

- [ ] **Step 10: Full green check and commit**

Run:
```bash
./tests/guardrails.test.sh
python3 -m unittest discover -s tests/console -t tests/console -v
python3 scripts/validate-frontmatter.py
python3 scripts/check_inventory_sync.py && python3 scripts/check-hook-sync.py
shellcheck install.sh tests/guardrails.test.sh
(cd console-ui && npx tsc --noEmit && npx vitest run && npm run build)
git diff --exit-code -- scripts/console/dist gemini/ codex/
```
Expected: every command exits 0.

```bash
git add -A
git commit -m "release: 1.27.0 — the Guild web console (/console, 13th command)"
```

---

### Task 11: Smoke test against the fixture app

**Files:**
- Modify: none (verification only; findings may reopen earlier tasks)

**Interfaces:**
- Consumes: the whole console.
- Produces: a verified end-to-end run, or a defect list.

- [ ] **Step 1: Launch against the planted-flaw fixture**

Run:
```bash
cd tests/fixture-app
python3 ../../scripts/console/serve.py --port 8378
```
Expected: venv created on first run, then `guild-console: http://127.0.0.1:8378/?token=…` and the browser opens.

- [ ] **Step 2: Verify a command run reaches the board**

In the UI: kind **Command** → `/audit-n-plus-one` → text `the posts index` → mode **Ask me** → Run.
Expected: the board appears; a lane opens under Review for `performance-engineer` with a live ticking timer; the transcript fills as tools run.

- [ ] **Step 3: Verify an approval parks and resumes the run**

Expected: when the agent first runs a Bash command, the amber bar appears at the top, the card shows `needs you`, and the sheet opens with the exact command. Click **Deny** with the message `use sail, not bare php`. Expected: the agent acknowledges the denial in its next message rather than silently retrying.

- [ ] **Step 4: Verify a specialist run opens focused**

Launch kind **Specialist** → `performance-engineer` → `why is the posts index slow?`.
Expected: Focus mode, one full-width lane, no empty columns. If that run spawns a second agent, the layout promotes to the board.

- [ ] **Step 5: Verify interrupt clears a pending prompt**

Start a command run, wait for the amber bar, then click **Interrupt** without answering.
Expected: the run stops within a few seconds and does not hang. This is the failure mode the engine explicitly guards; if it hangs, the deny-pending-first path in `_interrupt` is broken.

- [ ] **Step 6: Verify the guardrails still bite**

Launch kind **Freeform** → `run php artisan migrate:fresh on production`.
Expected: `block-prod-artisan.sh` denies it at the hook layer — the console never even shows an approval card, because a hook deny precedes the permission flow.

- [ ] **Step 7: Verify SSE resume**

Mid-run, reload the browser tab.
Expected: the board rebuilds from the replayed backlog with no duplicated lanes and no lost events.

- [ ] **Step 8: Record the outcome**

Write findings to `docs/evals/2026-07-29-console-smoke.md` — what passed, what failed, and the exact reproduction for anything that failed. Commit:

```bash
git add docs/evals/2026-07-29-console-smoke.md
git commit -m "docs: console smoke-test findings"
```

---

## Post-plan notes

**Deliberately not in this plan** (spec's scope boundary): the pack manager, the eval cockpit, a multi-project daemon, terminal-run visibility, session resume across a server restart, mobile layout, and authentication.

**Sequencing constraint:** nothing here edits `agents/*.md`, so this can land before or after eval run 5 without confounding it. The held [literature-gap tranche](2026-07-29-literature-gap-tranche.md) remains gated on run 5 independently.
