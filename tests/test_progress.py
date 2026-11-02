import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from practice.progress import ProgressStore


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "progress.json"
        self.store = ProgressStore(self.path, ["one", "two"])

    def test_save_creates_missing_data_directory(self):
        path = self.path.parent / 'data' / 'practice_progress.json'
        store = ProgressStore(path, ['one', 'two'])
        data = {'drafts': {'one': '# saved'}, 'solved': []}
        store.save(data)
        self.assertTrue(path.is_file())
        self.assertEqual(store.load(), data)

    def test_missing_file(self):
        self.assertEqual(self.store.load(), {"drafts": {}, "solved": []})
        self.assertIsNone(self.store.warning)
        self.assertFalse(self.path.exists())

    def test_round_trip_unicode_empty_and_multiline_drafts(self):
        data = {
            "drafts": {"one": "# café 🙂\ndef one():\n    return 0\n", "two": ""},
            "solved": ["one"],
        }
        self.store.save(data)
        self.assertEqual(self.store.load(), data)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_escaped_surrogates_do_not_poison_future_saves(self):
        data = {
            "drafts": {"one": "# " + chr(0xD800), "old-id": chr(0xDFFF)},
            "solved": [],
        }
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.store.load(), data)
        self.store.save(self.store.load())
        self.assertEqual(self.store.load(), data)
        self.assertIsNone(self.store.warning)

    def test_defaults_and_completion_ids(self):
        self.path.write_text(
            json.dumps(
                {
                    "drafts": {"old-id": "# preserved"},
                    "solved": ["one", "one", "removed", "two"],
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            self.store.load(),
            {"drafts": {"old-id": "# preserved"}, "solved": ["one", "two"]},
        )
        self.path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.store.load(), {"drafts": {}, "solved": []})

    def test_invalid_json_is_backed_up_before_save(self):
        raw = b'{"drafts": '
        self.path.write_bytes(raw)
        data = self.store.load()
        (backup,) = self.path.parent.glob("progress.corrupt-*.json")
        self.assertEqual(backup.read_bytes(), raw)
        self.assertEqual(self.path.read_bytes(), raw)
        assert self.store.warning is not None
        self.assertIn(str(backup), self.store.warning)
        self.store.save(data)
        self.assertEqual(backup.read_bytes(), raw)
        self.assertEqual(self.store.load(), data)

    def test_invalid_utf8_is_backed_up(self):
        self.path.write_bytes(b"\xff\xfe")
        self.assertEqual(self.store.load(), {"drafts": {}, "solved": []})
        (backup,) = self.path.parent.glob("progress.corrupt-*.json")
        self.assertEqual(backup.read_bytes(), b"\xff\xfe")

    def test_invalid_schema(self):
        for invalid in [
            [],
            None,
            {"drafts": []},
            {"drafts": {"one": None}},
            {"drafts": {"one": 42}},
            {"solved": "one"},
            {"solved": [True]},
        ]:
            with self.subTest(data=invalid):
                raw = json.dumps(invalid)
                self.path.write_text(raw, encoding="utf-8")
                self.assertEqual(self.store.load(), {"drafts": {}, "solved": []})
                self.assertEqual(self.path.read_text(encoding="utf-8"), raw)
                self.assertIsNotNone(self.store.warning)
                self.assertIsNone(self.store.save_blocked)

    def test_backup_failure_blocks_overwrite(self):
        self.path.write_text("broken", encoding="utf-8")
        with patch('practice.progress.shutil.copy2', side_effect=OSError('backup denied')):
            data = self.store.load()
        with self.assertRaisesRegex(OSError, "backup denied"):
            self.store.save(data)
        assert self.store.warning is not None
        self.assertIn("Saving is disabled", self.store.warning)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken")

    def test_read_failure_blocks_overwrite(self):
        with patch.object(
            Path, "read_text", side_effect=PermissionError("read denied")
        ):
            data = self.store.load()
        with self.assertRaisesRegex(OSError, "read denied"):
            self.store.save(data)
        self.assertFalse(self.path.exists())

    def test_replace_failure_preserves_existing_data(self):
        old = {"drafts": {"one": "# original"}, "solved": []}
        self.store.save(old)
        with patch('practice.progress.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaisesRegex(OSError, "locked"):
                self.store.save({"drafts": {"one": "# new"}, "solved": []})
        self.assertEqual(self.store.load(), old)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_flush_failure_preserves_existing_data(self):
        self.store.save(self.store.empty())
        raw = self.path.read_bytes()
        with patch('practice.progress.os.fsync', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.store.save({"drafts": {"one": "# new"}, "solved": ["one"]})
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
