"""Tests for paw.memory.status_store — two-layer project snapshot."""
from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timezone
from typing import List, Optional
from unittest import mock

from paw.memory import facts, status_store as ss


def _proc(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


class FakeGit:
    """Returns canned stdout per git subcommand, keyed by first rev arg."""

    def __init__(self, branch="main", head="abc1234", porcelain=""):
        self._branch = branch
        self._head = head
        self._porcelain = porcelain
        self.calls: List[list[str]] = []

    def __call__(self, cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        if "rev-parse" in cmd:
            if "--abbrev-ref" in cmd:
                return _proc(self._branch)
            if "--short" in cmd:
                return _proc(self._head)
        if "status" in cmd and "--porcelain" in cmd:
            return _proc(self._porcelain)
        return _proc("", returncode=1)


class FactsFakeRunner:
    """Fake for the facts runner. Stores the last-written value and serves gets."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}
        self.calls: List[list[str]] = []

    def __call__(self, cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        sub = cmd[2] if len(cmd) > 2 else ""  # icm.exe facts <sub> ...
        ent = cmd[3] if len(cmd) > 3 else ""
        key = cmd[4] if len(cmd) > 4 else ""
        if sub == "get":
            val = self.store.get((ent, key))
            if val is None:
                return _proc("", returncode=1)
            return _proc(val)
        if sub == "set":
            # cmd: facts set <ent> <key> <value> --source paw:status
            val = cmd[5] if len(cmd) > 5 else ""
            self.store[(ent, key)] = val
            return _proc(f"set: {ent}.{key} = {val}\n")
        if sub == "forget":
            removed = self.store.pop((ent, key), None) is not None
            return _proc(f"forgot {1 if removed else 0} row(s)\n")
        return _proc("", returncode=1)


# --------------------------------------------------------------------------- #
# git layer capture
# --------------------------------------------------------------------------- #

class CaptureGitLayerTests(unittest.TestCase):
    def test_captures_branch_head_dirty(self) -> None:
        fg = FakeGit(branch="feature/x", head="9f4c900", porcelain=" M a.py\n?? b.py\n")
        git = ss.capture_git_layer("/repo", runner=fg)
        self.assertEqual(git.branch, "feature/x")
        self.assertEqual(git.head_short, "9f4c900")
        self.assertEqual(git.dirty_count, 2)
        self.assertTrue(git.head_changed_at)  # ISO timestamp populated
        self.assertTrue(git.present)

    def test_clean_repo_zero_dirty(self) -> None:
        fg = FakeGit(branch="main", head="abc1234", porcelain="")
        git = ss.capture_git_layer("/repo", runner=fg)
        self.assertEqual(git.dirty_count, 0)

    def test_detached_head_falls_back(self) -> None:
        # rev-parse --abbrev-ref on detached HEAD returns "HEAD"
        fg = FakeGit(branch="HEAD", head="abc1234")
        git = ss.capture_git_layer("/repo", runner=fg)
        self.assertEqual(git.branch, "HEAD")
        self.assertTrue(git.present)

    def test_not_a_repo_returns_empty(self) -> None:
        def boom(cmd, cwd):
            return _proc("", returncode=128)
        git = ss.capture_git_layer("/nope", runner=boom)
        self.assertFalse(git.present)
        self.assertEqual(git.dirty_count, 0)


# --------------------------------------------------------------------------- #
# round-trip via facts fake
# --------------------------------------------------------------------------- #

class StatusRoundTripTests(unittest.TestCase):
    def test_save_git_then_read(self) -> None:
        fr = FactsFakeRunner()
        git = ss.GitLayer(branch="main", head_short="abc1234", dirty_count=0,
                          head_changed_at="2026-06-29T06:00:00+00:00")
        self.assertTrue(ss.save_git_layer("portable-harness", git, runner=fr))
        status = ss.read_status("portable-harness", runner=fr)
        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.git.branch, "main")
        self.assertEqual(status.git.head_short, "abc1234")
        self.assertIsNone(status.note)  # no note written yet

    def test_save_note_preserves_git(self) -> None:
        fr = FactsFakeRunner()
        git = ss.GitLayer(branch="main", head_short="abc1234", dirty_count=0,
                          head_changed_at="2026-06-29T06:00:00+00:00")
        ss.save_git_layer("p", git, runner=fr)
        self.assertTrue(ss.save_note(
            "p", "did X / hit Y / next Z",
            updated_by="claude-code:abc",
            base_head="abc1234",
            now=lambda: datetime(2026, 6, 29, 7, 0, tzinfo=timezone.utc),
            runner=fr,
        ))
        status = ss.read_status("p", runner=fr)
        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.git.head_short, "abc1234")  # git preserved
        self.assertEqual(status.note.summary, "did X / hit Y / next Z")
        self.assertEqual(status.note.updated_by, "claude-code:abc")

    def test_stale_when_head_moved(self) -> None:
        fr = FactsFakeRunner()
        # note written against abc1234
        ss.save_note("p", "old note", updated_by="x", base_head="abc1234", runner=fr)
        # then git moved to def5678
        new_git = ss.GitLayer(branch="main", head_short="def5678", dirty_count=1)
        ss.save_git_layer("p", new_git, runner=fr)
        status = ss.read_status("p", runner=fr)
        assert status is not None
        self.assertTrue(status.stale)  # note base abc1234 != head def5678

    def test_not_stale_when_note_refreshed(self) -> None:
        fr = FactsFakeRunner()
        ss.save_note("p", "fresh note", updated_by="x", base_head="def5678", runner=fr)
        git = ss.GitLayer(branch="main", head_short="def5678", dirty_count=0)
        ss.save_git_layer("p", git, runner=fr)
        status = ss.read_status("p", runner=fr)
        assert status is not None
        self.assertFalse(status.stale)

    def test_reset_removes_slot(self) -> None:
        fr = FactsFakeRunner()
        git = ss.GitLayer(branch="main", head_short="abc1234", dirty_count=0)
        ss.save_git_layer("p", git, runner=fr)
        self.assertTrue(ss.reset_status("p", runner=fr))
        self.assertIsNone(ss.read_status("p", runner=fr))

    def test_honesty_failure_returns_false(self) -> None:
        # get always returns a DIFFERENT value than what we wrote → False
        class LiarRunner:
            def __call__(self, cmd, *, timeout):
                sub = cmd[2]
                if sub == "set":
                    return _proc("set: ok\n")
                if sub == "get":
                    return _proc("TOTALLY_DIFFERENT")  # mismatch
                return _proc("", returncode=1)
        git = ss.GitLayer(branch="main", head_short="abc1234", dirty_count=0)
        self.assertFalse(ss.save_git_layer("p", git, runner=LiarRunner()))


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

class ParseTests(unittest.TestCase):
    def test_parse_full_blob(self) -> None:
        blob = json.dumps({
            "project": "p",
            "git": {"branch": "main", "head_short": "abc1234",
                    "dirty_count": 2, "head_changed_at": "t"},
            "note": {"summary": "did X", "updated_at": "t2",
                     "updated_by": "host:1", "base_head": "abc1234"},
        })
        status = ss.from_row(facts.FactRow("project:p", "status", blob))
        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.git.dirty_count, 2)
        self.assertEqual(status.note.summary, "did X")

    def test_parse_garbage_returns_none(self) -> None:
        self.assertIsNone(ss.from_row(None))
        self.assertIsNone(ss.from_row(facts.FactRow("e", "k", "not json{")))
        self.assertIsNone(ss.from_row(facts.FactRow("e", "k", "[]")))  # not dict

    def test_parse_git_only_no_note(self) -> None:
        blob = json.dumps({"project": "p", "git": {
            "branch": "main", "head_short": "x", "dirty_count": 0,
            "head_changed_at": "t"}, "note": None})
        status = ss.from_row(facts.FactRow("e", "k", blob))
        assert status is not None
        self.assertIsNone(status.note)
        self.assertTrue(status.git.present)


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class RenderTests(unittest.TestCase):
    def test_render_with_note_and_git(self) -> None:
        status = ss.ProjectStatus(
            project="p",
            git=ss.GitLayer(branch="main", head_short="abc1234", dirty_count=0),
            note=ss.NoteLayer(summary="did X / next Y", updated_at="t",
                              updated_by="h", base_head="abc1234"),
        )
        out = ss.render_resume(status)
        self.assertIn("status: did X / next Y", out)
        self.assertIn("git: main · abc1234 · dirty 0", out)
        self.assertNotIn("stale", out)

    def test_render_stale_flag(self) -> None:
        status = ss.ProjectStatus(
            project="p",
            git=ss.GitLayer(branch="main", head_short="NEW", dirty_count=0),
            note=ss.NoteLayer(summary="old", updated_at="t", updated_by="h",
                              base_head="OLD"),
        )
        out = ss.render_resume(status)
        self.assertIn("⚠️ stale", out)

    def test_render_git_only_fallback(self) -> None:
        status = ss.ProjectStatus(
            project="p",
            git=ss.GitLayer(branch="main", head_short="abc1234", dirty_count=3),
            note=None,
        )
        out = ss.render_resume(status)
        self.assertIn("(no AI note)", out)
        self.assertIn("dirty 3", out)

    def test_render_empty_returns_empty(self) -> None:
        self.assertEqual(ss.render_resume(None), "")
        self.assertEqual(ss.render_resume(ss.ProjectStatus(project="p")), "")


if __name__ == "__main__":
    unittest.main()
