import json
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


class DodTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_delivery_not_done_when_a_done_stage_lacks_verified_exit_0(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        delivery = kernel.load(self.root, "tag")
        delivery.stages[0].status = "done"
        delivery.stages[0].verified = []
        kernel.save(self.root, delivery)
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Http/Controllers/TagController.php\n"
            "VERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaises(kernel.ReportError):
            kernel.report(
                self.root,
                "tag",
                path,
                runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
            )
        saved = kernel.load(self.root, "tag")
        self.assertNotEqual(saved.status, "done")


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


class SprintStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sprint_start_writes_json_and_helper_view(self):
        sprint = kernel.sprint_start(
            self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2
        )
        self.assertEqual(sprint.status, "running")
        self.assertEqual(sprint.stories, [])
        self.assertTrue((self.root / "docs/sprints/3.1/sprint.json").is_file())
        lines = (self.root / "docs/sprints/3.1/sprint.md").read_text().splitlines()
        for label in ("GOAL:", "WIP:", "BOARD:", "STATUS:"):
            self.assertTrue(any(line.startswith(label) for line in lines), label)

    def test_second_sprint_start_does_not_reset_stories_or_wip(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        sprint = kernel.load_sprint(self.root, "3.1")
        sprint.stories = ["tag"]
        sprint.wip = 9
        kernel.save_sprint(self.root, sprint)
        again = kernel.sprint_start(self.root, id="other", goal="nope", wip=1)
        self.assertEqual(again.id, "3.1")
        self.assertEqual(again.stories, ["tag"])
        self.assertEqual(again.wip, 9)
        self.assertFalse((self.root / "docs/sprints/other/sprint.json").is_file())


class SprintCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.guild = REPO / "scripts/guild-kernel/guild.py"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(self.guild), *args],
            capture_output=True,
            text=True,
        )

    def test_plan_without_done_when_or_criteria_exits_nonzero(self):
        missing_done = self._run(
            "plan",
            "--root",
            str(self.root),
            "--name",
            "tag",
            "--stage",
            "a,database-developer,writer,,migration exists",
        )
        self.assertNotEqual(missing_done.returncode, 0)
        self.assertNotIn("Traceback", missing_done.stderr)
        missing_criteria = self._run(
            "plan",
            "--root",
            str(self.root),
            "--name",
            "tag",
            "--done-when",
            "POST /api/tags creates a Tag",
            "--stage",
            "a,database-developer,writer",
        )
        self.assertNotEqual(missing_criteria.returncode, 0)
        self.assertNotIn("Traceback", missing_criteria.stderr)

    def test_sprint_start_then_board_prints_goal_and_wip(self):
        started = self._run(
            "sprint",
            "start",
            "--root",
            str(self.root),
            "--id",
            "3.1",
            "--goal",
            "SDLC/Scrum kernel",
            "--wip",
            "2",
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        board = self._run(
            "sprint", "board", "--root", str(self.root), "--id", "3.1"
        )
        self.assertEqual(board.returncode, 0, board.stderr)
        self.assertIn("GOAL:", board.stdout)
        self.assertIn("WIP:", board.stdout)

    def test_plan_sprint_attaches(self):
        started = self._run(
            "sprint",
            "start",
            "--root",
            str(self.root),
            "--id",
            "3.1",
            "--goal",
            "SDLC/Scrum kernel",
            "--wip",
            "2",
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        planned = self._run(
            "plan",
            "--root",
            str(self.root),
            "--name",
            "tag",
            "--sprint",
            "3.1",
            "--done-when",
            "POST /api/tags creates a Tag",
            "--stage",
            "a,database-developer,writer,,migration exists",
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.sprint, "3.1")
        self.assertEqual(kernel.load_sprint(self.root, "3.1").stories, ["tag"])


class SprintAttachTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _stages(self):
        return [kernel.StageSpec("a", "database-developer", "writer", ["m"], [])]

    def _plan(self, name="tag", sprint=""):
        return kernel.plan(
            root=self.root,
            name=name,
            done_when="POST /api/tags creates a Tag",
            stages=self._stages(),
            sprint=sprint,
        )

    def test_plan_attaches_named_sprint(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        delivery = self._plan(sprint="3.1")
        self.assertEqual(delivery.sprint, "3.1")
        self.assertEqual(kernel.load_sprint(self.root, "3.1").stories, ["tag"])

    def test_wip_full_rejects_second_plan(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=1)
        self._plan(name="one", sprint="3.1")
        with self.assertRaises(kernel.PlanError):
            self._plan(name="two", sprint="3.1")
        self.assertFalse((self.root / "docs/delivery/two/kernel.json").is_file())

    def test_plan_without_a_running_sprint_stays_solo(self):
        delivery = self._plan()
        self.assertEqual(delivery.sprint, "")
        self.assertTrue((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_attaches_the_single_running_sprint(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        delivery = self._plan()
        self.assertEqual(delivery.sprint, "3.1")
        self.assertIn("tag", kernel.load_sprint(self.root, "3.1").stories)

    def test_two_running_sprints_reject_plan(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        kernel.save_sprint(
            self.root,
            kernel.Sprint(id="other", goal="x", wip=2, stories=[], status="running"),
        )
        with self.assertRaises(kernel.PlanError):
            self._plan()
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_missing_or_stopped_sprint_rejects(self):
        with self.assertRaises(kernel.PlanError):
            self._plan(sprint="missing")
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        sprint = kernel.load_sprint(self.root, "3.1")
        sprint.status = "stopped"
        kernel.save_sprint(self.root, sprint)
        with self.assertRaises(kernel.PlanError):
            self._plan(sprint="3.1")

    def test_load_defaults_missing_sprint_key(self):
        self._plan()
        path = self.root / "docs/delivery/tag/kernel.json"
        data = json.loads(path.read_text())
        del data["sprint"]
        path.write_text(json.dumps(data))
        self.assertEqual(kernel.load(self.root, "tag").sprint, "")

    def test_load_defaults_missing_craft_keys(self):
        self._plan()
        path = self.root / "docs/delivery/tag/kernel.json"
        data = json.loads(path.read_text())
        del data["rules_printed"]
        for stage in data["stages"]:
            del stage["flags"]
            del stage["pair"]
            del stage["awaiting_pair"]
        path.write_text(json.dumps(data))
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.rules_printed, [])
        self.assertEqual(delivery.stages[0].flags, [])
        self.assertEqual(delivery.stages[0].pair, "")
        self.assertFalse(delivery.stages[0].awaiting_pair)


class SprintCloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _running_story(self):
        kernel.sprint_start(self.root, id="3.1", goal="SDLC/Scrum kernel", wip=2)
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
            sprint="3.1",
        )

    def test_close_rejects_a_running_story(self):
        self._running_story()
        with self.assertRaises(kernel.PlanError):
            kernel.sprint_close(self.root, "3.1")
        self.assertEqual(kernel.load_sprint(self.root, "3.1").status, "running")

    def test_force_sets_sprint_stopped(self):
        self._running_story()
        closed = kernel.sprint_close(self.root, "3.1", force=True)
        self.assertEqual(closed.status, "stopped")

    def test_close_marks_done_when_stories_are_done(self):
        self._running_story()
        delivery = kernel.load(self.root, "tag")
        delivery.status = "done"
        kernel.save(self.root, delivery)
        closed = kernel.sprint_close(self.root, "3.1")
        self.assertEqual(closed.status, "done")


class LessonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, name, agent, flags):
        kernel.plan(
            root=self.root,
            name=name,
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", agent, "writer", ["m"], [])],
        )
        path = self.root / f"docs/delivery/{name}/stages/{agent}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            "VERIFIED: php artisan test --filter=TagTest\n"
            f"NOT-CHECKED: none\nFLAGS: {flags}\nNEXT: none\n"
        )
        return kernel.report(
            self.root,
            name,
            path,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )

    def test_none_flag_writes_no_lesson(self):
        self._report("tag", "database-developer", "none")
        self.assertFalse((self.root / "docs/team/lessons.json").is_file())

    def test_first_flag_is_seen_and_plan_prints_no_rule(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        self.assertEqual(lessons["lessons"][0]["status"], "seen")
        self.assertEqual(lessons["lessons"][0]["deliveries"], ["tag"])
        again = kernel.plan(
            root=self.root,
            name="other",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
        )
        self.assertEqual(again.rules_printed, [])

    def test_second_delivery_teaches_and_view_shows_rule(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        self._report("post", "backend-developer", "Do not call Model::all()")
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson = lessons["lessons"][0]
        self.assertEqual(lesson["status"], "taught")
        self.assertEqual(set(lesson["scope"]), {"database-developer", "backend-developer"})
        self.assertEqual(lesson["deliveries"], ["tag", "post"])
        view = (self.root / "docs/team/lessons.md").read_text()
        for label in ("LESSONS:", "RULE:", "SCOPE:", "STATUS:"):
            self.assertTrue(
                any(line.startswith(label) for line in view.splitlines()),
                f"lessons.md missing {label}",
            )
        self.assertIn("Do not call Model::all()", view)
        self.assertIn("STATUS: taught", view)
        taught_plan = kernel.plan(
            root=self.root,
            name="later",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], [])
            ],
        )
        self.assertEqual(taught_plan.rules_printed, ["Do not call Model::all()"])

    def test_same_delivery_twice_stays_seen(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        kernel._record_lesson(
            self.root, "tag", "backend-developer", "Do not call Model::all()"
        )
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson = lessons["lessons"][0]
        self.assertEqual(lesson["status"], "seen")
        self.assertEqual(lesson["deliveries"], ["tag"])

    def test_already_recorded_flag_refreshes_stale_view(self):
        team = self.root / "docs/team"
        team.mkdir(parents=True)
        (team / "lessons.json").write_text(
            json.dumps(
                {
                    "lessons": [
                        {
                            "norm": "do not call model::all()",
                            "text": "Do not call Model::all()",
                            "status": "taught",
                            "scope": ["database-developer", "backend-developer"],
                            "deliveries": ["tag", "post"],
                        }
                    ]
                },
                indent=2,
            )
            + "\n"
        )
        (team / "lessons.md").write_text("LESSONS: none\n")
        kernel._record_lesson(
            self.root, "tag", "database-developer", "Do not call Model::all()"
        )
        view = (team / "lessons.md").read_text()
        self.assertIn("RULE: Do not call Model::all()", view)
        self.assertIn("STATUS: taught", view)
        lessons = json.loads((team / "lessons.json").read_text())
        self.assertEqual(lessons["lessons"][0]["status"], "taught")
        self.assertEqual(lessons["lessons"][0]["deliveries"], ["tag", "post"])

    def _cli_plan(self, name, agent):
        guild = REPO / "scripts/guild-kernel/guild.py"
        return subprocess.run(
            [
                sys.executable,
                str(guild),
                "plan",
                "--root",
                str(self.root),
                "--name",
                name,
                "--done-when",
                "POST /api/tags creates a Tag",
                "--stage",
                f"a,{agent},writer,,m",
            ],
            capture_output=True,
            text=True,
        )

    def test_cli_plan_prints_rules_none_then_taught_rule(self):
        proc = self._cli_plan("fresh", "database-developer")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "RULES: none")

        self._report("tag", "database-developer", "Do not call Model::all()")
        self._report("post", "backend-developer", "Do not call Model::all()")
        proc = self._cli_plan("later", "database-developer")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "RULES: Do not call Model::all()")


if __name__ == "__main__":
    unittest.main()
