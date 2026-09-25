import json
import pathlib
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import guild  # noqa: E402
import kernel  # noqa: E402


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, cwd, argv):
        self.calls.append(list(argv))
        return 0


class KernelBenchmarkPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        artifact = self.root / "app/Http/TagController.php"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("<?php\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, *, benchmarks=None):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="tag endpoint is faster without behavior changes",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["queries are lower", "response is unchanged"],
                    [],
                    owned_paths=["app/Http"],
                    criterion_ids=["queries-lower", "response-unchanged"],
                    benchmark_criteria=(
                        ["queries-lower"] if benchmarks is None else benchmarks
                    ),
                )
            ],
        )

    def prepare_report(self, verification_lines):
        self.plan()
        kernel.claim_stage(self.root, "tag", "backend")
        kernel.record_stage_usage(
            self.root,
            "backend-developer",
            {
                "seconds": 0,
                "tool_calls": 0,
                "turns": 0,
                "tokens": 0,
                "cost_usd": 0,
            },
        )
        report = self.root / "docs/delivery/tag/stages/backend-developer.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "STATUS: done\n"
            "DID: app/Http/TagController.php\n"
            + "".join(f"VERIFIED: {line}\n" for line in verification_lines)
            + "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n",
            encoding="utf-8",
        )
        return report

    @staticmethod
    def verification(criterion, runner, args):
        return json.dumps(
            {"criterion": criterion, "runner": runner, "args": args},
            separators=(",", ":"),
        )

    def test_plan_persists_benchmark_requirement_on_criterion(self):
        delivery = self.plan()
        self.assertEqual(delivery.stages[0].benchmark_criteria, ["queries-lower"])
        rows = kernel.criterion_rows_for_stage(delivery.stages[0])
        self.assertEqual(
            [row["benchmarkRequired"] for row in rows],
            [True, False],
        )

    def test_plan_rejects_invalid_benchmark_criteria(self):
        for index, criteria in enumerate(
            (["queries-lower", "queries-lower"], ["not-a-criterion"], "queries-lower")
        ):
            with self.subTest(criteria=criteria), self.assertRaises(kernel.PlanError):
                self.root = pathlib.Path(self.tmp.name) / str(index)
                self.plan(benchmarks=criteria)

    def test_benchmark_criterion_rejects_non_benchmark_runner_before_execution(self):
        report = self.prepare_report(
            [
                self.verification(
                    "queries-lower", "file-exists", ["app/Http/TagController.php"]
                ),
                self.verification(
                    "response-unchanged",
                    "file-exists",
                    ["app/Http/TagController.php"],
                ),
            ]
        )
        runner = FakeRunner()
        with self.assertRaisesRegex(kernel.ReportError, "outcome-benchmark"):
            kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_non_benchmark_criterion_rejects_benchmark_runner(self):
        report = self.prepare_report(
            [
                self.verification(
                    "queries-lower",
                    "outcome-benchmark",
                    ["docs/delivery/perf/benchmarks/receipt.json"],
                ),
                self.verification(
                    "response-unchanged",
                    "outcome-benchmark",
                    ["docs/delivery/perf/benchmarks/receipt.json"],
                ),
            ]
        )
        runner = FakeRunner()
        with self.assertRaisesRegex(kernel.ReportError, "not declared"):
            kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_passing_receipt_is_executed_with_literal_path_argument(self):
        receipt = self.root / "docs/delivery/perf/benchmarks/receipt.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")
        report = self.prepare_report(
            [
                self.verification(
                    "queries-lower",
                    "outcome-benchmark",
                    ["docs/delivery/perf/benchmarks/receipt.json"],
                ),
                self.verification(
                    "response-unchanged",
                    "file-exists",
                    ["app/Http/TagController.php"],
                ),
            ]
        )
        runner = FakeRunner()
        delivery = kernel.report(self.root, "tag", report, runner=runner)
        self.assertEqual(delivery.stages[0].status, "done")
        self.assertEqual(
            runner.calls,
            [[
                "python3",
                "scripts/outcome-benchmark.py",
                "verify",
                "--root",
                ".",
                "--",
                "docs/delivery/perf/benchmarks/receipt.json",
            ]],
        )

    def test_stage_json_accepts_benchmark_criteria(self):
        stage = guild._stages_from_args(
            [],
            [json.dumps({
                "id": "backend",
                "agent": "backend-developer",
                "role": "writer",
                "success_criteria": ["queries are lower"],
                "criterion_ids": ["queries-lower"],
                "benchmark_criteria": ["queries-lower"],
                "depends_on": [],
                "owned_paths": ["app/Http"],
            })],
        )[0]
        self.assertEqual(stage.benchmark_criteria, ["queries-lower"])


if __name__ == "__main__":
    unittest.main()
