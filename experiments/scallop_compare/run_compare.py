"""Multi-system neuro-symbolic comparison on a shared 1-hop KG query.

Why this experiment exists:
    Sutra, Scallop, DeepProbLog, and TorchHD all live in the
    broader neuro-symbolic landscape, but they solve different
    problems. The fair comparison is *not* "which is fastest" but
    rather "what does each express, and on the intersection of
    what they all can do, how does each perform?"

    This script runs the *intersection* benchmark: a 1-hop
    relational query over a small knowledge graph that all four
    systems can answer. It reports per-query latency for each.
    The qualitative strengths/weaknesses matrix lives in the
    paper (§2.2) — that's where we explain *why* the systems
    differ and *what* tasks each is the right tool for.

    Result format intentionally focuses on what's expressible.
    Headline single-number "speedup" claims would misrepresent
    the comparison: Sutra is faster on this task because the KG
    is small and the encoding is one matmul; Scallop wins on
    larger KGs because its index scales; DeepProbLog wins on
    probabilistic queries because that's what it's built for.

Setup:
    A 6-fact KG (6 entities, 3 relations). 100 timed batches of
    6 queries each. Each system gets 10 warmup queries before
    timing begins.

Run (inside the docker container; see Dockerfile in this dir):
    python experiments/scallop_compare/run_compare.py

Outside the container, systems whose libraries aren't installed
SKIP gracefully. Sutra always runs (it's the host repo).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
N_QUERIES = 100
N_WARMUP = 10

# 6-fact KG: 6 entities, 3 relations. Kept small so Sutra's
# depth-2 nested binding stays under the §3.1.1 crosstalk floor.
ENTITIES = ["alice", "bob", "carol", "dave", "eve", "frank"]
RELATIONS = ["knows", "manages", "trusts"]
KG_TRIPLES = [
    ("alice", "knows", "bob"),
    ("bob", "manages", "carol"),
    ("carol", "trusts", "dave"),
    ("dave", "knows", "eve"),
    ("eve", "manages", "frank"),
    ("frank", "trusts", "alice"),
]
QUERIES = [(s, r) for s, r, _ in KG_TRIPLES]
EXPECTED = {(s, r): o for s, r, o in KG_TRIPLES}


# ---------------------------------------------------------------------
# Sutra
# ---------------------------------------------------------------------

def sutra_run() -> dict:
    sys.path.insert(0, str(REPO_ROOT / "sdk" / "sutra-compiler"))
    sys.path.insert(0, str(REPO_ROOT / "examples"))
    from _su_harness import compile_to_module

    mod = compile_to_module(str(REPO_ROOT / "examples" / "hello_world.su"))
    VSA = mod._VSA

    role_subj = {e: VSA.embed(f"role_subj_{e}") for e in ENTITIES}
    role_rel = {r: VSA.embed(f"role_rel_{r}") for r in RELATIONS}
    fillers = {e: VSA.embed(f"obj_{e}") for e in ENTITIES}

    kg = None
    for s, r, o in KG_TRIPLES:
        bound = VSA.bind(role_subj[s], VSA.bind(role_rel[r], fillers[o]))
        kg = bound if kg is None else VSA.bundle(kg, bound)

    is_torch = type(kg).__module__.startswith("torch")
    if is_torch:
        import torch
        codebook = torch.stack([fillers[e] for e in ENTITIES], dim=0)
        argmax = lambda x: int(torch.argmax(x))
    else:
        codebook = np.stack([fillers[e] for e in ENTITIES], axis=0)
        argmax = lambda x: int(np.argmax(x))

    def decode(s: str, r: str) -> str:
        recovered = VSA.unbind(role_rel[r], VSA.unbind(role_subj[s], kg))
        return ENTITIES[argmax(codebook @ recovered)]

    correct = sum(decode(s, r) == EXPECTED[(s, r)] for s, r in QUERIES)
    accuracy = correct / len(QUERIES)
    for _ in range(N_WARMUP):
        decode(QUERIES[0][0], QUERIES[0][1])
    t0 = time.monotonic_ns()
    for _ in range(N_QUERIES):
        for s, r in QUERIES:
            decode(s, r)
    per_query_us = (time.monotonic_ns() - t0) / 1e3 / (N_QUERIES * len(QUERIES))
    return {"accuracy": accuracy, "per_query_us": per_query_us}


# ---------------------------------------------------------------------
# Scallop
# ---------------------------------------------------------------------

def scallop_run() -> dict | None:
    try:
        import scallopy
    except ImportError:
        return None

    ctx = scallopy.ScallopContext(provenance="unit")
    ctx.add_relation("triple", (str, str, str))
    for s, r, o in KG_TRIPLES:
        ctx.add_facts("triple", [(s, r, o)])
    ctx.add_relation("ask", (str, str))
    ctx.add_rule('answer(O) :- ask(S, R), triple(S, R, O)')

    def decode(s: str, r: str) -> str:
        local = ctx.clone()
        local.add_facts("ask", [(s, r)])
        local.run()
        results = list(local.relation("answer"))
        return results[0][0] if results else ""

    correct = sum(decode(s, r) == EXPECTED[(s, r)] for s, r in QUERIES)
    accuracy = correct / len(QUERIES)
    for _ in range(N_WARMUP):
        decode(QUERIES[0][0], QUERIES[0][1])
    t0 = time.monotonic_ns()
    for _ in range(N_QUERIES):
        for s, r in QUERIES:
            decode(s, r)
    per_query_us = (time.monotonic_ns() - t0) / 1e3 / (N_QUERIES * len(QUERIES))
    return {"accuracy": accuracy, "per_query_us": per_query_us}


# ---------------------------------------------------------------------
# DeepProbLog
# ---------------------------------------------------------------------

def deepproblog_run() -> dict | None:
    """DeepProbLog runs on Prolog facts. We use plain ProbLog (the
    underlying engine) so we don't need to set up a neural network
    just to do exact lookup. Same KG, same queries."""
    try:
        from problog.program import PrologString
        from problog import get_evaluatable
    except ImportError:
        return None

    def decode(s: str, r: str) -> str:
        kg_str = "\n".join(f"triple({a}, {b}, {c})." for a, b, c in KG_TRIPLES)
        prog = f"""{kg_str}
