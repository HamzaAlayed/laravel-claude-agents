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
