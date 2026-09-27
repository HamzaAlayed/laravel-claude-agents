import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "guild_economics_harness", REPO / "scripts/economics-harness.py"
)
economics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(economics)


def configuration(tier):
    return {
        "modelTier": tier,
        "contextStrategy": "bounded",
        "cacheStrategy": "none",
        "batchSize": 1,
        "maxAttempts": 1,
    }


def run(run_id, *, success=True, passed=True, safety=0, duration=100,
        cost=1.0, inputs=1000, outputs=200, cache_read=0, cache_write=0,
        tools=10, retries=0, interventions=0):
    return {
        "id": run_id,
        "success": success,
        "requiredCriteria": ["behavior", "verification"],
        "passedCriteria": ["behavior", "verification"] if passed else ["behavior"],
        "safetyViolations": safety,
        "durationSeconds": duration,
        "billedUsd": cost,
        "inputTokens": inputs,
        "outputTokens": outputs,
        "cacheReadTokens": cache_read,
        "cacheWriteTokens": cache_write,
        "toolCalls": tools,
        "retries": retries,
        "humanInterventions": interventions,
    }


def observations(variant, *, count=5, tier=None, **overrides):
    chosen = tier or ("standard" if variant == "baseline" else "economy")
    return {
        "schemaVersion": 1,
        "workloadId": "orders-index",
        "variant": variant,
        "configuration": configuration(chosen),
        "runs": [run(f"{variant}-{index}", **overrides) for index in range(count)],
    }


class EconomicsHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy, cls.scenarios, cls.agents = economics.validate(REPO)

    def scenario_workload(self, index=0):
        return copy.deepcopy(self.scenarios["scenarios"][index]["workload"])

    def comparison(self, baseline_payload=None, candidate_payload=None):
        directory = tempfile.TemporaryDirectory(dir=REPO)
        root = pathlib.Path(directory.name)
        baseline = root / "baseline.json"
        candidate = root / "candidate.json"
        baseline.write_text(json.dumps(baseline_payload or observations("baseline")), encoding="utf-8")
        candidate.write_text(json.dumps(candidate_payload or observations("candidate", cost=0.8)), encoding="utf-8")
        self.addCleanup(directory.cleanup)
        return baseline, candidate

    def test_policy_and_all_registered_scenarios_validate(self):
        self.assertEqual(self.policy["policyId"], "laravel-guild-agent-economics-v1")
        self.assertEqual(len(self.scenarios["scenarios"]), 10)
        self.assertEqual(len(economics.exercise_scenarios(self.policy, self.scenarios, self.agents)), 10)

    def test_complexity_risk_and_context_raise_the_tier_floor(self):
        expected = ["economy", "standard", "premium", "premium", None, "premium", "standard"]
        actual = [
            economics.route_workload(self.policy, self.agents, self.scenario_workload(index))["tier"]
            for index in range(7)
        ]
        self.assertEqual(actual, expected)

    def test_protected_risk_requires_approval_even_if_boolean_is_false(self):
        workload = self.scenario_workload()
        workload.update(risk="protected", protectedAction=False, approvalGranted=False)
        route = economics.route_workload(self.policy, self.agents, workload)
        self.assertEqual(route["decision"], "hold")
        self.assertIn("protected-action-approval-missing", route["reasons"])

    def test_unknown_classification_holds(self):
        workload = self.scenario_workload()
        workload["complexity"] = "mysterious"
        route = economics.route_workload(self.policy, self.agents, workload)
        self.assertEqual(route["decision"], "hold")
        self.assertEqual(route["tier"], None)
        self.assertIn("unknown-classification", route["reasons"])

    def test_each_estimated_budget_dimension_holds(self):
        cases = {
            "estimatedSeconds": (901, "estimated-seconds-budget-exceeded"),
            "estimatedInputTokens": (500001, "estimated-tokens-budget-exceeded"),
            "estimatedToolCalls": (51, "estimated-tool-calls-budget-exceeded"),
            "estimatedRetries": (2, "estimated-retries-budget-exceeded"),
            "estimatedUsd": (5.01, "estimated-usd-budget-exceeded"),
        }
        for field, (value, reason) in cases.items():
            with self.subTest(field=field):
                workload = self.scenario_workload()
                workload[field] = value
                route = economics.route_workload(self.policy, self.agents, workload)
                self.assertEqual(route["decision"], "hold")
                self.assertIn(reason, route["reasons"])

    def test_task_budget_cannot_raise_shared_defaults(self):
        workload = self.scenario_workload()
        workload["budget"]["maxUsd"] = self.agents["shared"]["budgets"]["defaults"]["max_usd"] + 1
        with self.assertRaisesRegex(economics.EconomicsError, "cannot exceed"):
            economics.route_workload(self.policy, self.agents, workload)

    def test_nonfinite_numbers_fail_closed(self):
        workload = self.scenario_workload()
        workload["estimatedUsd"] = float("nan")
        with self.assertRaisesRegex(economics.EconomicsError, "estimatedUsd"):
            economics.route_workload(self.policy, self.agents, workload)

    def test_cache_requires_large_stable_prefix(self):
        workload = self.scenario_workload()
        workload["reusableInputTokens"] = 5000
        self.assertEqual(economics.route_workload(self.policy, self.agents, workload)["cache"], "not-eligible")
        workload["stablePrefixHash"] = "a" * 64
        self.assertEqual(economics.route_workload(self.policy, self.agents, workload)["cache"], "reuse-eligible")

    def test_batch_requires_independence_shared_authority_and_no_side_effects(self):
        workload = self.scenario_workload()
        workload.update(independentItems=4, itemsIndependent=True, sharedAuthorityScope=True, hasSideEffects=False)
        self.assertEqual(economics.route_workload(self.policy, self.agents, workload)["batch"], "eligible")
        for field, value in (("itemsIndependent", False), ("sharedAuthorityScope", False), ("hasSideEffects", True), ("independentItems", 9)):
            with self.subTest(field=field):
                changed = copy.deepcopy(workload)
                changed[field] = value
                self.assertEqual(economics.route_workload(self.policy, self.agents, changed)["batch"], "separate")

    def test_early_stop_never_skips_required_verification(self):
        route = economics.route_workload(self.policy, self.agents, self.scenario_workload())
        self.assertEqual(route["earlyStop"], "all-required-criteria-and-verification-pass")
        self.assertIn("required verification", self.policy["earlyStopPolicy"]["mustNotSkip"])

    def test_route_receipt_round_trips_and_detects_tampering(self):
        directory = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(directory.cleanup)
        workload = pathlib.Path(directory.name) / "workload.json"
        workload.write_text(json.dumps(self.scenario_workload()), encoding="utf-8")
        receipt = economics.build_route_receipt(REPO, workload)
        economics.verify_receipt(REPO, receipt)
        receipt["route"]["tier"] = "premium"
        with self.assertRaisesRegex(economics.EconomicsError, "tampered"):
            economics.verify_receipt(REPO, receipt)

    def test_material_cost_per_success_reduction_is_adopted(self):
        baseline, candidate = self.comparison()
        receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"]["decision"], "adopt-candidate")
        self.assertAlmostEqual(receipt["decision"]["costPerSuccessfulOutcomeReduction"], 0.2)
        economics.verify_receipt(REPO, receipt)

    def test_comparison_receipt_detects_evidence_source_drift(self):
        baseline, candidate = self.comparison()
        receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        payload["runs"][0]["billedUsd"] = 0.01
        candidate.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(economics.EconomicsError, "source-drifted"):
            economics.verify_receipt(REPO, receipt)

    def test_cheaper_requests_with_more_failures_are_not_adopted(self):
        payload = observations("candidate", count=5, cost=0.7)
        payload["runs"][0]["success"] = False
        payload["runs"][0]["passedCriteria"] = []
        baseline, candidate = self.comparison(candidate_payload=payload)
        receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"]["decision"], "keep-baseline")
        self.assertIn("quality-or-completion-regression", receipt["decision"]["reasons"])

    def test_insufficient_evidence_unhealthy_baseline_and_same_configuration_hold(self):
        pairs = [
            (observations("baseline", count=4), observations("candidate", count=4, cost=0.5), "insufficient-evidence"),
            (observations("baseline", passed=False), observations("candidate", cost=0.5), "baseline-unhealthy"),
            (observations("baseline"), observations("candidate", tier="standard", cost=0.5), "configuration-not-changed"),
        ]
        for base_payload, candidate_payload, reason in pairs:
            with self.subTest(reason=reason):
                baseline, candidate = self.comparison(base_payload, candidate_payload)
                receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
                self.assertEqual(receipt["decision"], {"decision": "hold", "reasons": [reason]})

    def test_changed_or_inconsistent_criteria_cannot_claim_savings(self):
        changed = observations("candidate", cost=0.5)
        for item in changed["runs"]:
            item["requiredCriteria"] = ["easier"]
            item["passedCriteria"] = ["easier"]
        baseline, candidate = self.comparison(candidate_payload=changed)
        receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"], {"decision": "hold", "reasons": ["criteria-definition-mismatch"]})

        changed = observations("candidate", cost=0.5)
        changed["runs"][0]["requiredCriteria"] = ["easier"]
        changed["runs"][0]["passedCriteria"] = ["easier"]
        baseline, candidate = self.comparison(candidate_payload=changed)
        with self.assertRaisesRegex(economics.EconomicsError, "one criteria definition"):
            economics.build_comparison_receipt(REPO, baseline, candidate)

    def test_safety_quality_and_no_success_fail_closed(self):
        cases = [
            (dict(safety=1, cost=0.1), "safety-violation"),
            (dict(passed=False, cost=0.1), "quality-or-completion-regression"),
            (dict(success=False, passed=False, cost=0.1), "no-successful-outcome"),
        ]
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                baseline, candidate = self.comparison(candidate_payload=observations("candidate", **overrides))
                decision = economics.build_comparison_receipt(REPO, baseline, candidate)["decision"]
                self.assertEqual(decision["decision"], "keep-baseline")
                self.assertIn(reason, decision["reasons"])

    def test_candidate_hard_budget_breaches_are_named(self):
        defaults = self.agents["shared"]["budgets"]["defaults"]
        cases = {
            "durationSeconds": (defaults["max_seconds"] + 1, "hard-duration-budget-breach"),
            "inputTokens": (defaults["max_tokens"] + 1, "hard-tokens-budget-breach"),
            "toolCalls": (defaults["max_tool_calls"] + 1, "hard-tool-calls-budget-breach"),
            "billedUsd": (defaults["max_usd"] + 1, "hard-usd-budget-breach"),
            "retries": (self.agents["shared"]["retryPolicy"]["maxRetries"] + 1, "hard-retries-budget-breach"),
        }
        for field, (value, reason) in cases.items():
            with self.subTest(field=field):
                payload = observations("candidate", cost=0.1)
                payload["runs"][0][field] = value
                baseline, candidate = self.comparison(candidate_payload=payload)
                decision = economics.build_comparison_receipt(REPO, baseline, candidate)["decision"]
                self.assertIn(reason, decision["reasons"])

    def test_operational_regressions_block_adoption(self):
        cases = [
            (dict(duration=126, cost=0.5), "duration-regression"),
            (dict(tools=13, cost=0.5), "tool-call-regression"),
            (dict(retries=1, cost=0.5), "retry-regression"),
            (dict(interventions=1, cost=0.5), "human-intervention-regression"),
            (dict(cost=0.9), "insufficient-cost-per-success-reduction"),
        ]
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                baseline, candidate = self.comparison(candidate_payload=observations("candidate", **overrides))
                decision = economics.build_comparison_receipt(REPO, baseline, candidate)["decision"]
                self.assertEqual(decision["decision"], "keep-baseline")
                self.assertIn(reason, decision["reasons"])

    def test_evidence_configuration_cannot_exceed_batch_or_retry_bounds(self):
        for field, value, message in (("batchSize", 9, "batchSize"), ("maxAttempts", 3, "maxAttempts")):
            with self.subTest(field=field):
                payload = observations("candidate", cost=0.5)
                payload["configuration"][field] = value
                baseline, candidate = self.comparison(candidate_payload=payload)
                with self.assertRaisesRegex(economics.EconomicsError, message):
                    economics.build_comparison_receipt(REPO, baseline, candidate)

    def test_receipt_excludes_run_ids_and_raw_content(self):
        baseline, candidate = self.comparison()
        receipt = economics.build_comparison_receipt(REPO, baseline, candidate)
        encoded = json.dumps(receipt)
        self.assertNotIn("baseline-0", encoded)
        self.assertNotIn("assistant text", encoded)
        self.assertEqual(receipt["baseline"]["runs"], 5)

    def test_evidence_paths_cannot_escape_or_use_symlinks(self):
        _, candidate = self.comparison()
        with self.assertRaisesRegex(economics.EconomicsError, "inside the repository"):
            economics.build_comparison_receipt(REPO, pathlib.Path("../outside.json"), candidate)
        directory = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(directory.cleanup)
        link = pathlib.Path(directory.name) / "baseline-link.json"
        link.symlink_to(candidate)
        with self.assertRaisesRegex(economics.EconomicsError, "non-symlink"):
            economics.build_comparison_receipt(REPO, link, candidate)

    def test_writer_rejects_nonempty_sealed_and_symlink_outputs(self):
        receipt = {"sealed": True}
        directory = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(directory.cleanup)
        output = pathlib.Path(directory.name) / "receipt.json"
        output.write_text("occupied", encoding="utf-8")
        with self.assertRaisesRegex(economics.EconomicsError, "nonempty"):
            economics.write_receipt(output, receipt, REPO, self.policy)
        with self.assertRaisesRegex(economics.EconomicsError, "sealed source"):
            economics.write_receipt(REPO / "config/economics-harness.json", receipt, REPO, self.policy)
        target = pathlib.Path(directory.name) / "target.json"
        link = pathlib.Path(directory.name) / "linked.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(economics.EconomicsError, "non-symlink"):
            economics.write_receipt(link, receipt, REPO, self.policy)

    def test_cli_compare_and_verify_round_trip(self):
        baseline, candidate = self.comparison()
        output = baseline.parent / "receipt.json"
        compare = subprocess.run(
            [sys.executable, "scripts/economics-harness.py", "compare", "--root", ".", "--baseline", str(baseline.relative_to(REPO)), "--candidate", str(candidate.relative_to(REPO)), "--output", str(output.relative_to(REPO))],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        self.assertEqual(compare.returncode, 0, compare.stderr)
        self.assertIn("adopt-candidate", compare.stdout)
        verify = subprocess.run(
            [sys.executable, "scripts/economics-harness.py", "verify", "--root", ".", "--receipt", str(output.relative_to(REPO))],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn("verified: adopt-candidate", verify.stdout)


if __name__ == "__main__":
    unittest.main()
