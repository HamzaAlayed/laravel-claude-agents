import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "guild_reliability_harness", REPO / "scripts/reliability-harness.py"
)
reliability = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reliability)


def attempt(operation, number=1, *, outcome="success", duration=100, cost=0.10,
            intervention=False, safety=0, side_effect="none", key=None):
    return {
        "id": f"{operation}-a{number}",
        "operationId": operation,
        "attempt": number,
        "outcome": outcome,
        "durationSeconds": duration,
        "costUsd": cost,
        "humanIntervention": intervention,
        "safetyViolations": safety,
        "idempotencyKey": key,
        "sideEffect": side_effect,
    }


def cohort(name, release, *, count=10, duration=100, cost=0.10):
    return {
        "schemaVersion": 1,
        "cohort": name,
        "release": release,
        "attempts": [attempt(f"op-{index:02d}", duration=duration, cost=cost) for index in range(count)],
    }


class ReliabilityHarnessTest(unittest.TestCase):
    def setUp(self):
        self.policy, self.scenarios = reliability.validate(REPO)
        self.tmp = tempfile.TemporaryDirectory(dir=REPO)
        self.directory = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, payload):
        path = self.directory / name
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def pair(self, baseline=None, canary=None):
        return (
            self.write("baseline.json", baseline or cohort("baseline", "9.6.0")),
            self.write("canary.json", canary or cohort("canary", "9.7.0")),
        )

    def test_policy_and_all_degraded_condition_scenarios_validate(self):
        self.assertEqual(self.policy["policyId"], self.scenarios["policyId"])
        results = reliability.exercise_scenarios(self.policy, self.scenarios)
        self.assertEqual(len(results), 9)
        self.assertEqual({row["id"] for row in results}, {f"REL-{index:03d}" for index in range(1, 10)})

    def test_healthy_canary_is_promoted_and_receipt_round_trips(self):
        baseline, canary = self.pair()
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "promote")
        reliability.verify_receipt(REPO, receipt)

    def test_cli_assesses_and_verifies_a_health_receipt(self):
        baseline, canary = self.pair()
        output = self.directory / "receipt.json"
        assessed = subprocess.run(
            [
                "python3", str(REPO / "scripts/reliability-harness.py"), "assess",
                "--root", str(REPO), "--baseline", str(baseline),
                "--canary", str(canary), "--output", str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        self.assertIn("promote:", assessed.stdout)
        verified = subprocess.run(
            [
                "python3", str(REPO / "scripts/reliability-harness.py"), "verify",
                "--root", str(REPO), "--receipt", str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("verified: promote", verified.stdout)

    def test_receipt_contains_aggregates_and_hashes_not_raw_agent_data(self):
        baseline, canary = self.pair()
        receipt = reliability.build_receipt(REPO, baseline, canary)
        serialized = json.dumps(receipt).lower()
        for forbidden in self.policy["receipt"]["excludedRawData"]:
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("op-00-a1", serialized)

    def test_insufficient_evidence_holds_the_canary(self):
        baseline, canary = self.pair(
            cohort("baseline", "9.6.0", count=9),
            cohort("canary", "9.7.0", count=9),
        )
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "hold")
        self.assertEqual(receipt["decision"]["reasons"], ["insufficient-evidence"])

    def test_safety_violation_rolls_back_even_before_the_sample_floor(self):
        bad = cohort("canary", "9.7.0", count=1)
        bad["attempts"][0]["outcome"] = "safety-violation"
        bad["attempts"][0]["safetyViolations"] = 1
        baseline, canary = self.pair(cohort("baseline", "9.6.0", count=1), bad)
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "rollback")
        self.assertEqual(receipt["decision"]["reasons"], ["circuit-open"])

    def test_unhealthy_baseline_holds_instead_of_claiming_candidate_regression(self):
        bad = cohort("baseline", "9.6.0")
        bad["attempts"][0]["outcome"] = "application-failure"
        baseline, canary = self.pair(bad, cohort("canary", "9.7.0"))
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "hold")
        self.assertEqual(receipt["decision"]["reasons"], ["baseline-unhealthy"])

    def test_candidate_slo_breach_rolls_back(self):
        bad = cohort("canary", "9.7.0")
        bad["attempts"][0]["outcome"] = "application-failure"
        baseline, canary = self.pair(cohort("baseline", "9.6.0"), bad)
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "rollback")
        self.assertEqual(receipt["decision"]["reasons"], ["candidate-slo-breach"])

    def test_material_latency_regression_rolls_back_even_inside_absolute_slo(self):
        baseline, canary = self.pair(
            cohort("baseline", "9.6.0", duration=100),
            cohort("canary", "9.7.0", duration=131),
        )
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["decision"]["decision"], "rollback")
        self.assertEqual(receipt["decision"]["reasons"], ["material-regression"])

    def test_duplicate_side_effect_opens_circuit_and_rolls_back(self):
        canary_payload = cohort("canary", "9.7.0")
        canary_payload["attempts"] = [
            attempt("op-00", 1, outcome="timeout", side_effect="applied", key="same"),
            attempt("op-00", 2, outcome="success", side_effect="applied", key="same"),
            *canary_payload["attempts"][1:],
        ]
        baseline, canary = self.pair(cohort("baseline", "9.6.0"), canary_payload)
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["canary"]["circuit"]["state"], "open")
        self.assertEqual(receipt["decision"]["reasons"], ["circuit-open"])

    def test_interrupted_side_effect_recovery_is_idempotent(self):
        canary_payload = cohort("canary", "9.7.0")
        canary_payload["attempts"] = [
            attempt("op-00", 1, outcome="timeout", duration=20, cost=0.01, side_effect="applied", key="stable"),
            attempt("op-00", 2, outcome="success", duration=20, cost=0.01, side_effect="deduplicated", key="stable"),
            *canary_payload["attempts"][1:],
        ]
        baseline, canary = self.pair(cohort("baseline", "9.6.0"), canary_payload)
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["canary"]["duplicateSideEffectRate"], 0)
        self.assertEqual(receipt["canary"]["recoveryRate"], 1)
        self.assertEqual(receipt["decision"]["decision"], "promote")

    def test_three_consecutive_retryable_failures_open_the_circuit(self):
        canary_payload = cohort("canary", "9.7.0")
        canary_payload["attempts"] = [
            attempt("op-00", 1, outcome="tool-unavailable"),
            attempt("op-00", 2, outcome="timeout"),
            attempt("op-00", 3, outcome="rate-limited"),
            *canary_payload["attempts"][1:],
        ]
        baseline, canary = self.pair(cohort("baseline", "9.6.0"), canary_payload)
        receipt = reliability.build_receipt(REPO, baseline, canary)
        self.assertEqual(receipt["canary"]["circuit"]["state"], "open")
        self.assertGreater(receipt["canary"]["circuit"]["attemptsAfterOpen"], 0)
        self.assertEqual(receipt["decision"]["decision"], "rollback")

    def test_retry_after_a_terminal_outcome_is_rejected(self):
        bad = cohort("canary", "9.7.0")
        bad["attempts"] = [
            attempt("op-00", 1, outcome="corrupt-state"),
            attempt("op-00", 2, outcome="success"),
            *bad["attempts"][1:],
        ]
        path = self.write("terminal-retry.json", bad)
        with self.assertRaisesRegex(reliability.ReliabilityError, "terminal outcome"):
            reliability.read_observations(REPO, path, "canary", self.policy)

    def test_tampered_receipt_is_rejected(self):
        baseline, canary = self.pair()
        receipt = reliability.build_receipt(REPO, baseline, canary)
        receipt["decision"]["decision"] = "rollback"
        with self.assertRaisesRegex(reliability.ReliabilityError, "tampered"):
            reliability.verify_receipt(REPO, receipt)

    def test_source_drift_is_rejected(self):
        baseline, canary = self.pair()
        receipt = reliability.build_receipt(REPO, baseline, canary)
        original = canary.read_text(encoding="utf-8")
        canary.write_text(original.replace("100", "101", 1), encoding="utf-8")
        with self.assertRaisesRegex(reliability.ReliabilityError, "source-drifted"):
            reliability.verify_receipt(REPO, receipt)

    def test_evidence_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = pathlib.Path(outside_directory) / "outside-reliability.json"
            outside.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(reliability.ReliabilityError, "inside the repository"):
                reliability.read_observations(REPO, outside, "baseline", self.policy)
        target = self.write("target.json", cohort("baseline", "9.6.0"))
        link = self.directory / "link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(reliability.ReliabilityError, "non-symlink"):
            reliability.read_observations(REPO, link, "baseline", self.policy)

    def test_receipt_writer_refuses_sealed_source_symlink_and_nonempty_output(self):
        baseline, canary = self.pair()
        receipt = reliability.build_receipt(REPO, baseline, canary)
        with self.assertRaisesRegex(reliability.ReliabilityError, "sealed source"):
            reliability.write_receipt(REPO / "config/reliability-harness.json", receipt, REPO, self.policy)
        occupied = self.directory / "occupied.json"
        occupied.write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(reliability.ReliabilityError, "nonempty"):
            reliability.write_receipt(occupied, receipt, REPO, self.policy)
        link = self.directory / "output-link.json"
        link.symlink_to(occupied)
        with self.assertRaisesRegex(reliability.ReliabilityError, "non-symlink"):
            reliability.write_receipt(link, receipt, REPO, self.policy)

    def test_policy_does_not_allow_automatic_database_rollback(self):
        self.assertEqual(self.policy["rollbackUnit"]["databaseAction"], "never-automatic")
        self.assertTrue(self.policy["rollbackUnit"]["operatorApprovalRequired"])


if __name__ == "__main__":
    unittest.main()
