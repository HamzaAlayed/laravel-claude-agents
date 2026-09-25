import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


def claim_and_measure(root, name, stage_id="a"):
    delivery = kernel.load(root, name)
    stage = next(item for item in delivery.stages if item.id == stage_id)
    if stage.status == "queued":
        kernel.claim_stage(root, name, stage_id)
        stage = next(
            item for item in kernel.load(root, name).stages if item.id == stage_id
        )
    if stage.claimed_at:
        kernel.record_stage_usage(
            root,
            stage.agent,
            {
                "seconds": 0,
                "tool_calls": 0,
                "turns": 0,
                "tokens": 0,
                "cost_usd": 0,
            },
            expected_target=(name, stage_id),
        )


def verify_artisan(filter_name):
    return json.dumps(
        {"criterion":"criterion-1","runner": "artisan-test", "args": [f"--filter={filter_name}"]},
        separators=(",", ":"),
    )


VERIFY_TAG = verify_artisan("TagTest")
VERIFY_TAG_ARGV = ["php", "artisan", "test", "--filter=TagTest"]


def scoped_stage(*args, **kwargs):
    """Create a broadly scoped legacy fixture; scope-specific tests opt out."""
    if len(args) < 13 and "owned_paths" not in kwargs:
        kwargs["owned_paths"] = ["."]
    return kernel.StageSpec(*args, **kwargs)


