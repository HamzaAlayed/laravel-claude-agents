import asyncio
import dataclasses
import pathlib
import sys
import tempfile
import threading
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import engine  # noqa: E402
import events  # noqa: E402


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

    def test_concurrent_answers_first_wins_race_closed(self):
        # Guards the fix to RunManager.answer: two callers racing to resolve
        # the SAME prompt_id must not both observe success. The buggy version
        # checked future.done() on the calling thread, then scheduled the
        # actual set via call_soon_threadsafe -- a window where two callers
        # can both pass the check before either set lands. Two real threads,
        # released together by a Barrier, exercise that window directly.
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.ask()
        event = self.drain(run_id, ["prompt"])[0]
        prompt_id = event["prompt_id"]

        results = [None, None]
        barrier = threading.Barrier(2)

        def call(index, payload):
            barrier.wait(timeout=5)
            results[index] = self.mgr.answer(run_id, prompt_id, payload)

        t1 = threading.Thread(target=call, args=(0, {"behavior": "allow"}))
        t2 = threading.Thread(target=call, args=(1, {"behavior": "deny", "message": "lost"}))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())
        self.assertEqual(sorted(results), [False, True])
        # Whichever answer landed, the SDK-side await must resolve exactly
        # once so the run doesn't stay parked.
        pending.result(timeout=5)

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


# ---------------------------------------------------------------------------
# Stand-ins for the real claude_agent_sdk message/content-block dataclasses.
#
# These are NOT imported from the SDK -- engine.py is required to stay free of
# `import claude_agent_sdk` (that is the guardrail this module is unit
# testable against), and the whole point of this fixture set is to stop
# pinning the CLI's stream-json wire format as if it were the SDK's shape.
# The 62 pre-existing tests in this file and in test_events.py all pass dicts
# shaped like the wire format -- they were passing while the console was
# completely broken, because `_as_dict` used to dataclasses.asdict() these
# objects and lose the `type` discriminator entirely. Class *names* and field
# *names* here are copied verbatim from introspecting the installed SDK, so
# that `_as_dict`'s `type(obj).__name__` dispatch is exercised for real.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SystemMessage:
    subtype: str
    data: dict = None


@dataclasses.dataclass
class AssistantMessage:
    content: list
    model: str = None
    parent_tool_use_id: str = None
    error: object = None
    usage: dict = None
    message_id: str = None
    stop_reason: str = None
    session_id: str = None
    uuid: str = None


@dataclasses.dataclass
class UserMessage:
    content: list
    uuid: str = None
    parent_tool_use_id: str = None
    tool_use_result: object = None


@dataclasses.dataclass
class ResultMessage:
    subtype: str = None
    duration_ms: int = None
    duration_api_ms: int = None
    is_error: bool = False
    num_turns: int = None
    session_id: str = None
    stop_reason: str = None
    total_cost_usd: float = None
    usage: dict = None
    result: str = None
    structured_output: object = None
    model_usage: object = None
    permission_denials: object = None
    deferred_tool_use: object = None
    errors: object = None
    api_error_status: object = None
    uuid: str = None
    terminal_reason: str = None


@dataclasses.dataclass
class HookEventMessage:
    subtype: str = None
    data: dict = None
    hook_event_name: str = None
    session_id: str = None
    uuid: str = None


@dataclasses.dataclass
class RateLimitEvent:
    rate_limit_info: dict = None
    uuid: str = None
    session_id: str = None


@dataclasses.dataclass
class TextBlock:
    text: str


@dataclasses.dataclass
class ThinkingBlock:
    thinking: str
    signature: str = None


@dataclasses.dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict = None


@dataclasses.dataclass
class ToolResultBlock:
    tool_use_id: str
    content: object = None
    is_error: bool = False


