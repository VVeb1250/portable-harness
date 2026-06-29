"""Tests for paw.memory.voice — classifier + renderer."""
from __future__ import annotations

import unittest

from paw.memory.voice import (
    SHOUT_THRESHOLD,
    WARN_THRESHOLD,
    Memory,
    Voice,
    bypasses_dedup,
    classify,
    render,
    render_memory,
)


def _m(kind: str, conf=None, summary="x") -> Memory:
    return Memory(kind=kind, confidence=conf, summary=summary)


class ClassifyTests(unittest.TestCase):
    def test_mistake_high_confidence_shouts(self) -> None:
        self.assertIs(classify(_m("mistake", 0.9)), Voice.SHOUT)
        self.assertIs(classify(_m("mistake", SHOUT_THRESHOLD)), Voice.SHOUT)

    def test_mistake_mid_confidence_warns(self) -> None:
        self.assertIs(classify(_m("mistake", 0.6)), Voice.WARN)
        self.assertIs(classify(_m("mistake", WARN_THRESHOLD)), Voice.WARN)

    def test_mistake_low_confidence_silent(self) -> None:
        self.assertIs(classify(_m("mistake", 0.2)), Voice.SILENT)
        self.assertIs(classify(_m("mistake", 0.0)), Voice.SILENT)

    def test_mistake_legacy_confidence_nudges(self) -> None:
        # None confidence = legacy entry: nudge, do not shout
        self.assertIs(classify(_m("mistake", None)), Voice.NUDGE)

    def test_decision_always_nudges(self) -> None:
        # decisions are revisable — never raise voice, regardless of confidence
        self.assertIs(classify(_m("decision", 0.99)), Voice.NUDGE)
        self.assertIs(classify(_m("decision", None)), Voice.NUDGE)

    def test_status_is_resume(self) -> None:
        self.assertIs(classify(_m("status", None)), Voice.RESUME)

    def test_unknown_kind_nudges(self) -> None:
        self.assertIs(classify(_m("lesson", 0.9)), Voice.NUDGE)
        self.assertIs(classify(_m("", None)), Voice.NUDGE)

    def test_kind_case_insensitive(self) -> None:
        self.assertIs(classify(_m("Mistake", 0.9)), Voice.SHOUT)
        self.assertIs(classify(_m("DECISION", 0.5)), Voice.NUDGE)


class DedupBypassTests(unittest.TestCase):
    def test_only_shout_bypasses_dedup(self) -> None:
        self.assertTrue(bypasses_dedup(Voice.SHOUT))
        self.assertFalse(bypasses_dedup(Voice.WARN))
        self.assertFalse(bypasses_dedup(Voice.NUDGE))
        self.assertFalse(bypasses_dedup(Voice.RESUME))
        self.assertFalse(bypasses_dedup(Voice.SILENT))


class RenderTests(unittest.TestCase):
    def test_shout_format(self) -> None:
        out = render(Voice.SHOUT, "rm -rf on wrong dir")
        self.assertIn("🛑 STOP — re-think:", out)
        self.assertIn("rm -rf on wrong dir", out)

    def test_warn_format(self) -> None:
        out = render(Voice.WARN, "unhandled None branch")
        self.assertIn("⚠️ caution:", out)

    def test_nudge_format(self) -> None:
        out = render(Voice.NUDGE, "we chose ICM over agentmemory")
        self.assertIn("💡 note:", out)

    def test_silent_returns_empty(self) -> None:
        self.assertEqual(render(Voice.SILENT, "anything"), "")

    def test_render_collapses_newlines(self) -> None:
        out = render(Voice.WARN, "line1\nline2\nline3")
        self.assertNotIn("\n", out)

    def test_render_empty_body_returns_empty(self) -> None:
        self.assertEqual(render(Voice.SHOUT, ""), "")
        self.assertEqual(render(Voice.SHOUT, "   "), "")

    def test_distinct_prefixes_across_voices(self) -> None:
        # the whole point: each voice has a visibly different prefix
        prefixes = {
            render(v, "x").split(" ")[0] + " " + (render(v, "x").split(" ")[1] if len(render(v, "x").split(" ")) > 1 else "")
            for v in (Voice.SHOUT, Voice.WARN, Voice.NUDGE)
        }
        # 3 distinct lead tokens
        leads = {render(v, "x")[:3] for v in (Voice.SHOUT, Voice.WARN, Voice.NUDGE)}
        self.assertEqual(len(leads), 3)


class RenderMemoryTests(unittest.TestCase):
    def test_high_confidence_mistake_renders_as_shout(self) -> None:
        out = render_memory(_m("mistake", 0.9, "never run X on Y"))
        self.assertIn("🛑", out)
        self.assertIn("never run X on Y", out)

    def test_low_confidence_mistake_renders_empty(self) -> None:
        self.assertEqual(render_memory(_m("mistake", 0.2, "maybe")), "")

    def test_decision_renders_as_nudge(self) -> None:
        out = render_memory(_m("decision", 0.5, "keep ICM"))
        self.assertIn("💡", out)


if __name__ == "__main__":
    unittest.main()
