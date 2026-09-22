import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class FakeRunner:
    def __init__(self, codes):
        self.codes = codes
        self.calls = []

    def run(self, cwd, cmd):
        self.calls.append((str(cwd), cmd))
        return self.codes[cmd]


class PlanNextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_writes_kernel_json_and_cap_is_n_plus_2(self):
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["tags migration exists"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )
        self.assertEqual(d.cap, 4)
        self.assertEqual(d.status, "running")
        self.assertTrue((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_next_is_first_stage_with_deps_met(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

    def test_next_does_not_name_dependent_before_upstream_done(self):
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        d.stages[0].status = "running"
        kernel.save(self.root, d)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")
        self.assertNotEqual(kernel.next_agent(self.root, "tag"), "backend-developer")


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_one(self):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["tags migration exists"], [])],
        )

    def test_prose_verified_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: the model looks right\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaises(kernel.ReportError):
            kernel.report(self.root, "tag", p, runner=FakeRunner({}))

    def test_command_exit_nonzero_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({"php artisan test --filter=TagTest": 1})
        with self.assertRaises(kernel.ReportError):
            kernel.report(self.root, "tag", p, runner=runner)

    def test_command_exit_zero_marks_done(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({"php artisan test --filter=TagTest": 0})
        d = kernel.report(self.root, "tag", p, runner=runner)
        self.assertEqual(d.stages[0].status, "done")
        self.assertEqual(runner.calls[0][1], "php artisan test --filter=TagTest")
        self.assertEqual(
            d.stages[0].verified,
            [{"cmd": "php artisan test --filter=TagTest", "exit": 0}],
        )
        saved = kernel.load(self.root, "tag")
        self.assertEqual(
            saved.stages[0].verified,
            [{"cmd": "php artisan test --filter=TagTest", "exit": 0}],
        )

    def test_not_checked_naming_criterion_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: tags migration exists\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaises(kernel.ReportError):
            kernel.report(
                self.root,
                "tag",
                p,
                runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
            )
        d = kernel.load(self.root, "tag")
        self.assertNotEqual(d.stages[0].status, "done")


class SkipCapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_two(self):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                kernel.StageSpec("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )

    def _write_stage(self, agent, *, did="app/Models/Tag.php"):
        p = self.root / f"docs/delivery/tag/stages/{agent}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"STATUS: done\nDID: {did}\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        return p

    def _ok_report(self, agent="database-developer", *, did="app/Models/Tag.php"):
        p = self._write_stage(agent, did=did)
        return kernel.report(
            self.root,
            "tag",
            p,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )

    def test_done_writer_with_did_on_disk_is_skipped(self):
        self._plan_two()
        did = self.root / "app/Models/Tag.php"
        did.parent.mkdir(parents=True, exist_ok=True)
        did.write_text("<?php\n")
        d = self._ok_report()
        self.assertEqual(d.stages[0].status, "done")
        self.assertEqual(getattr(d.stages[0], "did", []), ["app/Models/Tag.php"])
        self.assertEqual(kernel.next_agent(self.root, "tag"), "backend-developer")

    def test_done_writer_with_missing_did_is_not_skipped(self):
        self._plan_two()
        did = self.root / "app/Models/Tag.php"
        did.parent.mkdir(parents=True, exist_ok=True)
        did.write_text("<?php\n")
        self._ok_report()
        did.unlink()
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

    def test_spawns_at_cap_stops_when_done_when_unmet(self):
        self._plan_two()
        d = None
        for _ in range(4):
            d = self._ok_report()
        self.assertEqual(d.spawns, 4)
        self.assertEqual(d.cap, 4)
        self.assertEqual(d.status, "stopped")
        self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")

    def test_plan_on_running_kernel_does_not_reset_spawns(self):
        self._plan_two()
        self._ok_report()
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                kernel.StageSpec("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )
        self.assertEqual(d.spawns, 1)
        self.assertEqual(d.status, "running")

    def test_plan_on_existing_done_or_stopped_kernel_does_not_reset(self):
        for status in ("done", "stopped"):
            with self.subTest(status=status):
                tmp = tempfile.TemporaryDirectory()
                root = pathlib.Path(tmp.name)
                d = kernel.plan(
                    root=root,
                    name="tag",
                    done_when="POST /api/tags creates a Tag",
                    stages=[
                        kernel.StageSpec(
                            "a", "database-developer", "writer", ["m"], []
                        ),
                        kernel.StageSpec(
                            "b", "backend-developer", "writer", ["h"], ["a"]
                        ),
                    ],
                )
                d.status = status
                d.spawns = 3
                kernel.save(root, d)
                again = kernel.plan(
                    root=root,
                    name="tag",
                    done_when="wiped",
                    stages=[
                        kernel.StageSpec(
                            "z", "frontend-developer", "writer", ["x"], []
                        )
                    ],
                )
                self.assertEqual(again.status, status)
                self.assertEqual(again.spawns, 3)
                self.assertEqual([stage.id for stage in again.stages], ["a", "b"])
                saved = kernel.load(root, "tag")
                self.assertEqual(saved.status, status)
                self.assertEqual(saved.done_when, "POST /api/tags creates a Tag")
                tmp.cleanup()


class ViewsCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_two(self):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                kernel.StageSpec("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )

    def test_plan_writes_close_and_graph_helper_shape(self):
        self._plan_two()
        close = (self.root / "docs/delivery/tag/close.md").read_text()
        for label in ("VERIFIED:", "NOT-CHECKED:", "STATUS:", "BOARD:"):
            self.assertTrue(
                any(line.startswith(label) for line in close.splitlines()),
                f"close.md missing {label} at start of a line",
            )
        status = next(line for line in close.splitlines() if line.startswith("STATUS:"))
        self.assertIn(status.split(":", 1)[1].strip(), ("running", "done", "stopped"))

        graph = (self.root / "docs/delivery/tag/graph.md").read_text()
        for label in ("NODES:", "EDGES:", "PARALLEL:", "ON-FAIL:"):
            self.assertTrue(
                any(line.startswith(label) for line in graph.splitlines()),
                f"graph.md missing {label} at start of a line",
            )
        nodes = next(line for line in graph.splitlines() if line.startswith("NODES:"))
        self.assertIn("database-developer", nodes)
        self.assertIn("backend-developer", nodes)

    def test_report_rewrites_close_helper_shape(self):
        self._plan_two()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        kernel.report(
            self.root,
            "tag",
            p,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )
        close = (self.root / "docs/delivery/tag/close.md").read_text()
        for label in ("VERIFIED:", "NOT-CHECKED:", "STATUS:", "BOARD:"):
            self.assertTrue(
                any(line.startswith(label) for line in close.splitlines()),
                f"close.md missing {label} at start of a line",
            )
        status = next(line for line in close.splitlines() if line.startswith("STATUS:"))
        self.assertIn(status.split(":", 1)[1].strip(), ("running", "done", "stopped"))

    def test_cli_next_prints_agent_or_stop(self):
        self._plan_two()
        guild = REPO / "scripts/guild-kernel/guild.py"
        proc = subprocess.run(
            [sys.executable, str(guild), "next", "--root", str(self.root), "--name", "tag"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "database-developer")

        d = kernel.load(self.root, "tag")
        d.status = "stopped"
        kernel.save(self.root, d)
        proc = subprocess.run(
            [sys.executable, str(guild), "next", "--root", str(self.root), "--name", "tag"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "STOP")

    def test_cli_stage_carries_success_criteria(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(guild),
                "plan",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--done-when",
                "POST /api/tags creates a Tag",
                "--stage",
                "a,database-developer,writer,,tags migration exists|Tag model",
                "--stage",
                "b,backend-developer,writer,a,Tag HTTP",
                "--stage",
                "c,qa-engineer,reviewer,b,Pest covers Tag",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = kernel.load(self.root, "tag")
        self.assertEqual(
            d.stages[0].success_criteria, ["tags migration exists", "Tag model"]
        )
        self.assertEqual(d.stages[0].depends_on, [])
        self.assertEqual(d.stages[1].success_criteria, ["Tag HTTP"])
        self.assertEqual(d.stages[1].depends_on, ["a"])
        self.assertEqual(d.stages[2].success_criteria, ["Pest covers Tag"])
        self.assertEqual(d.stages[2].depends_on, ["b"])

    def test_cli_stage_too_few_fields_is_usage_error(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
        help_form = "id,agent,role[,dep+dep][,criterion|criterion]"
        for stage in ("a", ""):
            with self.subTest(stage=stage):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(guild),
                        "plan",
                        "--root",
                        str(self.root),
                        "--name",
                        "tag",
                        "--stage",
                        stage,
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                combined = proc.stderr + proc.stdout
                self.assertNotIn("list index out of range", combined)
                self.assertIn(help_form, combined)

    def test_cli_stage_joins_criteria_fields_past_commas(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(guild),
                "plan",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--done-when",
                "POST /api/tags creates a Tag",
                "--stage",
                "a,database-developer,writer,,POST /api/tags creates a Tag, returns 201",
                "--stage",
                "b,backend-developer,writer,a,hello, world|other",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = kernel.load(self.root, "tag")
        self.assertEqual(
            d.stages[0].success_criteria,
            ["POST /api/tags creates a Tag, returns 201"],
        )
        self.assertEqual(d.stages[1].success_criteria, ["hello, world", "other"])


class DorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_rejects_empty_done_when(self):
        with self.assertRaises(kernel.PlanError):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="",
                stages=[
                    kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                ],
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_rejects_stage_without_criteria(self):
        with self.assertRaises(kernel.PlanError):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="POST /api/tags creates a Tag",
                stages=[
                    kernel.StageSpec("a", "database-developer", "writer", [], []),
                ],
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())


if __name__ == "__main__":
    unittest.main()
