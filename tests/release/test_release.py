import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("guild_release", REPO / "scripts/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

JOBS = [
    "shellcheck",
    "guardrail tests",
    "plugin & marketplace manifests",
    "agent & command frontmatter",
    "gemini extension",
    "codex target",
    "ratchet budgets",
    "console python units",
    "guild kernel units",
    "adversarial engineering loop",
    "observability contract",
    "eval cost parser units",
    "console ui",
    "release automation",
]


def completed(stdout="", *, returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class QueueRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run(self, argv, *, cwd=release.ROOT, check=True):
        self.calls.append(list(argv))
        if not self.results:
            raise AssertionError(f"unexpected command: {argv}")
        result = self.results.pop(0)
        if check and result.returncode:
            raise release.ReleaseError("command failed")
        return result


def config():
    return {
        "schemaVersion": 1,
        "branch": "main",
        "ciWorkflow": "CI",
        "tagPrefix": "v",
        "releaseNotesDirectory": "docs/releases",
        "versionFiles": [
            {"path": ".claude-plugin/plugin.json", "field": "version"},
            {"path": ".claude-plugin/marketplace.json", "field": "plugins.0.version"},
        ],
        "requiredCiJobs": JOBS,
        "requiredReleaseNoteHeadings": [
            "## What’s new",
            "## Breaking changes",
            "## Fixes",
            "## Compatibility",
            "## Verification",
        ],
        "publication": {
            "tagType": "annotated",
            "draft": False,
            "prerelease": False,
            "force": False,
        },
    }


class ConfigTests(unittest.TestCase):
    def test_rejects_version_manifest_path_escape(self):
        payload = config()
        payload["versionFiles"][0]["path"] = "../VERSION"
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "release.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(release.ReleaseError, "inside the repository"):
                release._load_config(path)


class LocalValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / ".claude-plugin").mkdir()
        (self.root / "docs/releases").mkdir(parents=True)
        (self.root / "VERSION").write_text("8.6.0\n", encoding="utf-8")
        (self.root / ".claude-plugin/plugin.json").write_text(
            json.dumps({"version": "8.6.0"}), encoding="utf-8"
        )
        (self.root / ".claude-plugin/marketplace.json").write_text(
            json.dumps({"plugins": [{"version": "8.6.0"}]}), encoding="utf-8"
        )
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n## [8.6.0] - 2026-09-25\n",
            encoding="utf-8",
        )
        headings = "\n\n".join(config()["requiredReleaseNoteHeadings"])
        (self.root / "docs/releases/8.6.0.md").write_text(
            f"# Laravel Guild 8.6.0\n\n{headings}\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_synchronized_release_artifacts(self):
        result = release.validate_local(self.root, "8.6.0", config())

        self.assertEqual(result["version"], "8.6.0")
        self.assertEqual(result["notes"], "docs/releases/8.6.0.md")
        self.assertIn("CHANGELOG.md", result["artifacts"])

    def test_rejects_manifest_version_drift(self):
        path = self.root / ".claude-plugin/plugin.json"
        path.write_text(json.dumps({"version": "8.5.0"}), encoding="utf-8")

        with self.assertRaisesRegex(release.ReleaseError, "declares 8.5.0"):
            release.validate_local(self.root, "8.6.0", config())

    def test_rejects_incomplete_release_notes(self):
        path = self.root / "docs/releases/8.6.0.md"
        path.write_text("# Laravel Guild 8.6.0\n\n## What’s new\n", encoding="utf-8")

        with self.assertRaisesRegex(release.ReleaseError, "Breaking changes"):
            release.validate_local(self.root, "8.6.0", config())

    def test_rejects_non_stable_version(self):
        with self.assertRaisesRegex(release.ReleaseError, "stable X.Y.Z"):
            release.validate_local(self.root, "v8.6.0", config())

    def test_rejects_duplicate_changelog_entry(self):
        path = self.root / "CHANGELOG.md"
        entry = "## [8.6.0] - 2026-09-25\n"
        path.write_text(
            f"# Changelog\n\n## [Unreleased]\n\n{entry}\n{entry}", encoding="utf-8"
        )

        with self.assertRaisesRegex(release.ReleaseError, "dated release"):
            release.validate_local(self.root, "8.6.0", config())


class CiGateTests(unittest.TestCase):
    def runner(self, jobs=None, *, status="completed", conclusion="success"):
        run = {
            "databaseId": 42,
            "headSha": "a" * 40,
            "status": status,
            "conclusion": conclusion,
            "url": "https://example.test/actions/42",
            "createdAt": "2026-09-25T00:00:00Z",
        }
        details = {
            "status": status,
            "conclusion": conclusion,
            "url": run["url"],
            "jobs": jobs
            if jobs is not None
            else [
                {"name": name, "status": "completed", "conclusion": "success"}
                for name in JOBS
            ],
        }
        return QueueRunner(
            [completed(json.dumps([run])), completed(json.dumps(details))]
        )

    def test_requires_every_named_job_to_pass(self):
        result = release.verify_ci(
            self.runner(), pathlib.Path("."), "owner/repo", "a" * 40, config()
        )

        self.assertEqual(result["id"], 42)
        self.assertEqual(result["jobs"], sorted(JOBS))

    def test_rejects_missing_required_job(self):
        jobs = [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in JOBS[:-1]
        ]

        with self.assertRaisesRegex(release.ReleaseError, "release automation"):
            release.verify_ci(
                self.runner(jobs), pathlib.Path("."), "owner/repo", "a" * 40,
                config(),
            )

    def test_rejects_unsuccessful_run_before_reading_jobs(self):
        runner = self.runner(status="in_progress", conclusion="")

        with self.assertRaisesRegex(release.ReleaseError, "in_progress"):
            release.verify_ci(
                runner, pathlib.Path("."), "owner/repo", "a" * 40, config()
            )
        self.assertEqual(len(runner.calls), 1)

    def test_rejects_any_failed_job_even_if_not_on_allowlist(self):
        jobs = [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in JOBS
        ] + [{"name": "unexpected", "status": "completed", "conclusion": "failure"}]

        with self.assertRaisesRegex(release.ReleaseError, "unexpected"):
            release.verify_ci(
                self.runner(jobs), pathlib.Path("."), "owner/repo", "a" * 40,
                config(),
            )


class ImmutableTagTests(unittest.TestCase):
    def test_accepts_matching_annotated_local_and_remote_tag(self):
        commit = "a" * 40
        runner = QueueRunner(
            [
                completed(),
                completed(commit + "\n"),
                completed("tag\n"),
                completed(f"{'b' * 40}\trefs/tags/v8.6.0\n{commit}\trefs/tags/v8.6.0^{{}}\n"),
            ]
        )

        state = release._tag_state(runner, pathlib.Path("."), "v8.6.0", commit)

        self.assertTrue(state["local"])
        self.assertTrue(state["remote"])
        self.assertEqual(state["commit"], commit)

    def test_rejects_local_lightweight_tag(self):
        commit = "a" * 40
        runner = QueueRunner(
            [completed(), completed(commit + "\n"), completed("commit\n")]
        )

        with self.assertRaisesRegex(release.ReleaseError, "not annotated"):
            release._tag_state(runner, pathlib.Path("."), "v8.6.0", commit)

    def test_rejects_remote_lightweight_tag(self):
        commit = "a" * 40
        runner = QueueRunner(
            [completed(returncode=1), completed(f"{commit}\trefs/tags/v8.6.0\n")]
        )

        with self.assertRaisesRegex(release.ReleaseError, "not annotated"):
            release._tag_state(runner, pathlib.Path("."), "v8.6.0", commit)

    def test_rejects_remote_tag_for_another_commit(self):
        commit = "a" * 40
        runner = QueueRunner(
            [
                completed(returncode=1),
                completed(
                    f"{'b' * 40}\trefs/tags/v8.6.0\n"
                    f"{'c' * 40}\trefs/tags/v8.6.0^{{}}\n"
                ),
            ]
        )

        with self.assertRaisesRegex(release.ReleaseError, "not a{40}"):
            release._tag_state(runner, pathlib.Path("."), "v8.6.0", commit)

    def test_rejects_local_tag_inspection_error(self):
        runner = QueueRunner([completed(returncode=128)])

        with self.assertRaisesRegex(release.ReleaseError, "could not inspect"):
            release._tag_state(runner, pathlib.Path("."), "v8.6.0", "a" * 40)

    def test_rejects_malformed_remote_tag_response(self):
        runner = QueueRunner(
            [completed(returncode=1), completed("malformed refs/tags/v8.6.0\n")]
        )

        with self.assertRaisesRegex(release.ReleaseError, "malformed data"):
            release._tag_state(runner, pathlib.Path("."), "v8.6.0", "a" * 40)


class ExistingReleaseTests(unittest.TestCase):
    def test_absent_release_is_recoverable(self):
        runner = QueueRunner(
            [completed(returncode=1, stderr="release not found: v8.6.0")]
        )

        self.assertIsNone(
            release._release_state(
                runner, pathlib.Path("."), "owner/repo", "v8.6.0"
            )
        )

    def test_api_failure_is_not_mistaken_for_absence(self):
        runner = QueueRunner(
            [completed(returncode=1, stderr="HTTP 403: Resource not accessible")]
        )

        with self.assertRaisesRegex(release.ReleaseError, "could not inspect"):
            release._release_state(
                runner, pathlib.Path("."), "owner/repo", "v8.6.0"
            )

    def test_repository_not_found_is_not_mistaken_for_release_absence(self):
        runner = QueueRunner(
            [completed(returncode=1, stderr="HTTP 404: repository not found")]
        )

        with self.assertRaisesRegex(release.ReleaseError, "could not inspect"):
            release._release_state(
                runner, pathlib.Path("."), "owner/repo", "v8.6.0"
            )


class PublicationTests(unittest.TestCase):
    def state(self, *, local=False, remote=False, existing=None):
        return {
            "schemaVersion": 1,
            "version": "8.6.0",
            "tag": "v8.6.0",
            "commit": "a" * 40,
            "branch": "main",
            "repository": "owner/repo",
            "artifacts": ["VERSION"],
            "notes": "docs/releases/8.6.0.md",
            "ci": {"id": 42, "url": "https://example.test/actions/42", "jobs": JOBS},
            "tagState": {"local": local, "remote": remote, "commit": ""},
            "release": existing,
        }

    @mock.patch.object(release, "preflight")
    def test_publishes_tag_and_release_once(self, preflight):
        preflight.return_value = self.state()
        runner = QueueRunner(
            [completed(), completed(), completed("https://example.test/releases/v8.6.0\n")]
        )
        with tempfile.TemporaryDirectory() as tmp:
            receipt = pathlib.Path(tmp) / "receipt.json"
            result = release.publish(
                pathlib.Path(tmp),
                "8.6.0",
                "Laravel Guild 8.6.0 — Release Automation",
                receipt=str(receipt),
                runner=runner,
            )
            saved = json.loads(receipt.read_text(encoding="utf-8"))

        self.assertEqual(result["action"], "published")
        self.assertEqual(saved["releaseUrl"], result["releaseUrl"])
        self.assertEqual(runner.calls[0][:3], ["git", "tag", "-a"])
        self.assertEqual(runner.calls[1], ["git", "push", "origin", "v8.6.0"])
        self.assertEqual(runner.calls[2][:3], ["gh", "release", "create"])

    @mock.patch.object(release, "preflight")
    def test_rerun_is_noop_for_matching_existing_release(self, preflight):
        title = "Laravel Guild 8.6.0 — Release Automation"
        preflight.return_value = self.state(
            local=True,
            remote=True,
            existing={"name": title, "url": "https://example.test/releases/v8.6.0"},
        )
        runner = QueueRunner([])

        result = release.publish(pathlib.Path("."), "8.6.0", title, runner=runner)

        self.assertEqual(result["action"], "already-published")
        self.assertEqual(runner.calls, [])

    @mock.patch.object(release, "preflight")
    def test_rejects_existing_release_with_another_title(self, preflight):
        preflight.return_value = self.state(
            local=True,
            remote=True,
            existing={"name": "Wrong title", "url": "https://example.test/release"},
        )

        with self.assertRaisesRegex(release.ReleaseError, "title does not match"):
            release.publish(
                pathlib.Path("."),
                "8.6.0",
                "Laravel Guild 8.6.0 — Release Automation",
                runner=QueueRunner([]),
            )

    def test_rejects_noncanonical_title(self):
        with self.assertRaisesRegex(release.ReleaseError, "must start"):
            release._validate_title("Release automation", "8.6.0")


if __name__ == "__main__":
    unittest.main()
