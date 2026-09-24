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
import os
import queue
import re
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import events as events_mod
from independence import instructions, routine_command

# bypassPermissions is inherited by subagents and cannot be overridden per
# subagent; dontAsk denies AskUserQuestion, which is how checkpoints arrive.
ALLOWED_MODES = ("default", "acceptEdits", "plan", "managed")
FORBIDDEN_MODES = ("bypassPermissions", "dontAsk", "auto")
SENTINEL = object()

# Tools whose calls must reach the browser even when Claude Code would decide
# them itself. can_use_tool is NOT the first gate: read-only Bash commands are
# auto-allowed before the callback runs, so `echo hello` produced no `prompt`
# event and nobody was asked. No SDK option or settings key disables that -- a
# PreToolUse hook is the only layer that sees every call, which the SDK's own
# shadowing warning says outright ("To gate every tool call, use a PreToolUse
# hook instead"). Bash is the whole of the remaining hole and the only tool here
# that can do damage; forcing Read/Grep/Glob through the browser would park a
# routine run dozens of times for no safety gain.
ASK_ALWAYS_TOOLS = ("Bash",)
ASK_REASON = "The console asks about every Bash call, including read-only ones."

# Wall-clock cap for the answer() round trip to the engine loop. Answering a
# prompt is a single non-suspending coroutine step, so it is effectively
# instantaneous once scheduled; this only guards against a wedged/closed loop.
ANSWER_TIMEOUT = 5.0

HARNESS_PATH = Path(__file__).resolve().parents[2] / "config" / "agent-harness.json"


def _load_budget_policy() -> tuple[dict, dict]:
    """Load the release-owned budget policy; fail closed on malformed installs."""
    try:
        registry = json.loads(HARNESS_PATH.read_text(encoding="utf-8"))
        budgets = registry["shared"]["budgets"]
        defaults = budgets["defaults"]
        ceilings = budgets["hardCeilings"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid agent harness registry at {HARNESS_PATH}: {exc}") from exc
    return dict(defaults), dict(ceilings)


DEFAULT_BUDGET, HARD_BUDGET_CEILINGS = _load_budget_policy()
DEFAULT_RETENTION_DAYS = 14
DEFAULT_MAX_RUNS = 100
DEFAULT_MAX_TRACE_BYTES = 25 * 1024 * 1024
MAX_TRACE_VALUE_CHARS = 8192
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|apikey|private[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"(?:sk-ant-|ghp_|github_pat_)[A-Za-z0-9_-]+|"
    r"((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+"
)
_MODEL_RATES = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "sonnet": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "haiku": (1.0, 5.0),
}


def _normalize_budget(value) -> dict:
    if value is None:
        return dict(DEFAULT_BUDGET)
    if not isinstance(value, dict) or set(value) - set(DEFAULT_BUDGET):
        raise ValueError(f"budget accepts only {', '.join(DEFAULT_BUDGET)}")
    budget = dict(DEFAULT_BUDGET)
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
            raise ValueError(f"budget {key} must be a positive number")
        if key != "max_usd" and not isinstance(raw, int):
            raise ValueError(f"budget {key} must be a positive integer")
        if raw > HARD_BUDGET_CEILINGS[key]:
            raise ValueError(
                f"budget {key} exceeds hard ceiling {HARD_BUDGET_CEILINGS[key]}"
            )
        budget[key] = raw
    budget["max_seconds"] = int(budget["max_seconds"])
    budget["max_tool_calls"] = int(budget["max_tool_calls"])
    budget["max_turns"] = int(budget["max_turns"])
    budget["max_tokens"] = int(budget["max_tokens"])
    budget["max_usd"] = float(budget["max_usd"])
    return budget


def _redact(value, key=""):
    if _SENSITIVE_KEY.search(str(key)):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        text = _SECRET_VALUE.sub(
            lambda match: (match.group(1) or "") + "[REDACTED]", value
        )
        if len(text) > MAX_TRACE_VALUE_CHARS:
            return text[:MAX_TRACE_VALUE_CHARS] + "…[TRUNCATED]"
        return text
    return value


def _number(value) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _rates_for(model) -> tuple[float, float]:
    name = str(model or "")
    for alias, rates in _MODEL_RATES.items():
        if name == alias or name.startswith(alias + "-") or name.startswith(alias + "["):
            return rates
    # Unknown models use the most expensive known rate so the runtime never
    # silently understates spend.
    return (10.0, 50.0)


