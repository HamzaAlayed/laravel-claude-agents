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

    def test_a_rejected_client_option_leaves_no_zombie_run(self):
        """The run used to be registered BEFORE client_factory ran, so a factory
        failure (e.g. the SDK rejecting `model`) left an entry with client=None
        and status="running" forever: listed as live by GET /api/runs, and an
        AttributeError on every later /message, /mode or /interrupt."""
        def refuse(options):
            raise RuntimeError(f"model {options.get('model')!r} is not supported")

        self.mgr.client_factory = refuse
        with self.assertRaises(RuntimeError) as ctx:
            self.mgr.start({"kind": "prompt", "target": "", "text": "x", "model": "nope"})
        self.assertIn("nope", str(ctx.exception))
        self.assertEqual(self.mgr.runs, {})
        self.assertEqual(self.mgr.list_runs(), [])

    def test_is_live_is_true_only_for_runs_this_process_owns(self):
        # is_live is what the SSE route checks before it promises a stream --
        # subscribe() can only serve runs held in memory.
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.assertTrue(self.mgr.is_live(run_id))
        self.assertFalse(self.mgr.is_live("run_from_a_previous_process"))


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


class TestPromptAttribution(EngineTestCase):
    """engine.py used to hardcode `"agent": None` on prompt/prompt_resolved, so
    Board.tsx had to GUESS the parked card as "the first running lane" -- with
    several agents running it marked the wrong one, and the approval bar could
    not name who was blocked."""

    def push_assistant(self, blocks, parent=None):
        self.run_coro(self.clients[0].push(
            {"type": "assistant", "parent_tool_use_id": parent,
             "message": {"role": "assistant", "content": blocks}}
        ))

    def spawn(self, tool_use_id, slug):
        self.push_assistant([{"type": "tool_use", "id": tool_use_id, "name": "Agent",
                              "input": {"subagent_type": slug, "description": "work"}}])

    def ask(self, context, tool_name="Bash", tool_input=None):
        return self.mgr.submit(self.clients[0].can_use_tool(
            tool_name, tool_input or {"command": "ls"}, context))

    def settle(self, run_id, pending, expected_types):
        """Read the stream up to and including the prompt, then release the
        callback so no future is left dangling at shutdown."""
        events = self.drain(run_id, expected_types)
        prompt = events[-1]
        self.mgr.answer(run_id, prompt["prompt_id"], {"behavior": "allow"})
        pending.result(timeout=5)
        return prompt

    def test_prompt_names_the_subagent_whose_call_it_is(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "backend-developer")
        self.push_assistant(
            [{"type": "tool_use", "id": "tb1", "name": "Bash", "input": {"command": "ls"}}],
            parent="t1",
        )
        # Drain first: this guarantees _pump has normalized both messages, so the
        # exact tool_use_id -> lane path is what answers, not the fallback.
        self.drain(run_id, ["tool_use", "agent_start", "tool_use"])
        pending = self.ask(_FakeContext(tool_use_id="tb1", agent_id="agent_7"))
        prompt = self.settle(run_id, pending,
                             ["tool_use", "agent_start", "tool_use", "prompt"])
        self.assertEqual(prompt["agent"], "backend-developer")

    def test_prompt_from_the_main_thread_is_not_blamed_on_an_open_lane(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "backend-developer")
        self.push_assistant([{"type": "tool_use", "id": "tm1", "name": "Write", "input": {}}])
        self.drain(run_id, ["tool_use", "agent_start", "tool_use"])
        pending = self.ask(_FakeContext(tool_use_id="tm1", agent_id=None), tool_name="Write")
        prompt = self.settle(run_id, pending,
                             ["tool_use", "agent_start", "tool_use", "prompt"])
        self.assertIsNone(prompt["agent"])

    def test_unseen_subagent_call_falls_back_to_the_newest_open_lane(self):
        # The permission request can overtake its own assistant message in the
        # transport. agent_id proves a subagent asked; the most recently started
        # open lane is the best available attribution.
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "security-engineer")
        self.spawn("t2", "performance-engineer")
        self.drain(run_id, ["tool_use", "agent_start", "tool_use", "agent_start"])
        pending = self.ask(_FakeContext(tool_use_id="never-seen", agent_id="agent_9"))
        prompt = self.settle(
            run_id, pending,
            ["tool_use", "agent_start", "tool_use", "agent_start", "prompt"],
        )
        self.assertEqual(prompt["agent"], "performance-engineer")

    def test_unseen_main_thread_call_stays_unattributed(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "security-engineer")
        self.drain(run_id, ["tool_use", "agent_start"])
        pending = self.ask(_FakeContext(tool_use_id="never-seen", agent_id=None))
        prompt = self.settle(run_id, pending, ["tool_use", "agent_start", "prompt"])
        self.assertIsNone(prompt["agent"])

    def test_a_closed_lane_is_no_longer_a_fallback_candidate(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "security-engineer")
        self.run_coro(self.clients[0].push(
            {"type": "user", "parent_tool_use_id": None,
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                      "is_error": False, "content": "done"}]}}
        ))
        self.drain(run_id, ["tool_use", "agent_start", "tool_result", "agent_end"])
        pending = self.ask(_FakeContext(tool_use_id="never-seen", agent_id="agent_9"))
        prompt = self.settle(
            run_id, pending,
            ["tool_use", "agent_start", "tool_result", "agent_end", "prompt"],
        )
        self.assertIsNone(prompt["agent"])

    def test_prompt_resolved_carries_the_same_agent(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "qa-engineer")
        self.push_assistant(
            [{"type": "tool_use", "id": "tb1", "name": "Bash", "input": {"command": "ls"}}],
            parent="t1",
        )
        self.drain(run_id, ["tool_use", "agent_start", "tool_use"])
        pending = self.ask(_FakeContext(tool_use_id="tb1", agent_id="agent_7"))
        self.settle(run_id, pending, ["tool_use", "agent_start", "tool_use", "prompt"])
        events = self.drain(
            run_id,
            ["tool_use", "agent_start", "tool_use", "prompt", "prompt_resolved"],
        )
        self.assertEqual(events[-1]["agent"], "qa-engineer")

    def test_two_prompts_are_attributed_independently(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.spawn("t1", "security-engineer")
        self.spawn("t2", "performance-engineer")
        self.push_assistant(
            [{"type": "tool_use", "id": "ta", "name": "Bash", "input": {}}], parent="t1")
        self.push_assistant(
            [{"type": "tool_use", "id": "tb", "name": "Read", "input": {}}], parent="t2")
        prelude = ["tool_use", "agent_start", "tool_use", "agent_start",
                   "tool_use", "tool_use"]
        self.drain(run_id, prelude)
        first = self.ask(_FakeContext(tool_use_id="ta", agent_id="a1"))
        second = self.ask(_FakeContext(tool_use_id="tb", agent_id="a2"), tool_name="Read")
        events = self.drain(run_id, prelude + ["prompt", "prompt"])
        prompts = {e["agent"]: e["prompt_id"] for e in events[-2:]}
        self.assertEqual(set(prompts), {"security-engineer", "performance-engineer"})
        for prompt_id in prompts.values():
            self.mgr.answer(run_id, prompt_id, {"behavior": "allow"})
        first.result(timeout=5)
        second.result(timeout=5)


class TestPreToolUseGate(EngineTestCase):
    """can_use_tool is NOT the first gate: Claude Code auto-allows read-only Bash
    before the callback runs, so no `prompt` event was emitted and the browser was
    never asked. `echo hello` just ran. No SDK option or settings key disables
    that -- a PreToolUse hook is the only layer that sees every call, which the
    SDK's own shadowing warning says in as many words.

    The hook forces Bash back through can_use_tool and reports every other call
    as having run unasked.
    """

    def gate(self, tool_name="Bash", tool_input=None, tool_use_id="tu_1"):
        """Invoke the registered PreToolUse hook the way the SDK would."""
        hook = self.clients[0].options["pre_tool_use"]
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input if tool_input is not None else {"command": "ls"},
            "tool_use_id": tool_use_id,
        }
        return self.run_coro(hook(payload, tool_use_id, _FakeHookContext()))

    @staticmethod
    def decision(output):
        return (output or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def test_bash_is_forced_back_through_the_browser(self):
        self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        output = self.gate("Bash", {"command": "echo hello"})
        self.assertEqual(self.decision(output), "ask")

    def test_the_ask_carries_a_reason_for_the_sheet_to_show(self):
        # The SDK forwards permissionDecisionReason to
        # ToolPermissionContext.decision_reason, i.e. into the same can_use_tool
        # call the console turns into a `prompt` event.
        self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        output = self.gate("Bash", {"command": "echo hello"})
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Bash", reason)

    def test_other_tools_fall_through_untouched(self):
        # Read/Grep/Glob auto-allowing is not a safety story worth parking a run
        # for. No decision at all: permission rules and mode decide as before.
        self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        for tool in ("Read", "Grep", "Glob", "Edit", "AskUserQuestion"):
            self.assertIsNone(self.decision(self.gate(tool, {})), tool)

    def test_every_call_reports_whether_it_was_asked_about(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.gate("Bash", {"command": "ls"}, tool_use_id="tu_bash")
        self.gate("Read", {"file_path": "/x"}, tool_use_id="tu_read")
        events = self.drain(run_id, ["tool_gate", "tool_gate"])
        self.assertEqual(
            [(e["tool"], e["tool_use_id"], e["asked"]) for e in events],
            [("Bash", "tu_bash", True), ("Read", "tu_read", False)],
        )

    def test_the_gate_event_names_the_lane_that_made_the_call(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.run_coro(self.clients[0].push(
            {"type": "assistant", "parent_tool_use_id": None,
             "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Agent",
                                      "input": {"subagent_type": "qa-engineer",
                                                "description": "work"}}]}}
        ))
        self.run_coro(self.clients[0].push(
            {"type": "assistant", "parent_tool_use_id": "t1",
             "message": {"content": [{"type": "tool_use", "id": "tb1", "name": "Bash",
                                      "input": {"command": "ls"}}]}}
        ))
        self.drain(run_id, ["tool_use", "agent_start", "tool_use"])
        self.gate("Bash", {"command": "ls"}, tool_use_id="tb1")
        events = self.drain(
            run_id, ["tool_use", "agent_start", "tool_use", "tool_gate"])
        self.assertEqual(events[-1]["agent"], "qa-engineer")

    def test_allow_always_stops_the_hook_asking_again_this_run(self):
        """A hook `ask` outranks allow rules, so without this "Allow always"
        would persist a settings rule and then be overridden on the very next
        call -- a button that quietly lies."""
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.mgr.submit(self.clients[0].can_use_tool(
            "Bash", {"command": "git status"}, _FakeContext(tool_use_id="tb1")))
        prompt = self.drain(run_id, ["prompt"])[0]
        self.mgr.answer(run_id, prompt["prompt_id"],
                        {"behavior": "allow", "remember": True})
        pending.result(timeout=5)

        self.assertIsNone(self.decision(self.gate("Bash", {"command": "git status"})))

    def test_a_different_command_is_still_asked_about(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.mgr.submit(self.clients[0].can_use_tool(
            "Bash", {"command": "git status"}, _FakeContext(tool_use_id="tb1")))
        prompt = self.drain(run_id, ["prompt"])[0]
        self.mgr.answer(run_id, prompt["prompt_id"],
                        {"behavior": "allow", "remember": True})
        pending.result(timeout=5)

        self.assertEqual(self.decision(self.gate("Bash", {"command": "rm -rf /"})), "ask")

    def test_allow_once_does_not_stop_the_next_ask(self):
        run_id = self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        pending = self.mgr.submit(self.clients[0].can_use_tool(
            "Bash", {"command": "git status"}, _FakeContext(tool_use_id="tb1")))
        prompt = self.drain(run_id, ["prompt"])[0]
        self.mgr.answer(run_id, prompt["prompt_id"], {"behavior": "allow"})
        pending.result(timeout=5)

        self.assertEqual(self.decision(self.gate("Bash", {"command": "git status"})), "ask")

    def test_a_malformed_hook_payload_never_breaks_the_run(self):
        # This sits between a third-party library and the whole event pipeline.
        # An odd payload must degrade, not kill the agent loop.
        self.mgr.start({"kind": "prompt", "target": "", "text": "x"})
        self.assertIsNone(self.decision(self.gate(None, None, tool_use_id=None)))


class _FakeHookContext:
    """Stands in for the SDK's HookContext (a placeholder type carrying an abort
    signal; the console reads nothing off it)."""


class _FakeContext:
    """Stands in for the SDK's ToolPermissionContext. `tool_use_id` (the id of
    the call being asked about) and `agent_id` (None on the main thread) are
    real fields on it, copied from the installed SDK's types.py."""

    def __init__(self, tool_use_id=None, agent_id=None):
        self.suggestions = []
        self.tool_use_id = tool_use_id
        self.agent_id = agent_id


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
