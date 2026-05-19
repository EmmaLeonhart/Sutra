"""§3.6 — REAL compiled-graph training (Stage A).

Unlike differentiable_training.py (a hand-reimplementation proxy),
this compiles an actual `.su` fuzzy-rule program via the **PyTorch
codegen** and backprops the learnable prototypes through the
*emitted* graph. The per-class rule

    rule_i = similarity(x, p_i) && !similarity(x, p_j1) && ...

is computed by the compiler's output (`_VSA.similarity` + the
emitted Lagrange-Kleene AND/NOT polynomials). The harness only
stacks the K compiled rule scores -> softmax -> cross-entropy and
runs Adam; the rule graph itself is the compiler's, untouched by
training. Numbers printed are measurements, whatever they are.

The `.su` compiles ONCE (not per sample/epoch/seed). The default
per-sample path calls the emitted rule() N×K times/epoch in a
Python loop — correct but dominated by interpreter overhead, not
the compiled math. `--batched` torch.vmap's the SAME emitted
rule() over the N batch (a transform, not a reimplementation) and
asserts batched logits == per-sample logits within fp tolerance
before training — so the speedup is provably the identical
compiled computation, not a faked shortcut.

Usage:
  py experiments/differentiable_training_compiled.py [--k K]
     [--per-class N] [--epochs E] [--seeds S0,S1,...] [--lr LR]
"""
from __future__ import annotations

import argparse, os, sys, time, types, statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
HERE = os.path.dirname(os.path.abspath(__file__))

import torch
import torch.nn.functional as F

from sutra_compiler.validator import validate_file
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch

import differentiable_training as dt  # reuse CATEGORIES + embed cache


def gen_rule_su(k: int) -> str:
    """A real `.su`: per-class rule = sim(x,own) && !sim(x,o_j)…"""
    others = " ".join(f"vector o{j}," for j in range(k - 1))
    nots = " ".join(f"&& !similarity(x, o{j})" for j in range(k - 1))
    return (
        "// Generated fuzzy-rule classifier (Stage A — real compiled graph).\n"
        f"function fuzzy rule(vector x, vector own, {others.rstrip(',')}) {{\n"
        f"    return similarity(x, own) {nots};\n"
        "}\n\n"
        "function string main() { return \"ok\"; }\n"
    )


def compile_rule(k: int):
    su = gen_rule_su(k)
    path = os.path.join(HERE, ".stageA_rule.su")
    open(path, "w", encoding="utf-8").write(su)
    bag = validate_file(path)
    if getattr(bag, "errors", None):
        print("VALIDATION ERRORS in generated .su:")
        for d in bag:
            print(" ", d.format())
        raise SystemExit(1)
    src = open(path, encoding="utf-8").read()
    lx = Lexer(src, file=path)
    toks = lx.tokenize()
    mod_ast = Parser(toks, file=path, diagnostics=lx.diagnostics).parse_module()
    py = translate_pytorch(mod_ast, runtime_dim=768, runtime_seed=42,
                           loop_max_iterations=50)
    assert "def rule(" in py, "emitted module missing rule()"
    assert "float(_torch.dot" not in py.split("def similarity", 1)[1][:400], \
        "similarity still float()-collapses — Stage A0 not in effect"
    m = types.ModuleType("_stageA")
    m.__file__ = "<stageA rule>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m, py


def build_data(k, per_class):
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    cats = dt.CATEGORIES[:k]
    words = [w for _, ws in cats for w in ws]
    vecs = dt.embed_all(words, cache_path=cache)
    data = []
    for ci, (_, ws) in enumerate(cats):
        for w in ws[:per_class]:
            data.append((vecs[w], ci))
    dim = next(iter(vecs.values())).shape[0]
    return data, dim, k


