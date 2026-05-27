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

import differentiable_training as dt


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
        # IMPORTANT: format as fixed-point (.8f) not repr() — Sutra's
        # parser does not accept scientific notation like 4.5e-05, and
        # trained Adam weights can be small enough that repr() switches
        # to scientific (verified 2026-05-27 on the K=2 k=2 smoke). 8
        # decimal places gives precision ~5e-9, well below the 1e-4
        # round-trip threshold; far more than enough for bake-back.
        def fp(v: float) -> str:
            return f"{v:.8f}"
        for ci in range(K):
            v_names = []
            t_names = []
            for ri in range(k):
                idx = ci * k + ri
                values_csv = ", ".join(
                    f"({fp(v)})" for v in baked_vectors[idx]
                )
                v_names.append(f"vector_literal({values_csv})")
                t_names.append(f"({fp(baked_scalars[idx])})")
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


def build_data(K: int, k_rank: int, per_class: int, device, dtype, seed: int):
    """Load embeddings for K categories; build (data, prototype anchors).

    - data: list of (x_tensor, class_index) pairs, len = K * per_class.
    - protos: K*k tensors of shape (dim,) each, requires_grad-able.
      For k_rank=1 the proto is exactly embed(category-name).
      For k_rank>1 the first anchor is embed(category-name) and the
      remaining are eps-perturbations of it. (k-means cluster-centroid
      anchors are a queued follow-up — explicitly NOT done here.)
    """
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    cats = dt.CATEGORIES[:K]
    cat_names = [name for name, _ in cats]
    words = [w for _, ws in cats for w in ws]
    needed = sorted(set(words + cat_names))
    vecs_cpu = dt.embed_all(needed, cache_path=cache)
    dim = next(iter(vecs_cpu.values())).shape[0]

    def to_dev(t):
        return t.to(device=device, dtype=dtype).detach()

    g = torch.Generator(device="cpu").manual_seed(seed)

    protos = []  # length K * k_rank
    for ci, name in enumerate(cat_names):
        anchor = to_dev(vecs_cpu[name])
        protos.append(anchor.clone())
        for _ in range(k_rank - 1):
            noise = torch.randn(dim, generator=g, dtype=dtype).to(device) * 0.05
            protos.append((anchor + noise).clone())

    data = []
    for ci, (_, ws) in enumerate(cats):
        for w in ws[:per_class]:
            if w in cat_names:
                continue
            data.append((to_dev(vecs_cpu[w]), ci))
    return data, protos, dim


def logits_per_sample_factory(mod, K, k):
    """Returns single(x, protos, scalars) -> [K] using the emitted rule_i
    functions. protos: list len K*k of (dim,) tensors. scalars: list len
    K*k of 0-d tensors. The rule_i signature takes (x, all_vectors,
    all_scalars) per the .su generator."""
    rule_fns = [getattr(mod, f"rule_{i}") for i in range(K)]

    def single(x, protos, scalars):
        # All rules consume the same flat (protos..., scalars...) tail
        # because the .su generator's `other_arg` passes every class's
        # params to every rule body.
        tail = list(protos) + list(scalars)
        return torch.stack([fn(x, *tail) for fn in rule_fns])

    return single


def margin_per_sample(logits, y):
    """logit_correct - max logit_wrong, scalar."""
    K = logits.shape[-1]
    correct = logits[..., y]
    mask = torch.ones(K, dtype=torch.bool, device=logits.device)
    mask[y] = False
    wrong_max = logits[..., mask].max()
    return float(correct - wrong_max)


