from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "scripts" / "evaluation-harness.py"
SPEC = importlib.util.spec_from_file_location("evaluation_harness_under_test", MODULE_PATH)
evaluation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(evaluation)


class EvaluationHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        for directory in ("config", "tests/eval", "scripts"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        for relative in (
            "config/evaluation-harness.json",
            "config/evaluation-cases.json",
            "tests/eval/baseline.json",
            "tests/eval/run-evals.sh",
        ):
            destination = self.root / relative
            destination.write_text((REPO / relative).read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def evidence(self, label: str, *, usd=0.5, tokens=1_000_000, tools=10, checks=None):
        directory = self.root / "tests" / "eval" / "results" / label
        directory.mkdir(parents=True)
        checks = checks or [
            "  PASS  output: eager loading",
            "  PASS  output: withCount",
            "  PASS  output: names file",
            "  PASS  output: comments relation",
        ]
        paths = {
            "checks": directory / "n-plus-one.checks.txt",
            "cost": directory / "n-plus-one.cost.json",
            "status": directory / "n-plus-one.status.txt",
            "diff": directory / "n-plus-one.diff.patch",
        }
        paths["checks"].write_text("\n".join(checks) + "\n", encoding="utf-8")
        paths["cost"].write_text(json.dumps({
            "billed": {"usd": usd},
            "attributed": {"total": {"tokens": tokens}},
            "tools": {"Read": tools},
        }), encoding="utf-8")
        paths["status"].write_text(" M app/Http/Controllers/PostController.php\n", encoding="utf-8")
        paths["diff"].write_text("diff --git a/a b/a\n", encoding="utf-8")
        return {key: value.relative_to(self.root).as_posix() for key, value in paths.items()}

    def receipt(self, label="base", *, duration=100, exit_code=0, timed_out=False, judge=None, **evidence):
        paths = self.evidence(label, **evidence)
        return evaluation.create_receipt(
            self.root,
            case_id="n-plus-one",
            run_id=label,
            duration=duration,
            exit_code=exit_code,
            timed_out=timed_out,
            ignore_duration=False,
            checks_path=paths["checks"],
            cost_path=paths["cost"],
            status_path=paths["status"],
            diff_path=paths["diff"],
            judge_path=judge,
        )

    def test_contract_validates_all_registered_cases(self):
        result = evaluation.validate(self.root)
        self.assertEqual(11, result["cases"])
        self.assertEqual(5, result["defaultCases"])
        self.assertEqual(6, result["optInCases"])

    def test_registry_and_shell_case_sets_must_match(self):
        shell = self.root / "tests/eval/run-evals.sh"
        shell.write_text(shell.read_text().replace("ALL_CASES=(n-plus-one policy action tests hygiene)", "ALL_CASES=(n-plus-one policy)"))
        with self.assertRaisesRegex(evaluation.EvaluationError, "differ from registry"):
            evaluation.validate(self.root)

    def test_passing_receipt_binds_sources_and_all_metrics(self):
        receipt = self.receipt()
        self.assertEqual("pass", receipt["verdict"])
        self.assertEqual(4, receipt["deterministic"]["passCount"])
        self.assertEqual({"durationSeconds", "tokens", "billedUsd", "toolCalls"}, set(receipt["metrics"]))
        verified = evaluation.verify_receipt(self.root, receipt, check_sources=True)
        self.assertEqual("valid", verified["status"])

    def test_advisory_judge_cannot_flip_deterministic_pass(self):
        paths = self.evidence("judge")
        judge = self.root / "tests/eval/results/judge/n-plus-one.judge.json"
        judge.write_text('{"verdict":"fail","score":1}\n', encoding="utf-8")
        receipt = evaluation.create_receipt(
            self.root, case_id="n-plus-one", run_id="judge", duration=100,
            exit_code=0, timed_out=False, ignore_duration=False,
            checks_path=paths["checks"], cost_path=paths["cost"],
            status_path=paths["status"], diff_path=paths["diff"],
            judge_path=judge.relative_to(self.root).as_posix(),
        )
        self.assertEqual("pass", receipt["verdict"])
        self.assertEqual("advisory-only", receipt["judge"]["role"])
        self.assertEqual("fail", receipt["judge"]["verdict"])

    def test_failed_check_execution_and_budget_each_fail_closed(self):
        failed_check = self.receipt("check-fail", checks=[
            "  PASS  one", "  PASS  two", "  PASS  three", "  FAIL  four",
        ])
        self.assertEqual("fail", failed_check["verdict"])
        self.assertEqual("fail", failed_check["deterministic"]["verdict"])
        execution = self.receipt("execution-fail", exit_code=7)
        self.assertEqual("fail", execution["verdict"])
        budget = self.receipt("budget-fail", usd=2.41)
        self.assertEqual("fail", budget["verdict"])
        self.assertEqual("billedUsd", budget["budget"]["breaches"][0]["metric"])

    def test_minimum_check_coverage_cannot_be_reduced(self):
        receipt = self.receipt("short", checks=["  PASS  one", "  PASS  two", "  PASS  three"])
        self.assertFalse(receipt["deterministic"]["minimumMet"])
        self.assertEqual("fail", receipt["verdict"])

    def test_receipt_hash_and_source_drift_are_detected(self):
        receipt = self.receipt("tamper")
        altered = json.loads(json.dumps(receipt))
        altered["metrics"]["billedUsd"] = 0.01
        with self.assertRaisesRegex(evaluation.EvaluationError, "receiptHash"):
            evaluation.verify_receipt(self.root, altered, check_sources=False)
        expanded = json.loads(json.dumps(receipt))
        expanded["rawTranscript"] = "secret"
        expanded.pop("receiptHash")
        expanded["receiptHash"] = evaluation.digest_json(expanded)
        with self.assertRaisesRegex(evaluation.EvaluationError, "schema 1"):
            evaluation.verify_receipt(self.root, expanded, check_sources=False)
        forged = json.loads(json.dumps(receipt))
        forged["metrics"]["billedUsd"] = 0.01
        forged.pop("receiptHash")
        forged["receiptHash"] = evaluation.digest_json(forged)
        with self.assertRaisesRegex(evaluation.EvaluationError, "semantics"):
            evaluation.verify_receipt(self.root, forged, check_sources=True)
        source = self.root / receipt["artifacts"][0]["path"]
        source.write_text("  PASS  changed\n", encoding="utf-8")
        with self.assertRaisesRegex(evaluation.EvaluationError, "drifted"):
            evaluation.verify_receipt(self.root, receipt, check_sources=True)

    def test_symlinked_evidence_is_rejected(self):
        paths = self.evidence("symlink")
        outside = self.root / "outside.txt"
        outside.write_text("  PASS  outside\n", encoding="utf-8")
        checks = self.root / paths["checks"]
        checks.unlink()
        checks.symlink_to(outside)
        with self.assertRaisesRegex(evaluation.EvaluationError, "symlink"):
            evaluation.create_receipt(
                self.root, case_id="n-plus-one", run_id="symlink", duration=100,
                exit_code=0, timed_out=False, ignore_duration=False,
                checks_path=paths["checks"], cost_path=paths["cost"],
                status_path=paths["status"], diff_path=paths["diff"], judge_path=None,
            )

    def test_receipt_contains_hashes_not_raw_transcripts_or_diffs(self):
        encoded = json.dumps(self.receipt("privacy"))
        for forbidden in ("rawTranscript", "assistantText", "toolInputs", "diff --git"):
            self.assertNotIn(forbidden, encoded)

    def test_compare_passes_equal_quality_and_flags_material_regression(self):
        baseline = self.receipt("compare-before", duration=100, usd=0.5, tokens=1_000_000, tools=10)
        same = self.receipt("compare-same", duration=110, usd=0.55, tokens=1_050_000, tools=11)
        self.assertEqual("pass", evaluation.compare_receipts(self.root, baseline, same)["status"])
        candidate = self.receipt("compare-after", duration=200, usd=1.2, tokens=2_000_000, tools=20)
        result = evaluation.compare_receipts(self.root, baseline, candidate)
        self.assertEqual("regressed", result["status"])
        self.assertEqual(
            {"durationSeconds", "tokens", "billedUsd", "toolCalls"},
            {item["metric"] for item in result["regressions"] if item["type"] == "metric"},
        )

    def test_compare_rejects_failing_baseline_and_failing_candidate(self):
        bad_baseline = self.receipt("bad-before", exit_code=1)
        good = self.receipt("good-after")
        with self.assertRaisesRegex(evaluation.EvaluationError, "baseline receipt must pass"):
            evaluation.compare_receipts(self.root, bad_baseline, good)
        result = evaluation.compare_receipts(self.root, good, bad_baseline)
        self.assertIn("verdict", {item["type"] for item in result["regressions"]})

    def test_cli_validate_receipt_verify_and_compare_exit_codes(self):
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "validate", "--root", str(self.root)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("valid", json.loads(result.stdout)["status"])

        before = self.receipt("cli-before")
        after = self.receipt("cli-after", duration=200, usd=1.2, tokens=2_000_000, tools=20)
        before_path = self.root / "before.json"
        after_path = self.root / "after.json"
        before_path.write_text(json.dumps(before), encoding="utf-8")
        after_path.write_text(json.dumps(after), encoding="utf-8")
        compared = subprocess.run(
            [sys.executable, str(MODULE_PATH), "compare", "--root", str(self.root),
             "--baseline", str(before_path), "--candidate", str(after_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(1, compared.returncode)
        self.assertEqual("regressed", json.loads(compared.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
