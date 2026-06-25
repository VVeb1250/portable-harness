"""api-quality output A/B: raw response dump vs `hurl --test` summary.

Deterministic, no network: spins a local mock API, then compares what enters
agent context for two workflows on the SAME endpoint —

  RAW   : fetch the endpoint, the full JSON body lands in context (curl-style).
  HURL  : a .hurl with assertions, run via `hurl --test` -> compact summary on
          success; a bounded expected/actual diff on failure.

Metric = output size (chars + a chars/4 token proxy). Substantiates the
api-quality claim: test mode suppresses successful bodies and only failures
opt into evidence. Provenance: measured on this box, output bytes.

Run: py bench/_api_quality_hurl_ab.py
"""
from __future__ import annotations

import json
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
HURL = HERE / "_bin" / "hurl.exe"

# A realistic API response — the kind of body a raw curl drops into context.
BODY = {
    "id": 42,
    "email": "ada@example.com",
    "name": "Ada Lovelace",
    "active": True,
    "roles": ["admin", "engineer", "reviewer"],
    "address": {"street": "12 Analytical Way", "city": "London", "zip": "EC1A"},
    "teams": [{"id": 1, "name": "kernel"}, {"id": 2, "name": "router"}],
    "metadata": {
        "created_at": "2026-01-04T09:00:00Z",
        "updated_at": "2026-06-26T11:30:00Z",
        "login_count": 318,
        "preferences": {"theme": "dark", "tz": "UTC", "digest": "weekly"},
    },
    "quota": {"cpu_seconds": 86400, "storage_mb": 51200, "requests": 1_000_000},
}
PAYLOAD = json.dumps(BODY, indent=2).encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *a):  # silence
        pass


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def tok(s: str) -> int:
    return round(len(s) / 4)


def run_hurl(text: str) -> str:
    f = HERE / "_bin" / "_probe.hurl"
    f.write_text(text, encoding="utf-8")
    p = subprocess.run(
        [str(HURL), "--test", "--no-color", str(f)],
        capture_output=True, text=True,
    )
    f.unlink(missing_ok=True)
    return (p.stdout + p.stderr).strip()


def main() -> None:
    if not HURL.exists():
        raise SystemExit(f"hurl not found at {HURL} (run the bench/_bin download first)")

    port = free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/users/42"
    try:
        # RAW workflow: the full body enters context.
        raw = PAYLOAD.decode()

        # HURL success: assert status + two fields -> compact summary, body hidden.
        ok = run_hurl(
            f"GET {base}\nHTTP 200\n[Asserts]\n"
            'jsonpath "$.id" == 42\n'
            'jsonpath "$.email" == "ada@example.com"\n'
        )
        # HURL failure: one wrong assertion -> bounded expected/actual evidence.
        bad = run_hurl(
            f"GET {base}\nHTTP 200\n[Asserts]\n"
            'jsonpath "$.id" == 999\n'
        )
    finally:
        srv.shutdown()

    rows = [
        ("raw response dump (curl-style)", raw),
        ("hurl --test, success", ok),
        ("hurl --test, one failed assert", bad),
    ]
    w = max(len(r[0]) for r in rows)
    print(f"{'workflow':<{w}}  {'chars':>6}  {'~tok':>5}  {'lines':>5}")
    for name, out in rows:
        print(f"{name:<{w}}  {len(out):>6}  {tok(out):>5}  {out.count(chr(10)) + 1:>5}")

    cut = 100 * (1 - tok(ok) / tok(raw))
    print()
    print(f"success-path token cut vs raw body: {cut:.1f}%  ({tok(raw)} -> {tok(ok)})")
    assert tok(ok) < tok(raw), "hurl success summary should be smaller than raw body"
    assert "999" in bad or "assert" in bad.lower(), "failure output must carry bounded evidence"
    assert tok(bad) < tok(raw) * 2, "failure evidence should stay bounded"
    print("PASS — success path compact; failure path bounded.")


if __name__ == "__main__":
    main()
