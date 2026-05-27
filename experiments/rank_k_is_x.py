"""Rank-k is_X experiment — first matrix-valued constrain-train target.

Generalizes Stage-B (rank-1 = one prototype + one scalar gain per class)
to rank-k (k prototypes + k scalar gains per class). Each class X gets
k "modes" — useful when the category has multiple sub-clusters in
embedding space (e.g., "vehicle" = land vehicles ∪ water vehicles ∪
air vehicles).

Mechanism:
    is_X(x) = (T1*sim(x,v1)) || (T2*sim(x,v2)) || ... || (Tk*sim(x,vk))

where `||` is fuzzy OR (Lagrange poly on {-1,0,+1}^2). For K-class
classification the per-class rule gates against other classes' is_X
via Kleene AND/NOT, matching Stage-B's shape.

Trained parameters per class: k prototype vectors + k scalar gains.
Across K classes: K*k vectors + K*k scalars. All bake back via
vector_literal(...) (shipped 164e499d) + numeric literals.

Equivalence guard (per agenda integrity surface): torch.vmap batched
logits MUST agree with per-sample logits within 1e-4 before training
begins; otherwise the run aborts.

Bake-back round-trip: trained vectors emitted as vector_literal(...)
calls in baked .su (no vector/number params); recompile via the real
PyTorch codegen; assert max-logit Δ < 1e-4 vs the param-form model.

Metric: logit MARGIN (correct - max wrong) at rank-1 baseline vs at
rank-k trained, with prototypes initialized from embed(category-word)
anchors (extra anchors are k-means cluster centroids of the class's
words if k > 1; for now, additional anchors fall back to nudged
copies of the category-word embedding for rank-k > 1).

STATUS (2026-05-26): scaffold landed; smoke-compile-test verifies the
.su generator + codegen pipeline produces parseable Python. Training
+ measurement deliberately NOT executed this commit because
bu7o9mqxu (the equality-cosine K=5 n=3 measurement) holds the GPU.
The training run is the next work-loop tick.

Usage (when GPU is free):
    py experiments/rank_k_is_x.py [--k K_RANK] [--K NUM_CLASSES]
        [--per-class N] [--epochs E] [--seeds 0,1,2] [--lr LR]
    py experiments/rank_k_is_x.py --smoke   # compile-only sanity check
"""
from __future__ import annotations

import argparse
import io
import os
import statistics
import sys
import time
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch
import torch.nn.functional as F

from sutra_compiler.validator import validate_file
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch


def _rank_k_or(k: int, t_names: list[str], v_names: list[str]) -> str:
    """Generate a chained fuzzy-OR expression for rank-k is_X:
        (t1*sim(x,v1)) || (t2*sim(x,v2)) || ... || (tk*sim(x,vk))
    `t_names[i]` and `v_names[i]` may be either a param identifier or
    a literal-bake-back form (numeric literal or vector_literal call)."""
    terms = [f"({t_names[i]} * similarity(x, {v_names[i]}))" for i in range(k)]
    expr = terms[0]
    for term in terms[1:]:
        expr = f"({expr} || {term})"
    return expr


