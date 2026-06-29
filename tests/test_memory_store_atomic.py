"""Tests for paw.memory.store atomic write helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.memory import store


class WriteTextAtomicTests(unittest.TestCase):
    def test_writes_content(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "f.json"
            store.write_text_atomic(p, '{"k": 1}')
            self.assertEqual(p.read_text(encoding="utf-8"), '{"k": 1}')

    def test_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.json"
            p.write_text("OLD", encoding="utf-8")
            store.write_text_atomic(p, "NEW")
            self.assertEqual(p.read_text(encoding="utf-8"), "NEW")

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a" / "b" / "c" / "f.txt"
            store.write_text_atomic(p, "x")
            self.assertTrue(p.exists())
            self.assertEqual(p.read_text(encoding="utf-8"), "x")

    def test_no_tmp_left_behind(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.json"
            store.write_text_atomic(p, "x")
            tmps = list(Path(d).glob("*.tmp"))
            self.assertEqual(tmps, [])

    def test_empty_body_writes_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.txt"
            store.write_text_atomic(p, "")
            self.assertEqual(p.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
