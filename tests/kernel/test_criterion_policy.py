import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, cwd, argv):
        self.calls.append(list(argv))
        return 0


class CriterionPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.artifact = self.root / "app/Tag.php"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text("<?php\n")

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, *, ids=None):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="tag endpoint is complete",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["controller exists", "authorization is preserved"],
                    [],
                    owned_paths=["app"],
                    criterion_ids=ids or [],
                )
            ],
        )

    def report(self, criteria):
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        verified = "".join(
            "VERIFIED: "
            + json.dumps(
                {
                    "criterion": criterion,
                    "runner": "file-exists",
                    "args": ["app/Tag.php"],
                },
                separators=(",", ":"),
            )
            + "\n"
            for criterion in criteria
        )
        path.write_text(
            "STATUS: done\nDID: app/Tag.php\n"
            + verified
            + "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        return kernel.report(self.root, "tag", path, runner=FakeRunner())

    def test_plan_persists_stable_default_and_custom_ids(self):
        delivery = self.plan()
        self.assertEqual(
            delivery.stages[0].criterion_ids,
            ["criterion-1", "criterion-2"],
        )
        self.assertIn("criterion-1:·", kernel.board_line(delivery))

        other = pathlib.Path(self.tmp.name) / "other"
        custom = kernel.plan(
            root=other,
            name="tag",
            done_when="done",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["one", "two"],
                    [],
                    owned_paths=["app"],
                    criterion_ids=["query-count", "response-contract"],
                )
            ],
        )
        self.assertEqual(
            custom.stages[0].criterion_ids,
            ["query-count", "response-contract"],
        )

    def test_plan_rejects_invalid_duplicate_or_misaligned_ids(self):
        for index, ids in enumerate(
            (["Bad", "good"], ["same", "same"], ["only-one"])
        ):
            with self.subTest(ids=ids), self.assertRaises(kernel.PlanError):
                kernel.plan(
                    root=self.root / str(index),
                    name="tag",
                    done_when="done",
                    stages=[
                        kernel.StageSpec(
                            "backend",
                            "backend-developer",
                            "writer",
                            ["one", "two"],
                            [],
                            owned_paths=["app"],
                            criterion_ids=ids,
                        )
                    ],
                )

    def test_one_passing_record_cannot_complete_two_criteria(self):
        self.plan(ids=["controller", "authorization"])
        with self.assertRaisesRegex(kernel.ReportError, "authorization"):
            self.report(["controller"])
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "queued")

    def test_every_criterion_with_passing_evidence_completes_stage(self):
        self.plan(ids=["controller", "authorization"])
        delivery = self.report(["controller", "authorization"])
        stage = delivery.stages[0]
        self.assertEqual(stage.status, "done")
        self.assertTrue(kernel._criterion_coverage_complete(stage))
        self.assertIn("controller:✓", kernel.board_line(delivery))
        self.assertIn("authorization:✓", kernel.board_line(delivery))

    def test_unknown_criterion_is_rejected_before_external_runner(self):
        self.plan(ids=["controller", "authorization"])
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Tag.php\n"
            'VERIFIED: {"criterion":"invented","runner":"artisan-test",'
            '"args":["--filter=TagTest"]}\n'
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner()
        with self.assertRaisesRegex(kernel.ReportError, "unknown criterion"):
            kernel.report(self.root, "tag", path, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_user_waiver_is_durable_and_completes_missing_criterion(self):
        self.plan(ids=["controller", "authorization"])
        with self.assertRaisesRegex(kernel.PlanError, "only be granted by the user"):
            kernel.waive_stage_criterion(
                self.root,
                "tag",
                "backend",
                "authorization",
                "environment cannot exercise SSO",
                waived_by="agent",
            )
        waiver = kernel.waive_stage_criterion(
            self.root,
            "tag",
            "backend",
            "authorization",
            "environment cannot exercise SSO",
        )
        self.assertEqual(waiver["by"], "user")
        self.assertTrue(waiver["at"])
        delivery = self.report(["controller"])
        rows = kernel.criterion_rows_for_stage(delivery.stages[0])
        self.assertEqual([row["status"] for row in rows], ["verified", "waived"])
        self.assertIn("authorization:~", kernel.board_line(delivery))

    def test_criterion_cli_lists_and_waives(self):
        self.plan(ids=["controller", "authorization"])
        cli = REPO / "scripts/guild-kernel/guild.py"
        waived = subprocess.run(
            [
                sys.executable,
                str(cli),
                "criterion",
                "waive",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--stage",
                "backend",
                "--criterion",
                "authorization",
                "--reason",
                "SSO fixture unavailable",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("WAIVED: backend authorization by user", waived.stdout)
        listed = subprocess.run(
            [
                sys.executable,
                str(cli),
                "criterion",
                "list",
                "--root",
                str(self.root),
                "--name",
                "tag",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = json.loads(listed.stdout)[0]["criteria"]
        self.assertEqual(rows[1]["status"], "waived")
        self.assertEqual(rows[1]["waiver"]["reason"], "SSO fixture unavailable")

    def test_legacy_completed_stage_remains_complete(self):
        self.plan()
        state_path = self.root / "docs/delivery/tag/kernel.json"
        state = json.loads(state_path.read_text())
        stage = state["stages"][0]
        stage.pop("criterion_ids")
        stage.pop("criterion_waivers")
        stage.pop("criterion_contract")
        stage["status"] = "done"
        stage["verified"] = [
            {"runner": "file-exists", "args": ["app/Tag.php"], "exit": 0}
        ]
        state["status"] = "done"
        state_path.write_text(json.dumps(state))
        loaded = kernel.load(self.root, "tag")
        self.assertTrue(kernel._criterion_coverage_complete(loaded.stages[0]))
        self.assertTrue(kernel._dod_met(loaded))


class CriterionHookTest(unittest.TestCase):
    def test_subagent_cannot_waive_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = REPO / "scripts" / "enforce-kernel-approvals.sh"
            payload = {
                "hook_event_name": "PreToolUse",
                "agent_type": "laravel-team:backend-developer",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python3 scripts/guild-kernel/guild.py criterion waive "
                    "--root . --name tag --stage backend --criterion auth "
                    "--reason nope"
                },
            }
            result = subprocess.run(
                [str(hook)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env={**os.environ, "CLAUDE_PROJECT_DIR": tmp},
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("criterion waivers", result.stderr)


if __name__ == "__main__":
    unittest.main()
