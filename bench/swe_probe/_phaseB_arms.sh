#!/usr/bin/env bash
# Phase B: automated arms on trustworthy instances (args = instance ids).
# Per id: deepseek-solo (weak-member baseline) -> codex-solo (strong solo) ->
# team3 (3-role team, self-evals in its loop). claude-solo is authored by hand
# (the Claude seat) separately, NOT here.
set -u
cd "$(dirname "$0")/../.." || exit 1
for id in "$@"; do
  echo "########## $id ##########"
  echo "----- deepseek-solo -----"
  py -m bench.swe_probe.run deepseek-solo "$id" 2>&1 | tail -3
  py -m bench.swe_probe.run eval "$id" deepseek-solo 2>&1 | tail -2
  echo "----- codex-solo -----"
  py -m bench.swe_probe.run codex-solo "$id" 2>&1 | tail -3
  py -m bench.swe_probe.run eval "$id" codex-solo 2>&1 | tail -2
  echo "----- team3 -----"
  py -m bench.swe_probe.run team3 "$id" 2>&1 | tail -6
done
echo "=== PHASE B DONE ==="
