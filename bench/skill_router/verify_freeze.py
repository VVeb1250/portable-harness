"""Verify the frozen development benchmark artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZE = Path(__file__).with_name("FROZEN_DEV_2026-06-26.json")


def main() -> int:
    data = json.loads(FREEZE.read_text(encoding="utf-8"))
    failures = []
    for relative, expected in data["files"].items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(
                f"hash mismatch: {relative} expected={expected} actual={actual}"
            )
    if failures:
        print("\n".join(failures))
        return 1
    print(f"verified {len(data['files'])} frozen development artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
