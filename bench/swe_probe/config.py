"""Shared config for the team-vs-solo SWE-bench-Lite probe.

Probe question (STATUS #1 EXISTENTIAL + #2 measure-success):
  Does Claude-plan + DeepSeek-implement hold resolution-rate vs Claude-solo,
  while burning far less scarce Claude quota?

All arms use ORACLE retrieval (the files the gold patch edits) and a single
shot (no agentic retry loop) to keep Claude quota and DeepSeek $ minimal.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- dataset ---------------------------------------------------------------
DATASET = "princeton-nlp/SWE-bench_Lite"
SPLIT = "test"
CONFIG = "default"

# --- DeepSeek (Anthropic-compatible endpoint) ------------------------------
# verified 2026-06-23: DeepSeek exposes an Anthropic-compatible API at /anthropic
#   docs: https://api-docs.deepseek.com/quick_start/pricing
DEEPSEEK_BASE = "https://api.deepseek.com/anthropic"
DEEPSEEK_MODEL = "deepseek-v4-flash"  # deepseek-chat/reasoner deprecate 2026-07-24
DEEPSEEK_KEY_ENV = "DEEPSEEK_API_KEY"

# v4-flash USD/token (cache-miss input). recheck on price change.
PRICE_IN = 0.14 / 1_000_000
PRICE_OUT = 0.28 / 1_000_000

# --- API-equivalent pricing (USD per 1M tokens) ----------------------------
# For the cost axis we price EVERY member at API list rate, even the
# subscription seats (Claude/Codex real marginal $ is $0 — flat monthly fee).
# This puts all members in ONE currency = opportunity cost ("what this run
# would cost billed at API rates"). Without it the sub seats read as $0 and a
# team that adds metered DeepSeek cents looks worse than a "free" solo seat,
# hiding that the solo seat burned scarce, capped quota. Reasoning tokens are
# billed at the output rate.
# RATES verified 2026-06-24 (recheck on model/price change, STATUS §G):
#   Claude Opus 4.8 std  $5 / $25    platform.claude.com/docs pricing
#   gpt-5-codex          $1.25 / $10 help.openai.com codex rate-card (5.2/5.3=$1.75/$14)
#   DeepSeek v4-flash    $0.14 / $0.28  (metered = real out-of-pocket)
PRICING = {  # member: (usd_per_1M_input, usd_per_1M_output)
    "claude": (5.0, 25.0),
    "codex": (1.25, 10.0),
    "deepseek": (PRICE_IN * 1_000_000, PRICE_OUT * 1_000_000),
}


def usd(member: str, in_tok: int, out_tok: int, reason_tok: int = 0) -> float:
    """API-equivalent USD for one member's token usage (reasoning at out rate)."""
    pin, pout = PRICING[member]
    return (in_tok * pin + (out_tok + reason_tok) * pout) / 1_000_000

# --- arms ------------------------------------------------------------------
ARMS = ("claude-solo", "deepseek-solo", "team", "codex-solo",
        "claude-plan-codex", "codex-plan-deepseek", "team3")

# --- candidate instances (hermetic tests only; VERIFY via gold-validate) -----
# NB: psf/requests instances are NON-hermetic (need httpbin) -> gold-validate
# fails under container network isolation; SWE-bench Verified dropped them.
# Use repos with in-process tests (flask test_client, pytest, pylint).
CANDIDATES = [
    "pallets__flask-4045",
    "pallets__flask-4992",
]

# --- scorer ----------------------------------------------------------------
# swebench imports `resource` (Unix-only) → cannot run on Windows native python.
# On Windows we route scoring through WSL (Linux python + Docker Desktop).
USE_WSL = os.name == "nt"
WSL_DISTRO = os.environ.get("WSL_DISTRO", "Ubuntu")
# direct (non-Windows) fallback: a Linux/Mac python that has swebench installed.
SWEBENCH_PYTHON = os.environ.get("SWEBENCH_PYTHON", "python3")
CACHE_LEVEL = "env"  # env-level cache: keeps repo env image, drops per-instance


def win_to_wsl(p: Path) -> str:
    """E:\\portable-harness\\x -> /mnt/e/portable-harness/x"""
    posix = p.as_posix()  # 'E:/portable-harness/x'
    return f"/mnt/{posix[0].lower()}{posix[2:]}"

# --- paths -----------------------------------------------------------------
BASE = Path(__file__).parent
INSTANCES = BASE / "instances"   # oracle bundles (problem + files + gold)
PREDS = BASE / "preds"           # per-arm predictions.jsonl
RESULTS = BASE / "results"       # per-instance ledger json
EVAL_OUT = BASE / "eval_out"     # swebench report output dir

for _d in (INSTANCES, PREDS, RESULTS, EVAL_OUT):
    _d.mkdir(parents=True, exist_ok=True)


def deepseek_key() -> str:
    key = os.environ.get(DEEPSEEK_KEY_ENV, "").strip()
    if not key:
        raise SystemExit(f"set ${DEEPSEEK_KEY_ENV} before running DeepSeek arms")
    return key
