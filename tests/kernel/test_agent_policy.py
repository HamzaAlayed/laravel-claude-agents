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


class AgentPathPolicyIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.hook = REPO / "scripts" / "enforce-agent-paths.sh"
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="Tag model exists",
            stages=[
                kernel.StageSpec(
                    "model",
                    "backend-developer",
                    "writer",
                    ["Tag model exists"],
                    [],
                    owned_paths=["app/Models"],
                )
            ],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, path):
        payload = json.dumps(
            {
                "agent_type": "laravel-team:backend-developer",
                "tool_name": "Write",
                "tool_input": {"file_path": path},
            }
        )
        return subprocess.run(
            [str(self.hook)],
            input=payload,
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
        )

    def test_atomic_claim_changes_native_write_from_denied_to_scoped(self):
        queued = self.invoke("app/Models/Tag.php")
        self.assertEqual(queued.returncode, 2)
        self.assertIn("not claimed", queued.stderr)

        kernel.claim_stage(self.root, "tag", "model")

        owned = self.invoke("app/Models/Tag.php")
        self.assertEqual(owned.returncode, 0, owned.stderr)
        outside = self.invoke("routes/api.php")
        self.assertEqual(outside.returncode, 2)
        self.assertIn("outside stage model owned_paths", outside.stderr)


if __name__ == "__main__":
    unittest.main()
