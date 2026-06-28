"""Tests for paw.memory.distrust — miss-count overlay / suppression list."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.memory import distrust


class RecordMissTests(unittest.TestCase):
    def test_record_miss_increments(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("mem-1")
                distrust.record_miss("mem-1")
                d_map = distrust.load()
        self.assertEqual(d_map["mem-1"], 2)

    def test_record_miss_separate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("mem-1")
                distrust.record_miss("mem-2")
                distrust.record_miss("mem-2")
                d_map = distrust.load()
        self.assertEqual(d_map, {"mem-1": 1, "mem-2": 2})

    def test_empty_mem_id_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("")
                self.assertEqual(distrust.load(), {})


class DistrustedIdsTests(unittest.TestCase):
    def test_below_threshold_not_distrusted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("mem-1")  # count=1
                distrust.record_miss("mem-1")  # count=2
                ids = distrust.distrusted_ids()
        self.assertEqual(ids, set())  # threshold=3, so 2 < 3

    def test_at_threshold_is_distrusted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(3):
                    distrust.record_miss("mem-bad")
                ids = distrust.distrusted_ids()
        self.assertEqual(ids, {"mem-bad"})

    def test_custom_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("mem-x")
                distrust.record_miss("mem-x")
                ids = distrust.distrusted_ids(threshold=2)
        self.assertEqual(ids, {"mem-x"})

    def test_mixed_ids(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(5):
                    distrust.record_miss("bad-1")
                distrust.record_miss("ok-1")
                ids = distrust.distrusted_ids()
        self.assertEqual(ids, {"bad-1"})


class ForgetTests(unittest.TestCase):
    def test_forget_resets_counter(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(4):
                    distrust.record_miss("mem-1")
                self.assertTrue(distrust.forget("mem-1"))
                ids = distrust.distrusted_ids()
        self.assertEqual(ids, set())

    def test_forget_unknown_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                distrust.record_miss("mem-1")
                self.assertFalse(distrust.forget("never-existed"))

    def test_forget_only_target(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(4):
                    distrust.record_miss("keep-bad")
                distrust.record_miss("innocent")
                distrust.forget("innocent")
                d_map = distrust.load()
        self.assertEqual(set(d_map.keys()), {"keep-bad"})


class FailSafeTests(unittest.TestCase):
    def test_corrupt_jsonl_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = distrust._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("this is not json\n{broken\n", encoding="utf-8")
                self.assertEqual(distrust.load(), {})
                self.assertEqual(distrust.distrusted_ids(), set())

    def test_partial_corrupt_lines_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = distrust._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    json.dumps({"id": "good", "miss": 3}) + "\n"
                    "garbage line\n"
                    + json.dumps({"id": "good2", "miss": 2}) + "\n",
                    encoding="utf-8",
                )
                d_map = distrust.load()
        self.assertEqual(d_map, {"good": 3, "good2": 2})

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                self.assertEqual(distrust.load(), {})
                self.assertEqual(distrust.distrusted_ids(), set())


if __name__ == "__main__":
    unittest.main()
