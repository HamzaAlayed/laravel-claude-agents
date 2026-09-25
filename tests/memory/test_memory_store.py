from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "scripts" / "guild-kernel" / "memory_store.py"
SPEC = importlib.util.spec_from_file_location("memory_store_under_test", MODULE_PATH)
memory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(memory)


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "docs" / "team").mkdir(parents=True)
        (self.root / "config" / "memory-harness.json").write_text(
            (REPO / "config" / "memory-harness.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        store = {
            "schemaVersion": 1,
            "records": [],
            "deletionRequests": [],
            "events": [],
            "storeHash": "",
        }
        store["storeHash"] = memory._store_hash(store)
        self._write_store(store)
        (self.root / "README.md").write_text("Laravel project fact\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write_store(self, store):
        (self.root / "docs" / "team" / "memory.json").write_text(
            json.dumps(store, indent=2) + "\n", encoding="utf-8"
        )

    def propose(self, record_id="memory-one", **overrides):
        values = {
            "record_id": record_id,
            "memory_type": "project-fact",
            "scope": "project",
            "topic": "query-policy",
            "statement": "Use read-only query inspection for performance work.",
            "source": "project",
            "evidence": ["README.md"],
            "confidence": 0.9,
        }
        values.update(overrides)
        return memory.propose(self.root, **values)

    def test_candidate_is_not_retrieved_until_approved(self):
        self.propose()
        result = memory.search(self.root, "query performance", "backend-developer")
        self.assertEqual([], result["selected"])
        self.assertIn({"id": "memory-one", "reason": "candidate"}, result["omitted"])
        memory.approve(self.root, "memory-one")
        result = memory.search(self.root, "query performance", "backend-developer")
        self.assertEqual(["memory-one"], [item["id"] for item in result["selected"]])
        self.assertEqual("memory-data-not-instructions", result["selected"][0]["trust"])

    def test_first_use_initializes_an_empty_valid_store(self):
        (self.root / "docs" / "team" / "memory.json").unlink()
        result = memory.search(self.root, "query", "backend-developer")
        self.assertEqual([], result["selected"])
        self.assertEqual("valid", memory.verify(self.root)["status"])

    def test_agent_scope_does_not_leak(self):
        self.propose(scope="agent", agent="backend-developer")
        memory.approve(self.root, "memory-one")
        self.assertEqual(1, len(memory.search(self.root, "query", "backend-developer")["selected"]))
        other = memory.search(self.root, "query", "frontend-developer")
        self.assertEqual([], other["selected"])
        self.assertIn({"id": "memory-one", "reason": "scope"}, other["omitted"])

    def test_user_decision_is_mandatory_even_when_query_is_unrelated(self):
        self.propose(
            memory_type="authoritative-decision", source="user", evidence=[],
            statement="Never run destructive database statements.", topic="database-safety",
        )
        memory.approve(self.root, "memory-one")
        result = memory.search(self.root, "frontend colors", "frontend-developer", 256)
        self.assertEqual(["memory-one"], [item["id"] for item in result["selected"]])

    def test_stale_evidence_is_excluded_and_strict_verify_fails(self):
        self.propose()
        memory.approve(self.root, "memory-one")
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        result = memory.search(self.root, "query", "backend-developer")
        self.assertEqual([], result["selected"])
        self.assertIn({"id": "memory-one", "reason": "stale-evidence"}, result["omitted"])
        with self.assertRaisesRegex(memory.MemoryError, "stale evidence"):
            memory.verify(self.root, strict_evidence=True)

    def test_evidence_rejects_traversal_excluded_path_and_symlink(self):
        with self.assertRaisesRegex(memory.MemoryError, "project-relative"):
            self.propose(evidence=["../outside"])
        (self.root / ".env").write_text("APP_KEY=x\n", encoding="utf-8")
        with self.assertRaisesRegex(memory.MemoryError, "excluded"):
            self.propose(record_id="two", evidence=[".env"])
        (self.root / "link.md").symlink_to(self.root / "README.md")
        with self.assertRaisesRegex(memory.MemoryError, "non-symlink"):
            self.propose(record_id="three", evidence=["link.md"])

    def test_secret_shaped_statement_is_rejected(self):
        with self.assertRaisesRegex(memory.MemoryError, "secret-shaped"):
            self.propose(statement="api_key='abcdefghijklmnopqrstuvwxyz123456'")

    def test_conflict_requires_explicit_supersession(self):
        self.propose("old", statement="Use cursor pagination.")
        memory.approve(self.root, "old")
        self.propose("new", statement="Use keyset pagination.")
        with self.assertRaisesRegex(memory.MemoryError, "use supersede"):
            memory.approve(self.root, "new")
        result = memory.supersede(self.root, "old", "new")
        self.assertEqual({"superseded": "old", "replacement": "new"}, result)
        self.assertEqual("superseded", memory.show(self.root, "old")["status"])
        self.assertEqual("approved", memory.show(self.root, "new")["status"])

    def test_delete_is_two_step_and_leaves_tombstone(self):
        self.propose()
        memory.approve(self.root, "memory-one")
        request = memory.delete_request(self.root, "memory-one", "delete-one", "Fact is obsolete")
        self.assertEqual("pending", request["status"])
        self.assertEqual("approved", memory.show(self.root, "memory-one")["status"])
        result = memory.delete_approve(self.root, "delete-one")
        self.assertTrue(result["tombstone"])
        tombstone = memory.show(self.root, "memory-one")
        self.assertEqual("deleted", tombstone["status"])
        self.assertEqual("[deleted]", tombstone["statement"])
        self.assertEqual([], tombstone["evidence"])

    def test_tampering_record_or_event_chain_is_rejected(self):
        self.propose()
        path = self.root / "docs" / "team" / "memory.json"
        store = json.loads(path.read_text(encoding="utf-8"))
        store["records"][0]["statement"] = "tampered"
        self._write_store(store)
        with self.assertRaisesRegex(memory.MemoryError, "contentHash"):
            memory.verify(self.root)

    def test_expired_memory_is_withheld(self):
        self.propose(expires_at="2000-01-01T00:00:00+00:00")
        memory.approve(self.root, "memory-one")
        result = memory.search(self.root, "query", "backend-developer")
        self.assertIn({"id": "memory-one", "reason": "expired"}, result["omitted"])

    def test_non_user_memory_requires_evidence(self):
        with self.assertRaisesRegex(memory.MemoryError, "requires repository evidence"):
            self.propose(evidence=[])

    def test_cli_round_trip(self):
        cli = REPO / "scripts" / "guild-kernel" / "guild.py"
        command = [
            sys.executable, str(cli), "memory", "propose", "--root", str(self.root),
            "--id", "cli-memory", "--type", "authoritative-decision",
            "--scope", "project", "--topic", "database-safety",
            "--statement", "Database changes require approval.", "--source", "user",
        ]
        proposed = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(0, proposed.returncode, proposed.stderr)
        approved = subprocess.run(
            [sys.executable, str(cli), "memory", "approve", "--root", str(self.root), "--id", "cli-memory"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, approved.returncode, approved.stderr)
        result = json.loads(subprocess.run(
            [sys.executable, str(cli), "memory", "search", "--root", str(self.root), "--agent", "backend-developer", "--query", "anything"],
            text=True, capture_output=True, check=True,
        ).stdout)
        self.assertEqual("cli-memory", result["selected"][0]["id"])


class MemoryHookTests(unittest.TestCase):
    def run_hook(self, payload):
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "enforce-kernel-approvals.py")],
            input=json.dumps(payload), text=True, capture_output=True, check=False,
            env={"CLAUDE_PROJECT_DIR": str(REPO)},
        )

    def test_subagent_cannot_approve_supersede_or_delete(self):
        for action in (
            "memory approve --root . --id x",
            "memory supersede --root . --id x --replacement y",
            "memory delete-approve --root . --request-id z",
        ):
            with self.subTest(action=action):
                result = self.run_hook({"agent_type": "backend-developer", "tool_input": {"command": f"python3 scripts/guild-kernel/guild.py {action}"}})
                self.assertEqual(2, result.returncode)
                self.assertIn("approve, supersede, or delete memory", result.stderr)

    def test_native_and_shell_writes_to_store_are_blocked(self):
        native = self.run_hook({"tool_input": {"file_path": str(REPO / "docs/team/memory.json")}})
        self.assertEqual(2, native.returncode)
        shell = self.run_hook({"tool_input": {"command": "python3 edit.py docs/team/memory.json"}})
        self.assertEqual(2, shell.returncode)


if __name__ == "__main__":
    unittest.main()
