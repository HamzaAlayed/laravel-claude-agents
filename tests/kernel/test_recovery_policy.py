import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class RecoveryPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.artifact = self.root / "app/Feature.php"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text("<?php\n")
        self.report_path = (
            self.root / "docs/delivery/feature/stages/backend-developer.md"
        )
        self.report_path.parent.mkdir(parents=True)
        self.report_path.write_text(
            "STATUS: done\nDID: app/Feature.php\n"
            'VERIFIED: {"criterion":"feature-works","runner":"file-exists",'
            '"args":["app/Feature.php"]}\n'
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        kernel.plan(
            root=self.root,
            name="feature",
            done_when="the feature works",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["feature works"],
                    [],
                    owned_paths=["app"],
                    criterion_ids=["feature-works"],
                )
            ],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def claim_at(self, claimed="2026-09-25T10:00:00+00:00"):
        kernel.claim_stage(self.root, "feature", "backend")
        delivery = kernel.load(self.root, "feature")
        stage = delivery.stages[0]
        stage.claimed_at = claimed
        stage.last_activity_at = claimed
        stage.claim_usage = dict(stage.usage)
        kernel.save(self.root, delivery)
        return stage

    def interrupt(
        self,
        *,
        event_id="process:run-1",
        reason="the host process exited",
        source="process-exit",
        now="2026-09-25T10:05:00+00:00",
    ):
        return kernel.interrupt_stage(
            self.root,
            "feature",
            "backend",
            source=source,
            reason=reason,
            event_id=event_id,
            now=datetime.fromisoformat(now),
        )

    def test_recovery_list_exposes_an_active_claim_before_mutation(self):
        self.claim_at()
        rows = kernel.recovery_rows(self.root, "feature")
        self.assertEqual(rows["delivery_status"], "running")
        self.assertEqual(rows["active_claims"][0]["stage"], "backend")
        self.assertEqual(rows["events"], [])

    def test_interrupt_freezes_at_last_kernel_observed_activity(self):
        self.claim_at()
        kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id="tool:1",
            now=datetime(2026, 9, 25, 10, 2, tzinfo=timezone.utc),
        )
        event = self.interrupt()
        delivery = kernel.load(self.root, "feature")
        stage = delivery.stages[0]
        self.assertEqual(event["status"], "pending")
        self.assertEqual(event["accounted_seconds"], 120.0)
        self.assertEqual(event["interrupted_at"], "2026-09-25T10:02:00+00:00")
        self.assertEqual(
            event["unavailable_metrics"], ["turns", "tokens", "cost_usd"]
        )
        self.assertEqual(stage.status, "interrupted")
        self.assertEqual(stage.claimed_at, "")
        self.assertEqual(stage.usage["seconds"], 120.0)
        self.assertEqual(stage.usage["tool_calls"], 1)
        self.assertEqual(delivery.status, "interrupted")
        self.assertEqual(kernel.next_agent(self.root, "feature"), "RECOVERY_REQUIRED: process:run-1")

    def test_interrupted_stage_cannot_report_or_return_ready_work(self):
        self.claim_at()
        self.interrupt()
        with self.assertRaisesRegex(kernel.ReportError, "report requires"):
            kernel.report(self.root, "feature", self.report_path, runner=None)
        self.assertEqual(kernel.ready_stages(self.root, "feature"), [])

    def test_unresolved_parallel_interruption_blocks_new_dispatch(self):
        kernel.plan(
            root=self.root,
            name="parallel",
            done_when="all parallel work completes",
            max_parallel=2,
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["backend complete"],
                    [],
                    owned_paths=["app"],
                    criterion_ids=["backend-complete"],
                ),
                kernel.StageSpec(
                    "frontend",
                    "frontend-developer",
                    "writer",
                    ["frontend complete"],
                    [],
                    owned_paths=["resources"],
                    criterion_ids=["frontend-complete"],
                ),
                kernel.StageSpec(
                    "docs",
                    "technical-writer",
                    "writer",
                    ["docs complete"],
                    [],
                    owned_paths=["docs"],
                    criterion_ids=["docs-complete"],
                ),
            ],
        )
        kernel.claim_stage(self.root, "parallel", "backend")
        kernel.claim_stage(self.root, "parallel", "frontend")
        delivery = kernel.load(self.root, "parallel")
        backend = next(stage for stage in delivery.stages if stage.id == "backend")
        backend.claimed_at = "2026-09-25T10:00:00+00:00"
        backend.last_activity_at = backend.claimed_at
        kernel.save(self.root, delivery)

        kernel.interrupt_stage(
            self.root,
            "parallel",
            "backend",
            source="process-exit",
            reason="the backend runtime exited",
            event_id="process:parallel-backend",
            now=datetime(2026, 9, 25, 10, 5, tzinfo=timezone.utc),
        )

        delivery = kernel.load(self.root, "parallel")
        self.assertEqual(delivery.status, "running")
        self.assertEqual(kernel.ready_stages(self.root, "parallel"), [])
        self.assertEqual(
            kernel.next_agent(self.root, "parallel"),
            "RECOVERY_REQUIRED: process:parallel-backend",
        )

    def test_continue_requeues_for_a_fresh_claim_without_consuming_retry(self):
        self.claim_at()
        self.interrupt()
        event = kernel.resolve_recovery(
            self.root,
            "feature",
            "process:run-1",
            action="continue",
            note="inspect partial files before continuing",
        )
        delivery = kernel.load(self.root, "feature")
        stage = delivery.stages[0]
        self.assertEqual(event["status"], "continued")
        self.assertEqual(stage.status, "queued")
        self.assertEqual(stage.attempts, 1)
        self.assertEqual(stage.reopens, 0)
        self.assertEqual(delivery.status, "running")
        self.assertEqual([item.id for item in kernel.ready_stages(self.root, "feature")], ["backend"])
        claimed = kernel.claim_stage(self.root, "feature", "backend")
        self.assertEqual(claimed.attempts, 2)
        self.assertEqual(claimed.reopens, 0)
        self.assertIn("recovery:process-exit attempt:2", kernel.board_line(delivery))

    def test_stop_fails_the_stage_and_delivery(self):
        self.claim_at()
        self.interrupt()
        event = kernel.resolve_recovery(
            self.root,
            "feature",
            "process:run-1",
            action="stop",
            note="workspace state cannot be trusted",
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(event["status"], "stopped")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(delivery.stages[0].status, "failed")

    def test_interrupt_and_resolution_are_main_thread_only(self):
        self.claim_at()
        with self.assertRaisesRegex(kernel.PlanError, "main thread"):
            kernel.interrupt_stage(
                self.root,
                "feature",
                "backend",
                source="runtime-error",
                reason="agent runtime disconnected",
                event_id="runtime:1",
                recorded_by="backend-developer",
            )
        self.interrupt()
        with self.assertRaisesRegex(kernel.PlanError, "main thread"):
            kernel.resolve_recovery(
                self.root,
                "feature",
                "process:run-1",
                action="continue",
                resolved_by="backend-developer",
            )

    def test_interrupt_event_delivery_is_idempotent_and_conflicts_fail(self):
        self.claim_at()
        first = self.interrupt()
        again = self.interrupt()
        self.assertEqual(first, again)
        self.assertEqual(len(kernel.load(self.root, "feature").recovery_events), 1)
        with self.assertRaisesRegex(kernel.PlanError, "different data"):
            self.interrupt(reason="a conflicting reason")

    def test_resolution_is_idempotent_and_cannot_be_changed(self):
        self.claim_at()
        self.interrupt()
        first = kernel.resolve_recovery(
            self.root,
            "feature",
            "process:run-1",
            action="continue",
            note="resume carefully",
        )
        again = kernel.resolve_recovery(
            self.root,
            "feature",
            "process:run-1",
            action="continue",
            note="resume carefully",
        )
        self.assertEqual(first, again)
        with self.assertRaisesRegex(kernel.PlanError, "already resolved"):
            kernel.resolve_recovery(
                self.root,
                "feature",
                "process:run-1",
                action="stop",
            )

    def test_known_elapsed_budget_breach_remains_terminal(self):
        self.claim_at()
        delivery = kernel.load(self.root, "feature")
        delivery.stages[0].budget["max_seconds"] = 60
        delivery.stages[0].last_activity_at = "2026-09-25T10:02:00+00:00"
        kernel.save(self.root, delivery)
        event = self.interrupt()
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(event["status"], "budget_exceeded")
        self.assertEqual(delivery.status, "budget_exceeded")
        self.assertEqual(delivery.stages[0].status, "budget_exceeded")
        with self.assertRaisesRegex(kernel.PlanError, "budget_exceeded"):
            kernel.resolve_recovery(
                self.root,
                "feature",
                "process:run-1",
                action="continue",
            )

    def test_generated_view_and_transition_ledger_explain_recovery(self):
        self.claim_at()
        self.interrupt(reason="desktop app quit during the stage")
        recoveries = (self.root / "docs/delivery/feature/recoveries.md").read_text()
        transitions = (self.root / "docs/delivery/feature/transitions.md").read_text()
        self.assertIn("## backend — pending", recoveries)
        self.assertIn("desktop app quit during the stage", recoveries)
        self.assertIn("`running` → `interrupted` via `recovery:process-exit`", transitions)

    def test_legacy_state_loads_recovery_fields_without_inventing_events(self):
        state_path = self.root / "docs/delivery/feature/kernel.json"
        state = json.loads(state_path.read_text())
        state.pop("recovery_events")
        for key in (
            "last_activity_at",
            "recovery_event_id",
            "recovery_reason",
            "recovery_source",
        ):
            state["stages"][0].pop(key)
        state_path.write_text(json.dumps(state))
        loaded = kernel.load(self.root, "feature")
        self.assertEqual(loaded.recovery_events, [])
        self.assertEqual(loaded.stages[0].last_activity_at, "")
        self.assertEqual(loaded.stages[0].recovery_event_id, "")

    def test_recovery_cli_runs_interrupt_list_and_continue_lifecycle(self):
        self.claim_at("2020-01-01T00:00:00+00:00")
        guild = REPO / "scripts/guild-kernel/guild.py"
        interrupted = subprocess.run(
            [
                sys.executable,
                str(guild),
                "recovery",
                "interrupt",
                "--root",
                str(self.root),
                "--name",
                "feature",
                "--stage",
                "backend",
                "--source",
                "host-restart",
                "--reason",
                "the previous host restarted",
                "--event-id",
                "host:run-1",
            ],
            capture_output=True,
            text=True,
        )
        listed = subprocess.run(
            [
                sys.executable,
                str(guild),
                "recovery",
                "list",
                "--root",
                str(self.root),
                "--name",
                "feature",
            ],
            capture_output=True,
            text=True,
        )
        continued = subprocess.run(
            [
                sys.executable,
                str(guild),
                "recovery",
                "resolve",
                "--root",
                str(self.root),
                "--name",
                "feature",
                "--event-id",
                "host:run-1",
                "--action",
                "continue",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(interrupted.returncode, 0, interrupted.stderr)
        self.assertIn("RECOVERY: backend pending event=host:run-1", interrupted.stdout)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(json.loads(listed.stdout)["events"][0]["status"], "pending")
        self.assertEqual(continued.returncode, 0, continued.stderr)
        self.assertIn("RECOVERY: backend continued event=host:run-1", continued.stdout)


if __name__ == "__main__":
    unittest.main()
