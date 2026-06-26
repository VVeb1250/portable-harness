from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
