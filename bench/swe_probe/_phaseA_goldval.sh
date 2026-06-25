#!/usr/bin/env bash
# Phase A: gold-validate every sympy instance ONCE. Env image builds on the
# first id, reused after. PASS => env trustworthy; FAIL => drop from the bench.
set -u
IDS="sympy__sympy-13031 sympy__sympy-13177 sympy__sympy-13437 sympy__sympy-13647 sympy__sympy-13895 sympy__sympy-13915"
cd "$(dirname "$0")/../.." || exit 1
: > bench/swe_probe/_phaseA.result
for id in $IDS; do
  echo "===== gold-validate $id ====="
  out=$(py -m bench.swe_probe.run gold-validate "$id" 2>&1)
  echo "$out" | tail -2
  if echo "$out" | grep -q "PASS (env trustworthy)"; then
    echo "$id PASS" >> bench/swe_probe/_phaseA.result
  else
    echo "$id FAIL" >> bench/swe_probe/_phaseA.result
  fi
done
echo "=== PHASE A DONE ==="
cat bench/swe_probe/_phaseA.result
