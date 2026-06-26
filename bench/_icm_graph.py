"""Approach A — embedding-graph on ICM (the low-token wiki/synthesis layer).

Reads ICM memories.db, reuses the embeddings ICM already computed (768-dim
float32 blobs) to derive a similarity graph with ZERO LLM tokens, clusters it,
finds god-nodes, and (dry-run) shows how cluster summaries write BACK into ICM.

Bench is honest about scale: with a tiny corpus this proves MECHANISM + edge
COHERENCE (do embedding edges connect genuinely-related memories?), not
synthesis-quality (which needs a large corpus + multi-hop queries — gated on
ICM corpus growth via adopt-all/ECC capture).
"""
import sqlite3, os, struct, time, math, json, random

DB = os.path.join(os.environ["APPDATA"], "icm", "icm", "data", "memories.db")
KNN = 3          # edges per node
EDGE_MIN = 0.30  # cosine floor for an edge
CLUS_MIN = 0.45  # cosine floor for same-cluster (union-find)


def load():
    con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    rows = con.execute(
        "SELECT id, topic, summary, keywords, importance, related_ids, embedding "
        "FROM memories").fetchall()
    con.close()
    mem = []
    for id_, topic, summary, kw, imp, rel, emb in rows:
        n = len(emb) // 4
        vec = list(struct.unpack(f"<{n}f", emb))
        # parse keywords (json list or comma string)
        try:
            kws = json.loads(kw) if kw else []
            if not isinstance(kws, list): kws = [str(kws)]
        except Exception:
            kws = [t.strip() for t in (kw or "").split(",") if t.strip()]
        mem.append(dict(id=id_, topic=topic or "", summary=summary or "",
                        kws=set(k.lower() for k in kws), imp=imp or "",
                        rel=rel or "", vec=vec))
    return mem


def cos(a, b):
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return d / (na * nb) if na and nb else 0.0


def main():
    t0 = time.time()
    mem = load()
    n = len(mem)
    print(f"ICM corpus: {n} memories, dim={len(mem[0]['vec']) if mem else 0}")
    if n < 2:
        print("too few memories to graph."); return

    # similarity matrix (pure compute, 0 LLM tokens)
    S = [[cos(mem[i]["vec"], mem[j]["vec"]) if i != j else 1.0
          for j in range(n)] for i in range(n)]

    # kNN edges
    edges = []
    for i in range(n):
        nb = sorted(((S[i][j], j) for j in range(n) if j != i), reverse=True)[:KNN]
        for s, j in nb:
            if s >= EDGE_MIN and i < j:
                edges.append((i, j, s))
    edges = sorted(set((min(i, j), max(i, j), round(s, 3)) for i, j, s in edges),
                   key=lambda e: -e[2])

    # clusters: union-find on edges >= CLUS_MIN
    par = list(range(n))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for i, j, s in edges:
        if s >= CLUS_MIN: par[find(i)] = find(j)
    clus = {}
    for i in range(n): clus.setdefault(find(i), []).append(i)

    # god-node = max centrality (sum of similarities to others)
    cent = [sum(S[i][j] for j in range(n) if j != i) for i in range(n)]
    god = max(range(n), key=lambda i: cent[i])

    build_ms = (time.time() - t0) * 1000

    # ---- BENCH METRICS ----
    print(f"\n=== BENCH (init LLM tokens = 0, build = {build_ms:.0f} ms) ===")

    # M1 edge coherence: do edges connect memories sharing topic/keyword?
    def shares(a, b):
        return (mem[a]["topic"] and mem[a]["topic"] == mem[b]["topic"]) or \
               bool(mem[a]["kws"] & mem[b]["kws"])
    coh = sum(1 for i, j, _ in edges if shares(i, j)) / len(edges) if edges else 0
    # random-pair baseline
    random.seed(1)
    pairs = [(random.randrange(n), random.randrange(n)) for _ in range(200)]
    base = sum(1 for a, b in pairs if a != b and shares(a, b)) / \
           max(1, sum(1 for a, b in pairs if a != b))
    print(f"M1 edge coherence (share topic/kw): graph={coh:.0%}  random={base:.0%}  "
          f"lift={coh - base:+.0%}")

    # M2 cluster separation: intra vs inter mean cosine
    intra = [S[i][j] for cl in clus.values() for i in cl for j in cl if i < j]
    inter = [S[i][j] for i in range(n) for j in range(i + 1, n)
             if find(i) != find(j)]
    mi = sum(intra) / len(intra) if intra else 0
    mo = sum(inter) / len(inter) if inter else 0
    print(f"M2 cluster separation: intra={mi:.3f}  inter={mo:.3f}  gap={mi - mo:+.3f}")
    print(f"   clusters={len(clus)}  edges={len(edges)}")

    # ---- STRUCTURE ----
    print("\n=== GRAPH ===")
    for k, members in sorted(clus.items(), key=lambda kv: -len(kv[1])):
        print(f"\ncluster ({len(members)}):")
        for i in members:
            tag = " <god>" if i == god else ""
            print(f"   [{mem[i]['imp']:>6}] {mem[i]['topic'][:48]}{tag}")
    print(f"\ngod-node = central memory: {mem[god]['topic'][:60]}")
    print("top edges:")
    for i, j, s in edges[:6]:
        print(f"   {s:.2f}  {mem[i]['topic'][:28]} -- {mem[j]['topic'][:28]}")

    # ---- SAVE-BACK to ICM (dry-run) ----
    print("\n=== SAVE-BACK demo (dry-run) ===")
    big = max(clus.values(), key=len)
    topics = "; ".join(mem[i]["topic"][:30] for i in big[:4])
    payload = f"graph-cluster[{len(big)}]: {topics}"
    print("would run:")
    print(f'  icm store -t graph-synthesis -i medium '
          f'-k "graph,cluster" -c "{payload}"')
    print("(closes loop: graph synthesis -> recallable ICM memory)")

    if n < 15:
        print("\n[!] CAVEAT: n=%d too small for synthesis-vs-flat-recall bench." % n)
        print("    Mechanism + coherence proven. Quality-bench gated on corpus")
        print("    growth (adopt-all ECC observe-capture -> richer ICM).")


if __name__ == "__main__":
    main()
