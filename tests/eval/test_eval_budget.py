import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_eval_budget", ROOT / "scripts" / "check-eval-budget.py"
)
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class EvalBudgetTest(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "cases": {
                "feature": {
                    "max_seconds": 10,
                    "max_tokens": 100,
                    "max_usd": 1.0,
                }
            }
        }

    def cost(self, *, tokens=100, usd=1.0):
        return {
            "billed": {"usd": usd},
            "attributed": {"total": {"tokens": tokens}},
        }

    def test_at_ceiling_passes(self):
        self.assertEqual(
            budget.evaluate("feature", 10, self.baseline, self.cost()), []
        )

    def test_each_breach_fails(self):
        failures = budget.evaluate(
            "feature", 11, self.baseline, self.cost(tokens=101, usd=1.01)
        )
        self.assertEqual(len(failures), 3)

    def test_missing_cost_fails_closed(self):
        failures = budget.evaluate("feature", 1, self.baseline, None)
        self.assertIn("cost summary missing", failures[0])

    def test_parallel_mode_can_ignore_duration_but_not_spend(self):
        failures = budget.evaluate(
            "feature",
            100,
            self.baseline,
            self.cost(usd=1.01),
            check_duration=False,
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("cost ceiling", failures[0])


if __name__ == "__main__":
    unittest.main()
