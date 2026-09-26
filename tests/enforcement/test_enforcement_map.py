import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "guild_enforcement_map", REPO / "scripts" / "check-enforcement-map.py"
)
enforcement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enforcement)


class EnforcementMapTest(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(
            (REPO / "config" / "enforcement-map.json").read_text(encoding="utf-8")
        )

    def test_committed_manifest_and_document_are_exact(self):
        controls = enforcement.validate(self.payload)
        expected = enforcement.render(self.payload, controls)

        self.assertEqual(
            (REPO / "docs" / "enforcement-map.md").read_text(encoding="utf-8"),
            expected,
        )
        self.assertEqual(
            {control["id"] for control in controls},
            enforcement.REQUIRED_CONTROL_IDS,
        )

    def test_every_control_has_executable_evidence_and_a_non_prompt_boundary(self):
        controls = enforcement.validate(self.payload)

        for control in controls:
            self.assertTrue(control["evidence"])
            self.assertNotEqual(set(control["enforcement"]), {"prompt"})
            for path in control["evidence"]:
                self.assertTrue((REPO / path).is_file(), path)

    def test_rejects_repository_path_escape(self):
        payload = copy.deepcopy(self.payload)
        payload["controls"][0]["implementation"][0] = "../outside.py"

        with self.assertRaisesRegex(
            enforcement.EnforcementMapError, "inside the repository"
        ):
            enforcement.validate(payload)

    def test_rejects_ci_job_that_is_not_a_release_gate(self):
        payload = copy.deepcopy(self.payload)
        payload["controls"][0]["ciJobs"].append("advisory only")

        with self.assertRaisesRegex(
            enforcement.EnforcementMapError, "not release gates"
        ):
            enforcement.validate(payload)

    def test_rejects_prompt_only_guarantee(self):
        payload = copy.deepcopy(self.payload)
        payload["controls"][0]["enforcement"] = ["prompt"]
        payload["controls"][0]["ciJobs"] = []

        with self.assertRaisesRegex(enforcement.EnforcementMapError, "prompt text alone"):
            enforcement.validate(payload)

    def test_checker_cli_reports_the_control_count(self):
        result = subprocess.run(
            [sys.executable, "scripts/check-enforcement-map.py"],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok: 19 enforcement controls", result.stdout)


if __name__ == "__main__":
    unittest.main()
