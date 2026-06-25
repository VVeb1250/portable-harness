#!/usr/bin/env bash
# Deterministic remainder of the N=5 sympy bench, safe to hand to Codex so it
# finishes without burning Claude quota. All model patches are already authored
# + registered; this only WAITS for Phase B, then evals the 5 pre-authored
# claude-solo patches and prints the final report. Idempotent: re-running an
# eval just re-scores the same saved .diff.
set -u
cd "$(dirname "$0")/../.." || exit 1
LOG=bench/swe_probe/_finish.log
IDS="sympy__sympy-13031 sympy__sympy-13437 sympy__sympy-13647 sympy__sympy-13895 sympy__sympy-13915"
echo "=== finisher start $(date) ===" | tee -a "$LOG"

# 1. wait for Phase B (automated arms) to finish — up to 90 min
for i in $(seq 1 360); do
  grep -q "PHASE B DONE" bench/swe_probe/_phaseB.log 2>/dev/null && break
  sleep 15
done
if grep -q "PHASE B DONE" bench/swe_probe/_phaseB.log 2>/dev/null; then
  echo "Phase B complete." | tee -a "$LOG"
else
  echo "WARN: Phase B not marked done after wait; proceeding to claude-solo evals anyway." | tee -a "$LOG"
fi

# 2. guard: Docker daemon must be up (sleep is disabled, so it should be)
for i in $(seq 1 40); do
  docker info >/dev/null 2>&1 && break
  echo "  docker daemon down, waiting ($i)..." | tee -a "$LOG"; sleep 10
done
docker info >/dev/null 2>&1 || { echo "FATAL: docker still down; cannot eval. Start Docker Desktop, then re-run this script." | tee -a "$LOG"; exit 1; }

# 3. eval the 5 pre-authored claude-solo patches
for id in $IDS; do
  echo "--- eval $id claude-solo ---" | tee -a "$LOG"
  py -m bench.swe_probe.run eval "$id" claude-solo 2>&1 | tail -2 | tee -a "$LOG"
done

# 4. final report
echo "=== REPORT ===" | tee -a "$LOG"
py -m bench.swe_probe.run report 2>&1 | tee bench/swe_probe/_report.txt | tee -a "$LOG"
echo "=== finisher done $(date) -> bench/swe_probe/_report.txt ===" | tee -a "$LOG"
