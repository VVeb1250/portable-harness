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

# --- arms ------------------------------------------------------------------
ARMS = ("claude-solo", "deepseek-solo", "team", "codex-solo")

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
