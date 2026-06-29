"""Voice classifier — how loud should a memory be when delivered to the agent?

This is the fix for the "สะเปะสะปะ" feeling: today every recalled lesson is
whispered at the same volume, so the agent cannot tell a near-certain mistake
from a soft hunch. This module maps a (kind, confidence) pair to one of five
voices, and a renderer turns each voice into a distinct prefix/format.

The split the user insisted on, and that this encodes:

  • MISTAKE   — graduated by confidence. High = SHOUT ("stop, re-think"),
                mid = WARN (caution), low = SILENT (stored, not shown).
  • DECISION  — always a soft NUDGE ("we decided X; tell me if you change it").
                Decisions are revisable, so we never raise our voice.
  • STATUS    — RESUME voice, used only by the SessionStart block.

A SHOUT bypasses sessionlog dedup (a near-certain mistake must be heard every
time it is relevant, even if shown once already). Lower voices respect dedup.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Voice(str, Enum):
    SHOUT = "shout"
    WARN = "warn"
    NUDGE = "nudge"
    RESUME = "resume"
    SILENT = "silent"


# Thresholds — tuned defaults, expected to be adjusted against real traffic.
# Confidence < SHOUT but still notable → WARN. Below WARN → not worth the token.
SHOUT_THRESHOLD = 0.8
WARN_THRESHOLD = 0.4


@dataclass(frozen=True)
class Memory:
    """Minimal shape the classifier needs. Avoids coupling to ICM dict layout."""

    kind: str            # "mistake" | "decision" | "status" | other
    confidence: Optional[float]  # 0.0–1.0; None = legacy/unknown
    summary: str = ""

    @property
    def is_mistake(self) -> bool:
        return self.kind == "mistake"


def classify(mem: Memory) -> Voice:
    """Map (kind, confidence) → Voice. The single source of truth for volume.

    Defaults are conservative: unknown kind or confidence leans to NUDGE/SILENT,
    never to SHOUT. A false SHOUT is worse than a missed WARN because it breaks
    trust in the louder voices.
    """
    kind = (mem.kind or "").lower()
    conf = mem.confidence

    if kind == "status":
        return Voice.RESUME
    if kind == "decision":
        return Voice.NUDGE
    if kind == "mistake":
        # Legacy / unknown confidence: do not shout — nudge so it is at least
        # visible, but does not claim certainty it cannot back.
        if conf is None:
            return Voice.NUDGE
        if conf >= SHOUT_THRESHOLD:
            return Voice.SHOUT
        if conf >= WARN_THRESHOLD:
            return Voice.WARN
        return Voice.SILENT
    # Unknown kind: soft nudge, never silent (we might be missing a kind tag)
    # and never loud (no basis to).
    return Voice.NUDGE


def bypasses_dedup(voice: Voice) -> bool:
    """Only SHOUT bypasses the sessionlog once-per-session dedup.

    A SHOUT is a near-certain mistake that MUST be heard on every relevant
    prompt, even if it was shown earlier this session. Everything else can be
    deduplicated to keep the prompt lean.
    """
    return voice is Voice.SHOUT


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

_PREFIX = {
    Voice.SHOUT: "🛑 STOP — re-think:",
    Voice.WARN: "⚠️ caution:",
    Voice.NUDGE: "💡 note:",
    Voice.RESUME: "📌",
    Voice.SILENT: "",
}


def render(voice: Voice, text: str) -> str:
    """Format a memory line for injection. '' for SILENT.

    The prefix is deliberately distinct across voices so the agent's eye is
    drawn to a SHOUT and can tune out a NUDGE — restoring the signal gradient
    that a single uniform whisper destroys.
    """
    if voice is Voice.SILENT:
        return ""
    body = (text or "").strip().replace("\n", " ")
    if not body:
        return ""
    prefix = _PREFIX[voice]
    if voice is Voice.RESUME:
        return f"{prefix} {body}"
    return f"{prefix} {body}"


def render_memory(mem: Memory) -> str:
    """Classify then render in one call. '' if the voice is SILENT."""
    return render(classify(mem), mem.summary)