def run(seed, mod, data, dim, k, epochs, lr, batched):
    torch.manual_seed(seed)
    protos = [(_p := torch.randn(dim, dtype=torch.float32)) / _p.norm()
              for _ in range(k)]
    protos = [p.clone().requires_grad_(True) for p in protos]
    opt = torch.optim.Adam(protos, lr=lr)

    # single(x) -> [K] : the per-class stack of the EMITTED compiled
    # rule(). The K loop is tiny (3–5); the expensive axis is N.
    def single(x):
        return torch.stack([
            mod.rule(x, protos[i], *[protos[j] for j in range(k) if j != i])
            for i in range(k)])

    X = torch.stack([x for x, _ in data])              # [N, dim]
    Y = torch.tensor([y for _, y in data])             # [N]

    if batched:
        # torch.vmap is a *transform*: it runs the SAME emitted rule()
        # ops with a batch axis, not a reimplementation. Collapses the
        # N Python-level calls into one vectorized pass; gradients
        # still flow to the prototypes through the emitted graph.
        vlogits = torch.vmap(single)
        # Integrity guard: the batched path MUST equal the per-sample
        # path on identical inputs/params, else it is not the same
        # compiled computation. One forward each (cheap, not training).
        with torch.no_grad():
            lp = torch.stack([single(x) for x, _ in data])  # [N,K]
            lb = vlogits(X)                                  # [N,K]
            dmax = float((lp - lb).abs().max())
        assert dmax < 1e-4, (
            f"batched != per-sample (max|Δ|={dmax:.2e}) — vmap path is "
            "NOT the identical compiled computation; refusing to fake")
        all_logits = lambda: vlogits(X)                      # noqa: E731
    else:
        all_logits = lambda: torch.stack([single(x)          # noqa: E731
                                          for x, _ in data])

    def acc():
        with torch.no_grad():
            return float((all_logits().argmax(1) == Y).float().mean())

    a0 = acc()
    g_seen = False
    for _ in range(epochs):
        opt.zero_grad()
        # mean-reduced CE over [N,K] vs [N] == mean of the per-sample
        # CE the per-sample path used: same loss, just not in a Python
        # comprehension.
        loss = F.cross_entropy(all_logits() * 10.0, Y)
        loss.backward()
        if not g_seen:
            g_seen = protos[0].grad is not None and float(protos[0].grad.norm()) > 0
        opt.step()
    return a0, acc(), float(loss.item()), g_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--seeds", default="0,1,2,3,4")
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--batched", action="store_true",
                    help="vmap the emitted rule() over the batch "
                         "(same compiled ops; equivalence-asserted)")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    mod, py = compile_rule(args.k)
    data, dim, k = build_data(args.k, args.per_class)
    print(f"compiled .su via PyTorch codegen ({len(py)} chars); "
          f"k={k} per_class={args.per_class} N={len(data)} dim={dim} "
          f"epochs={args.epochs} seeds={seeds} lr={args.lr} "
          f"mode={'batched(vmap)' if args.batched else 'per-sample'}")
    print("emitted rule() body:")
    print("  " + py.split("def rule(", 1)[1].split("\n\n")[0][:300])

    befores, afters = [], []
    t0 = time.time()
    for s in seeds:
        b, a, ls, gflow = run(s, mod, data, dim, k, args.epochs, args.lr,
                              args.batched)
        befores.append(b); afters.append(a)
        print(f"  seed {s}: acc {b:.3f} -> {a:.3f}  loss={ls:.4f}  "
              f"grads_through_emitted_graph={gflow}")
    bm = statistics.mean(befores)
    am = statistics.mean(afters)
    bs = statistics.stdev(befores) if len(befores) > 1 else 0.0
    as_ = statistics.stdev(afters) if len(afters) > 1 else 0.0
    chance = 1.0 / k
    print(f"\n=== MEASURED (real compiled graph) in {time.time()-t0:.1f}s ===")
    print(f"chance={chance:.3f}  before={bm*100:.2f}±{bs*100:.2f}%  "
          f"after={am*100:.2f}±{as_*100:.2f}%  (n={len(seeds)})")


if __name__ == "__main__":
    main()