class TestAsDictTranslatesSdkMessages(unittest.TestCase):
    """_as_dict() is the seam between the real Agent SDK's typed dataclasses
    and events.normalize()'s wire-format reducer. These push SDK-shaped
    stand-in objects through _as_dict() and then normalize(), the same two
    calls engine._pump makes on every message from run.client.receive_messages().
    """

    def setUp(self):
        self.state = events.RunState("run_1")

    def emit(self, message):
        return events.normalize(engine._as_dict(message), self.state)

    def test_system_init_flattens_data_into_an_init_event(self):
        msg = SystemMessage(
            subtype="init",
            data={
                "plugins": [{"name": "laravel-team"}],
                "capabilities": ["interrupt_receipt_v1"],
                "model": "claude-sonnet-5",
                "cwd": "/repo",
                "permissionMode": "default",
            },
        )
        out = self.emit(msg)
        self.assertEqual([e["type"] for e in out], ["init"])
        self.assertIn("laravel-team", out[0]["plugins"])
        self.assertIn("interrupt_receipt_v1", out[0]["capabilities"])

    def test_assistant_text_block_becomes_a_text_event(self):
        msg = AssistantMessage(content=[TextBlock(text="hi")], parent_tool_use_id=None)
        out = self.emit(msg)
        self.assertEqual([e["type"] for e in out], ["text"])
        self.assertEqual(out[0]["text"], "hi")

    def test_assistant_tool_use_spawns_agent_start(self):
        msg = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tu_1",
                    name="Agent",
                    input={
                        "subagent_type": "laravel-team:backend-developer",
                        "description": "work",
                    },
                )
            ],
            parent_tool_use_id=None,
        )
        out = self.emit(msg)
        self.assertEqual([e["type"] for e in out], ["tool_use", "agent_start"])
        start = out[-1]
        self.assertEqual(start["type"], "agent_start")
        self.assertEqual(start["agent"], "backend-developer")

    def test_user_tool_result_closes_the_spawned_lane(self):
        spawn = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tu_1",
                    name="Agent",
                    input={
                        "subagent_type": "laravel-team:backend-developer",
                        "description": "work",
                    },
                )
            ],
            parent_tool_use_id=None,
        )
        self.emit(spawn)

        result = UserMessage(
            content=[ToolResultBlock(tool_use_id="tu_1", content="ok", is_error=False)],
            parent_tool_use_id=None,
        )
        out = self.emit(result)
        self.assertEqual([e["type"] for e in out], ["tool_result", "agent_end"])
        self.assertEqual(out[-1]["agent"], "backend-developer")

    def test_result_message_carries_the_final_answer(self):
        msg = ResultMessage(
            subtype="success",
            result="READY",
            duration_ms=10,
            total_cost_usd=0.01,
            usage={},
        )
        out = self.emit(msg)
        self.assertEqual([e["type"] for e in out], ["result"])
        self.assertEqual(out[0]["result"], "READY")

    def test_hook_event_message_yields_no_events_and_does_not_raise(self):
        msg = HookEventMessage(subtype="pre_tool_use", data={}, hook_event_name="PreToolUse")
        self.assertEqual(self.emit(msg), [])

    def test_rate_limit_event_yields_no_events_and_does_not_raise(self):
        msg = RateLimitEvent(rate_limit_info={"status": "allowed"})
        self.assertEqual(self.emit(msg), [])

    def test_plain_dict_wire_format_still_works_unchanged(self):
        # Regression guard: the unit tests (and the fixture-driven
        # test_events.py suite) feed events.normalize() dicts directly, and
        # that path must be untouched by the SDK-object translation.
        raw = {
            "type": "assistant",
            "parent_tool_use_id": None,
            "message": {"role": "assistant", "content": [{"type": "text", "text": "yo"}]},
        }
        self.assertEqual(engine._as_dict(raw), raw)
        out = self.emit(raw)
        self.assertEqual([e["type"] for e in out], ["text"])
        self.assertEqual(out[0]["text"], "yo")

    def test_unknown_object_class_does_not_raise(self):
        class SomethingTheSdkAddedLater:
            pass

        self.assertEqual(engine._as_dict(SomethingTheSdkAddedLater()), {})
        self.assertEqual(self.emit(SomethingTheSdkAddedLater()), [])


if __name__ == "__main__":
    unittest.main()
