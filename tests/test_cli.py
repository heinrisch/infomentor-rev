"""Tests for raw response dumps and the --no-notify flag.

Stdlib only (unittest); run with: python3 -m unittest discover tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from infomentor.storage import StorageManager


class StorageRawTest(unittest.TestCase):
    def test_save_raw_roundtrip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = StorageManager(Path(tmp) / "news", Path(tmp) / "files")
            first = storage.save_raw("news", {"items": [1]}, pupil_id="7")
            self.assertTrue(first.name.startswith("raw_news_7"))
            second = storage.save_raw("news", {"items": [1, 2]}, pupil_id="7")
            self.assertEqual(first, second)  # latest wins, no accumulation
            saved = json.loads(second.read_text(encoding="utf-8"))
            self.assertEqual(saved, {"items": [1, 2]})
            # raw files must not pollute the news id scan
            self.assertEqual(storage.get_existing_ids(pupil_id="7"), set())

    def test_save_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = StorageManager(Path(tmp) / "news", Path(tmp) / "files")
            path = storage.save_raw_text("raw_pupils.html", "<html></html>")
            self.assertEqual(path.read_text(encoding="utf-8"), "<html></html>")


class NoNotifyTest(unittest.TestCase):
    def test_no_notify_wires_zero_notifiers(self):
        from infomentor.runner import InfoMentorFetcher

        fetcher = InfoMentorFetcher(notify=False)
        self.assertEqual(fetcher.notifier.notifiers, [])

    def test_fetch_help_mentions_no_notify(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli.py"), "fetch", "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--no-notify", proc.stdout)


if __name__ == "__main__":
    unittest.main()
