import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class RetryPolicyTest(unittest.TestCase):
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

    def complete_attempt(self):
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.record_stage_usage(
            self.root,
            "backend-developer",
            {
                "seconds": 1,
                "tool_calls": 1,
                "turns": 1,
                "tokens": 100,
                "cost_usd": 0.01,
            },
        )
        return kernel.report(self.root, "feature", self.report_path, runner=None)

    def request(self, *, event_id="stage-return:1", reason="missing NOT-CHECKED"):
        return kernel.request_retry(
            self.root,
            "feature",
            "backend",
            source="stage-return",
            reason=reason,
            event_id=event_id,
        )

    def test_report_rejects_an_unclaimed_queued_stage_before_verification(self):
        with self.assertRaisesRegex(
            kernel.ReportError, "report requires a claimed running stage"
        ):
            kernel.report(self.root, "feature", self.report_path, runner=None)
        self.assertEqual(kernel.load(self.root, "feature").stages[0].status, "queued")

    def test_claim_and_report_record_legal_transition_ledger(self):
        delivery = self.complete_attempt()
        stage = delivery.stages[0]
        self.assertEqual(stage.status, "done")
        self.assertEqual(stage.attempts, 1)
        self.assertEqual(
            [(row["from"], row["to"], row["source"]) for row in delivery.transition_events],
            [("queued", "running", "claim"), ("running", "done", "report")],
        )

    def test_first_retry_requeues_and_requires_a_fresh_atomic_claim(self):
        self.complete_attempt()
        event = self.request()
        self.assertEqual(event["action"], "queued")
        delivery = kernel.load(self.root, "feature")
        stage = delivery.stages[0]
        self.assertEqual(stage.status, "queued")
        self.assertEqual(stage.reopens, 1)
        self.assertEqual(stage.attempts, 1)
        self.assertEqual(stage.did, [])
        self.assertEqual(stage.verified, [])
        self.assertEqual(stage.retry_source, "stage-return")
        self.assertIn("retry:stage-return attempt:2", kernel.board_line(delivery))
        ready = kernel.ready_stages(self.root, "feature")
        self.assertEqual([item.id for item in ready], ["backend"])
        claimed = kernel.claim_stage(self.root, "feature", "backend")
        self.assertEqual(claimed.status, "running")
        self.assertEqual(claimed.attempts, 2)

    def test_retry_cannot_cancel_an_active_claim_before_telemetry(self):
        kernel.claim_stage(self.root, "feature", "backend")
        with self.assertRaisesRegex(kernel.PlanError, "completion telemetry"):
            self.request()
        stage = kernel.load(self.root, "feature").stages[0]
        self.assertEqual(stage.status, "running")
        self.assertEqual(stage.reopens, 0)

    def test_retry_request_is_main_thread_only(self):
        self.complete_attempt()
        with self.assertRaisesRegex(kernel.PlanError, "main thread"):
            kernel.request_retry(
                self.root,
                "feature",
                "backend",
                source="verification",
                reason="verification output was incomplete",
                event_id="verification:1",
                requested_by="backend-developer",
            )

    def test_retry_event_delivery_is_idempotent(self):
        self.complete_attempt()
        first = self.request()
        again = self.request()
        self.assertEqual(first, again)
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(delivery.stages[0].reopens, 1)
        self.assertEqual(len(delivery.retry_events), 1)
        with self.assertRaisesRegex(kernel.PlanError, "different data"):
            self.request(reason="a conflicting reason cannot replace history")

    def test_second_distinct_failure_marks_stage_failed_and_stops(self):
        self.complete_attempt()
        self.request()
        self.complete_attempt()
        event = self.request(
            event_id="verification:2", reason="retry still misses criterion evidence"
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(event["action"], "stopped")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(delivery.stages[0].status, "failed")
        self.assertEqual(delivery.stages[0].attempts, 2)
        self.assertEqual(kernel.ready_stages(self.root, "feature"), [])
        self.assertEqual(kernel.next_agent(self.root, "feature"), "STOP")

    def test_invalid_retry_source_reason_and_event_id_are_rejected(self):
        self.complete_attempt()
        cases = [
            {"source": "guess", "reason": "real", "event_id": "event:1"},
            {"source": "ci", "reason": "", "event_id": "event:1"},
            {"source": "ci", "reason": "real", "event_id": "bad event"},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(kernel.PlanError):
                kernel.request_retry(
                    self.root,
                    "feature",
                    "backend",
                    **values,
                )
        self.assertEqual(kernel.load(self.root, "feature").retry_events, [])

    def test_generated_views_explain_retries_and_transitions(self):
        self.complete_attempt()
        self.request(reason="verification evidence did not cover authorization")
        retries = (self.root / "docs/delivery/feature/retries.md").read_text()
        transitions = (
            self.root / "docs/delivery/feature/transitions.md"
        ).read_text()
        self.assertIn("## backend — queued", retries)
        self.assertIn("verification evidence did not cover authorization", retries)
        self.assertIn("`done` → `queued` via `retry:stage-return`", transitions)

    def test_legacy_state_loads_retry_fields_without_rewriting_history(self):
        delivery = kernel.load(self.root, "feature")
        state_path = self.root / "docs/delivery/feature/kernel.json"
        state = json.loads(state_path.read_text())
        state.pop("retry_events")
        state.pop("transition_events")
        for key in ("attempts", "retry_reason", "retry_source"):
            state["stages"][0].pop(key)
        state_path.write_text(json.dumps(state))
        loaded = kernel.load(self.root, "feature")
        self.assertEqual(loaded.retry_events, [])
        self.assertEqual(loaded.transition_events, [])
        self.assertEqual(loaded.stages[0].attempts, 0)

    def test_retry_and_transition_cli_list_the_durable_events(self):
        self.complete_attempt()
        self.request()
        guild = REPO / "scripts/guild-kernel/guild.py"
        retry = subprocess.run(
            [
                sys.executable,
                str(guild),
                "retry",
                "list",
                "--root",
                str(self.root),
                "--name",
                "feature",
            ],
            capture_output=True,
            text=True,
        )
        transitions = subprocess.run(
            [
                sys.executable,
                str(guild),
                "transition",
                "list",
                "--root",
                str(self.root),
                "--name",
                "feature",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertEqual(transitions.returncode, 0, transitions.stderr)
        self.assertEqual(json.loads(retry.stdout)[0]["action"], "queued")
        self.assertEqual(json.loads(transitions.stdout)[-1]["to"], "queued")

    def test_retry_request_cli_requeues_the_stage(self):
        self.complete_attempt()
        guild = REPO / "scripts/guild-kernel/guild.py"
        requested = subprocess.run(
            [
                sys.executable,
                str(guild),
                "retry",
                "request",
                "--root",
                str(self.root),
                "--name",
                "feature",
                "--stage",
                "backend",
                "--source",
                "verification",
                "--reason",
                "authorization evidence is missing",
                "--event-id",
                "verification:backend:1",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(requested.returncode, 0, requested.stderr)
        self.assertEqual(
            requested.stdout.strip(),
            "RETRY: backend queued event=verification:backend:1",
        )
        self.assertEqual(
            kernel.load(self.root, "feature").stages[0].status, "queued"
        )


if __name__ == "__main__":
    unittest.main()
