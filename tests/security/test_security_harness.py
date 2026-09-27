import importlib.util
import json
import pathlib
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("guild_security_harness", REPO / "scripts/security-harness.py")
security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security)


class SecurityHarnessTest(unittest.TestCase):
    def test_policy_and_attack_registry_validate(self):
        policy, attacks = security.validate(REPO)
        self.assertEqual(policy["threatModel"]["framework"], "STRIDE")
        self.assertEqual(len(policy["controls"]), 6)
        self.assertEqual(len(attacks["attacks"]), 13)

    def test_receipt_round_trip_is_source_bound_and_contains_no_raw_inputs(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        security.verify_receipt(REPO, receipt, policy, attacks)
        serialized = json.dumps(receipt)
        for forbidden in policy["receipt"]["excludedRawData"]:
            self.assertNotIn(forbidden, serialized)

    def test_sec_011_tampered_receipt_is_rejected(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        receipt["summary"]["attacks"] = 999
        with self.assertRaisesRegex(security.SecurityHarnessError, "tampered"):
            security.verify_receipt(REPO, receipt, policy, attacks)

    def test_sec_012_source_drift_is_rejected(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        receipt["sources"]["config/security-attacks.json"] = "0" * 64
        receipt["receiptHash"] = security.digest_json({key: value for key, value in receipt.items() if key != "receiptHash"})
        with self.assertRaisesRegex(security.SecurityHarnessError, "source-drifted"):
            security.verify_receipt(REPO, receipt, policy, attacks)

    def test_path_escape_in_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            with self.assertRaisesRegex(security.SecurityHarnessError, "inside the repository"):
                security.repo_file(root, "../outside.txt", "evidence")

    def test_symlink_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "real.txt").write_text("evidence\n", encoding="utf-8")
            (root / "link.txt").symlink_to(root / "real.txt")
            with self.assertRaisesRegex(security.SecurityHarnessError, "non-symlink"):
                security.repo_file(root, "link.txt", "evidence")

    def test_receipt_hash_covers_all_fields(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        supplied = receipt.pop("receiptHash")
        self.assertEqual(supplied, security.digest_json(receipt))

    def test_receipt_writer_refuses_to_replace_a_sealed_source(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        with self.assertRaisesRegex(security.SecurityHarnessError, "sealed source"):
            security.write_receipt(
                REPO / "config/security-attacks.json", receipt, REPO, policy
            )

    def test_receipt_writer_refuses_symlink_and_nonempty_output(self):
        policy, attacks = security.validate(REPO)
        receipt = security.build_receipt(REPO, policy, attacks)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            occupied = root / "receipt.json"
            occupied.write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(security.SecurityHarnessError, "nonempty"):
                security.write_receipt(occupied, receipt, REPO, policy)
            link = root / "link.json"
            link.symlink_to(occupied)
            with self.assertRaisesRegex(security.SecurityHarnessError, "non-symlink"):
                security.write_receipt(link, receipt, REPO, policy)


if __name__ == "__main__":
    unittest.main()
