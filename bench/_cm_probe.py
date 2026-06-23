"""Probe context-mode's stdio MCP server: list tools + dump key input schemas.

Spawns `node server.bundle.mjs`, does the JSON-RPC handshake, prints every tool
name and the inputSchema for the lanes we want to A/B (ctx_execute_file,
ctx_index, ctx_search). No network; the server runs locally.
"""
import json, os, subprocess, sys

ENTRY = os.path.join(os.environ["APPDATA"], "npm", "node_modules",
                     "context-mode", "server.bundle.mjs")


def main() -> int:
    p = subprocess.Popen(["node", ENTRY], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", bufsize=1)

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def recv_until(_id):
        while True:
            line = p.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("id") == _id:
                return msg

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05",
                     "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}})
    init = recv_until(1)
    print("server:", (init or {}).get("result", {}).get("serverInfo"))
    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tl = recv_until(2)
    tools = (tl or {}).get("result", {}).get("tools", [])
    print(f"\n{len(tools)} tools:")
    for t in tools:
        print(" ", t["name"])
    want = {"ctx_execute_file", "ctx_index", "ctx_search", "ctx_execute"}
    for t in tools:
        if t["name"] in want:
            print(f"\n=== {t['name']} ===")
            print("desc:", (t.get("description") or "")[:200])
            props = t.get("inputSchema", {}).get("properties", {})
            print("params:", {k: v.get("type") for k, v in props.items()})
            print("required:", t.get("inputSchema", {}).get("required"))
    p.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
