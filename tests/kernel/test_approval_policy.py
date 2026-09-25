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


class ApprovalPolicyIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.hook = REPO / "scripts" / "enforce-kernel-approvals.sh"
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="migration is ready",
            stages=[
                kernel.StageSpec(
                    "database",
                    "database-developer",
                    "writer",
                    ["migration is reversible"],
                    [],
                    owned_paths=["database/migrations"],
                    approval_categories=["destructive migration"],
                )
            ],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, tool_name, tool_input, *, agent="database-developer"):
        payload = {"tool_name": tool_name, "tool_input": tool_input}
        if agent is not None:
            payload["agent_type"] = f"laravel-team:{agent}"
        return subprocess.run(
            [str(self.hook)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
        )

    def test_user_approval_then_claim_changes_bash_from_denied_to_allowed(self):
        pending = self.invoke("Bash", {"command": "php artisan migrate"})
        self.assertEqual(pending.returncode, 2)
        self.assertIn("user approval is pending", pending.stderr)

        kernel.approve_stage_action(
            self.root,
            "tag",
            "database",
            "destructive migration",
        )
        unclaimed = self.invoke("Bash", {"command": "php artisan migrate"})
        self.assertEqual(unclaimed.returncode, 2)
        self.assertIn("not claimed", unclaimed.stderr)

        kernel.claim_stage(self.root, "tag", "database")
        claimed = self.invoke("Bash", {"command": "php artisan migrate"})
        self.assertEqual(claimed.returncode, 0, claimed.stderr)

        persisted = json.loads(
            (self.root / "docs/delivery/tag/kernel.json").read_text()
        )
        self.assertEqual(
            persisted["stages"][0]["approvals"][0]["by"],
            "user",
        )

    def test_main_thread_cannot_replace_kernel_state_with_native_write(self):
        result = self.invoke(
            "Write",
            {
                "file_path": "docs/delivery/tag/kernel.json",
                "contents": "{}",
            },
            agent=None,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("kernel-owned", result.stderr)


if __name__ == "__main__":
    unittest.main()
