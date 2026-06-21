#!/usr/bin/env python
"""mcp_tax.py — BENCH Phase 0 instrument: measure per-server MCP tool-def tax.

Spawns an MCP server over stdio, lists its tools, serializes them to the
Anthropic `tools` schema, and counts tokens. The token count ≈ the static
"head" tax paid EVERY session (and re-paid on compaction) just for that
server's definitions — independent of whether any tool is ever called.

Counting backend (best→fallback):
  1. anthropic count_tokens API   (exact; needs ANTHROPIC_API_KEY)
  2. tiktoken cl100k_base         (proxy; ~±10% vs Anthropic tokenizer)
  3. char/4 estimate             (crude)

Usage:
  py bench/mcp_tax.py --name codegraph          # look up in ~/.claude.json
  py bench/mcp_tax.py --cmd "codegraph serve --mcp"
  py bench/mcp_tax.py --all                      # every server in ~/.claude.json

Not a vibe check — real numbers. (CLI/hook/proxy tools pay 0 here by construction.)
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, threading, time

CLAUDE_JSON = os.path.expanduser(r"~\.claude.json")


def load_roster() -> dict:
    """name -> {command,args,env} across global + per-project mcpServers."""
    out = {}
    try:
        d = json.load(open(CLAUDE_JSON, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] cannot read {CLAUDE_JSON}: {e}", file=sys.stderr)
        return out
    def collect(ms):
        for k, v in (ms or {}).items():
            if k not in out and v.get("command"):
                out[k] = v
    collect(d.get("mcpServers"))
    for pv in (d.get("projects") or {}).values():
        collect((pv or {}).get("mcpServers"))
    return out


def list_tools(command: str, args: list[str], env: dict | None, timeout: float = 60.0) -> list[dict]:
    """Minimal MCP stdio client: initialize → initialized → tools/list."""
    exe = shutil.which(command) or command
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        [exe, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, env=full_env, text=True, encoding="utf-8",
        bufsize=1,
    )
    tools: list[dict] = []
    done = threading.Event()

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n"); proc.stdin.flush()

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("id") == 1 and "result" in msg:          # initialize ok
                send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            elif msg.get("id") == 2:                              # tools/list reply
                tools.extend((msg.get("result") or {}).get("tools", []))
                done.set(); return

    t = threading.Thread(target=reader, daemon=True); t.start()
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "mcp-tax", "version": "0.1"}}})
    done.wait(timeout)
    try: proc.terminate()
    except Exception: pass
    return tools


def make_counter():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic
            c = anthropic.Anthropic()
            def count(tools):
                r = c.messages.count_tokens(model="claude-opus-4-8", tools=tools,
                                            messages=[{"role": "user", "content": "x"}])
                return r.input_tokens, "anthropic-api"
            return count
        except Exception:
            pass
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        def count(tools):
            return len(enc.encode(json.dumps(tools))), "tiktoken-cl100k(proxy)"
        return count
    except Exception:
        def count(tools):
            return len(json.dumps(tools)) // 4, "char/4(crude)"
        return count


def to_anthropic(tools: list[dict]) -> list[dict]:
    return [{"name": t.get("name", ""), "description": t.get("description", ""),
             "input_schema": t.get("inputSchema", t.get("input_schema", {}))} for t in tools]


def measure(name, command, args, env, counter):
    tools = list_tools(command, args, env)
    if not tools:
        print(f"  {name:<22} — NO TOOLS (spawn/handshake failed or 0 tools)")
        return None
    at = to_anthropic(tools)
    total, method = counter(at)
    per = []
    for t in at:
        tk, _ = counter([t])
        per.append((tk, t["name"]))
    per.sort(reverse=True)
    print(f"\n### {name}  —  {len(tools)} tools  =  {total} tok/session  [{method}]")
    print(f"    avg {total // max(len(tools),1)} tok/tool · top:")
    for tk, nm in per[:5]:
        print(f"      {tk:>6}  {nm}")
    return {"name": name, "tools": len(tools), "total": total, "method": method,
            "per_tool": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name"); ap.add_argument("--cmd"); ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    counter = make_counter()
    roster = load_roster()
    results = []
    if a.cmd:
        parts = a.cmd.split()
        results.append(measure(parts[0], parts[0], parts[1:], None, counter))
    elif a.all:
        for nm, spec in roster.items():
            results.append(measure(nm, spec["command"], spec.get("args", []), spec.get("env"), counter))
    elif a.name:
        spec = roster.get(a.name)
        if not spec: sys.exit(f"'{a.name}' not in roster: {list(roster)}")
        results.append(measure(a.name, spec["command"], spec.get("args", []), spec.get("env"), counter))
    else:
        ap.print_help(); return
    ok = [r for r in results if r]
    if len(ok) > 1:
        grand = sum(r["total"] for r in ok)
        print(f"\n=== TOTAL static tax: {grand} tok/session across {len(ok)} servers ===")
        for r in sorted(ok, key=lambda x: -x["total"]):
            print(f"    {r['total']:>7}  {r['name']} ({r['tools']} tools)")


if __name__ == "__main__":
    main()
