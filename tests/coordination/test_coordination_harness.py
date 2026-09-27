import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "guild_coordination_harness", REPO / "scripts/coordination-harness.py"
)
coordination = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coordination)


def task(task_id, capability="backend", *, dependencies=None, paths=None,
         seconds=120, cost=0.20, mutates=True, side_effect=None,
         specialist=False, required=None, granted=None):
    return {
        "id": task_id,
        "capability": capability,
        "dependencies": dependencies or [],
        "ownedPaths": paths or [f"app/{task_id}.php"],
        "estimatedSeconds": seconds,
        "estimatedCostUsd": cost,
        "mutates": mutates,
        "sideEffectKey": side_effect,
        "requiresSpecialist": specialist,
        "approvalsRequired": required or [],
        "approvalsGranted": granted or [],
        "contextPacketHash": hashlib.sha256(task_id.encode()).hexdigest(),
        "expectedOutput": f"verified {task_id} result",
    }


def workload(*tasks, workload_id="orders", coordinator="delivery-coordinator"):
    return {
        "schemaVersion": 1,
        "workloadId": workload_id,
        "coordinator": coordinator,
        "tasks": list(tasks),
    }


def run(run_id, *, success=True, passed=True, duration=100, cost=1.0,
        tools=10, interventions=0, duplicate=0, conflicts=0, deadlocks=0,
        stale=0):
    return {
        "id": run_id,
        "success": success,
        "requiredCriteria": ["behavior", "tests"],
        "passedCriteria": ["behavior", "tests"] if passed else ["behavior"],
        "durationSeconds": duration,
        "costUsd": cost,
        "toolCalls": tools,
        "humanInterventions": interventions,
        "duplicateWork": duplicate,
        "pathConflicts": conflicts,
        "deadlocks": deadlocks,
        "staleHandoffs": stale,
    }


def observations(variant, *, count=3, **overrides):
    return {
        "schemaVersion": 1,
        "workloadId": "orders",
        "variant": variant,
        "runs": [run(f"{variant}-{index}", **overrides) for index in range(count)],
    }


