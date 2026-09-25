import json
import pathlib
import sys
import tempfile
import threading
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


COVERED_ATTACKS = {
    "ADV-001", "ADV-002", "ADV-003", "ADV-004", "ADV-005", "ADV-006",
    "ADV-007", "ADV-008", "ADV-009", "ADV-010", "ADV-011", "ADV-012",
    "ADV-013", "ADV-014", "ADV-015", "ADV-016",
    "ADV-017", "ADV-018",
}


class NoExecutionRunner:
    def __init__(self):
        self.calls = []

    def run(self, cwd, argv):
        self.calls.append((str(cwd), list(argv)))
        raise AssertionError(f"untrusted verification executed: {argv}")


class EngineeringLoopAdversarialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sandbox = pathlib.Path(self.tmp.name)
        self.root = self.sandbox / "project"
        self.root.mkdir()
        self.outside = self.sandbox / "outside"
        self.outside.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, **overrides):
        values = {
            "id": "backend",
            "agent": "backend-developer",
            "role": "writer",
            "success_criteria": ["endpoint is tested"],
            "depends_on": [],
            "owned_paths": ["app/Http"],
            "approval_categories": [],
            "feedback_checks": ["phpunit"],
            "budget": {},
        }
        values.update(overrides)
        return kernel.StageSpec(**values)

    def plan(self, *, name="tag", stages=None):
        return kernel.plan(
            root=self.root,
            name=name,
            done_when="POST /api/tags creates a Tag",
            stages=stages or [self.stage()],
        )

    def claim_and_measure(self, *, name="tag", stage="backend"):
        kernel.claim_stage(self.root, name, stage)
        agent = next(
            item.agent for item in kernel.load(self.root, name).stages
            if item.id == stage
        )
        kernel.record_stage_usage(
            self.root,
            agent,
            {
                "seconds": 0,
                "tool_calls": 0,
                "turns": 0,
                "tokens": 0,
                "cost_usd": 0,
            },
            event_id=f"completion:{name}:{stage}",
            expected_target=(name, stage),
        )

    def report_text(self, *, runner="file-exists", criterion="criterion-1"):
        artifact = self.root / "app/Http/TagController.php"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("<?php\n", encoding="utf-8")
        verification = json.dumps(
            {
                "criterion": criterion,
                "runner": runner,
                "args": ["app/Http/TagController.php"],
            },
            separators=(",", ":"),
        )
        return (
            "STATUS: done\nDID: app/Http/TagController.php\n"
            f"VERIFIED: {verification}\nNOT-CHECKED: none\n"
            "FLAGS: none\nNEXT: none\n"
        )

    def stage_report(self, text=None):
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or self.report_text(), encoding="utf-8")
        return path

    def test_manifest_has_one_implemented_case_per_attack_id(self):
        manifest = json.loads(
            (REPO / "config/adversarial-harness.json").read_text(encoding="utf-8")
        )
        ids = [case["id"] for case in manifest["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), COVERED_ATTACKS)

    def test_adv_001_delivery_name_traversal_cannot_write_outside_project(self):
        with self.assertRaisesRegex(kernel.PlanError, "delivery name"):
            self.plan(name="../../../outside/escaped")
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_adv_002_delivery_symlink_cannot_redirect_state_outside_project(self):
        delivery_root = self.root / "docs/delivery"
        delivery_root.mkdir(parents=True)
        delivery_root.joinpath("tag").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(kernel.PlanError, "escapes the project"):
            self.plan()
        self.assertFalse((self.outside / "kernel.json").exists())

    def test_adv_003_sprint_id_traversal_cannot_write_outside_project(self):
        with self.assertRaisesRegex(kernel.PlanError, "sprint id"):
            kernel.sprint_start(
                self.root, id="../../../outside/escaped", goal="ship", wip=1
            )
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_adv_004_sprint_symlink_cannot_redirect_state_outside_project(self):
        sprint_root = self.root / "docs/sprints"
        sprint_root.mkdir(parents=True)
        sprint_root.joinpath("3.1").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(kernel.PlanError, "escapes the project"):
            kernel.sprint_start(self.root, id="3.1", goal="ship", wip=1)
        self.assertFalse((self.outside / "sprint.json").exists())

    def test_adv_005_external_report_is_rejected_before_verification(self):
        self.plan()
        self.claim_and_measure()
        attack = self.outside / "backend-developer.md"
        attack.write_text(self.report_text(), encoding="utf-8")
        runner = NoExecutionRunner()
        with self.assertRaisesRegex(kernel.ReportError, "delivery stage directory"):
            kernel.report(self.root, "tag", attack, runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "running")

    def test_adv_006_symlinked_report_is_rejected_before_verification(self):
        self.plan()
        self.claim_and_measure()
        attack = self.outside / "backend-developer.md"
        attack.write_text(self.report_text(), encoding="utf-8")
        report = self.root / "docs/delivery/tag/stages/backend-developer.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.symlink_to(attack)
        runner = NoExecutionRunner()
        with self.assertRaisesRegex(kernel.ReportError, "delivery stage directory"):
            kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "running")

    def test_adv_007_shell_payload_is_rejected_without_execution(self):
        self.plan()
        self.claim_and_measure()
        runner = NoExecutionRunner()
        report = self.stage_report(
            self.report_text(runner="shell").replace(
                '"args":["app/Http/TagController.php"]',
                '"args":["touch","outside/pwned"]',
            )
        )
        with self.assertRaisesRegex(kernel.ReportError, "unknown verification runner"):
            kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertFalse((self.outside / "pwned").exists())

    def test_adv_008_sensitive_stage_cannot_claim_before_approval(self):
        self.plan(
            stages=[
                self.stage(
                    agent="database-developer",
                    owned_paths=["database/migrations"],
                    approval_categories=["destructive migration"],
                )
            ]
        )
        with self.assertRaisesRegex(kernel.PlanError, "requires user approval"):
            kernel.claim_stage(self.root, "tag", "backend")
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "queued")

    def test_adv_009_report_without_completion_telemetry_stays_running(self):
        self.plan()
        kernel.claim_stage(self.root, "tag", "backend")
        report = self.stage_report()
        with self.assertRaisesRegex(kernel.ReportError, "requires budget telemetry"):
            kernel.report(self.root, "tag", report, runner=NoExecutionRunner())
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "running")

    def test_adv_010_budget_terminal_state_returns_no_ready_work(self):
        self.plan(stages=[self.stage(budget={"max_tool_calls": 1})])
        kernel.claim_stage(self.root, "tag", "backend")
        kernel.meter_tool_call(self.root, "backend-developer", event_id="tool:one")
        with self.assertRaisesRegex(kernel.PlanError, "max_tool_calls"):
            kernel.meter_tool_call(self.root, "backend-developer", event_id="tool:two")
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.status, "budget_exceeded")
        self.assertEqual(kernel.ready_stages(self.root, "tag"), [])

    def test_adv_011_repeated_cycle_stops_delivery_and_dispatch(self):
        self.plan()
        kernel.claim_stage(self.root, "tag", "backend")
        signature = kernel.tool_call_signature("Read", {"file_path": "app/Http/X.php"})
        for index in range(2):
            kernel.meter_tool_call(
                self.root,
                "backend-developer",
                event_id=f"tool:{index}",
                tool_name="Read",
                signature=signature,
            )
        with self.assertRaisesRegex(kernel.PlanError, "unproductive"):
            kernel.meter_tool_call(
                self.root,
                "backend-developer",
                event_id="tool:2",
                tool_name="Read",
                signature=signature,
            )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(kernel.ready_stages(self.root, "tag"), [])

    def test_adv_012_retry_event_replay_creates_one_transition(self):
        self.plan()
        self.claim_and_measure()
        kwargs = {
            "source": "verification",
            "reason": "evidence failed",
            "event_id": "verification:one",
        }
        first = kernel.request_retry(self.root, "tag", "backend", **kwargs)
        second = kernel.request_retry(self.root, "tag", "backend", **kwargs)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(first, second)
        self.assertEqual(len(delivery.retry_events), 1)
        self.assertEqual(delivery.stages[0].reopens, 1)

    def test_adv_013_wrong_feedback_owner_assertion_records_nothing(self):
        self.plan(
            stages=[
                self.stage(id="backend", feedback_checks=["phpunit"]),
                self.stage(
                    id="frontend",
                    agent="frontend-developer",
                    owned_paths=["resources/js"],
                    feedback_checks=["eslint"],
                ),
            ]
        )
        payload = {
            "event_id": "check:phpunit:1",
            "external_id": "1",
            "kind": "check",
            "check": "phpunit",
            "summary": "phpunit failed",
            "url": "https://example.test/runs/1",
        }
        with self.assertRaisesRegex(kernel.PlanError, "belongs to stage backend"):
            kernel._record_feedback(
                self.root, "tag", payload, asserted_stage="frontend"
            )
        self.assertEqual(kernel.load(self.root, "tag").feedback_events, [])

    def test_adv_014_concurrent_double_claim_is_atomic(self):
        self.plan()
        barrier = threading.Barrier(2)
        successes = []
        failures = []

        def attack():
            try:
                barrier.wait()
                successes.append(kernel.claim_stage(self.root, "tag", "backend"))
            except kernel.PlanError as exc:
                failures.append(exc)

        threads = [threading.Thread(target=attack) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stage = kernel.load(self.root, "tag").stages[0]
        self.assertEqual((len(successes), len(failures)), (1, 1))
        self.assertEqual(stage.status, "running")
        self.assertEqual(stage.attempts, 1)

    def test_adv_015_stale_report_after_retry_is_rejected_before_verification(self):
        self.plan()
        self.claim_and_measure()
        report = self.stage_report()
        kernel.request_retry(
            self.root,
            "tag",
            "backend",
            source="stage-return",
            reason="incomplete return",
            event_id="stage-return:one",
        )
        runner = NoExecutionRunner()
        with self.assertRaisesRegex(kernel.ReportError, "report requires a claimed"):
            kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "queued")

    def test_adv_016_spoofed_authority_cannot_mutate_state(self):
        self.plan(
            stages=[
                self.stage(
                    approval_categories=["auth"]
                )
            ]
        )
        state = self.root / "docs/delivery/tag/kernel.json"
        before = state.read_bytes()
        attempts = (
            lambda: kernel.approve_stage_action(
                self.root,
                "tag",
                "backend",
                "auth",
                approved_by="agent",
            ),
            lambda: kernel.waive_stage_criterion(
                self.root,
                "tag",
                "backend",
                "criterion-1",
                "trust me",
                waived_by="agent",
            ),
            lambda: kernel.request_retry(
                self.root,
                "tag",
                "backend",
                source="verification",
                reason="self retry",
                event_id="verification:self",
                requested_by="agent",
            ),
        )
        for attempt in attempts:
            with self.subTest(attempt=attempt), self.assertRaises(kernel.PlanError):
                attempt()
            self.assertEqual(state.read_bytes(), before)

    def test_adv_017_lesson_symlink_cannot_redirect_state_outside_project(self):
        docs = self.root / "docs"
        docs.mkdir()
        docs.joinpath("team").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(
            kernel.PlanError, r"lesson (?:lock )?path escapes the project"
        ):
            self.plan()
        self.assertFalse((self.outside / "lessons.json").exists())
        self.assertFalse((self.outside / "lessons.md").exists())

    def test_adv_018_stage_identifier_cannot_inject_trace_lines(self):
        with self.assertRaisesRegex(kernel.PlanError, "stage id"):
            self.plan(stages=[self.stage(id="backend\nSTATUS: done")])
        self.assertFalse(
            (self.root / "docs/delivery/tag/kernel.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
