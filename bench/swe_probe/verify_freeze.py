"""Verify the frozen SymPy N=8 benchmark evidence without running paid arms."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "FROZEN_N8_2026-06-25.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(paths: list[Path]) -> str:
    rows = [f"{sha256(path)}  {path.relative_to(BASE.parent.parent).as_posix()}" for path in paths]
    return hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["sha256"]
    failures: list[str] = []

    report_hash = sha256(BASE / "_report.txt")
    if report_hash != expected["report"]:
        failures.append(f"report hash: {report_hash}")

    for name, digest in expected["runner"].items():
        actual = sha256(BASE / name)
        if actual != digest:
            failures.append(f"{name} hash: {actual}")

    instance_ids = manifest["cohort"]["instance_ids"]
    instances = [BASE / "instances" / f"{instance_id}.json" for instance_id in instance_ids]
    results = [BASE / "results" / f"{instance_id}.json" for instance_id in instance_ids]
    if aggregate(instances) != expected["instances_aggregate"]:
        failures.append("instances aggregate")
    if aggregate(results) != expected["results_aggregate"]:
        failures.append("results aggregate")

    cohort = "|".join(re.escape(instance_id) for instance_id in instance_ids)
    prediction_pattern = re.compile(
        rf"^(?:{cohort})__(?:team3|codex-solo|claude-solo|deepseek-solo)"
        r"\.(?:diff|jsonl)$"
    )
    predictions = sorted(
        path for path in (BASE / "preds").iterdir() if prediction_pattern.fullmatch(path.name)
    )
    if aggregate(predictions) != expected["canonical_predictions_aggregate"]:
        failures.append("canonical predictions aggregate")

    for instance_id, digest in expected["blind_inputs"].items():
        path = BASE / "preds" / f"_blind_{instance_id}.txt"
        if not path.exists() or sha256(path) != digest:
            failures.append(f"blind input: {instance_id}")

    report = subprocess.run(
        [sys.executable, "-m", "bench.swe_probe.run", "report"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if report.returncode != 0:
        failures.append(f"report command failed: {report.stderr.strip()}")
    elif report.stdout.rstrip() != (BASE / "_report.txt").read_text(encoding="utf-8").rstrip():
        failures.append("regenerated report differs from _report.txt")

    if failures:
        print("freeze verification FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "freeze verification PASS: "
        f"{len(instances)} instances, {len(results)} result ledgers, "
        f"{len(predictions)} canonical prediction artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
