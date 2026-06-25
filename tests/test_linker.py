from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.linker import (
    apply_plan,
    build_plan,
    has_block,
    remove,
    verify,
)


class LinkerSliceZeroTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ctx = self.root / "CLAUDE.md"
        self.ctx.write_text("# project\n\noriginal content\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self):
        return build_plan("repo-pack", context=str(self.ctx), root=self.root)

    # --- plan ---------------------------------------------------------------
    def test_plan_for_cli_set_is_ok_with_inject_and_detect_actions(self) -> None:
        plan = self._plan()
        self.assertEqual(plan.status, "ok")
        kinds = {a.kind for a in plan.actions}
        self.assertIn("inject-context-block", kinds)
        self.assertIn("detect-binary", kinds)
        inject = next(a for a in plan.actions if a.kind == "inject-context-block")
        self.assertTrue(inject.requires_approval)

    def test_plan_blocks_a_set_with_mcp_servers(self) -> None:
        plan = build_plan("context-quality", context=str(self.ctx), root=self.root)
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any(w.startswith("BLOCK:") for w in plan.warnings))

    # --- apply --------------------------------------------------------------
    def test_apply_injects_block_preserves_content_and_records_ledger(self) -> None:
        result = apply_plan(self._plan(), root=self.root)
        self.assertEqual(result.status, "ok")
        text = self.ctx.read_text(encoding="utf-8")
        self.assertTrue(has_block(text, "repo-pack"))
        self.assertIn("original content", text)  # unrelated text untouched
        ledger = self.root / ".paw" / "state.json"
        self.assertTrue(ledger.exists())
        self.assertIn("repo-pack", ledger.read_text(encoding="utf-8"))

    def test_apply_is_idempotent(self) -> None:
        apply_plan(self._plan(), root=self.root)
        # rebuild plan against the now-injected file, then apply again
        apply_plan(self._plan(), root=self.root)
        text = self.ctx.read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- paw:repo-pack:start -->"), 1)

    def test_apply_refuses_a_stale_plan_after_drift(self) -> None:
        stale = self._plan()  # captures the pre-edit fingerprint
        self.ctx.write_text("# project\n\nedited elsewhere\n", encoding="utf-8")
        result = apply_plan(stale, root=self.root)
        self.assertEqual(result.status, "drifted")
        self.assertFalse(has_block(self.ctx.read_text(encoding="utf-8"), "repo-pack"))

    # --- verify -------------------------------------------------------------
    def test_verify_states(self) -> None:
        blocked = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(blocked.health, "blocked")
        apply_plan(self._plan(), root=self.root)
        linked = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertIn(linked.health, ("healthy", "degraded"))  # binary may be absent in CI

    def test_verify_detects_drift(self) -> None:
        apply_plan(self._plan(), root=self.root)
        self.ctx.write_text(
            self.ctx.read_text(encoding="utf-8") + "\nmanual edit\n", encoding="utf-8"
        )
        result = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.health, "drifted")

    # --- remove -------------------------------------------------------------
    def test_remove_round_trips_to_original_content(self) -> None:
        original = self.ctx.read_text(encoding="utf-8")
        apply_plan(self._plan(), root=self.root)
        result = remove("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.status, "ok")
        text = self.ctx.read_text(encoding="utf-8")
        self.assertFalse(has_block(text, "repo-pack"))
        self.assertIn("original content", text)
        ledger = self.root / ".paw" / "state.json"
        self.assertNotIn("\"repo-pack\"", ledger.read_text(encoding="utf-8"))

    def test_remove_refuses_after_user_drift(self) -> None:
        apply_plan(self._plan(), root=self.root)
        self.ctx.write_text(
            self.ctx.read_text(encoding="utf-8") + "\nuser touched this\n", encoding="utf-8"
        )
        result = remove("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.status, "drifted")
        self.assertTrue(has_block(self.ctx.read_text(encoding="utf-8"), "repo-pack"))


if __name__ == "__main__":
    unittest.main()