def run_one(K, k_rank, per_class, epochs, lr, seed, verbose=True):
    """Compile + train + bake + round-trip + measure. Returns a dict
    with the measured numbers."""
    mod = _compile(_su(K, k_rank, None, None), f"param_K{K}_k{k_rank}")
    runtime = mod._VSA
    device, dtype = runtime.device, runtime.dtype

    data, protos_init, dim = build_data(K, k_rank, per_class, device, dtype, seed)
    if verbose:
        print(
            f"  build_data: K={K} k_rank={k_rank} per_class={per_class} "
            f"N={len(data)} dim={dim} seed={seed}"
        )

    # --- Equivalence guard at init: vmap vs per-sample logits ---
    single = logits_per_sample_factory(mod, K, k_rank)
    init_protos = [p.clone() for p in protos_init]
    init_scalars = [
        torch.tensor(1.0, dtype=dtype, device=device) for _ in range(K * k_rank)
    ]
    with torch.no_grad():
        lp = torch.stack(
            [single(x, init_protos, init_scalars) for x, _ in data]
        )
        # vmap captures (init_protos, init_scalars) by closure; only x batches.
        vlogits = torch.vmap(lambda xx: single(xx, init_protos, init_scalars))
        X = torch.stack([x for x, _ in data])
        lb = vlogits(X)
        dmax = float((lp - lb).abs().max())
    if dmax >= 1e-4:
        raise SystemExit(
            f"EQUIVALENCE GUARD FAILED at init: vmap vs per-sample max|Δ|"
            f"={dmax:.2e}. Abort -- batched != per-sample compiled computation."
        )
    if verbose:
        print(f"  equivalence guard PASSED (max|Δ|={dmax:.2e} < 1e-4)")

    # --- Baseline margin (T_init=1, anchor protos) ---
    with torch.no_grad():
        baseline_margin = statistics.mean(
            margin_per_sample(single(x, init_protos, init_scalars), y)
            for x, y in data
        )

    # --- Train: all K*k vectors + K*k scalars ---
    torch.manual_seed(seed)
    protos = [p.clone().requires_grad_(True) for p in protos_init]
    scalars = [
        torch.tensor(1.0, dtype=dtype, device=device, requires_grad=True)
        for _ in range(K * k_rank)
    ]
    opt = torch.optim.Adam(protos + scalars, lr=lr)

    for _ in range(epochs):
        opt.zero_grad()
        losses = []
        for x, y in data:
            logits = single(x, protos, scalars)
            losses.append(
                F.cross_entropy(
                    (logits * 10.0).unsqueeze(0),
                    torch.tensor([y], device=device),
                )
            )
        loss = torch.stack(losses).mean()
        loss.backward()
        opt.step()

    # --- Trained margin ---
    with torch.no_grad():
        trained_margin = statistics.mean(
            margin_per_sample(single(x, protos, scalars), y) for x, y in data
        )

    # --- Bake back: each v_ci_ri -> vector_literal(...), each T_ci_ri -> literal ---
    baked_vecs = [
        [round(float(v), 6) for v in p.detach().cpu().tolist()] for p in protos
    ]
    baked_scalars = [round(float(t.detach()), 6) for t in scalars]
    baked = _compile(
        _su(K, k_rank, baked_vecs, baked_scalars),
        f"baked_K{K}_k{k_rank}_seed{seed}",
    )

    # --- Round-trip check: baked logits vs trained logits, per-sample ---
    baked_rules = [getattr(baked, f"rule_{i}") for i in range(K)]

    def baked_single(x):
        return torch.stack([fn(x) for fn in baked_rules])

    with torch.no_grad():
        max_rt = 0.0
        for x, _ in data:
            lp_ = single(x, protos, scalars)
            lb_ = baked_single(x)
            max_rt = max(max_rt, float((lp_ - lb_).abs().max()))
    rt_ok = max_rt < 1e-4

    return {
        "seed": seed,
        "K": K, "k_rank": k_rank, "per_class": per_class,
        "epochs": epochs, "lr": lr,
        "N": len(data), "dim": dim,
        "equiv_guard_dmax": dmax,
        "baseline_margin": baseline_margin,
        "trained_margin": trained_margin,
        "round_trip_max_delta": max_rt,
        "round_trip_ok": rt_ok,
    }


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

    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    t0 = time.time()
    results = []
    print(
        f"rank-k is_X training: K={a.K_classes} k={a.k_rank} "
        f"per_class={a.per_class} epochs={a.epochs} seeds={seeds} lr={a.lr}"
    )
    for s in seeds:
        print(f"--- seed {s} ---")
        r = run_one(
            K=a.K_classes,
            k_rank=a.k_rank,
            per_class=a.per_class,
            epochs=a.epochs,
            lr=a.lr,
            seed=s,
        )
        print(
            f"  seed {s}: baseline margin = {r['baseline_margin']:+.4f}  ->  "
            f"trained margin = {r['trained_margin']:+.4f}  "
            f"round-trip max|Δ|={r['round_trip_max_delta']:.2e}  "
            f"round_trip_ok={r['round_trip_ok']}"
        )
        results.append(r)

    bm = [r["baseline_margin"] for r in results]
    tm = [r["trained_margin"] for r in results]

    def ms(v):
        return (
            statistics.mean(v),
            statistics.stdev(v) if len(v) > 1 else 0.0,
        )

    bmean, bsd = ms(bm)
    tmean, tsd = ms(tm)
    print(
        f"\n=== RANK-{a.k_rank} is_X MEASURED (K={a.K_classes}, "
        f"per_class={a.per_class}, epochs={a.epochs}, n={len(seeds)}) "
        f"in {time.time() - t0:.1f}s ==="
    )
    print(f"baseline margin (T_init=1, embed-anchor protos): "
          f"{bmean:+.4f} ± {bsd:.4f}")
    print(f"trained  margin (joint Adam over K*k vectors + K*k scalars): "
          f"{tmean:+.4f} ± {tsd:.4f}")
    if abs(bmean) > 1e-9:
        print(f"trained / baseline margin ratio: {tmean / bmean:+.2f}x")
    print(
        f"round_trip_ok(all): {all(r['round_trip_ok'] for r in results)}  "
        f"max|Δ| over all seeds: "
        f"{max(r['round_trip_max_delta'] for r in results):.2e}"
    )


if __name__ == "__main__":
    main()
