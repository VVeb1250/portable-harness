"""quality-gate compact-output probe: actionlint + lychee diagnostics.

Deterministic, no network. Seeds one real defect per tool, runs the tool, and
measures the diagnostic that enters context. Substantiates the quality-gate
claim of BOUNDED, STRUCTURED diagnostics (file:line) that fail fast locally
instead of surfacing as a long CI log + repair loop.

This probe measures the diagnostic's absolute compactness + structure (the
direct, local-measurable half). The avoided long-CI-log cost is the
counterfactual upside, not measured here. Provenance: measured, output bytes.

Run: py bench/_quality_gate_output.py
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "_bin"
ACTIONLINT = BIN / "actionlint.exe"
LYCHEE = BIN / "lychee.exe"

FILE_LINE = re.compile(r":\d+:\d+:|:\d+:")  # file:line(:col) structured locator


def tok(s: str) -> int:
    return round(len(s) / 4)


def report(name: str, out: str, structured: bool) -> tuple[str, str]:
    return name, out


def main() -> None:
    for b in (ACTIONLINT, LYCHEE):
        if not b.exists():
            raise SystemExit(f"missing {b} (download bench/_bin binaries first)")

    work = Path(tempfile.mkdtemp())

    # --- actionlint: a workflow that needs a non-existent job ---
    wf = work / ".github" / "workflows" / "broken.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "on: push\njobs:\n  build:\n    needs: ghost-job\n"
        "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n",
        encoding="utf-8",
    )
    al = subprocess.run(
        [str(ACTIONLINT), "-no-color", str(wf)],
        capture_output=True, text=True,
    )
    al_out = (al.stdout + al.stderr).strip()

    # --- lychee: a markdown pointing at a missing local file (offline = no net) ---
    md = work / "page.md"
    md.write_text("# page\n[dead](./does-not-exist.md)\n", encoding="utf-8")
    ly = subprocess.run(
        [str(LYCHEE), "--offline", "--no-progress", str(md)],
        capture_output=True, text=True,
    )
    ly_out = (ly.stdout + ly.stderr).strip()

    rows = [
        ("actionlint (broken workflow)", al_out),
        ("lychee (dead local link)", ly_out),
    ]
    w = max(len(r[0]) for r in rows)
    print(f"{'tool / seeded defect':<{w}}  {'chars':>6}  {'~tok':>5}  {'lines':>5}  structured")
    for name, out in rows:
        struct = "yes" if FILE_LINE.search(out) or "does-not-exist" in out else "no"
        print(f"{name:<{w}}  {len(out):>6}  {tok(out):>5}  {out.count(chr(10)) + 1:>5}  {struct}")

    # gates: each tool flagged its defect, output is bounded + locatable
    assert al.returncode != 0 and FILE_LINE.search(al_out), "actionlint must emit file:line"
    assert "does-not-exist" in ly_out, "lychee must name the dead link"
    assert tok(al_out) < 200 and tok(ly_out) < 200, "diagnostics must stay bounded"
    print()
    print("PASS — both diagnostics bounded (<200 tok) and structured/locatable.")


if __name__ == "__main__":
    main()
