"""A/B the context-mode 'Think-in-Code' lane vs raw-dump vs rtk, same fixtures.

For each saved tool-output fixture (bench/out/compress/*.raw.txt) we drive
context-mode's stdio MCP server and call ctx_execute_file with a small JS
extractor — the digest an agent would actually need. Only what the sandbox
console.log()s enters context, so that output is the real context cost.

Lanes (tiktoken cl100k, same encoder => relative delta valid):
  raw  = read the whole file into context (what a naive tool dump costs)
  rtk  = rtk-compressed dump (from _compress_ab capture, if present)
  cm   = ctx_execute_file digest (bytes stay in sandbox)

This is an honest A/B: cm is LOSSY by design (it emits a summary, not the
bytes). It wins big on aggregate-able data (logs, stats, tallies) and little
on data you need verbatim — exactly where the lossless ctx_index/ctx_search
lane takes over. Completeness is an eyeball on the emitted digest.
"""
import json, os, subprocess, pathlib, tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
OUT = pathlib.Path(__file__).parent / "out" / "compress"
ENTRY = os.path.join(os.environ["APPDATA"], "npm", "node_modules",
                     "context-mode", "server.bundle.mjs")


def tk(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


# JS extractors keyed by fixture name. FILE_CONTENT = the file text (string).
EXTRACT = {
    "git_log_stat": r"""
const L=FILE_CONTENT.split("\n");
const commits=L.filter(x=>/^commit /.test(x)).length;
const files={};
for(const l of L){const m=l.match(/^\s(\S.*?)\s+\|\s+\d+/);if(m){const f=m[1].trim();files[f]=(files[f]||0)+1;}}
const top=Object.entries(files).sort((a,b)=>b[1]-a[1]).slice(0,8);
console.log(`commits=${commits} files_touched=${Object.keys(files).length}`);
for(const [f,n] of top) console.log(`${n}x ${f}`);
""",
    "git_status": r"""
const branch=(FILE_CONTENT.match(/On branch (\S+)/)||[])[1]||"?";
const L=FILE_CONTENT.split("\n").map(s=>s.trim()).filter(Boolean);
console.log(`branch=${branch} report_lines=${L.length}`);
""",
    "grep_todo": r"""
const L=FILE_CONTENT.split("\n").filter(Boolean);
const byf={};
for(const l of L){const f=l.split(":")[0];byf[f]=(byf[f]||0)+1;}
console.log(`todos=${L.length} files=${Object.keys(byf).length}`);
for(const [f,n] of Object.entries(byf).sort((a,b)=>b[1]-a[1]).slice(0,6)) console.log(`${n} ${f}`);
""",
    "ls_recursive": r"""
const L=FILE_CONTENT.split("\n").filter(Boolean);
const ext={};
for(const l of L){const e=(l.match(/\.([a-z0-9]+)$/i)||[])[1]||"(none)";ext[e]=(ext[e]||0)+1;}
console.log(`files=${L.length}`);
for(const [e,n] of Object.entries(ext).sort((a,b)=>b[1]-a[1]).slice(0,8)) console.log(`${n} .${e}`);
""",
    "pytest_v": r"""console.log(FILE_CONTENT.split("\n").filter(Boolean).slice(0,3).join(" | ").slice(0,200));""",
    "git_diff": r"""console.log(FILE_CONTENT.split("\n").filter(Boolean).slice(0,3).join(" | ").slice(0,200));""",
}


class Server:
    def __init__(self):
        self.p = subprocess.Popen(["node", ENTRY], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", bufsize=1)
        self._id = 0
        self._send({"jsonrpc": "2.0", "id": self._nid(), "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "ab", "version": "0"}}})
        self._recv(1)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def _nid(self):
        self._id += 1
        return self._id

    def _send(self, o):
        self.p.stdin.write(json.dumps(o) + "\n")
        self.p.stdin.flush()

    def _recv(self, _id):
        while True:
            line = self.p.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            if m.get("id") == _id:
                return m

    def call(self, name, arguments):
        """Generic tools/call -> concatenated text content of the result."""
        i = self._nid()
        self._send({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments}})
        m = self._recv(i) or {}
        content = (m.get("result", {}) or {}).get("content", [])
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))

    def execute_file(self, path, code, language="javascript"):
        return self.call("ctx_execute_file",
                         {"path": str(path), "language": language, "code": code})

    def close(self):
        self.p.terminate()


def main():
    s = Server()
    rows = []
    tot = {"raw": 0, "rtk": 0, "cm": 0}
    for name, code in EXTRACT.items():
        rawp = OUT / f"{name}.raw.txt"
        rtkp = OUT / f"{name}.rtk.txt"
        if not rawp.exists():
            continue
        raw_t = tk(rawp.read_text(encoding="utf-8"))
        rtk_t = tk(rtkp.read_text(encoding="utf-8")) if rtkp.exists() else None
        gross = s.execute_file(rawp.resolve(), code)
        # payload = stdout only (strip the echoed ```lang ... ``` code fence + path line)
        payload = gross.rsplit("```", 1)[-1].strip() if "```" in gross else gross.strip()
        cm_g, cm_p = tk(gross), tk(payload)
        rows.append((name, raw_t, rtk_t, cm_g, cm_p, payload))
        tot["raw"] += raw_t
        if rtk_t:
            tot["rtk"] += rtk_t
        tot["cm"] += cm_p          # durable context cost = payload
    s.close()

    print(f"\n{'fixture':<15}{'raw':>7}{'rtk%':>7}{'cm_pay':>8}{'pay%':>7}{'cm_gross':>9}")
    for name, r, k, cg, cp, _ in rows:
        kp = f"{100*(1-k/r):.0f}" if (r and k) else "-"
        pp = f"{100*(1-cp/r):.0f}" if r else "-"
        print(f"{name:<15}{r:>7}{kp:>7}{cp:>8}{pp:>7}{cg:>9}")
    R, K, C = tot["raw"], tot["rtk"], tot["cm"]
    print("-" * 50)
    print(f"{'TOTAL':<15}{R:>7}{100*(1-K/R):>6.0f}%{C:>8}{100*(1-C/R):>6.0f}%")
    big = [x for x in rows if x[1] >= 400]
    if big:
        br, bp = sum(x[1] for x in big), sum(x[4] for x in big)
        print(f"{'BIG (raw>=400)':<15}{br:>7}{'':>7}{bp:>8}{100*(1-bp/br):>6.0f}%   <- where execute_file is meant to run")
    print("\n--- payload digests (completeness eyeball) ---")
    for name, r, k, cg, cp, d in rows:
        print(f"\n[{name}] raw {r} -> payload {cp} tok (gross {cg}):")
        print("  " + d.replace("\n", "\n  "))


if __name__ == "__main__":
    main()