answer({s}, {r}, O) :- triple({s}, {r}, O).
query(answer({s}, {r}, _))."""
        try:
            result = get_evaluatable().create_from(PrologString(prog)).evaluate()
            for q, _p in result.items():
                # answer(s, r, O) — last arg is the binding.
                if hasattr(q, "args"):
                    return str(q.args[-1])
            return ""
        except Exception:
            return ""

    correct = sum(decode(s, r) == EXPECTED[(s, r)] for s, r in QUERIES)
    accuracy = correct / len(QUERIES)
    for _ in range(N_WARMUP):
        decode(QUERIES[0][0], QUERIES[0][1])
    t0 = time.monotonic_ns()
    for _ in range(N_QUERIES):
        for s, r in QUERIES:
            decode(s, r)
    per_query_us = (time.monotonic_ns() - t0) / 1e3 / (N_QUERIES * len(QUERIES))
    return {"accuracy": accuracy, "per_query_us": per_query_us}


# ---------------------------------------------------------------------
# TorchHD
# ---------------------------------------------------------------------

def torchhd_run() -> dict | None:
    try:
        import torch
        import torchhd
    except ImportError:
        return None

    DIM = 768
    torch.manual_seed(42)
    role_subj = {e: torchhd.random(1, DIM, vsa="MAP") for e in ENTITIES}
    role_rel = {r: torchhd.random(1, DIM, vsa="MAP") for r in RELATIONS}
    fillers = {e: torchhd.random(1, DIM, vsa="MAP") for e in ENTITIES}
    codebook = torch.cat([fillers[e] for e in ENTITIES], dim=0)

    kg = None
    for s, r, o in KG_TRIPLES:
        bound = torchhd.bind(role_subj[s], torchhd.bind(role_rel[r], fillers[o]))
        kg = bound if kg is None else torchhd.bundle(kg, bound)

    def decode(s: str, r: str) -> str:
        recovered = torchhd.bind(kg, torchhd.bind(
            torchhd.inverse(role_subj[s]),
            torchhd.inverse(role_rel[r])))
        sims = torchhd.cosine_similarity(recovered, codebook)
        return ENTITIES[int(torch.argmax(sims))]

    correct = sum(decode(s, r) == EXPECTED[(s, r)] for s, r in QUERIES)
    accuracy = correct / len(QUERIES)
    for _ in range(N_WARMUP):
        decode(QUERIES[0][0], QUERIES[0][1])
    t0 = time.monotonic_ns()
    for _ in range(N_QUERIES):
        for s, r in QUERIES:
            decode(s, r)
    per_query_us = (time.monotonic_ns() - t0) / 1e3 / (N_QUERIES * len(QUERIES))
    return {"accuracy": accuracy, "per_query_us": per_query_us}


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("Multi-system neuro-symbolic comparison — 1-hop KG query")
    print(f"KG: {len(ENTITIES)} entities, {len(RELATIONS)} relations, "
          f"{len(KG_TRIPLES)} triples; {N_QUERIES} timed batches "
          f"of {len(QUERIES)} queries each")
    print("=" * 78)

    systems = {
        "Sutra": sutra_run,
        "Scallop": scallop_run,
        "DeepProbLog": deepproblog_run,
        "TorchHD": torchhd_run,
    }

    results = {}
    for name, runner in systems.items():
        print(f"\n[{name}]")
        try:
            r = runner()
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            r = {"error": f"{type(e).__name__}: {e}"}
        if r is None:
            print(f"  not installed — skipping (build the docker image to run all four).")
            results[name] = None
            continue
        results[name] = r
        if "error" in r:
            continue
        print(f"  accuracy: {r['accuracy']:.1%}")
        print(f"  per-query latency: {r['per_query_us']:.1f} us")

    out_path = Path(__file__).resolve().parent / "results.json"
    out_path.write_text(json.dumps({
        "kg_size": {"entities": len(ENTITIES),
                    "relations": len(RELATIONS),
                    "triples": len(KG_TRIPLES)},
        "n_queries": N_QUERIES,
        "systems": results,
    }, indent=2), encoding="utf-8")
    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
