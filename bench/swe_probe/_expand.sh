#!/usr/bin/env bash
# Autonomous bench expansion (N=5 -> ~8) + backfill 13915. Runs the codex-driven
# arms only (deepseek/codex/team3) — claude-solo is authored by hand later, so
# this needs zero Claude quota. Fires after codex reset; produces _report.txt.
set -u
cd "$(dirname "$0")/../.." || exit 1
LOG=bench/swe_probe/_expand.log
NEW="sympy__sympy-11400 sympy__sympy-11870 sympy__sympy-11897"
echo "=== expand start $(date) ===" | tee -a "$LOG"

# 0. backfill the one missing pair from N=5 (codex was rate-limited last run)
echo "### backfill 13915 (codex-solo + team3)" | tee -a "$LOG"
py -m bench.swe_probe.run codex-solo sympy__sympy-13915 2>&1 | tail -3 | tee -a "$LOG"
py -m bench.swe_probe.run eval     sympy__sympy-13915 codex-solo 2>&1 | tail -2 | tee -a "$LOG"
py -m bench.swe_probe.run team3    sympy__sympy-13915 2>&1 | tail -4 | tee -a "$LOG"

# 1. pull + gold-validate the 3 new instances; keep only PASS (env trustworthy)
PASS=""
for id in $NEW; do
  echo "### pull+gold-validate $id" | tee -a "$LOG"
  py -m bench.swe_probe.run pull "$id" 2>&1 | tail -1 | tee -a "$LOG"
  out=$(py -m bench.swe_probe.run gold-validate "$id" 2>&1)
  echo "$out" | tail -1 | tee -a "$LOG"
  if echo "$out" | grep -q "PASS (env trustworthy)"; then PASS="$PASS $id"; fi
done
echo "### PASS instances:$PASS" | tee -a "$LOG"

# 2. automated arms on the PASS new instances (deepseek/codex/team3 + evals)
if [ -n "$PASS" ]; then
  bash bench/swe_probe/_phaseB_arms.sh $PASS 2>&1 | tee -a "$LOG"
fi

# 3. final report
echo "=== REPORT ===" | tee -a "$LOG"
py -m bench.swe_probe.run report 2>&1 | tee bench/swe_probe/_report.txt | tee -a "$LOG"
echo "=== expand done $(date) ===" | tee -a "$LOG"