class FakeRunner:
    def __init__(self, codes, captured=None):
        self.codes = codes
        self.captured = captured or {}
        self.calls = []

    def run(self, cwd, argv):
        self.calls.append((str(cwd), argv))
        return self.codes[" ".join(argv)]

    def capture(self, cwd, argv):
        cmd = " ".join(argv)
        self.calls.append((str(cwd), cmd))
        code, out = self.captured[cmd]
        return code, out


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
                scoped_stage("a", "database-developer", "writer", ["tags migration exists"], []),
                scoped_stage("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
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
                scoped_stage("a", "database-developer", "writer", ["m"], []),
                scoped_stage("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

    def test_next_does_not_name_dependent_before_upstream_done(self):
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], []),
                scoped_stage("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        d.stages[0].status = "running"
        kernel.save(self.root, d)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")
        self.assertNotEqual(kernel.next_agent(self.root, "tag"), "backend-developer")


class ParallelDispatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _stage(self, sid, agent, *, depends=(), owns=()):
        return scoped_stage(
            sid,
            agent,
            "writer",
            [f"{sid} complete"],
            list(depends),
            owned_paths=list(owns) or [f"fixtures/{sid}"],
        )

    def test_ready_returns_bounded_parallel_wave(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                self._stage("a", "database-developer"),
                self._stage("b", "backend-developer"),
                self._stage("c", "frontend-developer"),
            ],
            max_parallel=2,
        )
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "tag")],
            ["a", "b"],
        )
        kernel.claim_stage(self.root, "tag", "a")
        kernel.claim_stage(self.root, "tag", "b")
        self.assertEqual(kernel.ready_stages(self.root, "tag"), [])
        self.assertEqual(
            [stage.status for stage in kernel.load(self.root, "tag").stages],
            ["running", "running", "queued"],
        )

    def test_path_ownership_prevents_parallel_collision(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                self._stage("a", "database-developer", owns=["app/Models"]),
                self._stage("b", "backend-developer", owns=["app/Models/Tag.php"]),
            ],
        )
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "tag")], ["a"]
        )
        kernel.claim_stage(self.root, "tag", "a")
        with self.assertRaisesRegex(kernel.PlanError, "collides with running stage a"):
            kernel.claim_stage(self.root, "tag", "b")

    def test_concurrent_reports_preserve_both_stage_results(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                self._stage("a", "database-developer", owns=["database-developer.txt"]),
                self._stage("b", "backend-developer", owns=["backend-developer.txt"]),
            ],
            max_parallel=2,
        )
        kernel.claim_stage(self.root, "tag", "a")
        kernel.claim_stage(self.root, "tag", "b")
        for agent in ("database-developer", "backend-developer"):
            kernel.record_stage_usage(
                self.root,
                agent,
                {
                    "seconds": 1.0,
                    "tool_calls": 1,
                    "turns": 1,
                    "tokens": 1,
                    "cost_usd": 0.01,
                },
                event_id=f"completion:{agent}",
            )
        reports = []
        for agent in ("database-developer", "backend-developer"):
            artifact = self.root / f"{agent}.txt"
            artifact.write_text("done\n")
            report_path = self.root / "docs/delivery/tag/stages" / f"{agent}.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                f"STATUS: done\nDID: {artifact.name}\n"
                f'VERIFIED: {{"criterion":"criterion-1","runner":"file-exists","args":["{artifact.name}"]}}\n'
                "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
            )
            reports.append(report_path)

        barrier = threading.Barrier(2)
        failures = []

        def submit(report_path):
            try:
                barrier.wait()
                kernel.report(self.root, "tag", report_path, runner=FakeRunner({}))
            except Exception as exc:  # pragma: no cover - asserted below
                failures.append(exc)

        threads = [threading.Thread(target=submit, args=(path,)) for path in reports]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(failures, [])
        delivery = kernel.load(self.root, "tag")
        self.assertEqual([stage.status for stage in delivery.stages], ["done", "done"])
        self.assertEqual(delivery.spawns, 2)

    def test_dependency_blocks_ready_stage(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                self._stage("a", "database-developer"),
                self._stage("b", "backend-developer", depends=["a"]),
            ],
        )
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "tag")], ["a"]
        )

    def test_graph_names_parallel_lanes_and_limit(self):
        delivery = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                self._stage("a", "database-developer"),
                self._stage("b", "backend-developer"),
                self._stage("c", "qa-engineer", depends=["a", "b"]),
            ],
            max_parallel=2,
        )
        graph = kernel.render_graph(delivery)
        self.assertIn("PARALLEL: database-developer + backend-developer", graph)
        self.assertIn("MAX-PARALLEL: 2", graph)

    def test_invalid_owned_path_is_rejected(self):
        with self.assertRaisesRegex(kernel.PlanError, "invalid owned path"):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="x",
                stages=[self._stage("a", "database-developer", owns=["../app"])],
            )

    def test_mutation_capable_stage_requires_owned_path(self):
        with self.assertRaisesRegex(kernel.PlanError, "requires at least one owned path"):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="x",
                stages=[
                    kernel.StageSpec(
                        "a", "backend-developer", "writer", ["feature works"], []
                    )
                ],
            )

    def test_read_only_stage_may_have_no_owned_paths(self):
        delivery = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                kernel.StageSpec(
                    "a", "performance-engineer", "reviewer", ["profile reviewed"], []
                )
            ],
        )
        self.assertEqual(delivery.stages[0].owned_paths, [])

    def test_owned_paths_must_be_a_list_of_relative_strings(self):
        invalid = ("app", [42], ["app", "app"])
        for index, owned_paths in enumerate(invalid):
            with self.subTest(owned_paths=owned_paths), self.assertRaises(kernel.PlanError):
                kernel.plan(
                    root=self.root,
                    name=f"tag-{index}",
                    done_when="x",
                    stages=[
                        kernel.StageSpec(
                            "a", "backend-developer", "writer", ["feature works"], [],
                            owned_paths=owned_paths,
                        )
                    ],
                )


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_one(self):
        delivery = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[scoped_stage("a", "database-developer", "writer", ["tags migration exists"], [])],
        )
        claim_and_measure(self.root, "tag")
        return delivery

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

    def test_unknown_verification_runner_is_rejected_without_execution(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            'STATUS: done\nDID: app/Models/Tag.php\n'
            'VERIFIED: {"criterion":"criterion-1","runner":"shell","args":["rm","-rf","."]}\n'
            'NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n'
        )
        runner = FakeRunner({})
        with self.assertRaisesRegex(kernel.ReportError, "unknown verification runner"):
            kernel.report(self.root, "tag", p, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_legacy_shell_command_is_rejected_without_execution(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            "VERIFIED: php artisan test; touch escaped\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({})
        with self.assertRaisesRegex(kernel.ReportError, "VERIFIED must be JSON"):
            kernel.report(self.root, "tag", p, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_file_has_lines_verifier_stays_inside_project(self):
        self._plan_one()
        packet = self.root / "docs/delivery/tag/packets/a-to-b.md"
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text("FROM: a\nTO: b\n")
        stage = self.root / "docs/delivery/tag/stages/database-developer.md"
        stage.parent.mkdir(parents=True, exist_ok=True)
        spec = json.dumps(
            {
                "criterion": "criterion-1",
                "runner": "file-has-lines",
                "args": ["docs/delivery/tag/packets/a-to-b.md", "FROM:", "TO:"],
            },
            separators=(",", ":"),
        )
        stage.write_text(
            f"STATUS: done\nDID: {packet.relative_to(self.root)}\nVERIFIED: {spec}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({})
        delivery = kernel.report(self.root, "tag", stage, runner=runner)
        self.assertEqual(delivery.stages[0].status, "done")
        self.assertEqual(runner.calls, [])

    def test_file_verifier_rejects_path_escape(self):
        self._plan_one()
        stage = self.root / "docs/delivery/tag/stages/database-developer.md"
        stage.parent.mkdir(parents=True, exist_ok=True)
        stage.write_text(
            'STATUS: done\nDID: none\n'
            'VERIFIED: {"criterion":"criterion-1","runner":"file-exists","args":["../outside"]}\n'
            'NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n'
        )
        with self.assertRaisesRegex(kernel.ReportError, "paths must stay inside"):
            kernel.report(self.root, "tag", stage, runner=FakeRunner({}))

    def test_command_exit_nonzero_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: {VERIFY_TAG}\n"
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
            f"STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({"php artisan test --filter=TagTest": 0})
        d = kernel.report(self.root, "tag", p, runner=runner)
        self.assertEqual(d.stages[0].status, "done")
        self.assertEqual(runner.calls[0][1], VERIFY_TAG_ARGV)
        self.assertEqual(
            d.stages[0].verified,
            [{"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagTest"], "exit": 0}],
        )
        saved = kernel.load(self.root, "tag")
        self.assertEqual(
            saved.stages[0].verified,
            [{"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagTest"], "exit": 0}],
        )

    def test_not_checked_naming_criterion_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: {VERIFY_TAG}\n"
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

    def test_report_rejects_did_outside_owned_paths(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                kernel.StageSpec(
                    "a", "backend-developer", "writer", ["controller exists"], [],
                    owned_paths=["app/Http"],
                )
            ],
        )
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"STATUS: done\nDID: routes/api.php\nVERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaisesRegex(kernel.ReportError, "outside stage a owned paths"):
            kernel.report(
                self.root,
                "tag",
                path,
                runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
            )

    def test_report_accepts_nested_did_inside_owned_path(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                kernel.StageSpec(
                    "a", "backend-developer", "writer", ["controller exists"], [],
                    owned_paths=["app/Http"],
                )
            ],
        )
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/backend-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"STATUS: done\nDID: app/Http/Controllers/TagController.php\n"
            f"VERIFIED: {VERIFY_TAG}\nNOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        delivery = kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )
        self.assertEqual(delivery.stages[0].status, "done")


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
                scoped_stage(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                scoped_stage("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )

    def _write_stage(self, agent, *, did="app/Models/Tag.php"):
        p = self.root / f"docs/delivery/tag/stages/{agent}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"STATUS: done\nDID: {did}\nVERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        return p

    def _ok_report(self, agent="database-developer", *, did="app/Models/Tag.php"):
        stage = next(
            item
            for item in kernel.load(self.root, "tag").stages
            if item.agent == agent
        )
        claim_and_measure(self.root, "tag", stage.id)
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

    def test_duplicate_done_report_cannot_consume_spawn_capacity(self):
        self._plan_two()
        self._ok_report()
        with self.assertRaisesRegex(
            kernel.ReportError, "report requires a claimed running stage"
        ):
            self._ok_report()
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.spawns, 1)
        self.assertEqual(delivery.status, "running")

    def test_plan_on_running_kernel_does_not_reset_spawns(self):
        self._plan_two()
        self._ok_report()
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                scoped_stage("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
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
                        scoped_stage(
                            "a", "database-developer", "writer", ["m"], []
                        ),
                        scoped_stage(
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
                        scoped_stage(
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
                scoped_stage(
                    "a", "database-developer", "writer", ["tags migration exists"], []
                ),
                scoped_stage("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
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
        claim_and_measure(self.root, "tag")
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: {VERIFY_TAG}\n"
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
        stages = [
            {
                "id": "a", "agent": "database-developer", "role": "writer",
                "success_criteria": ["tags migration exists", "Tag model"],
                "depends_on": [], "owned_paths": ["database"],
            },
            {
                "id": "b", "agent": "backend-developer", "role": "writer",
                "success_criteria": ["Tag HTTP"], "depends_on": ["a"],
                "owned_paths": ["app"],
            },
            {
                "id": "c", "agent": "qa-engineer", "role": "reviewer",
                "success_criteria": ["Pest covers Tag"], "depends_on": ["b"],
                "owned_paths": ["tests"],
            },
        ]
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
                *[
                    item
                    for stage in stages
                    for item in ("--stage-json", json.dumps(stage))
                ],
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

    def test_cli_legacy_stage_is_a_migration_error(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
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
                self.assertIn("--stage was removed in v6", combined)

    def test_cli_stage_json_requires_owned_paths(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
        stage = json.dumps(
            {
                "id": "a",
                "agent": "database-developer",
                "success_criteria": ["migration exists"],
            }
        )
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
                "--stage-json",
                stage,
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("missing required fields: owned_paths", proc.stderr)

    def test_cli_stage_json_ready_and_claim(self):
        guild = REPO / "scripts/guild-kernel/guild.py"
        stage = json.dumps(
            {
                "id": "a",
                "agent": "database-developer",
                "role": "writer",
                "success_criteria": ["migration exists"],
                "depends_on": [],
                "owned_paths": ["database/migrations"],
            }
        )
        planned = subprocess.run(
            [
                sys.executable, str(guild), "plan", "--root", str(self.root),
                "--name", "tag", "--done-when", "x", "--stage-json", stage,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        ready = subprocess.run(
            [
                sys.executable, str(guild), "ready", "--root", str(self.root),
                "--name", "tag",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(ready.stdout)[0]["owned_paths"], ["database/migrations"]
        )
        claimed = subprocess.run(
            [
                sys.executable, str(guild), "claim", "--root", str(self.root),
                "--name", "tag", "--stage", "a",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        self.assertEqual(claimed.stdout.strip(), "AGENT: database-developer")


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
                scoped_stage("a", "database-developer", "writer", ["m"], []),
                scoped_stage("b", "backend-developer", "writer", ["h"], ["a"]),
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
            f"VERIFIED: {VERIFY_TAG}\n"
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
                    scoped_stage("a", "database-developer", "writer", ["m"], []),
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
                    scoped_stage("a", "database-developer", "writer", [], []),
                ],
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_rejects_empty_duplicate_unknown_and_cyclic_stages(self):
        invalid_sets = [
            [],
            [
                scoped_stage("a", "database-developer", "writer", ["m"], []),
                scoped_stage("a", "backend-developer", "writer", ["h"], []),
            ],
            [scoped_stage("a", "unknown-agent", "writer", ["m"], [])],
            [scoped_stage("a", "database-developer", "writer", ["m"], ["z"])],
            [
                scoped_stage("a", "database-developer", "writer", ["m"], ["b"]),
                scoped_stage("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        ]
        for index, stages in enumerate(invalid_sets):
            with self.subTest(index=index), self.assertRaises(kernel.PlanError):
                kernel.plan(
                    root=self.root,
                    name=f"tag-{index}",
                    done_when="x",
                    stages=stages,
                )


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
            "--stage-json",
            json.dumps(
                {
                    "id": "a",
                    "agent": "database-developer",
                    "role": "writer",
                    "success_criteria": ["migration exists"],
                    "depends_on": [],
                    "owned_paths": ["database"],
                }
            ),
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
        return [scoped_stage("a", "database-developer", "writer", ["m"], [])]

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
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
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
            stages=[scoped_stage("a", agent, "writer", ["m"], [])],
        )
        claim_and_measure(self.root, name)
        path = self.root / f"docs/delivery/{name}/stages/{agent}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            f"VERIFIED: {VERIFY_TAG}\n"
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

    def test_first_flag_is_observed_and_plan_prints_no_rule(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        self.assertEqual(lessons["lessons"][0]["status"], "observed")
        self.assertEqual(lessons["lessons"][0]["kind"], "learned_hypothesis")
        self.assertEqual(
            lessons["lessons"][0]["provenance"]["source"], "stage_flag"
        )
        self.assertEqual(lessons["lessons"][0]["deliveries"], ["tag"])
        again = kernel.plan(
            root=self.root,
            name="other",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
        )
        self.assertEqual(again.rules_printed, [])

    def test_second_delivery_creates_candidate_but_does_not_print_rule(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        self._report("post", "backend-developer", "Do not call Model::all()")
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson = lessons["lessons"][0]
        self.assertEqual(lesson["status"], "candidate")
        self.assertEqual(set(lesson["scope"]), {"database-developer", "backend-developer"})
        self.assertEqual(lesson["deliveries"], ["tag", "post"])
        view = (self.root / "docs/team/lessons.md").read_text()
        for label in ("LESSONS:", "RULE:", "SCOPE:", "STATUS:"):
            self.assertTrue(
                any(line.startswith(label) for line in view.splitlines()),
                f"lessons.md missing {label}",
            )
        self.assertIn("Do not call Model::all()", view)
        self.assertIn("STATUS: candidate", view)
        candidate_plan = kernel.plan(
            root=self.root,
            name="later",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], [])
            ],
        )
        self.assertEqual(candidate_plan.rules_printed, [])

    def test_explicit_user_approval_makes_candidate_authoritative(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        self._report("post", "backend-developer", "Do not call Model::all()")
        data = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson_id = data["lessons"][0]["id"]
        approved = kernel.approve_lesson(self.root, lesson_id)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["provenance"]["approval"]["by"], "user")
        plan = kernel.plan(
            root=self.root,
            name="later",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], [])
            ],
        )
        self.assertEqual(plan.rules_printed, ["Do not call Model::all()"])
        view = (self.root / "docs/team/lessons.md").read_text()
        self.assertIn("STATUS: approved", view)
        self.assertIn("APPROVED-BY: user at ", view)

    def test_approval_rejects_unknown_id(self):
        with self.assertRaisesRegex(kernel.PlanError, "unknown lesson id"):
            kernel.approve_lesson(self.root, "missing")

    def test_non_user_cannot_approve_lesson(self):
        with self.assertRaisesRegex(kernel.PlanError, "only be approved by the user"):
            kernel.approve_lesson(self.root, "missing", approved_by="agent")

    def test_same_delivery_twice_stays_observed(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        kernel._record_lesson(
            self.root, "tag", "backend-developer", "Do not call Model::all()"
        )
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson = lessons["lessons"][0]
        self.assertEqual(lesson["status"], "observed")
        self.assertEqual(lesson["deliveries"], ["tag"])

    def test_legacy_auto_taught_lesson_is_demoted_to_candidate(self):
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
        self.assertIn("STATUS: candidate", view)
        lessons = json.loads((team / "lessons.json").read_text())
        self.assertEqual(lessons["lessons"][0]["status"], "candidate")
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
                "--stage-json",
                json.dumps(
                    {
                        "id": "a",
                        "agent": agent,
                        "role": "writer",
                        "success_criteria": ["m"],
                        "depends_on": [],
                        "owned_paths": ["."],
                    }
                ),
            ],
            capture_output=True,
            text=True,
        )

    def test_cli_plan_prints_rule_only_after_explicit_approval(self):
        proc = self._cli_plan("fresh", "database-developer")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "RULES: none")

        self._report("tag", "database-developer", "Do not call Model::all()")
        self._report("post", "backend-developer", "Do not call Model::all()")
        proc = self._cli_plan("candidate", "database-developer")
        self.assertEqual(proc.stdout.strip(), "RULES: none")

        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        lesson_id = lessons["lessons"][0]["id"]
        guild = REPO / "scripts/guild-kernel/guild.py"
        approved = subprocess.run(
            [
                sys.executable,
                str(guild),
                "lesson",
                "approve",
                "--root",
                str(self.root),
                "--id",
                lesson_id,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertIn(f"APPROVED: {lesson_id}", approved.stdout)
        proc = self._cli_plan("later", "database-developer")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "RULES: Do not call Model::all()")


class PairTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], []),
            ],
        )

    def test_pair_sets_reviewer(self):
        self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        self.assertEqual(kernel.load(self.root, "tag").stages[0].pair, "tech-lead")

    def test_writer_report_waits_for_paired_reviewer(self):
        self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        claim_and_measure(self.root, "tag")
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            f"VERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        d = kernel.report(
            self.root,
            "tag",
            p,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )
        stage = d.stages[0]
        self.assertEqual(stage.status, "running")
        self.assertTrue(stage.awaiting_pair)
        self.assertEqual(
            stage.verified,
            [{"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagTest"], "exit": 0}],
        )
        self.assertEqual(kernel.next_agent(self.root, "tag"), "tech-lead")
        board = kernel.board_line(d)
        self.assertIn("tech-lead", board)
        self.assertIn("▶", board)

    def test_pair_rejects_unknown_self_missing_and_done(self):
        self._plan()
        cases = [
            ("nope", "a", None),
            ("database-developer", "a", None),
            ("tech-lead", "missing", None),
            ("tech-lead", "a", "done"),
        ]
        for reviewer, stage_id, status in cases:
            with self.subTest(reviewer=reviewer, stage_id=stage_id, status=status):
                delivery = kernel.load(self.root, "tag")
                delivery.stages[0].pair = ""
                if status is not None:
                    delivery.stages[0].status = status
                else:
                    delivery.stages[0].status = "queued"
                kernel.save(self.root, delivery)
                with self.assertRaises(kernel.PlanError):
                    kernel.pair(self.root, "tag", stage_id, reviewer=reviewer)
                self.assertEqual(kernel.load(self.root, "tag").stages[0].pair, "")

    def test_pair_same_reviewer_is_noop_conflict_rejects(self):
        self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        self.assertEqual(kernel.load(self.root, "tag").stages[0].pair, "tech-lead")
        with self.assertRaises(kernel.PlanError):
            kernel.pair(self.root, "tag", "a", reviewer="qa-engineer")
        self.assertEqual(kernel.load(self.root, "tag").stages[0].pair, "tech-lead")

    def test_cli_pair_unknown_reviewer_exits_nonzero(self):
        self._plan()
        guild = REPO / "scripts/guild-kernel/guild.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(guild),
                "pair",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--stage",
                "a",
                "--reviewer",
                "nope",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("Traceback", proc.stdout)

    def _waiting_pair(self):
        self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        claim_and_measure(self.root, "tag")
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            f"VERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        return kernel.report(
            self.root,
            "tag",
            p,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )

    def _reviewer_path(self, *, verified):
        p = self.root / "docs/delivery/tag/stages/tech-lead.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: review notes\n"
            f"VERIFIED: {verified}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        return p

    def test_reviewer_exit_zero_finishes_paired_stage(self):
        self._waiting_pair()
        p = self._reviewer_path(verified=verify_artisan("TagReview"))
        d = kernel.report(
            self.root,
            "tag",
            p,
            runner=FakeRunner({"php artisan test --filter=TagReview": 0}),
        )
        stage = d.stages[0]
        self.assertEqual(stage.status, "done")
        self.assertFalse(stage.awaiting_pair)
        self.assertEqual(
            stage.verified,
            [
                {"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagTest"], "exit": 0},
                {"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagReview"], "exit": 0},
            ],
        )

    def test_reviewer_prose_or_exit_one_keeps_waiting(self):
        self._waiting_pair()
        cases = [
            ("the review looks fine", {}),
            (
                verify_artisan("TagReview"),
                {"php artisan test --filter=TagReview": 1},
            ),
        ]
        for verified, codes in cases:
            with self.subTest(verified=verified):
                p = self._reviewer_path(verified=verified)
                with self.assertRaises(kernel.ReportError):
                    kernel.report(self.root, "tag", p, runner=FakeRunner(codes))
                stage = kernel.load(self.root, "tag").stages[0]
                self.assertEqual(stage.status, "running")
                self.assertTrue(stage.awaiting_pair)

    def test_reviewer_without_awaiting_pair_is_rejected(self):
        self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        p = self._reviewer_path(verified=verify_artisan("TagReview"))
        with self.assertRaises(kernel.ReportError):
            kernel.report(
                self.root,
                "tag",
                p,
                runner=FakeRunner({"php artisan test --filter=TagReview": 0}),
            )
        stage = kernel.load(self.root, "tag").stages[0]
        self.assertFalse(stage.awaiting_pair)
        self.assertNotEqual(stage.status, "done")

    def test_second_writer_report_while_awaiting_pair_is_rejected(self):
        self._waiting_pair()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            f"VERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaises(kernel.ReportError):
            kernel.report(
                self.root,
                "tag",
                p,
                runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
            )
        stage = kernel.load(self.root, "tag").stages[0]
        self.assertEqual(stage.status, "running")
        self.assertTrue(stage.awaiting_pair)
        self.assertEqual(
            stage.verified,
            [{"criterion":"criterion-1","runner": "artisan-test", "args": ["--filter=TagTest"], "exit": 0}],
        )

    def test_cap_while_waiting_stops_and_next_is_stop(self):
        delivery = self._plan()
        kernel.pair(self.root, "tag", "a", reviewer="tech-lead")
        delivery = kernel.load(self.root, "tag")
        delivery.spawns = delivery.cap - 1
        kernel.save(self.root, delivery)
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/database-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            f"VERIFIED: {VERIFY_TAG}\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        reported = kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )
        self.assertEqual(reported.status, "stopped")
        self.assertEqual(reported.stages[0].status, "running")
        self.assertTrue(reported.stages[0].awaiting_pair)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")


class WorkplaceLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_v32_kernel_json_loads_empty_workplace_fields(self):
        folder = self.root / "docs" / "delivery" / "tag"
        folder.mkdir(parents=True)
        folder.joinpath("kernel.json").write_text(
            json.dumps(
                {
                    "name": "tag",
                    "done_when": "POST /api/tags creates a Tag",
                    "cap": 3,
                    "status": "running",
                    "spawns": 0,
                    "sprint": "",
                    "rules_printed": [],
                    "stages": [
                        {
                            "id": "a",
                            "agent": "database-developer",
                            "role": "writer",
                            "success_criteria": ["tags migration exists"],
                            "depends_on": [],
                            "status": "queued",
                            "did": [],
                            "verified": [],
                            "flags": [],
                            "pair": "",
                            "awaiting_pair": False,
                        }
                    ],
                }
            )
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.issue, {})
        self.assertEqual(delivery.pr, {})
        self.assertEqual(delivery.repo, "")
        self.assertEqual(delivery.stages[0].reopens, 0)

    def test_close_view_appends_issue_and_pr_none(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
        )
        close = (self.root / "docs/delivery/tag/close.md").read_text()
        self.assertIn("\nISSUE: none\n", close)
        self.assertTrue(close.endswith("PR: none\n"))


class DeskLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_v33_kernel_json_loads_empty_seen_fields(self):
        folder = self.root / "docs" / "delivery" / "tag"
        folder.mkdir(parents=True)
        folder.joinpath("kernel.json").write_text(
            json.dumps(
                {
                    "name": "tag",
                    "done_when": "POST /api/tags creates a Tag",
                    "cap": 3,
                    "status": "running",
                    "spawns": 0,
                    "sprint": "",
                    "rules_printed": [],
                    "stages": [
                        {
                            "id": "a",
                            "agent": "database-developer",
                            "role": "writer",
                            "success_criteria": ["tags migration exists"],
                            "depends_on": [],
                            "status": "queued",
                            "did": [],
                            "verified": [],
                            "flags": [],
                            "pair": "",
                            "awaiting_pair": False,
                        }
                    ],
                }
            )
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.seen_checks, [])
        self.assertEqual(delivery.seen_comments, [])


