"""Tests for paw.memory.outcomes — router suggestion/use feedback loop + demotion."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from paw.memory import outcomes


class MarkSuggestedTests(unittest.TestCase):
    def test_mark_suggested_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_suggested(["efficiency-min"])
                outcomes.mark_suggested(["efficiency-min", "secure-agent"])
                recs = outcomes.load()
        self.assertEqual(recs["efficiency-min"]["suggested"], 2)
        self.assertEqual(recs["secure-agent"]["suggested"], 1)

    def test_mark_suggested_empty_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_suggested([])
                self.assertEqual(outcomes.load(), {})

    def test_mark_suggested_records_date(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_suggested(["efficiency-min"], today="2026-06-29")
                recs = outcomes.load()
        self.assertEqual(recs["efficiency-min"]["last_suggested"], "2026-06-29")


class MarkUsedTests(unittest.TestCase):
    def test_mark_used_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_used("efficiency-min")
                outcomes.mark_used("efficiency-min")
                recs = outcomes.load()
        self.assertEqual(recs["efficiency-min"]["used"], 2)

    def test_mark_used_empty_name_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_used("")
                self.assertEqual(outcomes.load(), {})

    def test_mark_used_on_fresh_name_initializes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_used("never-suggested", today="2026-06-29")
                recs = outcomes.load()
        self.assertEqual(recs["never-suggested"]["suggested"], 0)
        self.assertEqual(recs["never-suggested"]["used"], 1)


class DemotedNamesTests(unittest.TestCase):
    def test_suggested_enough_never_used_is_demoted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(outcomes.DEMOTE_MIN_SUGGESTED):
                    outcomes.mark_suggested(["ignored-set"])
                self.assertEqual(outcomes.demoted_names(), {"ignored-set"})

    def test_below_threshold_not_demoted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(outcomes.DEMOTE_MIN_SUGGESTED - 1):
                    outcomes.mark_suggested(["almost-set"])
                self.assertEqual(outcomes.demoted_names(), set())

    def test_any_use_ever_clears_demotion(self) -> None:
        """Once a set is used even once, it's no longer demoted even if suggested often."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(10):
                    outcomes.mark_suggested(["converted-set"])
                outcomes.mark_used("converted-set")
                self.assertEqual(outcomes.demoted_names(), set())

    def test_mixed_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(6):
                    outcomes.mark_suggested(["ignored-1"])
                for _ in range(6):
                    outcomes.mark_suggested(["ignored-2"])
                outcomes.mark_used("ignored-2")
                outcomes.mark_suggested(["ok-set"])  # only 1 suggestion
                self.assertEqual(outcomes.demoted_names(), {"ignored-1"})


class ForgetTests(unittest.TestCase):
    def test_forget_resets_counters(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                for _ in range(6):
                    outcomes.mark_suggested(["bad-set"])
                self.assertTrue(outcomes.forget("bad-set"))
                self.assertEqual(outcomes.demoted_names(), set())

    def test_forget_unknown_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                outcomes.mark_suggested(["real-set"])
                self.assertFalse(outcomes.forget("never-seen"))


class ParseApplyTargetTests(unittest.TestCase):
    def test_matches_paw_apply(self) -> None:
        self.assertEqual(outcomes.parse_apply_target("paw apply efficiency-min"), "efficiency-min")

    def test_matches_paw_apply_with_args(self) -> None:
        self.assertEqual(
            outcomes.parse_apply_target("paw apply secure-agent --host codex"),
            "secure-agent",
        )

    def test_matches_in_longer_command(self) -> None:
        self.assertEqual(
            outcomes.parse_apply_target("sudo paw apply doc-data-min 2>&1"),
            "doc-data-min",
        )

    def test_none_when_absent(self) -> None:
        self.assertIsNone(outcomes.parse_apply_target("paw sets list"))
        self.assertIsNone(outcomes.parse_apply_target("paw plan efficiency-min"))

    def test_none_for_empty(self) -> None:
        self.assertIsNone(outcomes.parse_apply_target(""))

    def test_does_not_match_portaw_install(self) -> None:
        """Legacy prototype verb must not false-trigger here."""
        self.assertIsNone(outcomes.parse_apply_target("portaw install efficiency-min"))


class FailSafeTests(unittest.TestCase):
    def test_corrupt_jsonl_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = outcomes._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("garbage\n{broken\n", encoding="utf-8")
                self.assertEqual(outcomes.load(), {})
                self.assertEqual(outcomes.demoted_names(), set())

    def test_partial_corrupt_lines_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                p = outcomes._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    json.dumps({"name": "good", "suggested": 5, "used": 0}) + "\n"
                    "garbage line\n",
                    encoding="utf-8",
                )
                recs = outcomes.load()
        self.assertEqual(set(recs.keys()), {"good"})

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                self.assertEqual(outcomes.load(), {})
                self.assertEqual(outcomes.demoted_names(), set())


if __name__ == "__main__":
    unittest.main()
