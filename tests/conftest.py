"""Shared pytest fixtures — keep tests OUT of the real ~/.paw ledger.

paw's router/distrust/sessionlog overlays live under ~/.paw (or $PAW_HOME) and
several modules write to them on the hot path (every prompt). Without isolation,
running the suite silently pollutes the real ledgers — e.g. mark_suggested
bumps a capability's suggest count until it crosses the demotion threshold,
which then breaks OTHER tests' routing assertions AND changes real routing.

Two guarantees every test inherits:

  1. ``PAW_HOME`` points at a temp dir, so distrust/sessionlog/outcomes ledgers
     are created and dropped per-session instead of touching ~/.paw.
  2. The router outcome-loop seam (``_OUTCOMES_PROBE``) is stubbed to a no-op
     (empty demoted set, discarded mark) so match_sets never writes a ledger
     unless a test EXPLICITLY opts back into the real path by setting it None.

Tests that want to assert loop behavior set ``rb._OUTCOMES_PROBE`` themselves;
the autouse fixture saves/restores it so they can't leak into siblings.
"""
from __future__ import annotations

import tempfile
from typing import Callable

import pytest

import paw.router_block as rb


@pytest.fixture(autouse=True)
def _isolate_paw_home(monkeypatch):
    """Redirect every ~/.paw write to a throwaway dir for the duration of a test."""
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("PAW_HOME", d)
        yield


@pytest.fixture(autouse=True)
def _stub_router_outcome_seam(monkeypatch):
    """match_sets must not bump the real suggest ledger unless a test asks it to.

    Saves the real seam, installs a no-op, and restores it after — so a test that
    sets its own probe for an assertion can't leak that probe to siblings.
    """
    saved = rb._OUTCOMES_PROBE
    monkeypatch.setattr(rb, "_OUTCOMES_PROBE", (set(), lambda _names: None))
    yield
    rb._OUTCOMES_PROBE = saved