def _su(K: int, k: int, baked_vectors: list[list[float]] | None,
        baked_scalars: list[float] | None) -> str:
    """Generate the K-class rank-k is_X classifier .su. If baked_vectors
    + baked_scalars are None: full param form (everything trainable).
    Else: the trained values inline as vector_literal(...) / numeric
    literals; param signatures drop accordingly."""
    if baked_vectors is None:
        # PARAM FORM: vector and scalar params per (class, rank).
        per_class_param_names = []
        per_class_t_names = []
        per_class_v_names = []
        for ci in range(K):
            t_names = [f"T_{ci}_{i}" for i in range(k)]
            v_names = [f"v_{ci}_{i}" for i in range(k)]
            per_class_param_names.extend(
                [f"vector {n}" for n in v_names]
                + [f"number {n}" for n in t_names]
            )
            per_class_t_names.append(t_names)
            per_class_v_names.append(v_names)
        sig = "vector x, " + ", ".join(per_class_param_names)
    else:
        assert len(baked_vectors) == K * k
        assert len(baked_scalars) == K * k
        per_class_t_names = []
        per_class_v_names = []
        for ci in range(K):
            v_names = []
            t_names = []
            for ri in range(k):
                idx = ci * k + ri
                values_csv = ", ".join(f"({v!r})" for v in baked_vectors[idx])
                v_names.append(f"vector_literal({values_csv})")
                t_names.append(f"({baked_scalars[idx]!r})")
            per_class_t_names.append(t_names)
            per_class_v_names.append(v_names)
        sig = "vector x"

    # is_X_i functions: rank-k fuzzy OR over (T_i_j * sim(x, v_i_j))
    is_funcs = []
    for ci in range(K):
        body = _rank_k_or(k, per_class_t_names[ci], per_class_v_names[ci])
        is_funcs.append(
            f"function fuzzy is_class_{ci}({sig}) {{ return {body}; }}\n"
        )

    # Per-class rule: is_class_i(x) AND NOT is_class_j(x) for j ≠ i.
    # Stage-B shape. For the param form this means the rule signature
    # needs all classes' vectors/scalars (every is_class_j is called).
    rule_funcs = []
    other_arg = ""
    if baked_vectors is None:
        # Forward every class's param list to is_class_j calls.
        all_vec_names = [v for cl in per_class_v_names for v in cl]
        all_t_names = [t for cl in per_class_t_names for t in cl]
        other_arg = ", " + ", ".join(all_vec_names + all_t_names)
    for ci in range(K):
        nots = " ".join(
            f"&& !(is_class_{cj}(x{other_arg}))"
            for cj in range(K)
            if cj != ci
        )
        rule_funcs.append(
            f"function fuzzy rule_{ci}({sig}) {{\n"
            f"    return is_class_{ci}(x{other_arg}) {nots};\n"
            f"}}\n"
        )

    src = (
        f"// Rank-{k} is_X classifier, K={K} classes "
        f"({'PARAM' if baked_vectors is None else 'BAKED'} form).\n"
        + "".join(is_funcs)
        + "\n"
        + "".join(rule_funcs)
        + "\nfunction string main() { return \"ok\"; }\n"
    )
    return src


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".rankk_{tag}.su")
    with open(path, "w", encoding="utf-8") as f:
        f.write(su_text)
    bag = validate_file(path)
    if getattr(bag, "errors", None):
        print(f"VALIDATION ERRORS ({tag}):")
        for d in bag:
            print(" ", d.format())
        raise SystemExit(1)
    src = open(path, encoding="utf-8").read()
    lx = Lexer(src, file=path)
    ast = Parser(
        lx.tokenize(), file=path, diagnostics=lx.diagnostics
    ).parse_module()
    py = translate_pytorch(
        ast, runtime_dim=768, runtime_seed=42, loop_max_iterations=50
    )
    m = types.ModuleType(f"_rankk_{tag}")
    m.__file__ = f"<rankk {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def smoke_compile_only(K: int = 2, k: int = 2):
    """Compile-only sanity check: K=2, k=2 .su compiles end-to-end and
    the emitted module exposes rule_0, rule_1, is_class_0, is_class_1.
    Does NOT execute training. Used to verify the harness wires without
    spending GPU time when bu7o9mqxu is in flight."""
    src = _su(K, k, baked_vectors=None, baked_scalars=None)
    print(f"smoke: generated .su for K={K} k={k} param form")
    print(f"  size: {len(src)} chars, {src.count(chr(10))} lines")
    m = _compile(src, f"smoke_K{K}_k{k}_param")
    expected = [f"rule_{i}" for i in range(K)] + [
        f"is_class_{i}" for i in range(K)
    ]
    missing = [n for n in expected if not hasattr(m, n)]
    if missing:
        raise SystemExit(f"smoke FAILED: missing emitted symbols {missing}")
    print(
        f"  PASS: emitted module has all expected symbols "
        f"({', '.join(expected)})"
    )

    # Also compile the BAKED form with synthetic small trained values,
    # to verify the bake-back .su path round-trips through the codegen.
    fake_vecs = [
        [0.1 + 0.01 * (ci * k + ri) for _ in range(768)]
        for ci in range(K)
        for ri in range(k)
    ]
    fake_scalars = [1.0 + 0.1 * i for i in range(K * k)]
    baked_src = _su(K, k, baked_vectors=fake_vecs, baked_scalars=fake_scalars)
    print(
        f"smoke: generated .su for K={K} k={k} BAKED form "
        f"({len(baked_src)} chars, {baked_src.count(chr(10))} lines)"
    )
    bm = _compile(baked_src, f"smoke_K{K}_k{k}_baked")
    bmissing = [n for n in expected if not hasattr(bm, n)]
    if bmissing:
        raise SystemExit(
            f"smoke (baked) FAILED: missing emitted symbols {bmissing}"
        )
    print(f"  PASS: baked form emits the same symbols; vector_literal round-trips through codegen")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="compile-only sanity check (no training, no GPU)",
    )
    ap.add_argument("--k", dest="k_rank", type=int, default=2)
    ap.add_argument("--K", dest="K_classes", type=int, default=3)
    ap.add_argument("--per-class", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--lr", type=float, default=0.05)
    a = ap.parse_args()

    if a.smoke:
        smoke_compile_only(K=a.K_classes, k=a.k_rank)
        return

    # Full training path -- NOT YET IMPLEMENTED in this scaffold commit.
    # See queue.md #2 PRIORITY for the full plan: vmap-batched logits
    # with equivalence guard, joint Adam over K*k vectors + K*k scalars,
    # bake-back via vector_literal + scalar literals, round-trip
    # recompile, rank-1 vs rank-k margin sweep.
    print(
        "training path not yet implemented; rerun with --smoke for the "
        "compile-only sanity check. The training scaffold lands in a "
        "follow-up commit once the bu7o9mqxu GPU is free."
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