def _usage_cost(usage: dict, model) -> float:
    if not isinstance(usage, dict):
        return 0.0
    input_rate, output_rate = _rates_for(model)
    input_tokens = _number(usage.get("input_tokens"))
    output_tokens = _number(usage.get("output_tokens"))
    cache_read = _number(usage.get("cache_read_input_tokens"))
    cache_write = _number(usage.get("cache_creation_input_tokens"))
    return (
        input_tokens * input_rate
        + output_tokens * output_rate
        + cache_read * input_rate * 0.1
        + cache_write * input_rate * 2.0
    ) / 1_000_000


def _usage_tokens(usage: dict) -> int:
    if not isinstance(usage, dict):
        return 0
    keys = (
        "input_tokens", "output_tokens", "cache_read_input_tokens",
        "cache_creation_input_tokens",
    )
    return int(sum(_number(usage.get(key)) for key in keys))


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
        self.budget = spec["budget"]
        self.mode = _check_mode(spec.get("mode"))
        self.path = path
        self.state = events_mod.RunState(run_id)
        self.client = None
        self.buffer: list[dict] = []
        self.subscribers: list[queue.SimpleQueue] = []
        self.pending: dict[str, asyncio.Future] = {}
        # (tool, exact command) pairs the user chose "Allow always" for. A hook
        # `ask` outranks allow rules, so without this the button would persist a
        # settings rule and then be overridden on the very next matching call.
        self.remembered: set[tuple[str, str]] = set()
        self.status = "running"
        self.started_at = int(time.time() * 1000)
        self.usage = {"tokens": 0, "tool_calls": 0, "turns": 0, "cost_usd": 0.0}
        self.budget_reason = None
        self.watchdog = None
        self.trace_persistence_capped = False
        self.lock = threading.Lock()