ISSUE_CMD = "gh issue view 42 --json number,title,url"
ISSUE_OUT = json.dumps(
    {"number": 42, "title": "Add tags", "url": "https://github.com/acme/app/issues/42"}
)


class WorkplacePlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, runner, issue=42):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
            issue=issue,
            runner=runner,
        )

    def test_plan_issue_stores_number_title_url(self):
        runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        delivery = self._plan(runner)
        self.assertEqual(delivery.issue["number"], 42)
        self.assertEqual(delivery.issue["title"], "Add tags")
        self.assertEqual(delivery.issue["url"], "https://github.com/acme/app/issues/42")
        self.assertEqual(runner.calls, [(str(self.root), ISSUE_CMD)])

    def test_plan_issue_nonzero_gh_writes_no_file(self):
        runner = FakeRunner({}, {ISSUE_CMD: (1, "")})
        with self.assertRaises(kernel.PlanError):
            self._plan(runner)
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_issue_malformed_json_raises_plan_error(self):
        runner = FakeRunner({}, {ISSUE_CMD: (0, "not-json")})
        with self.assertRaises(kernel.PlanError):
            self._plan(runner)
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_without_issue_does_not_capture(self):
        runner = FakeRunner({})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
            runner=runner,
        )
        self.assertEqual(runner.calls, [])

    def test_plan_issue_mismatched_number_writes_no_file(self):
        out = json.dumps(
            {
                "number": 99,
                "title": "Add tags",
                "url": "https://github.com/acme/app/issues/99",
            }
        )
        runner = FakeRunner({}, {ISSUE_CMD: (0, out)})
        with self.assertRaises(kernel.PlanError):
            self._plan(runner)
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_issue_without_runner_writes_no_file(self):
        with self.assertRaises(kernel.PlanError):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="POST /api/tags creates a Tag",
                stages=[
                    scoped_stage("a", "database-developer", "writer", ["m"], [])
                ],
                issue=42,
                runner=None,
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_second_plan_does_not_refetch_or_replace_issue(self):
        runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        self._plan(runner)
        other = "gh issue view 7 --json number,title,url"
        runner.captured[other] = (
            0,
            json.dumps({"number": 7, "title": "Other", "url": "https://example.test/7"}),
        )
        again = kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
            issue=7,
            runner=runner,
        )
        self.assertEqual(again.issue["number"], 42)
        self.assertEqual([call[1] for call in runner.calls], [ISSUE_CMD])


