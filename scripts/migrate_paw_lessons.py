"""One-time: migrate curated lessons from the dead ~/.paw L3 overlay into ICM.

Phase 6 of docs/MEMORY-PLAN.md. The portaw L3 store (~/.paw/memory/lessons.jsonl)
is frozen and unreadable by anything live (portaw.memory.store is gone). This
salvages the real lessons into the cross-host ICM brain and drops auto-capture
noise (raw shell commands). Idempotency is NOT attempted here; run `icm
consolidate` afterwards to merge any near-duplicates of existing ICM entries.

    py scripts/migrate_paw_lessons.py            # dry-run (default)
    py scripts/migrate_paw_lessons.py --commit    # write to ICM
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys

LESSONS = os.path.expanduser("~/.paw/memory/lessons.jsonl")
RAW = re.compile(
    r"^(py|npx|cd|git|cargo|npm|pnpm|pytest|python3?|node|bash|pwsh|powershell|"
    r"ls|cat|grep|rg|echo|tsc|uv)\b|&&|\| head|\| tail",
    re.I,
)


def _icm() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _is_raw(body: str) -> bool:
    return bool(RAW.search((body or "").strip()))


def _keep(r: dict) -> bool:
    body = (r.get("body") or "").strip()
    if _is_raw(body) or body.startswith("<"):  # raw command or template placeholder
        return False
    rec = r.get("recurrence") or 0
    conf = r.get("confidence")
    trig = r.get("trigger_terms") or []
    return bool(
        rec > 1
        or r.get("pinned")
        or (isinstance(conf, (int, float)) and conf >= 0.7)
        or (trig and len(body) > 25)
    )


def _importance(r: dict) -> str:
    rec = r.get("recurrence") or 0
    conf = r.get("confidence") or 0
    if rec >= 10:
        return "critical"
    if rec >= 2 or (isinstance(conf, (int, float)) and conf >= 0.85):
        return "high"
    return "medium"


def _keywords(r: dict) -> str:
    kws = list(r.get("trigger_terms") or [])
    kws.append(f"seen:{r.get('recurrence') or 1}")
    kws.append("migrated:paw-L3")
    return ",".join(k.replace(",", " ") for k in kws if k)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write to ICM (default: dry-run)")
    args = ap.parse_args()

    recs = [json.loads(line) for line in open(LESSONS, encoding="utf-8") if line.strip()]
    keep = [r for r in recs if _keep(r)]
    keep.sort(key=lambda r: -(r.get("recurrence") or 0))
    print(f"source={len(recs)}  migrating={len(keep)}  mode={'COMMIT' if args.commit else 'DRY-RUN'}")

    ok = 0
    for r in keep:
        body = (r.get("body") or "").strip()
        imp = _importance(r)
        kw = _keywords(r)
        if not args.commit:
            print(f"  [{imp}] {body[:70]}  ::kw={kw[:60]}")
            continue
        cmd = [_icm(), "store", "-t", "mistakes", "-c", body, "-i", imp, "-k", kw]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            ok += 1
        else:
            print(f"  FAIL: {body[:50]} :: {res.stderr.strip()[:80]}", file=sys.stderr)
    if args.commit:
        print(f"stored={ok}/{len(keep)}  → next: icm consolidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
