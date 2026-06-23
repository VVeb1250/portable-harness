#!/usr/bin/env bash
# Score one (instance, arm) with the official swebench harness inside WSL,
# against Docker Desktop. Called by run.py via: wsl -d Ubuntu bash <this> <id> <arm>
# The report.json lands under eval_out/logs/... where Windows run.py reads it.
set -euo pipefail
ID="$1"; ARM="$2"
ROOT="/mnt/e/portable-harness/bench/swe_probe"
PRED="$ROOT/preds/${ID}__${ARM}.jsonl"
RUN_ID="${ID}__${ARM}"
PY="${SWEBENCH_WSL_PY:-python3}"

[ -f "$PRED" ] || { echo "missing prediction: $PRED" >&2; exit 2; }
mkdir -p "$ROOT/eval_out"
cd "$ROOT/eval_out"
exec "$PY" -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --predictions_path "$PRED" \
  --instance_ids "$ID" \
  --run_id "$RUN_ID" \
  --cache_level env \
  --max_workers 1
