"""Tests for paw.memory.decision_mirror — markdown → facts index."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import List

from paw.memory import decision_mirror as dm
from paw.memory import facts


def _proc(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


class FactsFakeRunner:
    """Stores values per (entity,key); serves gets; honours honesty re-read."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}
        self.calls: List[list[str]] = []

    def __call__(self, cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        sub = cmd[2] if len(cmd) > 2 else ""
        ent = cmd[3] if len(cmd) > 3 else ""
        key = cmd[4] if len(cmd) > 4 else ""
        if sub == "get":
            val = self.store.get((ent, key))
            if val is None:
                return _proc("", returncode=1)
            return _proc(val)
        if sub == "set":
            val = cmd[5] if len(cmd) > 5 else ""
            self.store[(ent, key)] = val
            return _proc(f"set: {ent}.{key} = {val}\n")
        if sub == "forget":
            removed = self.store.pop((ent, key), None) is not None
            return _proc(f"forgot {1 if removed else 0} row(s)\n")
        if sub == "list":
            # return a tiny table for the requested entity
            rows = [r for r in self.store if r[0] == ent]
            if not rows:
                return _proc("", returncode=1)
            out = "key     value\n------  -----\n"
            for e, k in rows:
                out += f"{k}     {self.store[(e, k)]}\n"
            return _proc(out)
        return _proc("", returncode=1)


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

class ParseTests(unittest.TestCase):
    def test_parses_one_block(self) -> None:
        md = (
            "some intro\n\n"
            "<!-- paw:decision:keep-icm:start -->\n"
            "ICM = the only cross-host store.\n"
            "reason: daemon alternatives clash with no-daemon thesis.\n"
            "<!-- paw:decision:keep-icm:end -->\n"
        )
        decisions = dm.parse_decisions(md)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].slug, "keep-icm")
        self.assertIn("ICM = the only", decisions[0].body)
        self.assertEqual(decisions[0].entity, "decisions.keep-icm")

    def test_parses_multiple_blocks(self) -> None:
        md = (
            "<!-- paw:decision:a:start -->A body<!-- paw:decision:a:end -->\n"
            "<!-- paw:decision:b:start -->B body<!-- paw:decision:b:end -->\n"
        )
        decisions = dm.parse_decisions(md)
        self.assertEqual([d.slug for d in decisions], ["a", "b"])

    def test_duplicate_slug_kept_once(self) -> None:
        md = (
            "<!-- paw:decision:x:start -->first<!-- paw:decision:x:end -->\n"
            "<!-- paw:decision:x:start -->second<!-- paw:decision:x:end -->\n"
        )
        decisions = dm.parse_decisions(md)
        self.assertEqual(len(decisions), 1)
        self.assertIn("first", decisions[0].body)

    def test_ignores_unmarked_text(self) -> None:
        # Free-text "decision:" without the marker must NOT be picked up.
        md = "## Decision: use react\nwe chose react because...\n"
        self.assertEqual(dm.parse_decisions(md), [])

    def test_empty_body_skipped(self) -> None:
        md = "<!-- paw:decision:empty:start --><!-- paw:decision:empty:end -->\n"
        self.assertEqual(dm.parse_decisions(md), [])

    def test_malformed_slug_ignored(self) -> None:
        # leading digit ok, but spaces / dots in slug break the regex
        md = "<!-- paw:decision:bad slug:start -->x<!-- paw:decision:bad slug:end -->\n"
        self.assertEqual(dm.parse_decisions(md), [])


# --------------------------------------------------------------------------- #
# collect with file priority
# --------------------------------------------------------------------------- #

class CollectTests(unittest.TestCase):
    def test_first_file_wins_on_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "CLAUDE.md").write_text(
                "<!-- paw:decision:x:start -->FROM_CLAUDE<!-- paw:decision:x:end -->\n",
                encoding="utf-8",
            )
            (base / "AGENTS.md").write_text(
                "<!-- paw:decision:x:start -->FROM_AGENTS<!-- paw:decision:x:end -->\n",
                encoding="utf-8",
            )
            decisions = dm.collect_decisions(
                [Path("CLAUDE.md"), Path("AGENTS.md")], base=base
            )
            self.assertEqual(len(decisions), 1)
            self.assertIn("FROM_CLAUDE", decisions[0].body)

    def test_missing_files_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            decisions = dm.collect_decisions(
                [Path("CLAUDE.md"), Path("NOPE.md")], base=Path(d)
            )
            self.assertEqual(decisions, [])


# --------------------------------------------------------------------------- #
# mirror round-trip
# --------------------------------------------------------------------------- #

class MirrorTests(unittest.TestCase):
    def test_mirror_one_writes_and_verifies(self) -> None:
        fr = FactsFakeRunner()
        d = dm.Decision(slug="keep-icm", body="keep ICM\nreason: no-daemon")
        self.assertTrue(dm.mirror_one(d, runner=fr))
        row = facts.get_fact("decisions.keep-icm", "value", runner=fr)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIn("keep ICM", row.value)

    def test_mirror_decisions_counts_verified_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "CLAUDE.md").write_text(
                "<!-- paw:decision:a:start -->A<!-- paw:decision:a:end -->\n"
                "<!-- paw:decision:b:start -->B<!-- paw:decision:b:end -->\n",
                encoding="utf-8",
            )
            fr = FactsFakeRunner()
            count = dm.mirror_decisions([Path("CLAUDE.md")], base=base, runner=fr)
            self.assertEqual(count, 2)

    def test_mirror_collapses_whitespace(self) -> None:
        fr = FactsFakeRunner()
        d = dm.Decision(slug="x", body="line1\n\n\n\nline2\n   \n")
        dm.mirror_one(d, runner=fr)
        row = facts.get_fact("decisions.x", "value", runner=fr)
        assert row is not None
        # multiple blank lines collapsed to single, trailing ws gone
        self.assertNotIn("\n\n\n", row.value)

    def test_forget_decision(self) -> None:
        fr = FactsFakeRunner()
        dm.mirror_one(dm.Decision(slug="x", body="x"), runner=fr)
        self.assertTrue(dm.forget_decision("x", runner=fr))
        self.assertIsNone(facts.get_fact("decisions.x", "value", runner=fr))

    def test_forget_empty_slug_is_noop(self) -> None:
        fr = FactsFakeRunner()
        self.assertFalse(dm.forget_decision("", runner=fr))


if __name__ == "__main__":
    unittest.main()
