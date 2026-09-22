import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import guild  # noqa: E402
import kernel  # noqa: E402


class GuildCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_with_issue_passes_issue_and_runner(self):
        recorded = {}

        def fake_plan(**kwargs):
            recorded.update(kwargs)
            return types.SimpleNamespace(rules_printed=[])

        with mock.patch.object(kernel, "plan", side_effect=fake_plan):
            code = guild.main(
                [
                    "plan",
                    "--root",
                    str(self.root),
                    "--name",
                    "tag",
                    "--done-when",
                    "POST /api/tags creates a Tag",
                    "--stage",
                    "a,database-developer,writer,,m",
                    "--issue",
                    "42",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(recorded["issue"], 42)
        self.assertIsNotNone(recorded["runner"])

    def test_pr_records_number(self):
        recorded = {}

        def fake_record_pr(root, name, number, runner):
            recorded["root"] = root
            recorded["name"] = name
            recorded["number"] = number
            recorded["runner"] = runner
            return None

        with mock.patch.object(kernel, "record_pr", side_effect=fake_record_pr):
            code = guild.main(
                [
                    "pr",
                    "--root",
                    str(self.root),
                    "--name",
                    "tag",
                    "--number",
                    "17",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(recorded["number"], 17)
        self.assertIsNotNone(recorded["runner"])

    def test_ingest_check_records_kind_stage_check(self):
        recorded = {}

        def fake_ingest(root, name, **kwargs):
            recorded.update(kwargs)
            recorded["root"] = root
            recorded["name"] = name
            return None

        with mock.patch.object(kernel, "ingest", side_effect=fake_ingest):
            code = guild.main(
                [
                    "ingest",
                    "--root",
                    str(self.root),
                    "--name",
                    "tag",
                    "--kind",
                    "check",
                    "--stage",
                    "a",
                    "--check",
                    "pint",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(recorded["kind"], "check")
        self.assertEqual(recorded["stage_id"], "a")
        self.assertEqual(recorded["check"], "pint")
        self.assertIsNotNone(recorded["runner"])

    def test_ingest_review_records_kind_and_comment(self):
        recorded = {}

        def fake_ingest(root, name, **kwargs):
            recorded.update(kwargs)
            recorded["root"] = root
            recorded["name"] = name
            return None

        with mock.patch.object(kernel, "ingest", side_effect=fake_ingest):
            code = guild.main(
                [
                    "ingest",
                    "--root",
                    str(self.root),
                    "--name",
                    "tag",
                    "--kind",
                    "review",
                    "--stage",
                    "a",
                    "--comment",
                    "99",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(recorded["kind"], "review")
        self.assertEqual(recorded["comment"], "99")
        self.assertIsNotNone(recorded["runner"])

    def test_process_runner_capture_returns_stdout(self):
        code, out = guild.ProcessRunner().capture(
            self.root, "python3 -c 'print(123)'"
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "123")


if __name__ == "__main__":
    unittest.main()
