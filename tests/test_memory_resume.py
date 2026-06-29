"""Tests for paw.memory.resume — SessionStart resume block builder."""
from __future__ import annotations

import unittest
from pathlib import Path
from typing import List, Optional

from paw.memory import decision_mirror as dm
from paw.memory import resume, status_store as ss


def _status(note_summary: str = "", head: str = "abc1234") -> ss.ProjectStatus:
    return ss.ProjectStatus(
        project="p",
        git=ss.GitLayer(branch="main", head_short=head, dirty_count=0),
        note=ss.NoteLayer(summary=note_summary, updated_at="t",
                          updated_by="h", base_head=head) if note_summary else None,
    )


class BuildResumeBlockTests(unittest.TestCase):
    def test_empty_when_nothing_present(self) -> None:
        out = resume.build_resume_block(
            "p",
            md_paths=(),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: [],
            mirror_runner=None,
            handoff_reader=None,
        )
        self.assertEqual(out, "")

    def test_status_only(self) -> None:
        out = resume.build_resume_block(
            "portable-harness",
            md_paths=(),
            status_reader=lambda p: _status("did X / next Y"),
            decisions_reader=lambda paths, base: [],
            mirror_runner=None,
            handoff_reader=None,
        )
        self.assertIn("📌 paw resume (portable-harness)", out)
        self.assertIn("status: did X / next Y", out)
        self.assertIn("git: main · abc1234 · dirty 0", out)
        self.assertNotIn("decisions:", out)
        self.assertNotIn("last handoff:", out)

    def test_decisions_section_bounded(self) -> None:
        decisions = [dm.Decision(slug=f"d{i}", body=f"body {i}") for i in range(8)]
        out = resume.build_resume_block(
            "p",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: decisions,
            mirror_runner=lambda paths, base: 8,
            handoff_reader=None,
        )
        # only MAX_DECISIONS (5) shown
        self.assertEqual(out.count("• d"), 5)
        self.assertIn("• d0: body 0", out)
        self.assertNotIn("d5:", out)

    def test_decision_body_truncated(self) -> None:
        long_body = "x" * 200
        out = resume.build_resume_block(
            "p",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: [dm.Decision(slug="big", body=long_body)],
            mirror_runner=lambda paths, base: 1,
            handoff_reader=None,
        )
        # body line truncated to ~90 chars including ellipsis
        line = [ln for ln in out.splitlines() if "big:" in ln][0]
        self.assertLessEqual(len(line), 100)  # slug prefix + 90 + ellipsis

    def test_handoff_present(self) -> None:
        out = resume.build_resume_block(
            "p",
            md_paths=(),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: [],
            mirror_runner=None,
            handoff_reader=lambda proj, cwd: "Claude: continue from Phase 2",
        )
        self.assertIn("last handoff: Claude: continue from Phase 2", out)

    def test_handoff_truncated(self) -> None:
        long_handoff = "z" * 300
        out = resume.build_resume_block(
            "p",
            md_paths=(),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: [],
            mirror_runner=None,
            handoff_reader=lambda proj, cwd: long_handoff,
        )
        handoff_line = [ln for ln in out.splitlines() if "handoff" in ln][0]
        self.assertLessEqual(len(handoff_line), 160)

    def test_full_block_all_three(self) -> None:
        out = resume.build_resume_block(
            "portable-harness",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=lambda p: _status("building memory loop"),
            decisions_reader=lambda paths, base: [dm.Decision(slug="keep-icm", body="keep ICM")],
            mirror_runner=lambda paths, base: 1,
            handoff_reader=lambda proj, cwd: "next: Phase 3 voice",
        )
        self.assertIn("📌 paw resume (portable-harness)", out)
        self.assertIn("status:", out)
        self.assertIn("decisions:", out)
        self.assertIn("last handoff:", out)

    def test_status_exception_does_not_break_block(self) -> None:
        def boom(p):
            raise RuntimeError("icm down")
        out = resume.build_resume_block(
            "p",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=boom,
            decisions_reader=lambda paths, base: [dm.Decision(slug="x", body="y")],
            mirror_runner=lambda paths, base: 1,
            handoff_reader=None,
        )
        # status dropped, decisions still present
        self.assertNotIn("status:", out)
        self.assertIn("decisions:", out)

    def test_decisions_exception_does_not_break_block(self) -> None:
        out = resume.build_resume_block(
            "p",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=lambda p: _status("ok"),
            decisions_reader=lambda paths, base: (_ for _ in ()).throw(RuntimeError("parse fail")),
            mirror_runner=lambda paths, base: 0,
            handoff_reader=None,
        )
        self.assertIn("status:", out)
        self.assertNotIn("decisions:", out)

    def test_mirror_runner_skipped_when_none(self) -> None:
        called = {"mirror": False}

        def mirror(paths, base):
            called["mirror"] = True
            return 0

        resume.build_resume_block(
            "p",
            md_paths=(Path("CLAUDE.md"),),
            status_reader=lambda p: None,
            decisions_reader=lambda paths, base: [],
            mirror_runner=None,  # explicitly skip
            handoff_reader=None,
        )
        self.assertFalse(called["mirror"])

    def test_stale_status_flagged(self) -> None:
        # note base abc1234 but git moved to NEW → stale
        status = ss.ProjectStatus(
            project="p",
            git=ss.GitLayer(branch="main", head_short="NEW", dirty_count=0),
            note=ss.NoteLayer(summary="old note", updated_at="t",
                              updated_by="h", base_head="abc1234"),
        )
        out = resume.build_resume_block(
            "p", md_paths=(), status_reader=lambda p: status,
            decisions_reader=lambda paths, base: [], mirror_runner=None,
            handoff_reader=None,
        )
        self.assertIn("⚠️ stale", out)


if __name__ == "__main__":
    unittest.main()
