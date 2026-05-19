"""Stage B — weighted Equals: a learnable scalar gain `w` trained
THROUGH the compiled graph, then emitted back into `.su` source as
a numeric literal, with a recompile round-trip check.

Mechanism (de-risked cron fire 8): a `.su` rule
  rule(x, own, o..., number w) = (w*sim(x,own)) && !(w*sim(x,o)) ...
compiles via the PyTorch codegen to `(w * _VSA.similarity(...))`;
gradients reach `w` (verified). After training, the trained scalar
w* is substituted as a LITERAL into a fresh `.su` (no w param):
the trained model becomes recompilable, legible Sutra source.
Round-trip: recompile the baked `.su`, feed the same trained
prototypes, confirm identical logits/accuracy.

NO FAKING — numbers are measurements. Anisotropy framing: a learned
gain rescales the compressed cosine dynamic range of anisotropic
frozen embeddings.

Usage: py experiments/differentiable_training_weighted.py
       [--k K] [--per-class N] [--epochs E] [--seeds S0,S1,..]
"""
from __future__ import annotations
import argparse, io, os, sys, time, types, statistics

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


def _su(k: int, w_literal: float | None) -> str:
    """Generate the weighted-rule .su. If w_literal is None, `w` is a
    `number` param (trainable). Else the trained value is inlined as a
    literal and the param is dropped — the trained model AS source."""
    oth = [f"o{j}" for j in range(k - 1)]
    if w_literal is None:
        sig = "vector x, vector own, " + ", ".join(
            f"vector {o}" for o in oth) + ", number w"
        g = "w"
    else:
        sig = "vector x, vector own, " + ", ".join(f"vector {o}" for o in oth)
        g = f"({w_literal!r})"
    nots = " ".join(f"&& !({g} * similarity(x, {o}))" for o in oth)
    return (f"// Stage B weighted rule (w {'param' if w_literal is None else 'BAKED literal'}).\n"
            f"function fuzzy rule({sig}) {{\n"
            f"    return ({g} * similarity(x, own)) {nots};\n"
            f"}}\n\nfunction string main() {{ return \"ok\"; }}\n")


def _compile(su_text: str, tag: str):
    path = os.path.join(HERE, f".stageB_{tag}.su")
    open(path, "w", encoding="utf-8").write(su_text)
    bag = validate_file(path)
    if getattr(bag, "errors", None):
        print(f"VALIDATION ERRORS ({tag}):")
        for d in bag:
            print(" ", d.format())
        raise SystemExit(1)
    src = open(path, encoding="utf-8").read()
    lx = Lexer(src, file=path)
    ast = Parser(lx.tokenize(), file=path, diagnostics=lx.diagnostics).parse_module()
    py = translate_pytorch(ast, runtime_dim=768, runtime_seed=42,
                           loop_max_iterations=50)
    m = types.ModuleType(f"_sb_{tag}")
    m.__file__ = f"<stageB {tag}>"
    exec(compile(py, m.__file__, "exec"), m.__dict__)
    return m


def build_data(k, per_class):
    cache = os.path.join(HERE, ".diff_train_embeddings.pt")
    cats = dt.CATEGORIES[:k]
    words = [w for _, ws in cats for w in ws]
    vecs = dt.embed_all(words, cache_path=cache)
    data = []
    for ci, (_, ws) in enumerate(cats):
        for w in ws[:per_class]:
            data.append((vecs[w], ci))
    return data, next(iter(vecs.values())).shape[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--per-class", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--lr", type=float, default=0.02)
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    k = a.k

    mod = _compile(_su(k, None), "param")
    data, dim = build_data(k, a.per_class)
    print(f"compiled weighted .su (param w) via PyTorch codegen; "
          f"k={k} N={len(data)} dim={dim} epochs={a.epochs} "
          f"seeds={seeds} lr={a.lr}")

    def logits(m, protos, w, x):
        return torch.stack([
            m.rule(x, protos[i], *[protos[j] for j in range(k) if j != i], w)
            for i in range(k)])

    bef100, aft100, ws, rts = [], [], [], []
    t0 = time.time()
    for s in seeds:
        torch.manual_seed(s)
        protos = [(p := torch.randn(dim)) / p.norm() for _ in range(k)]
        protos = [p.clone().requires_grad_(True) for p in protos]
        w = torch.tensor(1.0, requires_grad=True)
        opt = torch.optim.Adam(protos + [w], lr=a.lr)

        def acc(m, P, wv):
            c = 0
            with torch.no_grad():
                for x, y in data:
                    if int(torch.argmax(logits(m, P, wv, x))) == y:
                        c += 1
            return c / len(data)

        b = acc(mod, protos, w)
        for _ in range(a.epochs):
            opt.zero_grad()
            loss = torch.stack([
                F.cross_entropy((logits(mod, protos, w, x) * 10.0).unsqueeze(0),
                                torch.tensor([y])) for x, y in data]).mean()
            loss.backward()
            opt.step()
        af = acc(mod, protos, w)
        wv = float(w.detach())

        # --- bake trained w as a .su literal, recompile, round-trip ---
        baked = _compile(_su(k, round(wv, 6)), "baked")

        def logits_baked(P, x):
            return torch.stack([
                baked.rule(x, P[i], *[P[j] for j in range(k) if j != i])
                for i in range(k)])
        with torch.no_grad():
            maxdiff, cb = 0.0, 0
            for x, y in data:
                lp = logits(mod, protos, w, x)
                lb = logits_baked(protos, x)
                maxdiff = max(maxdiff, float((lp - lb).abs().max()))
                cb += int(torch.argmax(lb)) == y
            rt_acc = cb / len(data)
        rt_ok = (maxdiff < 1e-4 and abs(rt_acc - af) < 1e-9)
        print(f"  seed {s}: acc {b:.3f} -> {af:.3f}  w*={wv:.4f}  "
              f"baked-recompile acc={rt_acc:.3f} maxlogitΔ={maxdiff:.2e} "
              f"round_trip_ok={rt_ok}")
        bef100.append(b); aft100.append(af); ws.append(wv); rts.append(rt_ok)

    def ms(v): return (statistics.mean(v),
                        statistics.stdev(v) if len(v) > 1 else 0.0)
    bm, bs = ms(bef100); am, as_ = ms(aft100); wm, wsd = ms(ws)
    print(f"\n=== STAGE B MEASURED (real compiled graph, weight trained) "
          f"in {time.time()-t0:.1f}s ===")
    print(f"k={k} chance={1/k:.3f}  before={bm*100:.2f}±{bs*100:.2f}%  "
          f"after={am*100:.2f}±{as_*100:.2f}%  (n={len(seeds)})")
    print(f"trained gain w*={wm:.4f}±{wsd:.4f}  "
          f"round_trip_ok(all)={all(rts)}  (baked .su recompiles to "
          f"identical logits → trained model IS legible source)")


if __name__ == "__main__":
    main()
