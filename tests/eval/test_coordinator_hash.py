"""Unit tests for the coordinator content hash in scripts/check_inventory_sync.py.

The hash pins the surfaces that steer delegation — the coordinator body and the
commands' shared Interface block — to the last billed run of the `feature` eval
case. CI cannot run billed evals; it CAN refuse to let those surfaces ship
changed without a human recording either a re-run or a dated waiver.
"""

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_inventory_sync", ROOT / "scripts" / "check_inventory_sync.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)


def make_tree(base: pathlib.Path, body="coordinator v1",
              interface="> **Interface:** the shared block") -> pathlib.Path:
    (base / "agents").mkdir(parents=True)
    (base / "commands").mkdir()
    (base / "tests" / "eval").mkdir(parents=True)
    (base / "agents" / "delivery-coordinator.md").write_text(body, encoding="utf-8")
    for name in ("a.md", "b.md"):
        (base / "commands" / name).write_text(
            f"# cmd\n\n{interface}\n\nbody\n", encoding="utf-8")
    return base


def pin(base: pathlib.Path, sha: str, waivers=()) -> None:
    (base / "tests" / "eval" / "baseline.json").write_text(json.dumps({
        "coordinator_hash": {"sha256": sha, "as_of": "2026-08-06",
                             "note": "test", "waivers": list(waivers)},
    }), encoding="utf-8")


class TestCoordinatorHash(unittest.TestCase):
    def test_stable_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            self.assertEqual(inv.coordinator_hash(root), inv.coordinator_hash(root))

    def test_changes_when_coordinator_body_changes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            h1 = inv.coordinator_hash(make_tree(pathlib.Path(a), body="v1"))
            h2 = inv.coordinator_hash(make_tree(pathlib.Path(b), body="v2"))
            self.assertNotEqual(h1, h2)

    def test_changes_when_interface_line_changes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            h1 = inv.coordinator_hash(make_tree(
                pathlib.Path(a), interface="> **Interface:** one"))
            h2 = inv.coordinator_hash(make_tree(
                pathlib.Path(b), interface="> **Interface:** two"))
            self.assertNotEqual(h1, h2)

    def test_ignores_command_edits_outside_the_interface_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            before = inv.coordinator_hash(root)
            cmd = root / "commands" / "a.md"
            cmd.write_text(cmd.read_text(encoding="utf-8")
                           + "\nan unrelated prose edit\n", encoding="utf-8")
            self.assertEqual(before, inv.coordinator_hash(root))

    def test_check_passes_on_pinned_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            pin(root, inv.coordinator_hash(root))
            self.assertEqual(inv.check_coordinator_hash(root), 0)

    def test_check_fails_on_unpinned_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            pin(root, "0" * 64)
            self.assertEqual(inv.check_coordinator_hash(root), 1)

    def test_waiver_accepts_the_drift_it_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            current = inv.coordinator_hash(root)
            pin(root, "0" * 64, waivers=[
                {"date": "2026-08-06", "sha256": current, "reason": "test waiver"}])
            self.assertEqual(inv.check_coordinator_hash(root), 0)

    def test_check_fails_when_pin_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            (root / "tests" / "eval" / "baseline.json").write_text("{}", encoding="utf-8")
            self.assertEqual(inv.check_coordinator_hash(root), 1)


if __name__ == "__main__":
    unittest.main()
