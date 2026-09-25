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


class CheckpointPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def options():
        return [
            {
                "id": "approve",
                "label": "Approve the guarded implementation",
                "action": "continue",
            },
            {
                "id": "modify",
                "label": "Continue with the answer note as a constraint",
                "action": "continue",
            },
            {
                "id": "stop",
                "label": "Stop this delivery lane",
                "action": "stop",
            },
        ]

    def plan(self, *, two=False):
        stages = [
            kernel.StageSpec(
                "backend",
                "backend-developer",
                "writer",
                ["endpoint behavior is verified"],
                [],
                owned_paths=["app"],
                criterion_ids=["endpoint-verified"],
            )
        ]
        if two:
            stages.append(
                kernel.StageSpec(
                    "frontend",
                    "frontend-developer",
                    "writer",
                    ["screen behavior is verified"],
                    [],
                    owned_paths=["resources"],
                    criterion_ids=["screen-verified"],
                )
            )
        return kernel.plan(
            root=self.root,
            name="checkout",
            done_when="checkout is complete",
            stages=stages,
            max_parallel=2,
        )

    def open(self, **overrides):
        values = {
            "stage_id": "backend",
            "checkpoint_id": "billing-contract",
            "question": "May this lane change the billing contract?",
            "risk": "A wrong choice can double-charge a retry.",
            "options": self.options(),
            "recommended": "approve",
        }
        values.update(overrides)
        return kernel.open_checkpoint(
            self.root,
            "checkout",
            values["stage_id"],
            values["checkpoint_id"],
            values["question"],
            values["risk"],
            values["options"],
            values["recommended"],
        )

    def test_open_persists_exact_prompt_and_pauses_only_its_stage(self):
        self.plan(two=True)
        checkpoint = self.open()

        self.assertEqual(checkpoint["status"], "pending")
        self.assertEqual(checkpoint["recommended"], "approve")
        self.assertEqual(checkpoint["opened_by"], "main")
        self.assertTrue(checkpoint["opened_at"])
        self.assertEqual(checkpoint["answer"], {})

        resumed = kernel.load(self.root, "checkout")
        backend, frontend = resumed.stages
        self.assertEqual(backend.status, "paused")
        self.assertEqual(backend.checkpoint_id, "billing-contract")
        self.assertEqual(frontend.status, "queued")
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "checkout")],
            ["frontend"],
        )
        self.assertEqual(
            kernel.next_agent(self.root, "checkout"),
            "CHECKPOINT_REQUIRED: billing-contract",
        )
        self.assertIn(
            "backend ⏸ backend-developer checkpoint:billing-contract",
            kernel.board_line(resumed),
        )
        view = (self.root / "docs/delivery/checkout/checkpoints.md").read_text()
        self.assertIn("May this lane change the billing contract?", view)
        self.assertIn("`approve` (recommended) [continue]", view)
        self.assertIn("Answer: pending", view)

    def test_open_is_idempotent_but_checkpoint_ids_cannot_be_redefined(self):
        self.plan()
        first = self.open()
        again = self.open()
        self.assertEqual(first, again)
        self.assertEqual(len(kernel.checkpoint_rows(self.root, "checkout")), 1)
        with self.assertRaisesRegex(kernel.PlanError, "already exists"):
            self.open(risk="A different risk cannot replace the stored prompt.")

    def test_open_rejects_invalid_shape_and_unfinished_claim(self):
        self.plan()
        invalid = [
            {"checkpoint_id": "Bad Id"},
            {"question": ""},
            {"risk": ""},
            {"options": self.options()[:1]},
            {
                "options": [
                    {"id": "same", "label": "One", "action": "continue"},
                    {"id": "same", "label": "Two", "action": "stop"},
                ]
            },
            {
                "options": [
                    {"id": "yes", "label": "Yes", "action": "invented"},
                    {"id": "no", "label": "No", "action": "stop"},
                ]
            },
            {"recommended": "missing"},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(kernel.PlanError):
                self.open(**values)

        kernel.claim_stage(self.root, "checkout", "backend")
        with self.assertRaisesRegex(kernel.PlanError, "completion telemetry"):
            self.open()

    def test_pending_checkpoint_blocks_claim_report_and_completion(self):
        self.plan()
        self.open()
        with self.assertRaisesRegex(kernel.PlanError, "paused at checkpoint"):
            kernel.claim_stage(self.root, "checkout", "backend")

        artifact = self.root / "app/Checkout.php"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("<?php\n")
        report = self.root / "docs/delivery/checkout/stages/backend-developer.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "STATUS: done\nDID: app/Checkout.php\n"
            'VERIFIED: {"criterion":"endpoint-verified","runner":"file-exists",'
            '"args":["app/Checkout.php"]}\n'
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner()
        with self.assertRaisesRegex(kernel.ReportError, "paused at checkpoint"):
            kernel.report(self.root, "checkout", report, runner)
        self.assertEqual(runner.calls, [])
        self.assertFalse(kernel._dod_met(kernel.load(self.root, "checkout")))

    def test_user_continue_answer_is_durable_and_requeues_the_lane(self):
        self.plan()
        self.open()
        with self.assertRaisesRegex(kernel.PlanError, "only be answered by the user"):
            kernel.resolve_checkpoint(
                self.root,
                "checkout",
                "billing-contract",
                "approve",
                answered_by="agent",
            )
        resolved = kernel.resolve_checkpoint(
            self.root,
            "checkout",
            "billing-contract",
            "modify",
            note="Keep the existing idempotency key.",
        )
        answer = resolved["answer"]
        self.assertEqual(answer["by"], "user")
        self.assertEqual(answer["option"], "modify")
        self.assertEqual(answer["action"], "continue")
        self.assertEqual(answer["note"], "Keep the existing idempotency key.")
        self.assertTrue(answer["at"])

        resumed = kernel.load(self.root, "checkout")
        self.assertEqual(resumed.stages[0].status, "queued")
        self.assertEqual(resumed.stages[0].checkpoint_id, "")
        self.assertEqual(
            [stage.id for stage in kernel.ready_stages(self.root, "checkout")],
            ["backend"],
        )
        self.assertIn("Answer: `modify` by user", kernel.render_checkpoints(resumed))
        self.assertEqual(
            kernel.resolve_checkpoint(
                self.root,
                "checkout",
                "billing-contract",
                "modify",
                note="Keep the existing idempotency key.",
            ),
            resolved,
        )

    def test_user_stop_answer_stops_the_lane_and_delivery(self):
        self.plan()
        self.open()
        resolved = kernel.resolve_checkpoint(
            self.root, "checkout", "billing-contract", "stop"
        )
        self.assertEqual(resolved["answer"]["action"], "stop")
        delivery = kernel.load(self.root, "checkout")
        self.assertEqual(delivery.status, "stopped")
        self.assertEqual(delivery.stages[0].status, "failed")
        self.assertEqual(kernel.ready_stages(self.root, "checkout"), [])
        self.assertEqual(kernel.next_agent(self.root, "checkout"), "STOP")

    def test_paused_stage_can_receive_a_user_criterion_waiver(self):
        self.plan()
        self.open()
        waiver = kernel.waive_stage_criterion(
            self.root,
            "checkout",
            "backend",
            "endpoint-verified",
            "User accepted manual staging verification",
        )
        self.assertEqual(waiver["by"], "user")

    def test_legacy_state_loads_empty_checkpoint_fields(self):
        self.plan()
        state_path = self.root / "docs/delivery/checkout/kernel.json"
        state = json.loads(state_path.read_text())
        state.pop("checkpoints")
        state["stages"][0].pop("checkpoint_id")
        state_path.write_text(json.dumps(state))
        loaded = kernel.load(self.root, "checkout")
        self.assertEqual(loaded.checkpoints, [])
        self.assertEqual(loaded.stages[0].checkpoint_id, "")

    def test_checkpoint_cli_open_list_and_resolve(self):
        self.plan()
        cli = REPO / "scripts/guild-kernel/guild.py"
        common = ["--root", str(self.root), "--name", "checkout"]
        opened = subprocess.run(
            [
                sys.executable,
                str(cli),
                "checkpoint",
                "open",
                *common,
                "--stage",
                "backend",
                "--id",
                "billing-contract",
                "--question",
                "May billing change?",
                "--risk",
                "Retries can double-charge.",
                "--option-json",
                json.dumps(self.options()[0]),
                "--option-json",
                json.dumps(self.options()[2]),
                "--recommended",
                "approve",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("CHECKPOINT: billing-contract pending for backend", opened.stdout)
        listed = subprocess.run(
            [sys.executable, str(cli), "checkpoint", "list", *common],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(listed.stdout)[0]["question"], "May billing change?")
        resolved = subprocess.run(
            [
                sys.executable,
                str(cli),
                "checkpoint",
                "resolve",
                *common,
                "--id",
                "billing-contract",
                "--option",
                "approve",
                "--note",
                "Accepted by the user",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("RESOLVED: billing-contract approve by user", resolved.stdout)


class CheckpointHookTest(unittest.TestCase):
    def test_subagent_cannot_open_or_resolve_checkpoints(self):
        hook = REPO / "scripts" / "enforce-kernel-approvals.sh"
        for action in (
            "checkpoint open --root . --name checkout --stage backend",
            "checkpoint resolve --root . --name checkout --id billing --option approve",
        ):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                payload = {
                    "agent_type": "laravel-team:backend-developer",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "python3 scripts/guild-kernel/guild.py " + action
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
                self.assertIn("mutate checkpoints", result.stderr)


if __name__ == "__main__":
    unittest.main()
