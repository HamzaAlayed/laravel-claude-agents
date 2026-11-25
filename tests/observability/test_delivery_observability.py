import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class PassingRunner:
    def run(self, cwd, argv):
        return 0


class DeliveryObservabilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.stage = kernel.StageSpec(
            id="backend",
            agent="backend-developer",
            role="writer",
            success_criteria=["endpoint works"],
            criterion_ids=["endpoint-works"],
            depends_on=[],
            owned_paths=["app"],
            approval_categories=[],
            feedback_checks=["phpunit"],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        return kernel.plan(
            root=self.root,
            name="feature",
            done_when="POST /api/features returns 201",
            stages=[self.stage],
        )

    def report(self):
        artifact = self.root / "app/Feature.php"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("<?php\n", encoding="utf-8")
        report = self.root / "docs/delivery/feature/stages/backend-developer.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        record = json.dumps(
            {
                "criterion": "endpoint-works",
                "runner": "file-exists",
                "args": ["app/Feature.php"],
            },
            separators=(",", ":"),
        )
        report.write_text(
            "STATUS: done\n"
            "DID: app/Feature.php\n"
            f"VERIFIED: {record}\n"
            "NOT-CHECKED: none\n"
            "FLAGS: none\n"
            "NEXT: none\n"
            "TOP-SECRET-REPORT-BODY\n",
            encoding="utf-8",
        )
        kernel.report(self.root, "feature", report, PassingRunner())

    def test_manifest_and_runtime_event_contract_match(self):
        manifest = json.loads(
            (REPO / "config/observability-harness.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["eventSchemaVersion"], kernel.OBSERVABILITY_SCHEMA)
        self.assertEqual(set(manifest["requiredFields"]), set(kernel.OBSERVABILITY_FIELDS))
        self.assertEqual(set(manifest["eventTypes"]), set(kernel.OBSERVABILITY_EVENT_TYPES))
        self.assertEqual(manifest["workerEventFields"], ["workerHash"])
        registry = json.loads(
            (REPO / "config/agent-harness.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            registry["shared"]["observabilityPolicy"], kernel._OBSERVABILITY_POLICY
        )
        source = (REPO / "scripts/guild-kernel/kernel.py").read_text(encoding="utf-8")
        for event_type in manifest["eventTypes"]:
            with self.subTest(event_type=event_type):
                self.assertGreaterEqual(source.count(f'"{event_type}"'), 2)

    def test_plan_creates_correlated_derived_artifacts_and_healthy_status(self):
        self.plan()
        folder = self.root / "docs/delivery/feature"
        events = kernel.observability_rows(self.root, "feature")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["type"], "stage.eligible")
        event = events[0]
        self.assertEqual(event["type"], "delivery.planned")
        self.assertEqual(event["seq"], 1)
        self.assertEqual(event["traceId"], "delivery:feature")
        self.assertEqual(event["previousEventHash"], "")
        self.assertEqual(event["parentSpanId"], "")
        self.assertTrue(event["eventHash"])
        self.assertTrue((folder / "events.jsonl").is_file())
        view = (folder / "observability.md").read_text(encoding="utf-8")
        self.assertIn("Trace: `delivery:feature`", view)
        self.assertIn("Events: 2", view)
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "healthy")
        self.assertEqual(status["events"], 2)
        self.assertEqual(status["latestStateHash"], events[-1]["stateHash"])
        self.plan()
        self.assertEqual(len(kernel.observability_rows(self.root, "feature")), 2)

    def test_timing_distinguishes_eligibility_claim_work_and_verification(self):
        epoch = datetime(2026, 11, 25, tzinfo=timezone.utc)
        with patch.object(kernel, "_now_utc") as now:
            now.return_value = epoch
            self.plan()
            now.return_value = epoch + timedelta(seconds=2)
            kernel.claim_stage(self.root, "feature", "backend")
            now.return_value = epoch + timedelta(seconds=2.25)
            kernel.record_worker_event(self.root, "backend-developer", "worker-one", "start")
            kernel.record_worker_event(self.root, "backend-developer", "worker-one", "start")
            now.return_value = epoch + timedelta(seconds=4.75)
            kernel.record_worker_event(self.root, "backend-developer", "other-worker", "finish")
            kernel.record_worker_event(self.root, "backend-developer", "worker-one", "finish")
            kernel.record_stage_usage(
                self.root, "backend-developer",
                {"seconds": 2.5, "tool_calls": 0, "turns": 1, "tokens": 10, "cost_usd": 0.01},
            )
            now.return_value = epoch + timedelta(seconds=5)
            self.report()

        row, = kernel.timing_rows(self.root, "feature")
        self.assertEqual(row["attempt"], 1)
        self.assertEqual(row["eligibleToClaimMs"], 2000)
        self.assertEqual(row["claimToStartMs"], 250)
        self.assertEqual(row["executionMs"], 2500)
        self.assertEqual(row["returnToVerifiedMs"], 250)
        self.assertEqual(row["checkpointWaitMs"], 0)
        events = kernel.observability_rows(self.root, "feature")
        self.assertEqual(sum(event["type"] == "stage.worker_started" for event in events), 1)
        self.assertEqual(sum(event["type"] == "stage.worker_finished" for event in events), 1)
        self.assertNotIn("worker-one", json.dumps(events))
        self.assertEqual(kernel.observability_status(self.root, "feature")["status"], "healthy")

    def test_timing_distinguishes_dependency_and_checkpoint_wait_from_capacity(self):
        dependent = kernel.StageSpec(
            "review", "qa-engineer", "writer", ["Review the endpoint"], ["backend"],
            criterion_ids=["reviewed"], owned_paths=["tests"],
        )
        independent = kernel.StageSpec(
            "documentation", "technical-writer", "writer", ["Write user guidance"], [],
            criterion_ids=["guidance"], owned_paths=["docs/features"],
        )
        epoch = datetime(2026, 11, 25, tzinfo=timezone.utc)
        with patch.object(kernel, "_now_utc") as now:
            now.return_value = epoch
            kernel.plan(
                root=self.root, name="feature", done_when="Deliver the endpoint",
                stages=[self.stage, dependent, independent], max_parallel=1,
            )
            kernel.claim_stage(self.root, "feature", "backend")
            self.assertEqual(kernel.ready_stages(self.root, "feature"), [])
            rows = {row["stage"]: row for row in kernel.timing_rows(self.root, "feature")}
            self.assertEqual(rows["documentation"]["eligibleAt"], rows["backend"]["eligibleAt"])
            self.assertNotIn("review", rows)
            now.return_value = epoch + timedelta(seconds=1)
            kernel.record_stage_usage(
                self.root, "backend-developer",
                {"seconds": 1, "tool_calls": 0, "turns": 1, "tokens": 10, "cost_usd": 0.01},
            )
            self.report()
            rows = {row["stage"]: row for row in kernel.timing_rows(self.root, "feature")}
            self.assertEqual(rows["review"]["eligibleAt"], rows["backend"]["verifiedAt"])
            now.return_value = epoch + timedelta(seconds=2)
            kernel.open_checkpoint(
                self.root, "feature", "review", "review-scope", "Proceed?", "Scope may change",
                [{"id": "continue", "label": "Continue", "action": "continue"},
                 {"id": "stop", "label": "Stop", "action": "stop"}], "continue",
            )
            now.return_value = epoch + timedelta(seconds=2.75)
            kernel.resolve_checkpoint(self.root, "feature", "review-scope", "continue", note="approved")
            now.return_value = epoch + timedelta(seconds=3)
            kernel.claim_stage(self.root, "feature", "review")
        row = next(row for row in kernel.timing_rows(self.root, "feature") if row["stage"] == "review")
        self.assertEqual(row["checkpointWaitMs"], 750)
        self.assertEqual(row["eligibleToClaimMs"], 250)
        self.assertIsNone(row["claimToStartMs"])
        self.assertIsNone(row["executionMs"])

    def test_claude_lifecycle_hook_feeds_cli_timing_without_raw_worker_ids(self):
        self.plan()
        kernel.claim_stage(self.root, "feature", "backend")
        hook = REPO / "scripts/enforce-kernel-budgets.py"
        for kind in ("SubagentStart", "SubagentStop"):
            result = subprocess.run(
                [sys.executable, str(hook)],
                input=json.dumps({
                    "hook_event_name": kind, "agent_type": "laravel-team:backend-developer",
                    "agent_id": "opaque-native-worker", "session_id": "opaque-native-session",
                }),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
                text=True, capture_output=True, check=True,
            )
            self.assertEqual(result.stdout, "")
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/guild-kernel/guild.py"), "observe", "timing",
             "--root", str(self.root), "--name", "feature"],
            text=True, capture_output=True, check=True,
        )
        row, = json.loads(result.stdout)
        self.assertGreaterEqual(row["executionMs"], 0)
        self.assertIsNone(row["verifiedAt"])
        self.assertNotIn("opaque-native", json.dumps(kernel.observability_rows(self.root, "feature")))

    def test_late_worker_hooks_cannot_update_the_next_attempt(self):
        self.plan()
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.record_worker_event(self.root, "backend-developer", "old-worker", "start")
        kernel.record_stage_usage(
            self.root, "backend-developer",
            {"seconds": 1, "tool_calls": 0, "turns": 1, "tokens": 10, "cost_usd": 0.01},
        )
        kernel.request_retry(
            self.root, "feature", "backend", source="verification",
            reason="Retry the stage", event_id="retry:one",
        )
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.record_worker_event(self.root, "backend-developer", "old-worker", "start")
        kernel.record_worker_event(self.root, "backend-developer", "new-worker", "start")
        kernel.record_worker_event(self.root, "backend-developer", "old-worker", "finish")
        first, second = kernel.timing_rows(self.root, "feature")
        self.assertEqual((first["attempt"], second["attempt"]), (1, 2))
        self.assertIsNone(first["finishedAt"])
        self.assertIsNone(second["finishedAt"])
        kernel.record_worker_event(self.root, "backend-developer", "new-worker", "finish")
        first, second = kernel.timing_rows(self.root, "feature")
        self.assertIsNone(first["finishedAt"])
        self.assertGreaterEqual(second["executionMs"], 0)

    def test_pre_timing_trace_remains_healthy_and_has_no_fabricated_intervals(self):
        delivery = self.plan()
        delivery.observability_events = delivery.observability_events[:1]
        event = delivery.observability_events[0]
        event["at"] = datetime.fromisoformat(event["at"]).isoformat(timespec="seconds")
        event["eventHash"] = kernel._event_digest(event)
        kernel.save(self.root, delivery)
        self.assertEqual(kernel.observability_status(self.root, "feature")["status"], "healthy")
        self.assertEqual(kernel.timing_rows(self.root, "feature"), [])

    def test_mutations_emit_typed_monotonic_hash_chained_events_without_raw_payloads(self):
        self.plan()
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.meter_tool_call(
            self.root,
            "backend-developer",
            event_id="tool:one",
            tool_name="Bash",
            signature=kernel.tool_call_signature(
                "Bash", {"command": "printf TOP-SECRET-TOOL-INPUT"}
            ),
        )
        kernel.record_stage_usage(
            self.root,
            "backend-developer",
            {"seconds": 1, "tool_calls": 1, "turns": 1, "tokens": 10, "cost_usd": 0.01},
            event_id="completion:one",
            expected_target=("feature", "backend"),
        )
        self.report()
        events = kernel.observability_rows(self.root, "feature")
        self.assertEqual(
            [event["type"] for event in events],
            [
                "delivery.planned",
                "stage.eligible",
                "stage.claimed",
                "tool.metered",
                "usage.recorded",
                "stage.reported",
            ],
        )
        self.assertEqual([event["seq"] for event in events], list(range(1, 7)))
        for previous, current in zip(events, events[1:]):
            self.assertEqual(current["previousEventHash"], previous["eventHash"])
        serialized = json.dumps(events)
        self.assertNotIn("TOP-SECRET-TOOL-INPUT", serialized)
        self.assertNotIn("TOP-SECRET-REPORT-BODY", serialized)
        self.assertEqual(events[-1]["usage"]["tool_calls"], 1)
        self.assertEqual(events[-1]["stageStatus"], "done")
        self.assertEqual(kernel.observability_status(self.root, "feature")["status"], "healthy")

    def test_tampered_derived_event_is_detected(self):
        self.plan()
        path = self.root / "docs/delivery/feature/events.jsonl"
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        events[0]["actor"] = "attacker"
        path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "unhealthy")
        self.assertTrue(any("derived event ledger" in error for error in status["errors"]))
        before = len(kernel.observability_rows(self.root, "feature"))
        repaired = kernel.repair_observability_views(self.root, "feature")
        self.assertEqual(repaired["status"], "healthy")
        self.assertEqual(len(kernel.observability_rows(self.root, "feature")), before)

    def test_tampered_summary_view_is_detected_and_repaired(self):
        self.plan()
        path = self.root / "docs/delivery/feature/observability.md"
        path.write_text("# forged summary\n", encoding="utf-8")
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "unhealthy")
        self.assertTrue(any("observability view" in error for error in status["errors"]))
        self.assertEqual(
            kernel.repair_observability_views(self.root, "feature")["status"],
            "healthy",
        )

    def test_tampered_authoritative_state_is_detected(self):
        self.plan()
        path = self.root / "docs/delivery/feature/kernel.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["done_when"] = "tampered completion condition"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "unhealthy")
        self.assertTrue(any("state hash" in error for error in status["errors"]))
        with self.assertRaisesRegex(kernel.PlanError, "authoritative observability state"):
            kernel.repair_observability_views(self.root, "feature")

    def test_malformed_authoritative_event_fails_closed_without_a_traceback(self):
        self.plan()
        path = self.root / "docs/delivery/feature/kernel.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["observability_events"][-1] = "malformed"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "unhealthy")
        self.assertTrue(any("not an object" in error for error in status["errors"]))
        with self.assertRaisesRegex(kernel.PlanError, "authoritative observability state"):
            kernel.repair_observability_views(self.root, "feature")

    def test_checkpoint_payload_stays_out_of_correlated_event_ledger(self):
        self.plan()
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.record_stage_usage(
            self.root,
            "backend-developer",
            {"seconds": 1, "tool_calls": 0, "turns": 1, "tokens": 10, "cost_usd": 0.01},
            event_id="completion:checkpoint",
            expected_target=("feature", "backend"),
        )
        kernel.open_checkpoint(
            self.root,
            "feature",
            "backend",
            "ship-decision",
            "Should TOP-SECRET-CHECKPOINT ship?",
            "TOP-SECRET-RISK",
            [
                {"id": "continue", "label": "Continue", "action": "continue"},
                {"id": "stop", "label": "Stop", "action": "stop"},
            ],
            "continue",
        )
        kernel.resolve_checkpoint(
            self.root, "feature", "ship-decision", "continue", note="approved"
        )
        events = kernel.observability_rows(self.root, "feature")
        self.assertEqual(
            [event["type"] for event in events if event["type"].startswith("checkpoint.")],
            ["checkpoint.opened", "checkpoint.resolved"],
        )
        serialized = json.dumps(events)
        self.assertNotIn("TOP-SECRET-CHECKPOINT", serialized)
        self.assertNotIn("TOP-SECRET-RISK", serialized)

    def test_legacy_state_loads_without_inventing_history_and_next_mutation_starts_trace(self):
        self.plan()
        state = self.root / "docs/delivery/feature/kernel.json"
        payload = json.loads(state.read_text(encoding="utf-8"))
        payload.pop("observability_events")
        state.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        (self.root / "docs/delivery/feature/events.jsonl").unlink()
        loaded = kernel.load(self.root, "feature")
        self.assertEqual(loaded.observability_events, [])
        self.assertEqual(kernel.observability_status(self.root, "feature")["status"], "unavailable")
        kernel.pair(self.root, "feature", "backend", reviewer="tech-lead")
        events = kernel.observability_rows(self.root, "feature")
        self.assertEqual([event["type"] for event in events], ["pair.assigned", "stage.eligible"])
        self.assertEqual(kernel.observability_status(self.root, "feature")["status"], "healthy")

    def test_cli_lists_and_verifies_observability(self):
        self.plan()
        cli = REPO / "scripts/guild-kernel/guild.py"
        listed = subprocess.run(
            [sys.executable, str(cli), "observe", "list", "--root", str(self.root), "--name", "feature"],
            text=True,
            capture_output=True,
        )
        verified = subprocess.run(
            [sys.executable, str(cli), "observe", "verify", "--root", str(self.root), "--name", "feature"],
            text=True,
            capture_output=True,
        )
        (self.root / "docs/delivery/feature/observability.md").write_text(
            "stale\n", encoding="utf-8"
        )
        repaired = subprocess.run(
            [sys.executable, str(cli), "observe", "repair", "--root", str(self.root), "--name", "feature"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(json.loads(listed.stdout)[0]["type"], "delivery.planned")
        self.assertEqual(json.loads(verified.stdout)["status"], "healthy")
        self.assertEqual(json.loads(repaired.stdout)["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
