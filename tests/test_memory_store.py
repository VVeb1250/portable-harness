"""Tests for paw.memory.store — atomic write + cross-process lock primitives."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from paw.memory import store


class GlobalDirTests(unittest.TestCase):
    def test_global_dir_under_paw_root(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                gd = store.global_dir()
        self.assertEqual(gd, Path(d) / "memory")

    def test_global_dir_default_when_no_override(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "PAW_HOME"}
        with mock.patch.dict(os.environ, env, clear=True):
            gd = store.global_dir()
        self.assertEqual(gd.name, "memory")
        self.assertEqual(gd.parent.name, ".paw")


class WriteJsonlRawTests(unittest.TestCase):
    def test_atomic_write_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "memory" / "ledger.jsonl"
            store._write_jsonl_raw(p, [
                json.dumps({"id": "a", "n": 1}),
                json.dumps({"id": "b", "n": 2}),
            ])
            self.assertTrue(p.exists())
            lines = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0]), {"id": "a", "n": 1})

    def test_no_tmp_file_left_behind(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            store._write_jsonl_raw(p, [json.dumps({"x": 1})])
            leftovers = list(p.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_empty_lines_writes_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            store._write_jsonl_raw(p, [])
            self.assertTrue(p.exists())
            self.assertEqual(p.read_text(encoding="utf-8"), "")

    def test_creates_parent_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "deep" / "nest" / "ledger.jsonl"
            store._write_jsonl_raw(p, [json.dumps({"k": 1})])
            self.assertTrue(p.exists())

    def test_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            store._write_jsonl_raw(p, [json.dumps({"v": "old"})])
            store._write_jsonl_raw(p, [json.dumps({"v": "new"})])
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"v": "new"})


class LockedTests(unittest.TestCase):
    def test_locked_is_context_manager(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            with store.locked(p):
                store._write_jsonl_raw(p, [json.dumps({"k": 1})])
            self.assertTrue(p.exists())

    def test_lockfile_released_after_context(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            lock = p.with_name(p.name + ".lock")
            with store.locked(p):
                pass
            self.assertFalse(lock.exists())  # cleaned up

    def test_concurrent_writers_do_not_lose_updates(self) -> None:
        """Two threads each incrementing a counter under lock must both land.

        Without the lock, a naive read→modify→write loses one writer's update.
        The lock serializes the spans so both increments persist.
        """
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "counter.jsonl"
            p.write_text(json.dumps({"n": 0}) + "\n", encoding="utf-8")
            barrier = threading.Barrier(2)

            def bump() -> None:
                barrier.wait()
                for _ in range(20):
                    with store.locked(p):
                        # read current
                        n = json.loads(p.read_text(encoding="utf-8").strip())["n"]
                        store._write_jsonl_raw(p, [json.dumps({"n": n + 1})])

            t1 = threading.Thread(target=bump)
            t2 = threading.Thread(target=bump)
            t1.start(); t2.start()
            t1.join(timeout=30); t2.join(timeout=30)
            final = json.loads(p.read_text(encoding="utf-8").strip())["n"]
        self.assertEqual(final, 40)


if __name__ == "__main__":
    unittest.main()