class RunManager:
    def __init__(
        self, root: Path, client_factory, *, retention_days=DEFAULT_RETENTION_DAYS,
        max_runs=DEFAULT_MAX_RUNS, max_trace_bytes=DEFAULT_MAX_TRACE_BYTES,
        persist_raw=False
    ):
        self.root = Path(root)
        self.client_factory = client_factory
        self.runs_dir = self.root / ".claude" / "console" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.max_runs = max_runs
        self.max_trace_bytes = max_trace_bytes
        self.persist_raw = persist_raw
        self._prune_traces()
        self.runs: dict[str, Run] = {}
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, name="guild-engine", daemon=True)
        self.thread.start()

    def _prune_traces(self):
        now = time.time()
        paths = sorted(
            self.runs_dir.glob("run_*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for index, path in enumerate(paths):
            expired = now - path.stat().st_mtime > self.retention_days * 86400
            if expired or index >= self.max_runs:
                path.unlink(missing_ok=True)

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
        if not self.thread.is_alive() and not self.loop.is_closed():
            self.loop.close()

    # ---- run lifecycle -----------------------------------------------------

    def start(self, spec: dict, *, _prompt_override=None) -> str:
        spec = dict(spec)
        spec["budget"] = _normalize_budget(spec.get("budget"))
        mode = _check_mode(spec.get("mode"))
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = Run(run_id, spec, self.runs_dir / f"{run_id}.jsonl")
        options = {
            "cwd": str(self.root),
            "permission_mode": "acceptEdits" if mode == "managed" else mode,
            "system_prompt": instructions(self.root, mode == "managed"),
            "can_use_tool": self._make_can_use_tool(run),
            "pre_tool_use": self._make_pre_tool_use(run),
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
        self._append_record(
            run,
            {
                "meta": {
                    "version": 1,
                    "run_id": run_id,
                    "started_at": run.started_at,
                    "spec": spec,
                }
            },
        )
        # A _boot failure deliberately KEEPS the registration: the client exists
        # and may hold a live CLI subprocess, so shutdown() must still be able
        # to disconnect it. _pump reports the failure as an `error` event.
        prompt = _prompt_override if _prompt_override is not None else build_prompt(spec)
        self.submit(self._boot(run, prompt)).result(timeout=30)
        return run_id

    def resume(self, run_id: str) -> str:
        if run_id in self.runs and self.runs[run_id].status == "running":
            raise ValueError("a running run cannot be resumed")
        metadata = self._load_metadata(run_id)
        if metadata is None or not isinstance(metadata.get("spec"), dict):
            raise ValueError("run has no resumable metadata")
        spec = dict(metadata["spec"])
        spec["resumes_run_id"] = run_id
        original = build_prompt(spec)
        prompt = (
            f"Resume interrupted run {run_id}. Inspect the current workspace and any "
            "guild kernel state before continuing; do not repeat completed work. "
            f"Original request: {original}"
        )
        return self.start(spec, _prompt_override=prompt)

    async def _boot(self, run: Run, text: str):
        try:
            await run.client.connect()
            asyncio.create_task(self._pump(run))
            run.watchdog = asyncio.create_task(self._budget_watchdog(run))
            if text:
                await run.client.query(text)
        except Exception as exc:
            # _pump is what reports a client that dies mid-run -- but a connect()
            # that never succeeded means _pump was never started, so the run sat
            # registered as "running" forever with nothing on its stream to say
            # why. Re-raised, so POST /api/runs still answers 400 with the reason.
            self._publish(run, {
                "seq": run.state.next_seq(), "run_id": run.run_id,
                "ts": int(time.time() * 1000), "type": "error",
                "agent": None, "message": str(exc),
            })
            run.status = "finished"
            raise

    async def _pump(self, run: Run):
        try:
            async for message in run.client.receive_messages():
                # _as_dict once, not once per event -- and `raw` rides only the
                # FIRST event of the message. One SDK message can normalize to
                # several events (an Agent call is tool_use + agent_start; a
                # multi-block turn is one per block), and every line used to carry
                # its own full copy of the same message.
                raw = _as_dict(message)
                for index, event in enumerate(events_mod.normalize(raw, run.state)):
                    self._publish(run, event, raw=raw if index == 0 else None)
                reason = self._record_usage(run, raw)
                if reason:
                    await self._budget_interrupt(run, reason)
                    break
        except Exception as exc:  # never let a dead client kill the loop
            self._publish(run, {
                "seq": run.state.next_seq(), "run_id": run.run_id,
                "ts": int(time.time() * 1000), "type": "error",
                "agent": None, "message": str(exc),
            })
        finally:
            if run.watchdog is not None:
                run.watchdog.cancel()
            if run.status == "running":
                run.status = "finished"

    async def _budget_watchdog(self, run: Run):
        try:
            await asyncio.sleep(run.budget["max_seconds"])
            if run.status == "running":
                await self._budget_interrupt(run, "max_seconds")
        except asyncio.CancelledError:
            return

    def _record_usage(self, run: Run, raw: dict):
        kind = raw.get("type") if isinstance(raw, dict) else None
        if kind == "assistant":
            run.usage["turns"] += 1
            usage = raw.get("usage") or (raw.get("message") or {}).get("usage") or {}
            run.usage["tokens"] += _usage_tokens(usage)
            run.usage["cost_usd"] += _usage_cost(
                usage, raw.get("model") or (raw.get("message") or {}).get("model")
            )
        elif kind == "result":
            usage = raw.get("usage") or {}
            if run.usage["tokens"] == 0:
                run.usage["tokens"] = _usage_tokens(usage)
            actual = _number(raw.get("total_cost_usd"))
            if actual:
                run.usage["cost_usd"] = max(run.usage["cost_usd"], actual)
        return self._budget_reason(run)

    def _budget_reason(self, run: Run):
        elapsed = (int(time.time() * 1000) - run.started_at) / 1000
        if elapsed >= run.budget["max_seconds"]:
            return "max_seconds"
        if run.usage["tool_calls"] >= run.budget["max_tool_calls"]:
            return "max_tool_calls"
        if run.usage["turns"] >= run.budget["max_turns"]:
            return "max_turns"
        if run.usage["tokens"] >= run.budget["max_tokens"]:
            return "max_tokens"
        if run.usage["cost_usd"] >= run.budget["max_usd"]:
            return "max_usd"
        return None

    async def _budget_interrupt(self, run: Run, reason: str):
        if run.budget_reason is not None:
            return
        run.budget_reason = reason
        self._publish(
            run,
            {
                "seq": run.state.next_seq(),
                "run_id": run.run_id,
                "ts": int(time.time() * 1000),
                "type": "budget_exceeded",
                "agent": None,
                "reason": reason,
                "budget": run.budget,
                "usage": run.usage,
            },
        )
        await self._interrupt(run, reason=f"Runtime budget exceeded: {reason}.")
        run.status = "budget_exceeded"

    def _append_record(self, run: Run, record: dict):
        if run.trace_persistence_capped:
            return
        safe = _redact(record)
        line = (json.dumps(safe, separators=(",", ":")) + "\n").encode("utf-8")
        current_size = run.path.stat().st_size if run.path.exists() else 0
        if current_size + len(line) > self.max_trace_bytes:
            run.trace_persistence_capped = True
            return
        with run.path.open("ab") as handle:
            handle.write(line)

    def _publish(self, run: Run, event: dict, raw: dict | None = None):
        event = _redact(dict(event))
        event.setdefault("trace_id", run.run_id)
        event.setdefault(
            "span_id",
            event.get("tool_use_id") or event.get("lane_id") or f"event-{event.get('seq', 0)}",
        )
        event.setdefault("parent_span_id", event.get("lane_id"))
        with run.lock:
            run.buffer.append(event)
            subscribers = list(run.subscribers)
        self._append_record(
            run, {"event": event, "raw": raw if self.persist_raw else None}
        )
        for sub in subscribers:
            sub.put(event)

    def send(self, run_id: str, text: str):
        run = self.runs[run_id]
        self.submit(run.client.query(text)).result(timeout=30)

    def set_mode(self, run_id: str, mode: str | None = None, model: str | None = None):
        run = self.runs[run_id]
        if mode is not None:
            mode = _check_mode(mode)
            async def change_mode():
                await run.client.set_permission_mode("acceptEdits" if mode == "managed" else mode)
                run.mode = mode
            self.submit(change_mode()).result(timeout=10)
        if model is not None:
            self.submit(run.client.set_model(model)).result(timeout=10)

    def interrupt(self, run_id: str):
        run = self.runs[run_id]
        self.submit(self._interrupt(run)).result(timeout=15)

    async def _interrupt(self, run: Run, reason="Run interrupted by the user."):
        # Deny pending prompts FIRST — otherwise the loop stays parked.
        for prompt_id, future in list(run.pending.items()):
            if not future.done():
                future.set_result({"behavior": "deny",
                                   "message": reason})
            run.pending.pop(prompt_id, None)
        await run.client.interrupt()
        if run.budget_reason is None:
            run.status = "interrupted"

    # ---- approvals ---------------------------------------------------------

    @staticmethod
    def _agent_for_prompt(run: Run, context) -> tuple[str | None, str]:
        """Which agent's lane is blocked on this approval, and how sure we are.

        Returns `(agent, confidence)` where confidence is `"exact"` for a fact and
        `"guess"` for the one heuristic below. The browser cannot tell the two
        apart on its own, and it marks a card either way -- so the difference has
        to travel with the event.

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
            return lane, "exact"
        if _getattr(context, "agent_id", None) is None:
            return None, "exact"
        return run.state.newest_open_lane(), "guess"

    def _make_pre_tool_use(self, run: Run):
        """The PreToolUse hook: the only layer that sees every tool call.

        Two jobs, and deliberately no more. It forces the tools in
        ASK_ALWAYS_TOOLS back through `can_use_tool` -- which is what emits the
        `prompt` event the browser already knows how to answer, so the whole
        approval path is reused rather than duplicated -- and it publishes a
        `tool_gate` event for EVERY call recording whether the browser was asked,
        so a transcript stops implying that every call was approved.

        Returning `{}` is not "allow": it is no decision at all, leaving
        permission rules and the run's mode to decide exactly as before.
        """
        async def pre_tool_use(payload, tool_use_id, context):
            data = payload if isinstance(payload, dict) else {}
            tool_name = data.get("tool_name") or ""
            tool_input = data.get("tool_input")
            # The hook's own tool_use_id is authoritative; the positional one is
            # the SDK's convenience copy and may be None.
            call_id = data.get("tool_use_id") or tool_use_id or ""
            reason = self._budget_reason(run)
            if reason:
                asyncio.create_task(self._budget_interrupt(run, reason))
                return {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Runtime budget exceeded: {reason}.",
                }}
            run.usage["tool_calls"] += 1
            # An unparseable signature yields None, which is never in the
            # remembered set -- so a Bash call whose input we cannot read is
            # asked about rather than waved through.
            remembered = _signature(tool_name, tool_input) in run.remembered
            routine = run.mode == "managed" and tool_name == "Bash" and routine_command(tool_input)
            ask = tool_name in ASK_ALWAYS_TOOLS and not remembered and not routine
            if run.mode == "managed" and tool_name.startswith("mcp__"):
                ask = True
            if run.mode == "managed" and tool_name in ("Edit", "Write", "NotebookEdit"):
                edit_input = tool_input if isinstance(tool_input, dict) else {}
                path = edit_input.get("file_path") or edit_input.get("notebook_path")
                candidate = self.root / path if isinstance(path, str) else None
                if candidate is None or not candidate.resolve().is_relative_to(self.root.resolve()):
                    ask = True

            lane = run.state.lane_for_tool_use(call_id)
            self._publish(run, {
                "seq": run.state.next_seq(),
                "run_id": run.run_id,
                "ts": int(time.time() * 1000),
                "type": "tool_gate",
                "agent": None if lane is events_mod.MISSING else lane,
                "tool": tool_name,
                "tool_use_id": call_id,
                "asked": ask,
            })

            if routine:
                return {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "allow",
                    "permissionDecisionReason": "Independent mode: standard project validation command.",
                }}
            if not ask:
                return {}
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Independent mode requires review for this action."
                    if run.mode == "managed" else ASK_REASON
                ),
            }}

        return pre_tool_use

    def _make_can_use_tool(self, run: Run):
        async def can_use_tool(tool_name, input_data, context):
            if run.mode == "managed" and tool_name == "Bash" and routine_command(input_data):
                return {"behavior": "allow", "updated_input": input_data}
            prompt_id = f"p_{uuid.uuid4().hex[:10]}"
            agent, confidence = self._agent_for_prompt(run, context)
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
                "agent_confidence": confidence,
                "prompt_id": prompt_id,
                "tool": tool_name,
                "input": input_data,
                "is_question": tool_name == "AskUserQuestion",
                "suggestions": suggestions,
            })
            decision = await future
            run.pending.pop(prompt_id, None)
            # "Allow always" has to mean something for the tools the hook forces:
            # the SDK persists a localSettings rule, but a hook `ask` outranks
            # allow rules, so only this stops the same command being asked again.
            if decision.get("remember"):
                signature = _signature(tool_name, input_data)
                if signature is not None:
                    run.remembered.add(signature)
            self._publish(run, {
                "seq": run.state.next_seq(),
                "run_id": run.run_id,
                "ts": int(time.time() * 1000),
                "type": "prompt_resolved",
                "agent": agent,
                "agent_confidence": confidence,
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

    def _load_metadata(self, run_id: str):
        path = self.runs_dir / f"{run_id}.jsonl"
        if not path.is_file():
            return None
        try:
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    record = json.loads(line)
                    if isinstance(record.get("meta"), dict):
                        return record["meta"]
        except (OSError, ValueError):
            return None
        return None

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
                "budget": run.budget,
                "usage": dict(run.usage),
            })
            seen.add(run_id)

        # 2. Disk-derived runs for runs this process does not own.
        # A run this process does not own must report "interrupted" because
        # the SDK child process died with whatever process started it.
        for path in sorted(self.runs_dir.glob("run_*.jsonl")):
            run_id = path.stem
            if run_id not in seen:
                metadata = self._load_metadata(run_id) or {}
                rows.append({
                    "run_id": run_id,
                    "status": "interrupted",
                    "spec": metadata.get("spec"),
                    "started_at": metadata.get("started_at") or int(path.stat().st_mtime * 1000),
                    "budget": (metadata.get("spec") or {}).get("budget"),
                    "usage": None,
                })
                seen.add(run_id)

        # Stable, deterministic ordering by run_id.
        rows.sort(key=lambda r: r["run_id"])
        return rows


def _signature(tool_name: str, tool_input) -> tuple[str, str] | None:
    """What an "Allow always" answer covers: one tool, one exact command string.

    Only for the tools the hook forces -- nothing else is overridden, so nothing
    else needs remembering. Exact match, never a pattern: a signature scheme
    cleverer than the user's expectation is a way to auto-approve something they
    did not mean to approve.
    """
    if tool_name not in ASK_ALWAYS_TOOLS or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None
    return (tool_name, command)


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
            "model": _getattr(message, "model"),
            "usage": _getattr(message, "usage") or {},
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
