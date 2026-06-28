"""Tests for paw.memory.sessionlog — per-session inject dedup with TTL."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from paw.memory import sessionlog


class SeenMarkTests(unittest.TestCase):
    def test_mark_then_seen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["mem-a", "mem-b"])
                self.assertEqual(sessionlog.seen("sess-1"), {"mem-a", "mem-b"})

    def test_empty_ids_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", [])
                self.assertEqual(sessionlog.seen("sess-1"), set())

    def test_mark_merges_ids(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["mem-a"])
                sessionlog.mark("sess-1", ["mem-b"])
                self.assertEqual(sessionlog.seen("sess-1"), {"mem-a", "mem-b"})

    def test_sessions_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["mem-a"])
                sessionlog.mark("sess-2", ["mem-b"])
                self.assertEqual(sessionlog.seen("sess-1"), {"mem-a"})
                self.assertEqual(sessionlog.seen("sess-2"), {"mem-b"})

    def test_unsanitized_session_id_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("weird/id with spaces", ["mem-a"])
                self.assertEqual(sessionlog.seen("weird/id with spaces"), {"mem-a"})
                # no path traversal possible — slashes sanitized
                self.assertFalse(any(
                    "\\" in f.name or "/" in f.name for f in sessionlog._dir().glob("*")
                ))


class TtlTests(unittest.TestCase):
    def test_old_id_drops_after_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                old_ts = time.time() - sessionlog._DEDUP_TTL_S - 100
                sessionlog.mark("sess-1", ["mem-old"], now=old_ts)
                # id is older than the TTL window → no longer counts as "seen"
                self.assertEqual(sessionlog.seen("sess-1"), set())

    def test_recent_id_still_seen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                recent_ts = time.time() - 100  # well within ttl
                sessionlog.mark("sess-1", ["mem-recent"], now=recent_ts)
                self.assertEqual(sessionlog.seen("sess-1"), {"mem-recent"})

    def test_relevant_again_a_day_later_can_re_surface(self) -> None:
        """A lesson relevant again past ttl re-surfaces — earlier inject scrolled out."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["mem-stale"], now=time.time() - 2 * 86400)
                self.assertEqual(sessionlog.seen("sess-1"), set())


class ResetTests(unittest.TestCase):
    def test_reset_wipes_log(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["mem-a", "mem-b"])
                self.assertEqual(sessionlog.seen("sess-1"), {"mem-a", "mem-b"})
                sessionlog.reset("sess-1")
                self.assertEqual(sessionlog.seen("sess-1"), set())

    def test_reset_allows_re_inject_after_compact(self) -> None:
        """SessionStart(compact) summarizes earlier injects away → pins re-fire."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.mark("sess-1", ["pin-x"])
                sessionlog.reset("sess-1")
                sessionlog.mark("sess-1", ["pin-x"])  # re-fire is intentional
                self.assertEqual(sessionlog.seen("sess-1"), {"pin-x"})

    def test_reset_missing_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                sessionlog.reset("never-existed")  # must not raise
                self.assertEqual(sessionlog.seen("never-existed"), set())


class FailSafeTests(unittest.TestCase):
    def test_corrupt_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = sessionlog._path("sess-1")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("not json at all", encoding="utf-8")
                self.assertEqual(sessionlog.seen("sess-1"), set())

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                self.assertEqual(sessionlog.seen("nothing-here"), set())

    def test_legacy_ids_shape_still_reads(self) -> None:
        """Old {ids:[...], ts} logs still dedup within their ttl."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = sessionlog._path("sess-legacy")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    json.dumps({"ids": ["legacy-a", "legacy-b"], "ts": time.time()}),
                    encoding="utf-8",
                )
                self.assertEqual(sessionlog.seen("sess-legacy"), {"legacy-a", "legacy-b"})


if __name__ == "__main__":
    unittest.main()
