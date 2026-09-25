import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class LoopPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        delivery = kernel.plan(
            root=self.root,
            name="tag",
            done_when="tag endpoint is complete",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["tag endpoint is tested"],
                    [],
                    owned_paths=["app/Http"],
                )
            ],
        )
        kernel.claim_stage(self.root, "tag", "backend")
        return delivery

    @staticmethod
    def signature(tool, value):
        return kernel.tool_call_signature(tool, {"value": value})

    def meter(self, index, tool="Read", value="same"):
        return kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id=f"tool:{index}",
            tool_name=tool,
            signature=self.signature(tool, value),
        )

    def test_third_identical_call_stops_before_execution_and_is_auditable(self):
        self.plan()
        self.meter(1)
        self.meter(2)
        with self.assertRaisesRegex(kernel.PlanError, "unproductive 1-step"):
            self.meter(3)

        delivery = kernel.load(self.root, "tag")
        stage = delivery.stages[0]
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(stage.status, "failed")
        self.assertEqual(stage.usage["tool_calls"], 2)
        self.assertEqual(stage.loop_detected_reason, "1-step-cycle-x3")
        self.assertEqual(len(stage.loop_history), 3)
        self.assertEqual(len(delivery.loop_events), 1)
        event = delivery.loop_events[0]
        self.assertEqual(event["cycle_length"], 1)
        self.assertEqual(event["repeats"], 3)
        self.assertEqual(event["tools"], ["Read"])
        self.assertRegex(event["fingerprint"], r"^[0-9a-f]{16}$")
        self.assertIn("loop:1-step-cycle-x3", kernel.board_line(delivery))
        self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")
        view = (self.root / "docs/delivery/tag/loops.md").read_text()
        self.assertIn("1-step cycle repeated 3 times", view)
        self.assertIn("raw tool input is not persisted", view)

    def test_two_step_cycle_is_detected_on_its_third_repetition(self):
        self.plan()
        sequence = [
            ("Read", "controller"),
            ("Bash", "test"),
            ("Read", "controller"),
            ("Bash", "test"),
            ("Read", "controller"),
        ]
        for index, (tool, value) in enumerate(sequence, start=1):
            self.meter(index, tool, value)
        with self.assertRaisesRegex(kernel.PlanError, "unproductive 2-step"):
            self.meter(6, "Bash", "test")
        event = kernel.loop_rows(self.root, "tag")[0]
        self.assertEqual(event["tools"], ["Read", "Bash"])

    def test_a_changed_call_breaks_the_repeated_tail(self):
        self.plan()
        for index, value in enumerate(["same", "same", "changed", "same", "same"], 1):
            self.meter(index, value=value)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.status, "running")
        self.assertEqual(delivery.loop_events, [])
        self.assertEqual(delivery.stages[0].usage["tool_calls"], 5)

    def test_duplicate_hook_event_is_idempotent_for_loop_counting(self):
        self.plan()
        signature = self.signature("Read", "same")
        first = kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id="tool:one",
            tool_name="Read",
            signature=signature,
        )
        duplicate = kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id="tool:one",
            tool_name="Read",
            signature=signature,
        )
        self.assertEqual(first.usage["tool_calls"], 1)
        self.assertEqual(duplicate.usage["tool_calls"], 1)
        self.meter(2)
        with self.assertRaisesRegex(kernel.PlanError, "unproductive"):
            self.meter(3)

    def test_cycles_longer_than_policy_window_are_not_guessed(self):
        self.plan()
        pattern = ["a", "b", "c", "d", "e"]
        for index, value in enumerate(pattern * 3, start=1):
            self.meter(index, value=value)
        self.assertEqual(kernel.load(self.root, "tag").status, "running")

    def test_history_is_bounded_and_raw_sensitive_input_never_persists(self):
        self.plan()
        secret = "sk-live-do-not-store"
        digest = kernel.tool_call_signature("Read", {"token": secret})
        self.assertNotIn(secret, digest)
        kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id="tool:secret",
            tool_name="Read",
            signature=digest,
        )
        for index in range(1, 30):
            self.meter(f"unique-{index}", value=f"path-{index}")
        state = (self.root / "docs/delivery/tag/kernel.json").read_text()
        self.assertNotIn(secret, state)
        self.assertEqual(len(kernel.load(self.root, "tag").stages[0].loop_history), 24)

    def test_new_claim_resets_the_detection_window(self):
        self.plan()
        delivery = kernel.load(self.root, "tag")
        stage = delivery.stages[0]
        stage.status = "queued"
        stage.claimed_at = ""
        stage.claim_usage = {}
        stage.loop_history = [
            {"signature": self.signature("Read", "same"), "tool": "Read", "at": "x"}
        ] * 2
        kernel.save(self.root, delivery)

        claimed = kernel.claim_stage(self.root, "tag", "backend")
        self.assertEqual(claimed.loop_history, [])
        self.meter(1)
        self.meter(2)
        self.assertEqual(kernel.load(self.root, "tag").status, "running")

    def test_legacy_state_loads_empty_loop_fields(self):
        self.plan()
        path = self.root / "docs/delivery/tag/kernel.json"
        payload = json.loads(path.read_text())
        payload.pop("loop_events")
        payload["stages"][0].pop("loop_history")
        payload["stages"][0].pop("loop_detected_reason")
        path.write_text(json.dumps(payload))

        loaded = kernel.load(self.root, "tag")
        self.assertEqual(loaded.loop_events, [])
        self.assertEqual(loaded.stages[0].loop_history, [])
        self.assertEqual(loaded.stages[0].loop_detected_reason, "")

    def test_loop_cli_lists_durable_events(self):
        self.plan()
        self.meter(1)
        self.meter(2)
        with self.assertRaises(kernel.PlanError):
            self.meter(3)
        cli = REPO / "scripts" / "guild-kernel" / "guild.py"
        result = subprocess.run(
            [
                sys.executable,
                str(cli),
                "loop",
                "list",
                "--root",
                str(self.root),
                "--name",
                "tag",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)[0]["stage"], "backend")


class LoopHookIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.hook = REPO / "scripts" / "enforce-kernel-budgets.sh"
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="tag endpoint is complete",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["tag endpoint is tested"],
                    [],
                    owned_paths=["app/Http"],
                )
            ],
        )
        kernel.claim_stage(self.root, "tag", "backend")

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, event_id):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_use_id": event_id,
            "agent_type": "laravel-team:backend-developer",
            "tool_name": "Bash",
            "tool_input": {"command": "php artisan test --filter=TagTest"},
        }
        return subprocess.run(
            [str(self.hook)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
        )

    def test_hook_blocks_the_third_identical_tool_call(self):
        self.assertEqual(self.invoke("one").returncode, 0)
        self.assertEqual(self.invoke("two").returncode, 0)
        stopped = self.invoke("three")
        self.assertEqual(stopped.returncode, 2)
        self.assertIn("unproductive 1-step tool cycle", stopped.stderr)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(delivery.stages[0].usage["tool_calls"], 2)


if __name__ == "__main__":
    unittest.main()