class CoordinationHarnessTest(unittest.TestCase):
    def setUp(self):
        self.policy, self.scenarios = coordination.validate(REPO)
        self.agents = coordination.load_json(
            REPO / "config/agent-harness.json", "agents"
        )
        self.tmp = tempfile.TemporaryDirectory(dir=REPO)
        self.directory = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, payload):
        path = self.directory / name
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def comparison(self, baseline=None, candidate=None):
        return (
            self.write("single.json", baseline or observations("single-agent", duration=100)),
            self.write("multi.json", candidate or observations("multi-agent", duration=70)),
        )

    def test_policy_covers_every_agent_and_all_scenarios(self):
        self.assertEqual(
            set(self.policy["capabilityRouting"].values()),
            set(self.agents["agents"]),
        )
        results = coordination.exercise_scenarios(
            self.policy, self.scenarios, REPO
        )
        self.assertEqual(len(results), 10)
        self.assertEqual(
            {row["id"] for row in results},
            {f"COORD-{index:03d}" for index in range(1, 11)},
        )

    def test_independent_specialists_get_parallel_typed_handoffs(self):
        payload = workload(
            task("backend", specialist=True, seconds=300),
            task("frontend", "frontend", paths=["resources/js/page.tsx"], specialist=True, seconds=300),
        )
        plan = coordination.plan_workload(self.policy, self.agents, payload)
        self.assertEqual((plan["decision"], plan["topology"]), ("delegate", "parallel"))
        self.assertEqual(plan["waves"], [["backend", "frontend"]])
        self.assertEqual(
            set(plan["handoffs"][0]),
            set(self.policy["handoffContract"]["requiredFields"]),
        )
        self.assertTrue(plan["preserveCompletedWork"])
        self.assertTrue(plan["containFailedLane"])

    def test_one_task_and_tiny_sequential_tasks_stay_single_agent(self):
        one = coordination.plan_workload(
            self.policy, self.agents, workload(task("only"))
        )
        tiny = coordination.plan_workload(
            self.policy,
            self.agents,
            workload(task("a", seconds=10, cost=0.05), task("b", dependencies=["a"], seconds=10, cost=0.05)),
        )
        self.assertEqual(one["decision"], "single-agent")
        self.assertEqual(tiny["decision"], "single-agent")
        self.assertEqual(tiny["handoffs"], [])

    def test_dependency_cycle_holds_before_dispatch(self):
        payload = workload(
            task("a", dependencies=["b"], specialist=True),
            task("b", "testing", dependencies=["a"], specialist=True),
        )
        plan = coordination.plan_workload(self.policy, self.agents, payload)
        self.assertEqual(plan["decision"], "hold")
        self.assertEqual(plan["reasons"], ["dependency-cycle"])

    def test_unordered_write_collision_holds_but_ordered_ownership_can_pipeline(self):
        collision = workload(
            task("a", paths=["routes/api.php"], specialist=True),
            task("b", "testing", paths=["routes/api.php"], specialist=True),
        )
        ordered = copy.deepcopy(collision)
        ordered["tasks"][1]["dependencies"] = ["a"]
        held = coordination.plan_workload(self.policy, self.agents, collision)
        piped = coordination.plan_workload(self.policy, self.agents, ordered)
        self.assertEqual(held["reasons"], ["unordered-write-conflict"])
        self.assertEqual((piped["decision"], piped["topology"]), ("delegate", "pipeline"))

    def test_duplicate_side_effect_key_holds(self):
        payload = workload(
            task("a", side_effect="email-42", specialist=True),
            task("b", "testing", side_effect="email-42", specialist=True),
        )
        plan = coordination.plan_workload(self.policy, self.agents, payload)
        self.assertEqual(plan["reasons"], ["duplicate-side-effect-key"])

    def test_missing_capability_or_approval_holds(self):
        missing_route = workload(
            task("a", "legal", specialist=True),
            task("b", "documentation", specialist=True),
        )
        missing_approval = workload(
            task("a", required=["destructive migration"], specialist=True),
            task("b", "testing", specialist=True),
        )
        self.assertEqual(
            coordination.plan_workload(self.policy, self.agents, missing_route)["reasons"],
            ["missing-capability"],
        )
        self.assertEqual(
            coordination.plan_workload(self.policy, self.agents, missing_approval)["reasons"],
            ["missing-approval"],
        )
        restricted_agents = copy.deepcopy(self.agents)
        restricted_agents["agents"]["delivery-coordinator"]["handoffs"].remove("frontend-developer")
        unauthorized = workload(
            task("backend", specialist=True, seconds=300),
            task("frontend", "frontend", specialist=True, seconds=300),
        )
        self.assertEqual(
            coordination.plan_workload(self.policy, restricted_agents, unauthorized)["reasons"],
            ["unauthorized-handoff"],
        )

    def test_undeclared_approval_and_path_escape_are_rejected(self):
        bad_grant = workload(task("a", granted=["auth"]))
        bad_path = workload(task("a", paths=["../outside.php"]))
        with self.assertRaisesRegex(coordination.CoordinationError, "undeclared approvals"):
            coordination.plan_workload(self.policy, self.agents, bad_grant)
        with self.assertRaisesRegex(coordination.CoordinationError, "repository-relative"):
            coordination.plan_workload(self.policy, self.agents, bad_path)

    def test_parallel_wave_never_exceeds_the_declared_cap(self):
        capabilities = ["backend", "frontend", "testing", "security", "documentation"]
        payload = workload(*[
            task(f"task-{index}", capability, paths=[f"area/{index}"], specialist=True, seconds=300)
            for index, capability in enumerate(capabilities)
        ])
        plan = coordination.plan_workload(self.policy, self.agents, payload)
        self.assertEqual(plan["decision"], "delegate")
        self.assertEqual([len(wave) for wave in plan["waves"]], [4, 1])
        self.assertEqual(plan["topology"], "hybrid")

    def test_one_agent_is_not_double_booked_inside_a_wave(self):
        payload = workload(
            task("a", seconds=300),
            task("b", paths=["app/b.php"], seconds=300),
            task("frontend", "frontend", paths=["resources/js/page.tsx"], seconds=300),
        )
        plan = coordination.plan_workload(self.policy, self.agents, payload)
        for wave in plan["waves"]:
            routed = [
                self.policy["capabilityRouting"][next(item for item in payload["tasks"] if item["id"] == task_id)["capability"]]
                for task_id in wave
            ]
            self.assertEqual(len(routed), len(set(routed)))

    def test_measured_faster_candidate_is_adopted_and_receipt_round_trips(self):
        baseline, candidate = self.comparison()
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"]["decision"], "adopt-multi-agent")
        coordination.verify_receipt(REPO, receipt)

    def test_insufficient_or_unhealthy_baseline_holds(self):
        baseline, candidate = self.comparison(
            observations("single-agent", count=2),
            observations("multi-agent", count=2, duration=50),
        )
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"], {"decision": "hold", "reasons": ["insufficient-evidence"]})

        unhealthy = observations("single-agent")
        unhealthy["runs"][0]["success"] = False
        baseline, candidate = self.comparison(unhealthy, observations("multi-agent", duration=50))
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"], {"decision": "hold", "reasons": ["baseline-unhealthy"]})

    def test_coordination_failures_keep_single_agent(self):
        failure_fields = {
            "duplicate": "duplicateWork",
            "conflicts": "pathConflicts",
            "deadlocks": "deadlocks",
            "stale": "staleHandoffs",
        }
        for argument, aggregate_key in failure_fields.items():
            with self.subTest(aggregate_key=aggregate_key):
                baseline, candidate = self.comparison(
                    observations("single-agent", duration=100),
                    observations("multi-agent", duration=50, **{argument: 1}),
                )
                receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
                self.assertEqual(receipt["decision"]["decision"], "keep-single-agent")
                self.assertIn("coordination-failure", receipt["decision"]["reasons"])
                self.assertEqual(receipt["multiAgent"]["coordinationFailures"][aggregate_key], 3)

    def test_changed_or_inconsistent_criteria_cannot_claim_improvement(self):
        baseline_payload = observations("single-agent")
        candidate_payload = observations("multi-agent", duration=50)
        candidate_payload["runs"][0]["requiredCriteria"] = ["easier"]
        candidate_payload["runs"][0]["passedCriteria"] = ["easier"]
        baseline, candidate = self.comparison(baseline_payload, candidate_payload)
        with self.assertRaisesRegex(coordination.CoordinationError, "one criteria definition"):
            coordination.build_comparison_receipt(REPO, baseline, candidate)

        candidate_payload = observations("multi-agent", duration=50)
        for item in candidate_payload["runs"]:
            item["requiredCriteria"] = ["easier"]
            item["passedCriteria"] = ["easier"]
        baseline, candidate = self.comparison(baseline_payload, candidate_payload)
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"], {"decision": "hold", "reasons": ["criteria-definition-mismatch"]})

    def test_quality_gain_can_justify_coordination_without_a_speed_gain(self):
        required = [f"criterion-{index}" for index in range(10)]
        baseline_payload = observations("single-agent", duration=100)
        candidate_payload = observations("multi-agent", duration=100)
        for item in baseline_payload["runs"]:
            item["requiredCriteria"] = required
            item["passedCriteria"] = required[:-1]
        for item in candidate_payload["runs"]:
            item["requiredCriteria"] = required
            item["passedCriteria"] = required
        baseline, candidate = self.comparison(baseline_payload, candidate_payload)
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"]["decision"], "adopt-multi-agent")
        self.assertEqual(receipt["decision"]["qualityPassRateIncrease"], 0.1)

    def test_quality_regression_or_no_material_benefit_keeps_single_agent(self):
        baseline, candidate = self.comparison(
            observations("single-agent", duration=100),
            observations("multi-agent", duration=50, passed=False),
        )
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertIn("quality-or-completion-regression", receipt["decision"]["reasons"])

        baseline, candidate = self.comparison(
            observations("single-agent", duration=100),
            observations("multi-agent", duration=90),
        )
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        self.assertEqual(receipt["decision"]["reasons"], ["no-material-benefit"])

    def test_cost_tool_and_human_regressions_are_named(self):
        baseline, candidate = self.comparison(
            observations("single-agent", duration=100, cost=1, tools=10),
            observations("multi-agent", duration=50, cost=2, tools=20, interventions=1),
        )
        reasons = coordination.build_comparison_receipt(REPO, baseline, candidate)["decision"]["reasons"]
        self.assertEqual(
            reasons,
            ["cost-regression", "human-intervention-regression", "tool-call-regression"],
        )

    def test_plan_cli_writes_and_verifies_a_source_bound_receipt(self):
        payload = workload(
            task("backend", specialist=True, seconds=300),
            task("frontend", "frontend", paths=["resources/js/page.tsx"], specialist=True, seconds=300),
        )
        workload_path = self.write("workload.json", payload)
        receipt_path = self.directory / "plan-receipt.json"
        planned = subprocess.run(
            [
                "python3", str(REPO / "scripts/coordination-harness.py"), "plan",
                "--root", str(REPO), "--workload", str(workload_path), "--output", str(receipt_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.assertIn("delegate: parallel", planned.stdout)
        verified = subprocess.run(
            [
                "python3", str(REPO / "scripts/coordination-harness.py"), "verify",
                "--root", str(REPO), "--receipt", str(receipt_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("verified: delegate", verified.stdout)

    def test_receipts_contain_aggregates_and_hashes_not_run_ids_or_raw_data(self):
        baseline, candidate = self.comparison()
        serialized = json.dumps(
            coordination.build_comparison_receipt(REPO, baseline, candidate)
        ).lower()
        self.assertNotIn("single-agent-0", serialized)
        for forbidden in self.policy["receipt"]["excludedRawData"]:
            self.assertNotIn(forbidden, serialized)

    def test_tampering_and_evidence_source_drift_are_rejected(self):
        baseline, candidate = self.comparison()
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        tampered = copy.deepcopy(receipt)
        tampered["decision"]["decision"] = "keep-single-agent"
        with self.assertRaisesRegex(coordination.CoordinationError, "tampered"):
            coordination.verify_receipt(REPO, tampered)
        candidate.write_text(
            candidate.read_text(encoding="utf-8").replace('"durationSeconds": 70', '"durationSeconds": 71', 1),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(coordination.CoordinationError, "source-drifted"):
            coordination.verify_receipt(REPO, receipt)

    def test_evidence_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = pathlib.Path(outside_directory) / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(coordination.CoordinationError, "inside the repository"):
                coordination.read_observations(REPO, outside, "single-agent", self.policy)
        target = self.write("target.json", observations("single-agent"))
        link = self.directory / "link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(coordination.CoordinationError, "non-symlink"):
            coordination.read_observations(REPO, link, "single-agent", self.policy)

    def test_receipt_writer_refuses_sealed_source_symlink_and_nonempty_output(self):
        baseline, candidate = self.comparison()
        receipt = coordination.build_comparison_receipt(REPO, baseline, candidate)
        with self.assertRaisesRegex(coordination.CoordinationError, "sealed source"):
            coordination.write_receipt(REPO / "config/coordination-harness.json", receipt, REPO, self.policy)
        occupied = self.directory / "occupied.json"
        occupied.write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(coordination.CoordinationError, "nonempty"):
            coordination.write_receipt(occupied, receipt, REPO, self.policy)
        link = self.directory / "output-link.json"
        link.symlink_to(occupied)
        with self.assertRaisesRegex(coordination.CoordinationError, "non-symlink"):
            coordination.write_receipt(link, receipt, REPO, self.policy)
        outside = tempfile.TemporaryDirectory()
        try:
            parent_link = self.directory / "linked-parent"
            parent_link.symlink_to(pathlib.Path(outside.name), target_is_directory=True)
            with self.assertRaisesRegex(coordination.CoordinationError, "parent must not be a symlink"):
                coordination.write_receipt(parent_link / "receipt.json", receipt, REPO, self.policy)
        finally:
            outside.cleanup()


if __name__ == "__main__":
    unittest.main()
