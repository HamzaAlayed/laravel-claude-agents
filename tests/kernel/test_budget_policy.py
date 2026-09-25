import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class BudgetPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, budget=None):
        return kernel.plan(
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
                    budget=budget or {},
                )
            ],
        )

    def claim(self):
        return kernel.claim_stage(self.root, "tag", "backend")

    def test_defaults_are_snapshotted_and_overrides_respect_hard_ceilings(self):
        delivery = self.plan({"max_seconds": 60, "max_tool_calls": 3})
        stage = delivery.stages[0]
        self.assertEqual(stage.budget["max_seconds"], 60)
        self.assertEqual(stage.budget["max_tool_calls"], 3)
        self.assertEqual(stage.budget["max_tokens"], 5_000_000)
        self.assertEqual(stage.usage, kernel._EMPTY_USAGE)

        other = pathlib.Path(self.tmp.name) / "other"
        with self.assertRaisesRegex(kernel.PlanError, "exceeds hard ceiling"):
            kernel.plan(
                root=other,
                name="too-large",
                done_when="x",
                stages=[
                    kernel.StageSpec(
                        "backend",
                        "backend-developer",
                        "writer",
                        ["x"],
                        [],
                        owned_paths=["app"],
                        budget={"max_tool_calls": 1001},
                    )
                ],
            )

    def test_pre_tool_meter_is_idempotent_and_stops_the_next_call(self):
        self.plan({"max_tool_calls": 1})
        self.claim()
        first = kernel.meter_tool_call(
            self.root, "backend-developer", event_id="tool:one"
        )
        self.assertEqual(first.usage["tool_calls"], 1)
        duplicate = kernel.meter_tool_call(
            self.root, "backend-developer", event_id="tool:one"
        )
        self.assertEqual(duplicate.usage["tool_calls"], 1)

        with self.assertRaisesRegex(kernel.PlanError, "max_tool_calls"):
            kernel.meter_tool_call(
                self.root, "backend-developer", event_id="tool:two"
            )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.status, "budget_exceeded")
        self.assertEqual(delivery.stages[0].status, "budget_exceeded")
        self.assertEqual(
            delivery.stages[0].budget_exceeded_reason, "max_tool_calls"
        )
        self.assertIn("backend ⛔", kernel.board_line(delivery))
        self.assertEqual(kernel.ready_stages(self.root, "tag"), [])

    def test_elapsed_time_is_checked_before_a_tool_runs(self):
        self.plan({"max_seconds": 10})
        self.claim()
        delivery = kernel.load(self.root, "tag")
        start = datetime(2026, 9, 25, tzinfo=timezone.utc)
        delivery.stages[0].claimed_at = start.isoformat()
        kernel.save(self.root, delivery)

        with self.assertRaisesRegex(kernel.PlanError, "max_seconds"):
            kernel.meter_tool_call(
                self.root,
                "backend-developer",
                event_id="late",
                now=start + timedelta(seconds=10),
            )
        self.assertEqual(
            kernel.load(self.root, "tag").stages[0].usage["seconds"], 10.0
        )

    def test_completion_usage_is_persisted_and_overage_stops_delivery(self):
        self.plan({"max_tokens": 100, "max_turns": 2, "max_usd": 1.0})
        self.claim()
        with self.assertRaisesRegex(kernel.PlanError, "max_tokens"):
            kernel.record_stage_usage(
                self.root,
                "backend-developer",
                {
                    "seconds": 2.0,
                    "tool_calls": 1,
                    "turns": 1,
                    "tokens": 101,
                    "cost_usd": 0.01,
                },
                event_id="completion:one",
            )
        stage = kernel.load(self.root, "tag").stages[0]
        self.assertEqual(stage.usage["tokens"], 101)
        self.assertEqual(stage.budget_exceeded_reason, "max_tokens")

    def test_claimed_stage_cannot_report_without_completion_telemetry(self):
        self.plan()
        self.claim()
        artifact = self.root / "app/Http/TagController.php"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("<?php\n")
        report = self.root / "docs/delivery/tag/stages/backend-developer.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "STATUS: done\n"
            "DID: app/Http/TagController.php\n"
            'VERIFIED: {"runner":"file-exists","args":["app/Http/TagController.php"]}\n'
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaisesRegex(
            kernel.ReportError, "requires budget telemetry before report"
        ):
            kernel.report(self.root, "tag", report, runner=None)

    def test_budget_cli_lists_and_records_usage(self):
        self.plan()
        self.claim()
        cli = REPO / "scripts" / "guild-kernel" / "guild.py"
        record = subprocess.run(
            [
                sys.executable,
                str(cli),
                "budget",
                "record",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--stage",
                "backend",
                "--seconds",
                "2",
                "--tool-calls",
                "3",
                "--turns",
                "1",
                "--tokens",
                "100",
                "--usd",
                "0.01",
                "--event-id",
                "manual:one",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("BUDGET: backend recorded", record.stdout)
        listed = subprocess.run(
            [
                sys.executable,
                str(cli),
                "budget",
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
        row = json.loads(listed.stdout)[0]
        self.assertEqual(row["usage"]["tokens"], 100)
        self.assertEqual(row["reason"], None)

    def test_budget_cli_cannot_record_a_different_delivery_for_same_agent(self):
        self.plan()
        kernel.plan(
            root=self.root,
            name="other",
            done_when="other endpoint is complete",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["other endpoint is tested"],
                    [],
                    owned_paths=["app/Other"],
                )
            ],
        )
        kernel.claim_stage(self.root, "other", "backend")
        cli = REPO / "scripts" / "guild-kernel" / "guild.py"
        record = subprocess.run(
            [
                sys.executable,
                str(cli),
                "budget",
                "record",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--stage",
                "backend",
                "--seconds",
                "2",
                "--tool-calls",
                "3",
                "--turns",
                "1",
                "--tokens",
                "100",
                "--usd",
                "0.01",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(record.returncode, 1)
        self.assertIn("stage backend is not running", record.stderr)
        other = kernel.load(self.root, "other").stages[0]
        self.assertEqual(other.usage, kernel._EMPTY_USAGE)


class BudgetHookIntegrationTest(unittest.TestCase):
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
                    budget={"max_tool_calls": 1},
                )
            ],
        )
        kernel.claim_stage(self.root, "tag", "backend")

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, payload):
        return subprocess.run(
            [str(self.hook)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
        )

    def test_pre_tool_hook_blocks_after_ceiling(self):
        first = self.invoke(
            {
                "hook_event_name": "PreToolUse",
                "tool_use_id": "one",
                "agent_type": "laravel-team:backend-developer",
                "tool_name": "Read",
                "tool_input": {"file_path": "app/Http/Controller.php"},
            }
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.invoke(
            {
                "hook_event_name": "PreToolUse",
                "tool_use_id": "two",
                "agent_type": "laravel-team:backend-developer",
                "tool_name": "Read",
                "tool_input": {"file_path": "app/Http/Request.php"},
            }
        )
        self.assertEqual(second.returncode, 2)
        self.assertIn("max_tool_calls", second.stderr)

    def test_completion_hook_records_all_dimensions(self):
        response = {
            "status": "completed",
            "resolvedModel": "claude-sonnet-5",
            "totalDurationMs": 2500,
            "totalTokens": 115,
            "totalToolUseCount": 1,
            "usage": {
                "input_tokens": 5,
                "output_tokens": 10,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 0,
                "iterations": [{"type": "message"}],
            },
        }
        result = self.invoke(
            {
                "hook_event_name": "PostToolUse",
                "tool_use_id": "agent-one",
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "laravel-team:backend-developer"
                },
                "tool_response": response,
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = kernel.load(self.root, "tag").stages[0].usage
        self.assertEqual(usage["tokens"], 115)
        self.assertEqual(usage["turns"], 1)
        self.assertEqual(usage["tool_calls"], 1)
        self.assertGreaterEqual(usage["seconds"], 2.5)
        self.assertGreater(usage["cost_usd"], 0)

    def test_missing_completion_telemetry_fails_closed(self):
        result = self.invoke(
            {
                "hook_event_name": "PostToolUse",
                "tool_use_id": "agent-missing",
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "laravel-team:backend-developer"
                },
                "tool_response": {"status": "completed"},
            }
        )
        self.assertEqual(result.returncode, 2)
        stage = kernel.load(self.root, "tag").stages[0]
        self.assertEqual(stage.status, "budget_exceeded")
        self.assertIn("missing_budget_telemetry", stage.budget_exceeded_reason)

    def test_direct_agent_without_kernel_stage_ignores_missing_telemetry(self):
        delivery = kernel.load(self.root, "tag")
        delivery.status = "done"
        delivery.stages[0].status = "done"
        delivery.stages[0].claimed_at = ""
        kernel.save(self.root, delivery)

        result = self.invoke(
            {
                "hook_event_name": "PostToolUse",
                "tool_use_id": "direct-agent",
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "laravel-team:backend-developer"
                },
                "tool_response": {"status": "completed"},
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
