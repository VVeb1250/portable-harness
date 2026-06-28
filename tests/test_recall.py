from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.recall import grep_committed, icm_recall, recall


class GrepCommittedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "CLAUDE.md").write_text(
            "# project\n"
            "- Windows: use `py` launcher not python3\n"
            "- Paths use backslash and PowerShell syntax\n"
            "unrelated trivia line\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_matches_convention_line_by_token_overlap(self) -> None:
        hits = grep_committed("how do I run python on windows", "claude-code", self.root)
        texts = " ".join(t for _, t in hits)
        self.assertIn("py", texts)
        self.assertIn("launcher", texts)

    def test_no_overlap_returns_nothing(self) -> None:
        self.assertEqual(grep_committed("kubernetes helm chart", "claude-code", self.root), [])

    def test_unknown_host_returns_nothing(self) -> None:
        self.assertEqual(grep_committed("python", "nope", self.root), [])

    def test_missing_file_returns_nothing(self) -> None:
        self.assertEqual(grep_committed("python", "codex", self.root), [])  # no AGENTS.md


class IcmRecallTests(unittest.TestCase):
    def test_parses_list_json(self) -> None:
        canned = json.dumps([{"summary": "x", "importance": "high", "topic": "mistakes"}])
        out = icm_recall("q", runner=lambda c: canned)
        self.assertEqual(len(out), 1)

    def test_failure_is_silent(self) -> None:
        def boom(_c):
            raise OSError("icm missing")

        self.assertEqual(icm_recall("q", runner=boom), [])

    def test_non_list_json_is_silent(self) -> None:
        self.assertEqual(icm_recall("q", runner=lambda c: '{"error":"x"}'), [])


class RecallResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "CLAUDE.md").write_text("- use py not python on windows\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_combines_icm_and_committed(self) -> None:
        canned = json.dumps([{"summary": "py launcher lesson", "importance": "high", "topic": "mistakes"}])
        res = recall("python windows", root=self.root, icm_runner=lambda c: canned)
        self.assertFalse(res.empty)
        rendered = res.render()
        self.assertIn("ICM", rendered)
        self.assertIn("committed", rendered)

    def test_empty_when_nothing_matches(self) -> None:
        res = recall("kubernetes helm", root=self.root, icm_runner=lambda c: "[]")
        self.assertTrue(res.empty)
        self.assertIn("no matches", res.render())


class DistrustFilterTests(unittest.TestCase):
    """Recall suppresses memories whose recalled fix keeps failing (loop closure)."""

    def _recall_with_distrust(self, distrust_map: dict[str, int], canned_memories: str):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                # seed the distrust ledger at the path recall reads
                from paw.memory import distrust
                p = distrust._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    "".join(json.dumps({"id": i, "miss": m}) + "\n" for i, m in distrust_map.items()),
                    encoding="utf-8",
                )
                return icm_recall("query", runner=lambda c: canned_memories)

    def test_distrusted_id_is_filtered_from_recall(self) -> None:
        canned = json.dumps([
            {"id": "bad-mem", "summary": "stale fix", "importance": "high", "topic": "mistakes"},
            {"id": "good-mem", "summary": "working fix", "importance": "high", "topic": "mistakes"},
        ])
        out = self._recall_with_distrust({"bad-mem": 5}, canned)
        ids = {m.get("id") for m in out}
        self.assertNotIn("bad-mem", ids)
        self.assertIn("good-mem", ids)

    def test_below_threshold_not_filtered(self) -> None:
        canned = json.dumps([
            {"id": "mem-1", "summary": "fix", "importance": "high", "topic": "mistakes"},
        ])
        out = self._recall_with_distrust({"mem-1": 2}, canned)  # threshold=3
        self.assertEqual(len(out), 1)

    def test_pending_never_affected_by_distrust(self) -> None:
        """Pending entries are always excluded by topic, before distrust."""
        canned = json.dumps([
            {"id": "p1", "summary": "pending thing", "importance": "high", "topic": "pending"},
        ])
        out = self._recall_with_distrust({"p1": 5}, canned)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