REPO_CMD = "gh repo view --json nameWithOwner"
REPO_OUT = json.dumps({"nameWithOwner": "acme/app"})
PR_CMD = "gh pr view 17 --json number,url,state"
PR_OUT = json.dumps(
    {
        "number": 17,
        "url": "https://github.com/acme/app/pull/17",
        "state": "OPEN",
    }
)


class WorkplacePrTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, runner, issue=42):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
            issue=issue,
            runner=runner,
        )

    def _plant_issue(self, captured=None):
        captured = dict(captured or {})
        captured[ISSUE_CMD] = (0, ISSUE_OUT)
        runner = FakeRunner({}, captured)
        self._plan(runner)
        runner.calls.clear()
        return runner

    def test_record_pr_stores_open_state_and_repo(self):
        runner = self._plant_issue(
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, PR_OUT)}
        )
        delivery = kernel.record_pr(self.root, "tag", 17, runner)
        self.assertEqual(delivery.repo, "acme/app")
        self.assertEqual(delivery.pr["state"], "open")
        self.assertEqual(delivery.pr["url"], "https://github.com/acme/app/pull/17")
        close = (self.root / "docs/delivery/tag/close.md").read_text()
        self.assertIn("PR: https://github.com/acme/app/pull/17\n", close)

    def test_record_pr_without_issue_raises(self):
        runner = FakeRunner(
            {},
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, PR_OUT)},
        )
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[scoped_stage("a", "database-developer", "writer", ["m"], [])],
            runner=runner,
        )
        runner.calls.clear()
        with self.assertRaises(kernel.PlanError):
            kernel.record_pr(self.root, "tag", 17, runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.pr, {})
        self.assertEqual(runner.calls, [])

    def test_failed_pr_view_leaves_pr_empty(self):
        runner = self._plant_issue(
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (1, "")}
        )
        with self.assertRaises(kernel.PlanError):
            kernel.record_pr(self.root, "tag", 17, runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.pr, {})
        self.assertEqual(delivery.repo, "")

    def test_malformed_pr_json_leaves_pr_empty(self):
        runner = self._plant_issue(
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, "not-json")}
        )
        with self.assertRaises(kernel.PlanError):
            kernel.record_pr(self.root, "tag", 17, runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.pr, {})
        self.assertEqual(delivery.repo, "")


