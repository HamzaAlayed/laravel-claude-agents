import asyncio
import pathlib
import sys
import tempfile
import threading
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


if __name__ == "__main__":
    unittest.main()
