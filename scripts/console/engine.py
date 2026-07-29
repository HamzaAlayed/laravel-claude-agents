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

Answering a prompt (`RunManager.answer`) must be safe when two callers race to
resolve the SAME prompt_id (e.g. two browser tabs open on one run). The
check ("is this prompt still pending?") and the set (resolve the future) are
therefore performed together as a single, non-suspending coroutine submitted
to the engine loop via run_coroutine_threadsafe, and the calling thread blocks
on its real result. Because that coroutine never awaits anything, the loop
runs it to completion in one step — no other callback can interleave between
the check and the set — so exactly one racing caller ever observes success.
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

# Wall-clock cap for the answer() round trip to the engine loop. Answering a
# prompt is a single non-suspending coroutine step, so it is effectively
# instantaneous once scheduled; this only guards against a wedged/closed loop.
ANSWER_TIMEOUT = 5.0


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
        options = {
            "cwd": str(self.root),
            "permission_mode": mode,
            "can_use_tool": self._make_can_use_tool(run),
        }
        if spec.get("model"):
            options["model"] = spec["model"]
        # Build the client BEFORE registering the run. client_factory does real
        # work on this thread (imports the SDK, constructs ClaudeAgentOptions
        # with an unvalidated `model`), so it can raise -- and registering first
        # left a zombie behind: client=None, status="running" forever, listed by
        # GET /api/runs, AttributeError on every later /message|/mode|/interrupt.
        # Raising here instead makes POST /api/runs answer 400 with the reason.
        run.client = self.client_factory(options)
        self.runs[run_id] = run
        # A _boot failure deliberately KEEPS the registration: the client exists
        # and may hold a live CLI subprocess, so shutdown() must still be able
        # to disconnect it. _pump reports the failure as an `error` event.
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

    @staticmethod
    def _agent_for_prompt(run: Run, context) -> str | None:
        """Which agent's lane is blocked on this approval.

        can_use_tool is not handed a lane id, so this is layered, most exact
        first:

        1. `context.tool_use_id` is the id of the very call being asked about.
           If the assistant message carrying that tool_use block has already
           been normalized, `lane_by_tool_use` knows exactly which lane emitted
           it -- including `None` for the main thread. Exact, not a guess.
        2. Otherwise the permission request overtook its own assistant message
           in the transport (both are handled on this loop, but messages queue
           through receive_messages while control requests are dispatched
           directly). `context.agent_id` is None on the main thread, so a None
           there is still a fact: no subagent asked.
        3. A subagent did ask but we cannot yet say which block: attribute to
           the most recently started still-open lane. This is the one
           heuristic, and it is strictly better than the browser's previous
           behaviour of marking whichever lane happened to be first.
        """
        lane = run.state.lane_for_tool_use(_getattr(context, "tool_use_id", None))
        if lane is not events_mod.MISSING:
            return lane
        if _getattr(context, "agent_id", None) is None:
            return None
        return run.state.newest_open_lane()

    def _make_can_use_tool(self, run: Run):
        async def can_use_tool(tool_name, input_data, context):
            prompt_id = f"p_{uuid.uuid4().hex[:10]}"
            agent = self._agent_for_prompt(run, context)
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
                "agent": agent,
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
                "agent": agent,
                "prompt_id": prompt_id,
                "behavior": decision.get("behavior"),
            })
            return _to_permission_result(decision, input_data)

        return can_use_tool

    def answer(self, run_id: str, prompt_id: str, payload: dict) -> bool:
        """Resolve a pending prompt. False when it is unknown or already answered.

        The check ("is prompt_id still pending?") and the set (resolve its
        future) happen inside one coroutine that never awaits, submitted to
        the engine loop. Because the loop is single-threaded and this
        coroutine has no suspension point, it runs atomically with respect to
        every other callback on that loop -- including a second call to
        answer() for the same prompt_id racing in from another thread. The
        first to be scheduled wins and returns True; every other caller sees
        the future already done and returns False. This is what makes
        first-answer-wins safe when two browser tabs both try to resolve the
        same prompt.
        """
        run = self.runs.get(run_id)
        if run is None:
            return False

        async def _check_and_set() -> bool:
            future = run.pending.get(prompt_id)
            if future is None or future.done():
                return False
            future.set_result(payload)
            return True

        try:
            return self.submit(_check_and_set()).result(timeout=ANSWER_TIMEOUT)
        except Exception:
            # Unknown run/prompt, closed loop, or a timeout all mean this
            # caller's answer did not land -- tell the truth, not a crash.
            return False

    # ---- reads -------------------------------------------------------------

    def is_live(self, run_id: str) -> bool:
        """True when this process owns the run, i.e. subscribe() can serve it.

        A run replayable from disk is NOT live: subscribe() would raise KeyError
        on its first next(), so the HTTP layer must refuse before it promises a
        stream. snapshot() still serves those from the jsonl.
        """
        return run_id in self.runs

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
        # UNION of live in-memory runs (authoritative for status/spec/started_at)
        # and disk-derived runs for runs not owned by this process. No duplicates.
        rows = []
        seen = set()

        # 1. Live in-memory runs — authoritative source.
        for run_id in sorted(self.runs.keys()):
            run = self.runs[run_id]
            rows.append({
                "run_id": run_id,
                "status": run.status,
                "spec": run.spec,
                "started_at": run.started_at,
            })
            seen.add(run_id)

        # 2. Disk-derived runs for runs this process does not own.
        # A run this process does not own must report "interrupted" because
        # the SDK child process died with whatever process started it.
        for path in sorted(self.runs_dir.glob("run_*.jsonl")):
            run_id = path.stem
            if run_id not in seen:
                rows.append({
                    "run_id": run_id,
                    "status": "interrupted",
                    "spec": None,
                    "started_at": int(path.stat().st_mtime * 1000),
                })
                seen.add(run_id)

        # Stable, deterministic ordering by run_id.
        rows.sort(key=lambda r: r["run_id"])
        return rows


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