STAGE_BODY = (
    "STATUS: done\nDID: app/Models/Tag.php\n"
    f"VERIFIED: {VERIFY_TAG}\n"
    "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
)
VERIFY_CMD = "php artisan test --filter=TagTest"


class WorkplaceDoneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_workplace(self):
        runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], [])
            ],
            issue=42,
            runner=runner,
        )

    def _write_stage(self):
        path = self.root / "docs/delivery/tag/stages/database-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STAGE_BODY)
        return path

    def _finish_stages(self):
        self._plan_workplace()
        claim_and_measure(self.root, "tag")
        path = self._write_stage()
        return kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({VERIFY_CMD: 0}),
        )

    def test_workplace_stays_running_until_pr_is_open(self):
        d = self._finish_stages()
        self.assertEqual(d.stages[0].status, "done")
        self.assertEqual(d.status, "running")
        self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")

    def test_record_pr_promotes_finished_workplace_delivery(self):
        self._finish_stages()
        runner = FakeRunner(
            {},
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, PR_OUT)},
        )
        delivery = kernel.record_pr(self.root, "tag", 17, runner)
        self.assertEqual(delivery.status, "done")

    def test_record_pr_merged_does_not_promote(self):
        self._finish_stages()
        merged = json.dumps(
            {
                "number": 17,
                "url": "https://github.com/acme/app/pull/17",
                "state": "MERGED",
            }
        )
        runner = FakeRunner(
            {},
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, merged)},
        )
        delivery = kernel.record_pr(self.root, "tag", 17, runner)
        self.assertEqual(delivery.status, "running")

    def test_delivery_without_issue_can_finish_with_empty_pr(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], [])
            ],
        )
        claim_and_measure(self.root, "tag")
        path = self._write_stage()
        delivery = kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({VERIFY_CMD: 0}),
        )
        self.assertEqual(delivery.status, "done")
        self.assertEqual(delivery.pr, {})

    def test_waiting_for_pr_at_cap_stays_running(self):
        d = self._finish_stages()
        self.assertEqual(d.cap, 3)
        self.assertEqual(d.spawns, 1)
        self.assertEqual(d.status, "running")
        d.spawns = d.cap
        kernel.save(self.root, d)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")
        self.assertEqual(kernel.load(self.root, "tag").status, "running")


CHECKS = "gh pr checks 17 --json name,bucket,link"
FAIL_CHECK = json.dumps(
    [{"name": "pint", "bucket": "fail", "link": "https://github.com/acme/app/runs/1"}]
)
PASS_CHECK = json.dumps(
    [{"name": "pint", "bucket": "pass", "link": "https://github.com/acme/app/runs/1"}]
)
REVIEW = "gh api repos/acme/app/pulls/17/comments"
REVIEW_ITEMS = json.dumps(
    [
        {"id": 99, "path": "database/migrations/tags.php", "line": 12},
        {"id": 100, "path": "database/migrations/tags.php", "line": 14},
    ]
)


class WorkplaceIngestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self._plant()

    def tearDown(self):
        self.tmp.cleanup()

    def _plant(self):
        plan_runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage(
                    "a",
                    "database-developer",
                    "writer",
                    ["m"],
                    [],
                    feedback_checks=["pint", "phpunit"],
                )
            ],
            issue=42,
            runner=plan_runner,
        )
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/database-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STAGE_BODY)
        kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({VERIFY_CMD: 0}),
        )
        pr_runner = FakeRunner(
            {},
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, PR_OUT)},
        )
        delivery = kernel.record_pr(self.root, "tag", 17, pr_runner)
        delivery.spawns = delivery.cap
        kernel.save(self.root, delivery)

    def test_failing_check_reopens_once_and_allows_one_spawn(self):
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        result = kernel.ingest(
            self.root,
            "tag",
            kind="check",
            stage_id="a",
            check="pint",
            runner=runner,
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(delivery.stages[0].status, "queued")
        self.assertEqual(delivery.stages[0].reopens, 1)
        self.assertEqual(delivery.status, "running")
        self.assertGreaterEqual(delivery.cap, delivery.spawns + 1)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

    def test_green_check_does_not_write(self):
        before = (self.root / "docs/delivery/tag/kernel.json").read_text()
        runner = FakeRunner({}, {CHECKS: (0, PASS_CHECK)})
        kernel.ingest(
            self.root,
            "tag",
            kind="check",
            stage_id="a",
            check="pint",
            runner=runner,
        )
        self.assertEqual(
            (self.root / "docs/delivery/tag/kernel.json").read_text(), before
        )

    def test_duplicate_check_delivery_is_idempotent(self):
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        kernel.ingest(
            self.root,
            "tag",
            kind="check",
            stage_id="a",
            check="pint",
            runner=runner,
        )
        result = kernel.ingest(
            self.root,
            "tag",
            kind="check",
            stage_id="a",
            check="pint",
            runner=runner,
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "noop")
        self.assertEqual(delivery.status, "running")
        self.assertEqual(delivery.stages[0].status, "queued")
        self.assertEqual(delivery.stages[0].reopens, 1)
        self.assertEqual(len(delivery.retry_events), 1)

    def test_missing_check_name_rejects(self):
        other = json.dumps(
            [
                {
                    "name": "phpunit",
                    "bucket": "fail",
                    "link": "https://github.com/acme/app/runs/2",
                }
            ]
        )
        runner = FakeRunner({}, {CHECKS: (0, other)})
        with self.assertRaises(kernel.PlanError):
            kernel.ingest(
                self.root,
                "tag",
                kind="check",
                stage_id="a",
                check="pint",
                runner=runner,
            )
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "done")

    def test_non_int_pr_number_rejects_before_capture(self):
        delivery = kernel.load(self.root, "tag")
        delivery.pr["number"] = "17; touch pwned"
        kernel.save(self.root, delivery)
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        with self.assertRaises(kernel.PlanError):
            kernel.ingest(
                self.root,
                "tag",
                kind="check",
                stage_id="a",
                check="pint",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])

    def test_review_id_in_payload_reopens(self):
        runner = FakeRunner({}, {REVIEW: (0, REVIEW_ITEMS)})
        result = kernel.ingest(
            self.root,
            "tag",
            kind="review",
            stage_id="a",
            comment="99",
            runner=runner,
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(delivery.stages[0].status, "queued")

    def test_missing_review_id_rejects(self):
        runner = FakeRunner(
            {},
            {
                REVIEW: (
                    0,
                    json.dumps(
                        [{"id": 100, "path": "database/migrations/tags.php"}]
                    ),
                )
            },
        )
        with self.assertRaises(kernel.PlanError):
            kernel.ingest(
                self.root,
                "tag",
                kind="review",
                stage_id="a",
                comment="99",
                runner=runner,
            )
        self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "done")

    def test_ingest_without_pr_rejects(self):
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        plan_runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage(
                    "a",
                    "database-developer",
                    "writer",
                    ["m"],
                    [],
                    feedback_checks=["pint", "phpunit"],
                )
            ],
            issue=42,
            runner=plan_runner,
        )
        runner = FakeRunner({}, {})
        with self.assertRaises(kernel.PlanError):
            kernel.ingest(
                self.root,
                "tag",
                kind="check",
                stage_id="a",
                check="pint",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])

    def test_unsafe_repo_rejects_before_capture(self):
        delivery = kernel.load(self.root, "tag")
        delivery.repo = "acme/app; touch pwned"
        kernel.save(self.root, delivery)
        runner = FakeRunner({}, {REVIEW: (0, "99\n")})
        with self.assertRaises(kernel.PlanError):
            kernel.ingest(
                self.root,
                "tag",
                kind="review",
                stage_id="a",
                comment="99",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])


class ApprovalPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, *, category="destructive migration"):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="tags migration is ready",
            stages=[
                scoped_stage(
                    "database",
                    "database-developer",
                    "writer",
                    ["migration is reversible"],
                    [],
                    approval_categories=[category],
                )
            ],
        )

    def test_unknown_agent_approval_category_is_rejected(self):
        with self.assertRaisesRegex(kernel.PlanError, "unknown approval category"):
            self._plan(category="payment UI")

    def test_malformed_and_duplicate_approval_categories_are_rejected(self):
        for categories in ("destructive migration", [1], ["production data"] * 2):
            with self.subTest(categories=categories), self.assertRaises(kernel.PlanError):
                kernel.plan(
                    root=self.root,
                    name="tag",
                    done_when="x",
                    stages=[
                        scoped_stage(
                            "database",
                            "database-developer",
                            "writer",
                            ["safe"],
                            [],
                            approval_categories=categories,
                        )
                    ],
                )

    def test_pending_approval_pauses_dispatch_and_claim(self):
        delivery = self._plan()
        self.assertEqual(kernel.ready_stages(self.root, "tag"), [])
        self.assertEqual(
            kernel.next_agent(self.root, "tag"),
            "APPROVAL_REQUIRED: database: destructive migration",
        )
        self.assertIn("database ⏸ database-developer", kernel.board_line(delivery))
        self.assertIn("approval:destructive migration", kernel.board_line(delivery))
        with self.assertRaisesRegex(
            kernel.PlanError,
            "requires user approval before claim: destructive migration",
        ):
            kernel.claim_stage(self.root, "tag", "database")

    def test_user_approval_is_durable_and_enables_claim(self):
        self._plan()
        approval = kernel.approve_stage_action(
            self.root,
            "tag",
            "database",
            "destructive migration",
        )
        self.assertEqual(approval["category"], "destructive migration")
        self.assertEqual(approval["by"], "user")
        self.assertTrue(approval["at"].endswith("+00:00"))
        persisted = kernel.load(self.root, "tag").stages[0]
        self.assertEqual(persisted.approvals, [approval])
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "tag")],
            ["database"],
        )
        claimed = kernel.claim_stage(self.root, "tag", "database")
        self.assertEqual(claimed.status, "running")

    def test_only_user_can_grant_and_duplicate_grant_is_idempotent(self):
        self._plan()
        with self.assertRaisesRegex(kernel.PlanError, "only be approved by the user"):
            kernel.approve_stage_action(
                self.root,
                "tag",
                "database",
                "destructive migration",
                approved_by="agent",
            )
        first = kernel.approve_stage_action(
            self.root,
            "tag",
            "database",
            "destructive migration",
        )
        second = kernel.approve_stage_action(
            self.root,
            "tag",
            "database",
            "destructive migration",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(kernel.load(self.root, "tag").stages[0].approvals), 1)

    def test_approval_must_be_declared_and_stage_must_be_queued(self):
        self._plan()
        with self.assertRaisesRegex(kernel.PlanError, "was not declared"):
            kernel.approve_stage_action(
                self.root, "tag", "database", "production data"
            )
        kernel.approve_stage_action(
            self.root, "tag", "database", "destructive migration"
        )
        kernel.claim_stage(self.root, "tag", "database")
        with self.assertRaisesRegex(kernel.PlanError, "stage database is running"):
            kernel.approve_stage_action(
                self.root, "tag", "database", "destructive migration"
            )

    def test_approval_cli_lists_pending_and_grants(self):
        self._plan()
        command = [
            sys.executable,
            str(REPO / "scripts/guild-kernel/guild.py"),
            "approval",
            "list",
            "--root",
            str(self.root),
            "--name",
            "tag",
        ]
        listed = subprocess.run(command, capture_output=True, text=True, check=True)
        rows = json.loads(listed.stdout)
        self.assertEqual(
            rows,
            [
                {
                    "stage": "database",
                    "agent": "database-developer",
                    "category": "destructive migration",
                    "status": "pending",
                }
            ],
        )
        granted = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/guild-kernel/guild.py"),
                "approval",
                "grant",
                "--root",
                str(self.root),
                "--name",
                "tag",
                "--stage",
                "database",
                "--category",
                "destructive migration",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("APPROVED: database destructive migration", granted.stdout)
        listed = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(listed.stdout)[0]["status"], "approved")

    def test_plan_cli_persists_declared_approval_categories(self):
        subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/guild-kernel/guild.py"),
                "plan",
                "--root",
                str(self.root),
                "--name",
                "invoice",
                "--done-when",
                "invoice endpoint is authorized",
                "--stage-json",
                json.dumps(
                    {
                        "id": "backend",
                        "agent": "backend-developer",
                        "role": "writer",
                        "success_criteria": ["authorization is enforced"],
                        "depends_on": [],
                        "owned_paths": ["app/Http"],
                        "approval_categories": ["auth"],
                    }
                ),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        stage = kernel.load(self.root, "invoice").stages[0]
        self.assertEqual(stage.approval_categories, ["auth"])
        self.assertEqual(stage.approvals, [])


class WatchOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self._plant()

    def tearDown(self):
        self.tmp.cleanup()

    def _plant(self):
        plan_runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage(
                    "a",
                    "database-developer",
                    "writer",
                    ["m"],
                    [],
                    feedback_checks=["pint", "phpunit"],
                )
            ],
            issue=42,
            runner=plan_runner,
        )
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/database-developer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STAGE_BODY)
        kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({VERIFY_CMD: 0}),
        )
        pr_runner = FakeRunner(
            {},
            {REPO_CMD: (0, REPO_OUT), PR_CMD: (0, PR_OUT)},
        )
        delivery = kernel.record_pr(self.root, "tag", 17, pr_runner)
        delivery.spawns = delivery.cap
        delivery.status = "running"
        kernel.save(self.root, delivery)

    def test_watch_skips_without_pr(self):
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        plan_runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                scoped_stage("a", "database-developer", "writer", ["m"], [])
            ],
            issue=42,
            runner=plan_runner,
        )
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        result = kernel.watch_once(self.root, "tag", runner)
        self.assertEqual(result, {"action": "skip"})
        self.assertEqual(runner.calls, [])

    def test_watch_reopens_one_failing_check(self):
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        result = kernel.watch_once(self.root, "tag", runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["check"], "pint")
        self.assertEqual(result["stage"], "a")
        self.assertEqual(delivery.stages[0].status, "queued")
        self.assertEqual(delivery.stages[0].reopens, 1)
        self.assertEqual(delivery.seen_checks, ["pint"])
        self.assertEqual(runner.calls, [(str(self.root), CHECKS)])

    def test_watch_green_does_not_save(self):
        before = (self.root / "docs/delivery/tag/kernel.json").read_bytes()
        runner = FakeRunner({}, {CHECKS: (0, PASS_CHECK), REVIEW: (0, "[]")})
        result = kernel.watch_once(self.root, "tag", runner)
        self.assertEqual(result, {"action": "noop"})
        self.assertEqual(
            (self.root / "docs/delivery/tag/kernel.json").read_bytes(), before
        )

    def test_watch_dedupes_while_repair_running(self):
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        kernel.watch_once(self.root, "tag", runner)
        kernel.claim_stage(self.root, "tag", "a")
        runner2 = FakeRunner(
            {}, {CHECKS: (0, FAIL_CHECK), REVIEW: (0, "[]")}
        )
        result = kernel.watch_once(self.root, "tag", runner2)
        self.assertEqual(result, {"action": "noop"})
        self.assertEqual(
            runner2.calls,
            [(str(self.root), CHECKS), (str(self.root), REVIEW)],
        )
        self.assertEqual(kernel.load(self.root, "tag").seen_checks, ["pint"])

    def test_watch_second_failure_stops(self):
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        kernel.watch_once(self.root, "tag", runner)
        claim_and_measure(self.root, "tag")
        path = self.root / "docs/delivery/tag/stages/database-developer.md"
        kernel.report(
            self.root,
            "tag",
            path,
            runner=FakeRunner({VERIFY_CMD: 0}),
        )
        delivery = kernel.load(self.root, "tag")
        delivery.status = "running"
        kernel.save(self.root, delivery)
        phpunit_fail = json.dumps(
            [
                {
                    "name": "phpunit",
                    "bucket": "fail",
                    "link": "https://github.com/acme/app/runs/2",
                }
            ]
        )
        runner2 = FakeRunner(
            {},
            {"gh pr checks 17 --json name,bucket,link": (0, phpunit_fail)},
        )
        result = kernel.watch_once(self.root, "tag", runner2)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "stopped")
        self.assertEqual(result["check"], "phpunit")
        self.assertEqual(result["stage"], "a")
        self.assertEqual(delivery.status, "stopped")
        self.assertIn("phpunit", delivery.seen_checks)

    def test_failing_check_skips_review_api(self):
        runner = FakeRunner(
            {},
            {CHECKS: (0, FAIL_CHECK), REVIEW: (0, REVIEW_ITEMS)},
        )
        result = kernel.watch_once(self.root, "tag", runner)
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["check"], "pint")
        self.assertEqual(result["stage"], "a")
        self.assertNotIn(REVIEW, [call[1] for call in runner.calls])

    def test_new_comment_reopens_when_checks_pass(self):
        runner = FakeRunner(
            {}, {CHECKS: (0, PASS_CHECK), REVIEW: (0, REVIEW_ITEMS)}
        )
        result = kernel.watch_once(self.root, "tag", runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["comment"], "99")
        self.assertEqual(result["stage"], "a")
        self.assertEqual(delivery.stages[0].status, "queued")
        self.assertEqual(delivery.seen_comments, ["99"])
        self.assertEqual(
            runner.calls,
            [(str(self.root), CHECKS), (str(self.root), REVIEW)],
        )

    def test_seen_comment_does_not_reopen(self):
        delivery = kernel.load(self.root, "tag")
        delivery.seen_comments = ["99"]
        delivery.feedback_events = [
            {
                "event_id": "review:99",
                "kind": "review",
                "external_id": "99",
                "status": "resolved",
                "stage": "a",
                "route": "owned_path",
                "check": "",
                "path": "database/migrations/tags.php",
                "line": 12,
                "url": "",
            }
        ]
        kernel.save(self.root, delivery)
        runner = FakeRunner(
            {},
            {
                CHECKS: (0, PASS_CHECK),
                REVIEW: (
                    0,
                    json.dumps(
                        [
                            {
                                "id": 99,
                                "path": "database/migrations/tags.php",
                                "line": 12,
                            }
                        ]
                    ),
                ),
            },
        )
        result = kernel.watch_once(self.root, "tag", runner)
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(result, {"action": "noop"})
        self.assertEqual(delivery.stages[0].status, "done")
        self.assertEqual(delivery.seen_comments, ["99"])

    def test_watch_polls_done_delivery_but_skips_stopped_delivery(self):
        delivery = kernel.load(self.root, "tag")
        delivery.status = "done"
        kernel.save(self.root, delivery)
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        result = kernel.watch_once(self.root, "tag", runner)
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["check"], "pint")
        self.assertEqual(runner.calls, [(str(self.root), CHECKS)])

        delivery = kernel.load(self.root, "tag")
        delivery.status = "stopped"
        kernel.save(self.root, delivery)
        runner = FakeRunner({}, {CHECKS: (0, FAIL_CHECK)})
        result = kernel.watch_once(self.root, "tag", runner)
        self.assertEqual(result, {"action": "skip"})
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
