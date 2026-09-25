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
    "outcome_benchmark", REPO / "scripts" / "outcome-benchmark.py"
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class OutcomeBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "config").mkdir()
        (self.root / "config/benchmark-harness.json").write_text(
            (REPO / "config/benchmark-harness.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.folder = self.root / "docs/delivery/perf/benchmarks"
        self.folder.mkdir(parents=True)
        self.baseline_path = self.folder / "baseline.json"
        self.candidate_path = self.folder / "candidate.json"

    def tearDown(self):
        self.tmp.cleanup()

    def scenario(self, *, objective="query-count"):
        return {
            "id": "orders-index",
            "version": 1,
            "kind": "http",
            "target": "GET /api/orders",
            "objective": objective,
            "datasetHash": "a" * 64,
            "datasetRows": 10000,
            "runtimeHash": "b" * 64,
            "databaseMode": "read-only",
            "warmupRuns": 2,
        }

    def capture(
        self,
        *,
        objective="query-count",
        queries=40,
        latency=100.0,
        response_hash=None,
        writes=0,
        runs=7,
    ):
        return {
            "schemaVersion": 1,
            "scenario": self.scenario(objective=objective),
            "runs": [
                {
                    "queryCount": queries,
                    "writeQueryCount": writes,
                    "latencyMs": latency + index / 10,
                    "status": "http:200",
                    "responseHash": response_hash or "c" * 64,
                    "databaseHash": "d" * 64,
                    "eventsHash": "e" * 64,
                    "jobsHash": "f" * 64,
                }
                for index in range(runs)
            ],
        }

    def write_pair(self, baseline=None, candidate=None):
        self.baseline_path.write_text(
            json.dumps(baseline or self.capture()), encoding="utf-8"
        )
        self.candidate_path.write_text(
            json.dumps(candidate or self.capture(queries=20, latency=102)),
            encoding="utf-8",
        )

    def compare(self):
        return benchmark.compare(
            self.root,
            "docs/delivery/perf/benchmarks/baseline.json",
            "docs/delivery/perf/benchmarks/candidate.json",
            created_at="2026-09-25T12:00:00+00:00",
        )

    def test_query_objective_passes_only_with_equivalence_and_reduction(self):
        self.write_pair()

        receipt = self.compare()

        self.assertEqual(receipt["verdict"], "pass")
        self.assertTrue(receipt["comparison"]["behaviorEquivalent"])
        self.assertEqual(receipt["comparison"]["queryReductionCount"], 20.0)
        self.assertEqual(receipt["comparison"]["queryReductionPercent"], 50.0)
        self.assertTrue(receipt["comparison"]["objectivePassed"])
        self.assertRegex(receipt["receiptHash"], r"^[0-9a-f]{64}$")

    def test_behavior_change_fails_even_when_queries_improve(self):
        self.write_pair(
            candidate=self.capture(
                queries=20, latency=90, response_hash="1" * 64
            )
        )

        receipt = self.compare()

        self.assertEqual(receipt["verdict"], "fail")
        self.assertIn("observable behavior changed", receipt["failures"])

    def test_query_objective_fails_without_query_reduction(self):
        self.write_pair(candidate=self.capture(queries=40, latency=90))

        receipt = self.compare()

        self.assertEqual(receipt["verdict"], "fail")
        self.assertIn(
            "query reduction threshold was not met", receipt["failures"]
        )

    def test_latency_objective_requires_p95_improvement_without_more_queries(self):
        self.write_pair(
            baseline=self.capture(objective="latency", queries=40, latency=100),
            candidate=self.capture(objective="latency", queries=40, latency=90),
        )
        self.assertEqual(self.compare()["verdict"], "pass")

        self.write_pair(
            baseline=self.capture(objective="latency", queries=40, latency=100),
            candidate=self.capture(objective="latency", queries=41, latency=90),
        )
        receipt = self.compare()
        self.assertEqual(receipt["verdict"], "fail")
        self.assertIn(
            "query p95 increased for a latency objective", receipt["failures"]
        )

    def test_capture_rejects_writes_and_too_few_runs(self):
        config = benchmark.load_config(self.root)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "database write"):
            benchmark.validate_capture(
                self.capture(writes=1), config, "candidate"
            )
        with self.assertRaisesRegex(benchmark.BenchmarkError, "measured runs"):
            benchmark.validate_capture(
                self.capture(runs=6), config, "candidate"
            )

    def test_comparison_rejects_different_dataset_or_runtime(self):
        candidate = self.capture(queries=20)
        candidate["scenario"]["datasetHash"] = "9" * 64
        self.write_pair(candidate=candidate)

        with self.assertRaisesRegex(benchmark.BenchmarkError, "identical scenario"):
            self.compare()

    def test_verify_recomputes_receipt_and_source_hashes(self):
        self.write_pair()
        receipt = self.compare()
        receipt_path = self.folder / "receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        verified = benchmark.verify(
            self.root, "docs/delivery/perf/benchmarks/receipt.json"
        )
        self.assertEqual(verified["receiptHash"], receipt["receiptHash"])

        changed = self.capture(queries=19, latency=102)
        self.candidate_path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "source hash changed"):
            benchmark.verify(
                self.root, "docs/delivery/perf/benchmarks/receipt.json"
            )

    def test_verify_rejects_tampered_or_failed_receipt(self):
        self.write_pair()
        receipt = self.compare()
        receipt_path = self.folder / "receipt.json"
        tampered = copy.deepcopy(receipt)
        tampered["candidate"]["queryMedian"] = 0
        receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "hash"):
            benchmark.verify(
                self.root, "docs/delivery/perf/benchmarks/receipt.json"
            )

        self.write_pair(candidate=self.capture(queries=40, latency=90))
        failed = self.compare()
        receipt_path.write_text(json.dumps(failed), encoding="utf-8")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "verdict is fail"):
            benchmark.verify(
                self.root, "docs/delivery/perf/benchmarks/receipt.json"
            )

    def test_cli_writes_and_verifies_receipt(self):
        self.write_pair()
        cli = REPO / "scripts/outcome-benchmark.py"
        output = "docs/delivery/perf/benchmarks/receipt.json"
        compared = subprocess.run(
            [
                sys.executable,
                str(cli),
                "compare",
                "--root",
                str(self.root),
                "--baseline",
                "docs/delivery/perf/benchmarks/baseline.json",
                "--candidate",
                "docs/delivery/perf/benchmarks/candidate.json",
                "--output",
                output,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(compared.returncode, 0, compared.stderr)
        verified = subprocess.run(
            [
                sys.executable,
                str(cli),
                "verify",
                "--root",
                str(self.root),
                output,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["status"], "verified")

    def test_cli_rejects_output_outside_delivery_artifacts(self):
        self.write_pair()
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/outcome-benchmark.py"),
                "compare",
                "--root",
                str(self.root),
                "--baseline",
                "docs/delivery/perf/benchmarks/baseline.json",
                "--candidate",
                "docs/delivery/perf/benchmarks/candidate.json",
                "--output",
                "../outside.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root.parent / "outside.json").exists())

    def test_cli_rejects_source_outside_delivery_artifacts(self):
        self.write_pair()
        outside = self.root / "baseline.json"
        outside.write_text(self.baseline_path.read_text(encoding="utf-8"))
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/outcome-benchmark.py"),
                "compare",
                "--root",
                str(self.root),
                "--baseline",
                "baseline.json",
                "--candidate",
                "docs/delivery/perf/benchmarks/candidate.json",
                "--output",
                "docs/delivery/perf/benchmarks/receipt.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("under docs/delivery", result.stderr)

    def test_cli_refuses_to_overwrite_a_source_capture(self):
        self.write_pair()
        original = self.baseline_path.read_text(encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/outcome-benchmark.py"),
                "compare",
                "--root",
                str(self.root),
                "--baseline",
                "docs/delivery/perf/benchmarks/baseline.json",
                "--candidate",
                "docs/delivery/perf/benchmarks/candidate.json",
                "--output",
                "docs/delivery/perf/benchmarks/baseline.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.baseline_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
