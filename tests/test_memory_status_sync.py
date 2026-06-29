"""Tests for paw.memory.status_sync — the โพย managed block."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.memory import status_sync as sync


class RenderBlockTests(unittest.TestCase):
    def test_block_has_markers(self) -> None:
        block = sync.render_block()
        self.assertIn("<!-- paw:status-sync:start -->", block)
        self.assertIn("<!-- paw:status-sync:end -->", block)

    def test_block_contains_commands(self) -> None:
        block = sync.render_block()
        # the two commands the AI must run
        self.assertIn("paw memory status save", block)
        self.assertIn("paw memory status note", block)
        self.assertIn("resume block", block)  # tells AI why this matters


class InjectStripTests(unittest.TestCase):
    def test_inject_into_empty(self) -> None:
        out = sync.inject_block("")
        self.assertTrue(sync.has_block(out))

    def test_inject_appends_to_existing(self) -> None:
        before = "# Project\n\nSome intro.\n"
        out = sync.inject_block(before)
        # original content preserved
        self.assertIn("# Project", out)
        self.assertIn("Some intro.", out)
        self.assertTrue(sync.has_block(out))

    def test_inject_is_idempotent(self) -> None:
        before = "# Project\n"
        once = sync.inject_block(before)
        twice = sync.inject_block(once)
        # only ONE block, content stable
        self.assertEqual(once.count("paw:status-sync:start"), 1)
        self.assertEqual(twice.count("paw:status-sync:start"), 1)
        self.assertEqual(once, twice)

    def test_inject_replaces_stale_block(self) -> None:
        # an old version of the block present → replaced, not duplicated
        before = (
            "# Project\n\n"
            "<!-- paw:status-sync:start -->\nOLD BODY\n<!-- paw:status-sync:end -->\n"
        )
        out = sync.inject_block(before)
        self.assertEqual(out.count("paw:status-sync:start"), 1)
        self.assertNotIn("OLD BODY", out)

    def test_strip_removes_block(self) -> None:
        before = sync.inject_block("# Project\n")
        stripped = sync.strip_block(before)
        self.assertFalse(sync.has_block(stripped))
        # original content intact
        self.assertIn("# Project", stripped)

    def test_strip_idempotent(self) -> None:
        before = sync.inject_block("# Project\n")
        once = sync.strip_block(before)
        twice = sync.strip_block(once)
        self.assertEqual(once, twice)


class ResolveApplyRemoveTests(unittest.TestCase):
    def _setup(self, with_agents: bool = True, with_block: bool = False) -> tuple[Path, Path]:
        d = tempfile.mkdtemp()
        cwd = Path(d)
        if with_agents:
            content = "# AGENTS\n"
            if with_block:
                content = sync.inject_block(content)
            (cwd / "AGENTS.md").write_text(content, encoding="utf-8")
        return cwd, cwd / "AGENTS.md"

    def test_resolve_finds_agents_md(self) -> None:
        cwd, _ = self._setup(with_agents=True)
        target = sync.resolve_target(cwd=str(cwd))
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.name, "AGENTS.md")

    def test_resolve_falls_back_to_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            (cwd / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
            target = sync.resolve_target(cwd=str(cwd))
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(target.name, "CLAUDE.md")

    def test_resolve_none_when_no_context_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(sync.resolve_target(cwd=d))

    def test_apply_injects_when_absent(self) -> None:
        cwd, target = self._setup(with_agents=True, with_block=False)
        result = sync.apply(cwd=str(cwd))
        self.assertTrue(result.applied)
        self.assertTrue(result.changed)
        self.assertTrue(sync.has_block(target.read_text(encoding="utf-8")))

    def test_apply_idempotent_when_present(self) -> None:
        cwd, target = self._setup(with_agents=True, with_block=True)
        result = sync.apply(cwd=str(cwd))
        self.assertTrue(result.applied)  # block IS present
        self.assertFalse(result.changed)  # but no change

    def test_apply_reports_no_context_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result = sync.apply(cwd=d)
            self.assertFalse(result.applied)
            self.assertIn("no host context", result.message)

    def test_remove_strips_when_present(self) -> None:
        cwd, target = self._setup(with_agents=True, with_block=True)
        result = sync.remove(cwd=str(cwd))
        self.assertFalse(result.applied)  # block now absent
        self.assertTrue(result.changed)
        self.assertFalse(sync.has_block(target.read_text(encoding="utf-8")))

    def test_remove_idempotent_when_absent(self) -> None:
        cwd, target = self._setup(with_agents=True, with_block=False)
        result = sync.remove(cwd=str(cwd))
        self.assertFalse(result.applied)
        self.assertFalse(result.changed)

    def test_verify_reports_present(self) -> None:
        cwd, _ = self._setup(with_agents=True, with_block=True)
        result = sync.verify(cwd=str(cwd))
        self.assertTrue(result.applied)
        self.assertIn("present", result.message)

    def test_verify_reports_absent(self) -> None:
        cwd, _ = self._setup(with_agents=True, with_block=False)
        result = sync.verify(cwd=str(cwd))
        self.assertFalse(result.applied)
        self.assertIn("absent", result.message)

    def test_verify_does_not_modify_file(self) -> None:
        cwd, target = self._setup(with_agents=True, with_block=False)
        before = target.read_text(encoding="utf-8")
        sync.verify(cwd=str(cwd))
        self.assertEqual(target.read_text(encoding="utf-8"), before)


class MultiTargetTests(unittest.TestCase):
    """apply/verify/remove touch BOTH AGENTS.md and CLAUDE.md when both exist."""

    def _setup_both(self, agents_block=False, claude_block=False) -> Path:
        d = tempfile.mkdtemp()
        cwd = Path(d)
        a = "# AGENTS\n"
        c = "# CLAUDE\n"
        if agents_block:
            a = sync.inject_block(a)
        if claude_block:
            c = sync.inject_block(c)
        (cwd / "AGENTS.md").write_text(a, encoding="utf-8")
        (cwd / "CLAUDE.md").write_text(c, encoding="utf-8")
        return cwd

    def test_resolve_targets_returns_both(self) -> None:
        cwd = self._setup_both()
        targets = sync.resolve_targets(cwd=str(cwd))
        self.assertEqual([t.name for t in targets], ["AGENTS.md", "CLAUDE.md"])

    def test_apply_injects_into_both(self) -> None:
        cwd = self._setup_both()
        result = sync.apply(cwd=str(cwd))
        self.assertTrue(result.applied)
        self.assertTrue(result.changed)
        agents = (cwd / "AGENTS.md").read_text(encoding="utf-8")
        claude = (cwd / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(sync.has_block(agents))
        self.assertTrue(sync.has_block(claude))
        # summary mentions both files
        self.assertIn("AGENTS.md", result.message)
        self.assertIn("CLAUDE.md", result.message)

    def test_apply_idempotent_when_both_present(self) -> None:
        cwd = self._setup_both(agents_block=True, claude_block=True)
        result = sync.apply(cwd=str(cwd))
        self.assertTrue(result.applied)   # present in all
        self.assertFalse(result.changed)  # no change

    def test_apply_partial_fills_missing(self) -> None:
        # block in AGENTS only → apply adds to CLAUDE, reports changed
        cwd = self._setup_both(agents_block=True, claude_block=False)
        result = sync.apply(cwd=str(cwd))
        self.assertTrue(result.applied)   # now in both
        self.assertTrue(result.changed)   # CLAUDE was modified

    def test_verify_present_in_both(self) -> None:
        cwd = self._setup_both(agents_block=True, claude_block=True)
        result = sync.verify(cwd=str(cwd))
        self.assertTrue(result.applied)

    def test_verify_absent_in_one_reports_false(self) -> None:
        cwd = self._setup_both(agents_block=True, claude_block=False)
        result = sync.verify(cwd=str(cwd))
        self.assertFalse(result.applied)  # not in ALL

    def test_remove_strips_from_both(self) -> None:
        cwd = self._setup_both(agents_block=True, claude_block=True)
        result = sync.remove(cwd=str(cwd))
        self.assertTrue(result.changed)
        agents = (cwd / "AGENTS.md").read_text(encoding="utf-8")
        claude = (cwd / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertFalse(sync.has_block(agents))
        self.assertFalse(sync.has_block(claude))

    def test_remove_partial_reports_changed(self) -> None:
        # block in AGENTS only → remove strips it, CLAUDE no-op, changed=True
        cwd = self._setup_both(agents_block=True, claude_block=False)
        result = sync.remove(cwd=str(cwd))
        self.assertTrue(result.changed)
        self.assertFalse(sync.has_block((cwd / "AGENTS.md").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
