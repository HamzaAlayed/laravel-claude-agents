import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


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
        self.assertEqual(len(events), 1)
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
        self.assertIn("Events: 1", view)
        status = kernel.observability_status(self.root, "feature")
        self.assertEqual(status["status"], "healthy")
        self.assertEqual(status["events"], 1)
        self.assertEqual(status["latestStateHash"], event["stateHash"])
        self.plan()
        self.assertEqual(len(kernel.observability_rows(self.root, "feature")), 1)

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
                "stage.claimed",
                "tool.metered",
                "usage.recorded",
                "stage.reported",
            ],
        )
        self.assertEqual([event["seq"] for event in events], list(range(1, 6)))
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
        event = json.loads(path.read_text(encoding="utf-8"))
        event["actor"] = "attacker"
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")
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
        self.assertEqual(events[-2]["type"], "checkpoint.opened")
        self.assertEqual(events[-1]["type"], "checkpoint.resolved")
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
        self.assertEqual([event["type"] for event in events], ["pair.assigned"])
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