def _getattr(obj, name, default=None):
    """getattr that never raises -- _as_dict sits between a third-party
    library and the whole event pipeline, so a missing/odd attribute on an
    SDK object must degrade to `default`, not blow up the run."""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _block_to_dict(block) -> dict:
    """Translate one Agent SDK content-block dataclass into the wire-format
    block shape events.normalize reads. Dispatches on class name, never
    isinstance, so this file never needs to import claude_agent_sdk.
    Already-dict blocks pass through; anything unrecognized becomes {} which
    normalize's `block.get("type")` skips silently."""
    if isinstance(block, dict):
        return block
    name = type(block).__name__
    if name == "TextBlock":
        return {"type": "text", "text": _getattr(block, "text", "")}
    if name == "ThinkingBlock":
        return {"type": "thinking", "thinking": _getattr(block, "thinking", "")}
    if name == "ToolUseBlock":
        return {
            "type": "tool_use",
            "id": _getattr(block, "id"),
            "name": _getattr(block, "name"),
            "input": _getattr(block, "input") or {},
        }
    if name == "ToolResultBlock":
        return {
            "type": "tool_result",
            "tool_use_id": _getattr(block, "tool_use_id"),
            "content": _getattr(block, "content"),
            "is_error": _getattr(block, "is_error"),
        }
    return {}


def _as_dict(message) -> dict:
    """Agent SDK message objects -> the CLI stream-json wire-format dicts
    events.normalize is written against.

    The SDK yields typed dataclasses (SystemMessage, AssistantMessage,
    UserMessage, ResultMessage, HookEventMessage, RateLimitEvent) that do not
    carry a `type` field and nest their payloads differently from the wire
    format -- a plain dataclasses.asdict() (the previous implementation)
    produces a dict with no "type" key, so normalize() silently returns []
    for every message. This dispatches on `type(message).__name__` (never
    isinstance, so engine.py never needs `import claude_agent_sdk` -- it
    stays unit-testable without the SDK installed) and rebuilds the exact
    shape normalize() reads.

    Inputs that are already dicts pass through unchanged: the fixture-driven
    unit tests feed dicts directly and that path must keep working as-is.
    """
    if isinstance(message, dict):
        return message

    name = type(message).__name__

    if name == "SystemMessage":
        out = {"type": "system", "subtype": _getattr(message, "subtype")}
        data = _getattr(message, "data") or {}
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "subtype":  # never let the init payload shadow it
                    continue
                out[key] = value
        return out

    if name == "AssistantMessage":
        content = _getattr(message, "content") or []
        return {
            "type": "assistant",
            "parent_tool_use_id": _getattr(message, "parent_tool_use_id"),
            "message": {"content": [_block_to_dict(b) for b in content]},
        }

    if name == "UserMessage":
        content = _getattr(message, "content") or []
        return {
            "type": "user",
            "parent_tool_use_id": _getattr(message, "parent_tool_use_id"),
            "message": {"content": [_block_to_dict(b) for b in content]},
        }

    if name == "ResultMessage":
        # Already flat and already matches what normalize() reads -- this
        # only needs a "type" key added.
        return {
            "type": "result",
            "subtype": _getattr(message, "subtype"),
            "result": _getattr(message, "result"),
            "duration_ms": _getattr(message, "duration_ms"),
            "total_cost_usd": _getattr(message, "total_cost_usd"),
            "usage": _getattr(message, "usage") or {},
        }

    # HookEventMessage, RateLimitEvent, and anything else the SDK might ever
    # add have no wire equivalent normalize() handles. Returning {} makes
    # raw.get("type") None, so normalize() takes its no-match path and
    # yields zero events instead of raising.
    return {}
