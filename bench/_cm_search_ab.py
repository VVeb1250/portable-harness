"""A/B the context-mode LOSSLESS lane (ctx_index + ctx_search, FTS5 BM25) vs read-all.

Index a real doc once, then answer targeted questions by searching it. This lane
returns verbatim chunks (lossy digest is the other lane), so we measure BOTH
token savings AND recall: does the returned chunk contain the known answer span?
A search that saves tokens but drops the answer is not a win (anti-vibes, #5).

To separate "engine weak" from "my query phrasing", we run a matrix:
  NL      = naturalistic paraphrase questions (semantic gap to doc vocab)
  LEXICAL = queries using doc vocabulary (what an agent issues after a miss)
each at limit 3 and 5. BM25 is lexical (Porter stem + trigram), so the NL-vs-
LEXICAL gap is the real signal.

Source doc: context-mode README.md (94 KB real docs). Ground-truth = 8
(query, expected verbatim substring) pairs; substrings are verbatim in the doc.
"""
import os, sys, pathlib, tiktoken

sys.path.insert(0, os.path.dirname(__file__))
from _cm_ab import Server  # noqa: E402

ENC = tiktoken.get_encoding("cl100k_base")
DOC = pathlib.Path(__file__).parent / "out" / "cm" / "README.md"
SRC = "bench-cm-readme"


def tk(t: str) -> int:
    return len(ENC.encode(t, disallowed_special=()))


# (NL query, LEXICAL query, expected verbatim substring in returned chunk)
CASES = [
    ("copilot platform identifier environment variable", "CONTEXT_MODE_PLATFORM copilot", "CONTEXT_MODE_PLATFORM"),
    ("install cursor plugin on windows",                  "robocopy cursor plugin local",  "robocopy"),
    ("full text search knowledge base engine",            "FTS5 knowledge base BM25",       "FTS5"),
    ("authenticated CLI secrets not exposed",             "credential passthrough gh aws", "credential passthrough"),
    ("session memory snapshot size budget",               "priority-tiered XML snapshot",  "XML snapshot"),
    ("codex hooks config file location",                  "CODEX_HOME hooks.json",         "hooks.json"),
    ("which platforms do not support hooks",              "Antigravity Zed do not support hooks", "Antigravity"),
    ("codex pretooluse deny permission decision",         "permissionDecision deny PreToolUse",   "permissionDecision"),
]


def run_cell(doc, queries_expected, limit):
    """Fresh server = fresh session (avoids session-level dedup re-query artifact).
    index -> search each query -> purge. Returns (hits, total_tok, detail)."""
    s = Server()
    s.call("ctx_index", {"content": doc, "source": SRC})
    hits, total, detail = 0, 0, []
    for q, exp in queries_expected:
        res = s.call("ctx_search", {"queries": [q], "limit": limit, "source": SRC})
        t = tk(res)
        hit = exp.lower() in res.lower()
        hits += hit
        total += t
        detail.append((exp, t, hit))
    s.call("ctx_purge", {"confirm": True, "scope": "project"})
    s.close()
    return hits, total, detail


def main():
    if not DOC.exists():
        print("missing", DOC); return
    doc = DOC.read_text(encoding="utf-8")
    raw = tk(doc)
    n = len(CASES)
    nl = [(q_nl, exp) for q_nl, _, exp in CASES]
    lex = [(q_lx, exp) for _, q_lx, exp in CASES]
    print(f"raw doc (read-all) = {raw} tok  ({n} sections indexed)\n")
    print(f"{'lane':<10}{'limit':>6}{'recall':>9}{'avg/q':>8}{'savings/q':>11}{'basket':>8}")
    cells = {}
    for label, qs in (("NL", nl), ("LEXICAL", lex)):
        for limit in (3, 5):
            h, tot, det = run_cell(doc, qs, limit)
            avg = tot / n
            print(f"{label:<10}{limit:>6}{h}/{n:>7}{avg:>8.0f}{100*(1-avg/raw):>10.1f}%{tot:>8}")
            cells[(label, limit)] = det

    print("\n--- per-case hit @limit5 (expected span in returned chunk) ---")
    print(f"{'expected span':<26}{'NL':>5}{'LEX':>5}")
    for i, (_, _, exp) in enumerate(CASES):
        print(f"{exp[:24]:<26}{'Y' if cells[('NL',5)][i][2] else 'N':>5}{'Y' if cells[('LEXICAL',5)][i][2] else 'N':>5}")


if __name__ == "__main__":
    main()
