import importlib.util
import pathlib
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sync_orchestration_contract",
    REPO / "scripts/sync-orchestration-contract.py",
)
syncer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(syncer)


def contract(labels=syncer.LABELS):
    return "\n\n".join(f"{label} rule" for label in labels)


class ContractSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "config").mkdir()
        (self.root / "commands").mkdir()
        (self.root / "agents").mkdir()
        self.write_source(contract())
        block = syncer.generated(contract())
        for relative in syncer.CARRIERS:
            path = self.root / relative
            path.write_text(f"header\n{block}\nfooter\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_source(self, text):
        (self.root / syncer.SOURCE).write_text(text + "\n", encoding="utf-8")

    def test_all_runtime_carriers_match_one_source(self):
        self.assertEqual(syncer.sync(self.root, write=False), [])

    def test_check_reports_the_exact_drifted_carrier(self):
        relative = syncer.COMMANDS[0]
        path = self.root / relative
        path.write_text(
            path.read_text(encoding="utf-8").replace("Interface:** rule", "Interface:** drift"),
            encoding="utf-8",
        )

        self.assertEqual(syncer.sync(self.root, write=False), [relative])

    def test_write_repairs_drift_and_is_idempotent(self):
        relative = "agents/delivery-coordinator.md"
        path = self.root / relative
        path.write_text(
            path.read_text(encoding="utf-8").replace("Loop guard:** rule", "Loop guard:** stale"),
            encoding="utf-8",
        )

        self.assertEqual(syncer.sync(self.root, write=True), [relative])
        self.assertEqual(syncer.sync(self.root, write=True), [])

    def test_check_rejects_missing_markers(self):
        relative = syncer.COMMANDS[0]
        path = self.root / relative
        path.write_text(f"header\n{contract()}\nfooter\n", encoding="utf-8")

        with self.assertRaisesRegex(syncer.ContractError, "marker pair"):
            syncer.sync(self.root, write=False)

    def test_write_migrates_legacy_carriers(self):
        for relative in syncer.CARRIERS:
            path = self.root / relative
            path.write_text(f"header\n{contract()}\nfooter\n", encoding="utf-8")

        self.assertEqual(set(syncer.sync(self.root, write=True)), set(syncer.CARRIERS))
        self.assertEqual(syncer.sync(self.root, write=False), [])

    def test_unexpected_interface_carrier_fails_closed(self):
        (self.root / "commands/unregistered.md").write_text(
            "> **Interface:** unregistered\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(syncer.ContractError, "unexpected"):
            syncer.sync(self.root, write=False)

    def test_source_heading_order_is_structural(self):
        labels = list(syncer.LABELS)
        labels[0], labels[1] = labels[1], labels[0]
        self.write_source(contract(labels))

        with self.assertRaisesRegex(syncer.ContractError, "out of order"):
            syncer.sync(self.root, write=False)


if __name__ == "__main__":
    unittest.main()
