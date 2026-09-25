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


CHECKS = "gh pr checks 17 --json name,bucket,link"
REVIEWS = "gh api repos/acme/app/pulls/17/comments"


class FakeRunner:
    def __init__(self, captured):
        self.captured = captured
        self.calls = []

    def capture(self, cwd, argv):
        command = " ".join(argv)
        self.calls.append((str(cwd), command))
        return self.captured[command]


class VerifyRunner:
    def run(self, _cwd, _argv):
        return 0


class FeedbackPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "app/Backend").mkdir(parents=True)
        (self.root / "app/Frontend").mkdir(parents=True)
        (self.root / "app/Backend/Feature.php").write_text("<?php\n")
        (self.root / "app/Frontend/Page.php").write_text("<?php\n")
        kernel.plan(
            root=self.root,
            name="feature",
            done_when="the feature is accepted",
            stages=[
                kernel.StageSpec(
                    "backend",
                    "backend-developer",
                    "writer",
                    ["backend accepted"],
                    [],
                    owned_paths=["app/Backend"],
                    criterion_ids=["backend-accepted"],
                    feedback_checks=["phpunit"],
                ),
                kernel.StageSpec(
                    "frontend",
                    "frontend-developer",
                    "writer",
                    ["frontend accepted"],
                    [],
                    owned_paths=["app/Frontend"],
                    criterion_ids=["frontend-accepted"],
                    feedback_checks=["frontend-tests"],
                ),
            ],
        )
        delivery = kernel.load(self.root, "feature")
        delivery.issue = {"number": 42, "title": "Feature", "url": "https://example/42"}
        delivery.pr = {"number": 17, "url": "https://example/pr/17", "state": "open"}
        delivery.repo = "acme/app"
        delivery.status = "done"
        for stage in delivery.stages:
            stage.status = "done"
            stage.attempts = 1
            stage.verified = [
                {
                    "criterion": stage.criterion_ids[0],
                    "runner": "file-exists",
                    "args": [stage.owned_paths[0]],
                    "exit": 0,
                }
            ]
        kernel.save(self.root, delivery)
        kernel.write_views(self.root, delivery)

    def tearDown(self):
        self.tmp.cleanup()

    def check_runner(self, name="phpunit", link="https://example/runs/1", bucket="fail"):
        return FakeRunner(
            {
                CHECKS: (
                    0,
                    json.dumps([{"name": name, "bucket": bucket, "link": link}]),
                )
            }
        )

    def review_runner(self, comment="99", path="app/Backend/Feature.php"):
        return FakeRunner(
            {
                REVIEWS: (
                    0,
                    json.dumps(
                        [
                            {
                                "id": int(comment),
                                "path": path,
                                "line": 12,
                                "html_url": f"https://example/comments/{comment}",
                            }
                        ]
                    ),
                )
            }
        )

    def ingest_check(self, **kwargs):
        return kernel.ingest(
            self.root,
            "feature",
            kind="check",
            check=kwargs.pop("check", "phpunit"),
            runner=kwargs.pop("runner", self.check_runner()),
            **kwargs,
        )

    def report_backend(self):
        kernel.claim_stage(self.root, "feature", "backend")
        kernel.record_stage_usage(
            self.root,
            "backend-developer",
            {
                "seconds": 1,
                "tool_calls": 1,
                "turns": 1,
                "tokens": 10,
                "cost_usd": 0.01,
            },
            expected_target=("feature", "backend"),
        )
        report = self.root / "docs/delivery/feature/stages/backend-developer.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "STATUS: done\n"
            "DID: app/Backend/Feature.php\n"
            'VERIFIED: {"criterion":"backend-accepted","runner":"file-exists",'
            '"args":["app/Backend/Feature.php"]}\n'
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        kernel.report(self.root, "feature", report, VerifyRunner())

    def test_feedback_checks_are_unique_across_stages(self):
        with self.assertRaisesRegex(kernel.PlanError, "belongs to both"):
            kernel.plan(
                root=self.root,
                name="duplicate",
                done_when="done",
                stages=[
                    kernel.StageSpec(
                        "one", "backend-developer", "writer", ["one"], [],
                        owned_paths=["one"], feedback_checks=["phpunit"]
                    ),
                    kernel.StageSpec(
                        "two", "frontend-developer", "writer", ["two"], [],
                        owned_paths=["two"], feedback_checks=["phpunit"]
                    ),
                ],
            )

    def test_ci_failure_routes_to_declared_owner(self):
        result = self.ingest_check()
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["stage"], "backend")
        self.assertEqual(delivery.stages[0].status, "queued")
        self.assertEqual(delivery.stages[1].status, "done")
        self.assertEqual(delivery.feedback_events[0]["route"], "declared-check")

    def test_caller_cannot_redirect_feedback_to_another_stage(self):
        with self.assertRaisesRegex(kernel.PlanError, "belongs to stage backend"):
            self.ingest_check(stage_id="frontend")
        self.assertEqual(kernel.load(self.root, "feature").feedback_events, [])

    def test_unmapped_check_requires_a_durable_route_before_dispatch(self):
        result = self.ingest_check(
            check="security",
            runner=self.check_runner(name="security"),
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(result["action"], "route_required")
        self.assertEqual(delivery.feedback_events[0]["status"], "route_required")
        self.assertEqual(kernel.ready_stages(self.root, "feature"), [])
        self.assertTrue(kernel.next_agent(self.root, "feature").startswith("FEEDBACK_ROUTE_REQUIRED:"))

    def test_main_assignment_persists_the_check_route_and_reopens_owner(self):
        result = self.ingest_check(
            check="security",
            runner=self.check_runner(name="security"),
        )
        assigned = kernel.assign_feedback(
            self.root, "feature", result["event_id"], "backend"
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(assigned["action"], "reopen")
        self.assertIn("security", delivery.stages[0].feedback_checks)
        self.assertEqual(delivery.feedback_events[0]["route"], "main-assignment")
        with self.assertRaisesRegex(kernel.PlanError, "main thread"):
            kernel.assign_feedback(
                self.root,
                "feature",
                result["event_id"],
                "backend",
                assigned_by="backend-developer",
            )

    def test_review_comment_routes_by_owned_path(self):
        result = kernel.ingest(
            self.root,
            "feature",
            kind="review",
            comment="99",
            runner=self.review_runner(path="app/Frontend/Page.php"),
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(result["stage"], "frontend")
        self.assertEqual(delivery.stages[1].status, "queued")
        self.assertEqual(delivery.feedback_events[0]["route"], "owned-path")

    def test_unowned_review_cannot_be_assigned_to_a_non_owner(self):
        result = kernel.ingest(
            self.root,
            "feature",
            kind="review",
            comment="99",
            runner=self.review_runner(path="README.md"),
        )
        with self.assertRaisesRegex(kernel.PlanError, "not owned"):
            kernel.assign_feedback(
                self.root, "feature", result["event_id"], "backend"
            )

    def test_multiple_open_feedback_items_share_one_repair_attempt(self):
        first = self.ingest_check()
        second = kernel.ingest(
            self.root,
            "feature",
            kind="review",
            comment="99",
            runner=self.review_runner(),
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(first["action"], "reopen")
        self.assertEqual(second["action"], "attached")
        self.assertEqual(delivery.stages[0].reopens, 1)
        self.assertEqual(len(delivery.retry_events), 1)
        self.assertEqual(len(delivery.feedback_events), 2)

    def test_successful_report_resolves_every_open_feedback_item(self):
        self.ingest_check()
        kernel.ingest(
            self.root,
            "feature",
            kind="review",
            comment="99",
            runner=self.review_runner(),
        )
        self.report_backend()
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(
            [event["status"] for event in delivery.feedback_events],
            ["resolved", "resolved"],
        )
        self.assertEqual(delivery.stages[0].feedback_event_ids, [])
        self.assertTrue(all(event["resolved_attempt"] == 2 for event in delivery.feedback_events))

    def test_resolved_event_is_idempotent_but_new_failure_stops(self):
        first = self.ingest_check()
        self.report_backend()
        duplicate = self.ingest_check()
        self.assertEqual(duplicate["action"], "noop")
        self.assertEqual(duplicate["event_id"], first["event_id"])

        new_failure = self.ingest_check(
            runner=self.check_runner(link="https://example/runs/2")
        )
        delivery = kernel.load(self.root, "feature")
        self.assertEqual(new_failure["action"], "stopped")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(delivery.feedback_events[-1]["status"], "stopped")

    def test_watch_routes_feedback_even_after_delivery_is_done(self):
        runner = FakeRunner(
            {
                CHECKS: (
                    0,
                    json.dumps(
                        [
                            {
                                "name": "frontend-tests",
                                "bucket": "fail",
                                "link": "https://example/runs/frontend-1",
                            }
                        ]
                    ),
                )
            }
        )
        result = kernel.watch_once(self.root, "feature", runner)
        self.assertEqual(result["action"], "reopen")
        self.assertEqual(result["stage"], "frontend")

    def test_closed_pr_rejects_ingest_and_stops_watching(self):
        delivery = kernel.load(self.root, "feature")
        delivery.pr["state"] = "merged"
        kernel.save(self.root, delivery)
        with self.assertRaisesRegex(kernel.PlanError, "open PR"):
            self.ingest_check()
        result = kernel.watch_once(self.root, "feature", self.check_runner())
        self.assertEqual(result, {"action": "closed"})

    def test_legacy_state_loads_empty_feedback_fields(self):
        state_path = self.root / "docs/delivery/feature/kernel.json"
        state = json.loads(state_path.read_text())
        state.pop("feedback_events")
        for stage in state["stages"]:
            stage.pop("feedback_checks")
            stage.pop("feedback_event_ids")
        state_path.write_text(json.dumps(state))
        loaded = kernel.load(self.root, "feature")
        self.assertEqual(loaded.feedback_events, [])
        self.assertTrue(all(stage.feedback_checks == [] for stage in loaded.stages))

    def test_feedback_view_and_cli_list_preserve_the_audit_trail(self):
        self.ingest_check()
        view = (self.root / "docs/delivery/feature/feedback.md").read_text()
        self.assertIn("CI check", view)
        self.assertIn("declared-check", view)
        guild = REPO / "scripts/guild-kernel/guild.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(guild),
                "feedback",
                "list",
                "--root",
                str(self.root),
                "--name",
                "feature",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["events"][0]["stage"], "backend")
        self.assertIn(
            {"kind": "check", "selector": "phpunit", "stage": "backend"},
            payload["routes"],
        )


class FeedbackHookTest(unittest.TestCase):
    def test_subagent_cannot_assign_feedback_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = REPO / "scripts" / "enforce-kernel-approvals.sh"
            payload = {
                "hook_event_name": "PreToolUse",
                "agent_type": "laravel-team:backend-developer",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python3 scripts/guild-kernel/guild.py feedback assign "
                    "--root . --name feature --event-id check:security:1 "
                    "--stage backend"
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
            self.assertIn("assign feedback routes", result.stderr)


if __name__ == "__main__":
    unittest.main()
