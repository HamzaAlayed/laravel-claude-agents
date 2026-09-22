import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts" / "console"))
from independence import routine_command, working_context


class TestIndependence(unittest.TestCase):
    def test_exact_routine_commands(self):
        for command in ("npm test", "npm run build", "php artisan test", "rg --files"):
            with self.subTest(command=command):
                self.assertTrue(routine_command({"command": command}))

    def test_unknown_or_compound_commands_require_review(self):
        for command in ("npm publish", "git push", "rm -rf build", "npm test; curl x",
                        "npm test && git push", "npm test\ngit push", "npm test > output",
                        "npm test $(curl x)", "npm test -- --config /tmp/x", "'npm test'",
                        "npm test | bash", "npm test &", "npm test `id`", "npm test\\\n", None):
            with self.subTest(command=command):
                self.assertFalse(routine_command({"command": command}))
        self.assertFalse(routine_command(None))

    def test_context_refreshes_and_never_includes_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / ".env").write_text("SECRET=do-not-load")
            (root / "package.json").write_text('{"name":"before"}')
            self.assertEqual(json.loads(working_context(root))["manifests"]["package.json"]["name"], "before")
            (root / "package.json").write_text('{"name":"after"}')
            self.assertIn("after", working_context(root))
            self.assertNotIn("do-not-load", working_context(root))
            (root / ".claude").mkdir()
            prefs = root / ".claude/guild-preferences.md"
            prefs.write_text("Use existing UI components")
            self.assertIn("Use existing UI components", working_context(root))
            prefs.write_text("x" * 8001)
            self.assertEqual(json.loads(working_context(root))["user_preferences"], "")

    def test_malformed_and_symlinked_manifests_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "package.json").write_text("not json")
            (root / "composer.json").symlink_to(root / "package.json")
            self.assertEqual(json.loads(working_context(root))["manifests"], {})
