"""weight->code seq2seq — tick 3: substrate-grounded eval.

The metric that makes "weight->code" real rather than a string-match exercise.
For each held-out (val) program:

  1. Generate `.su` source from the program's weights+IO (greedy decode),
     reusing the *actual* training `W2CDataset` + `model.greedy` so the model
     sees training-identical inputs.
  2. Reverse prepare.py's `load_matrix("M0")` normalization: write the real
     weight matrices to CSVs and substitute the paths back in.
  3. COMPILE the generated source (sutra_compiler lexer -> parser ->
     codegen_pytorch, runtime_dim = K, model-free) and RUN `apply(x)` on the
     substrate (Tensor.MatrixMul lowers to a torch matmul).
  4. Check it reproduces the held-out program's IO within tolerance.

Reports (real measured numbers, no targets):
  - exact-match rate         generated source == ground-truth normalized source
  - IO-reproduction rate     compiles, runs, reproduces ALL IO pairs (= the
                             decompilation-accuracy metric)
  - non-exact-but-IO-ok      different source, same behavior (the wins)
  - compile-fail / run-fail  generated source that failed to compile / ran wrong

Run:  py experiments/w2c_seq2seq/eval_substrate.py
Needs the gitignored data/ + data/model.pt (run prepare.py then model.py first).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))

from model import W2CSeq2Seq, W2CDataset, collate, decode_ids, _to  # noqa: E402
from prepare import COEFF_CLASSES  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch  # noqa: E402

import re  # noqa: E402

TOL = 1e-3
_LM = re.compile(r'load_matrix\("([^"]+)"\)')
# Multiplicative-identity coefficient: the generator renders a unit coefficient
# as the redundant literal `1.0 * EXPR`, but `1.0 * EXPR == EXPR`. The model
# correctly drops it, so raw exact-match mis-scores those (tick-3 finding: the
# 17 all-unit-coeff val cases scored 0.000 exact despite reproducing IO).
# Canonicalizing both sides credits the correct simplification. Only 1.0 is the
# identity here (COEFFS = {0.5,1,1.5,2,3}; no 0.0), so this never rewrites a
# behaviorally-meaningful coefficient.
_UNIT_COEFF = re.compile(r'1\.0 \* ')


def canonicalize_source(src: str) -> str:
    """Drop redundant `1.0 * ` so a correct unit-coeff simplification compares
    equal. Pure/string-only — does NOT touch non-unit coefficients (0.5, 2.0…)."""
    return _UNIT_COEFF.sub("", src)


# Post-hoc coefficient substitution (follow-up #2 lever 1): overwrite the
# coefficient literal(s) the decoder emitted with the coeff-head's prediction.
# A `<float> * ` token is a coefficient slot; positionally the 1st is slot a,
# the 2nd is slot b. Gated by slot-presence (caller passes has_a/has_b from the
# corpus label) so the fixed-coeff families (affine 0.5*, scaled 2.0*) are never
# touched. Capped by head accuracy; measures the lever's lift, not a decompiler.
_COEFF_LIT = re.compile(r'\d+\.\d+ \* ')


def substitute_coeffs(src: str, pred_a: int, pred_b: int, has_a: bool, has_b: bool) -> str:
    reps = []
    if has_a:
        reps.append(f"{COEFF_CLASSES[pred_a]!r} * ")
    if has_b:
        reps.append(f"{COEFF_CLASSES[pred_b]!r} * ")
    if not reps:
        return src
    out, idx = [], 0
    last = 0
    for m in _COEFF_LIT.finditer(src):
        if idx >= len(reps):
            break
        out.append(src[last:m.start()])
        out.append(reps[idx])
        last = m.end()
        idx += 1
    out.append(src[last:])
    return "".join(out)


def write_csv(path: str, mat) -> None:
    """Match weight_to_code_corpus.write_csv exactly (repr float, \\n rows)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in mat:
            f.write(",".join(repr(float(v)) for v in row) + "\n")


def write_weight_csvs(weights, d: str) -> dict:
    """weights = list of matrices; write M{i}.csv; return {ref: abs posix path}."""
    paths = {}
    for i, mat in enumerate(weights):
        p = os.path.join(d, f"M{i}.csv")
        write_csv(p, mat)
        paths[f"M{i}"] = p.replace("\\", "/")
    return paths


def resubstitute(src: str, paths: dict) -> str:
    def sub(m):
        key = m.group(1)
        return f'load_matrix("{paths[key]}")' if key in paths else m.group(0)
    return _LM.sub(sub, src)


def compile_su(src: str, runtime_dim: int):
    """Compile a .su source to a runnable namespace on the substrate."""
    lx = Lexer(src, file="<gen>")
    toks = lx.tokenize()
    ast = Parser(toks, file="<gen>", diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        raise RuntimeError(f"parse errors: {list(lx.diagnostics)}")
    py = translate_pytorch(ast, llm_model="none", runtime_dim=runtime_dim)
    ns: dict = {}
    exec(py, ns)
    return ns


def check_io(apply_fn, vsa, io_pairs):
    for pair in io_pairs:
        x = torch.tensor([float(v) for v in pair["input"]], dtype=vsa.dtype).to(vsa.device)
        y = apply_fn(x).detach().reshape(-1).to(torch.float64).cpu()
        exp = torch.tensor([float(v) for v in pair["output"]], dtype=torch.float64)
        if y.numel() != exp.numel():
            return False, f"shape {tuple(y.shape)} vs {tuple(exp.shape)}"
        if torch.max(torch.abs(y - exp)).item() > TOL:
            return False, "value mismatch"
    return True, "ok"


def main() -> None:
    ckpt_path = os.path.join(DATA, "model.pt")
    if not os.path.exists(ckpt_path):
        sys.exit("missing data/model.pt — run prepare.py then model.py first")
    ck = torch.load(ckpt_path, map_location="cpu")
    vocab = ck["vocab"]
    inv = {i: c for c, i in vocab.items()}
    args = ck.get("args", {})
    d_model = args.get("d_model", 128)
    layers = args.get("layers", 3)

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = W2CSeq2Seq(len(vocab), d_model=d_model, enc_layers=layers, dec_layers=layers).to(dev)
    model.load_state_dict(ck["model"])  # size mismatch here = wrong arch, fails loudly
    model.eval()

    ds = W2CDataset(os.path.join(DATA, "val.jsonl"))
    n = len(ds)
    exact = exact_canon = io_ok = compile_fail = run_fail = 0
    wins, fails = [], []
    # Per-structure (family) breakdown — the tick-3 hardening question is
    # whether the new inference-forcing families (chain4 / coeff families)
    # recover behavior, so aggregate exact + io_ok by structure. Built from
    # every val program (not the truncated fails list).
    per_structure: dict = {}
    # Post-hoc coefficient substitution (follow-up #2 lever 1): for programs that
    # carry a coeff slot, compare IO-reproduction of the decoder's raw source vs
    # the source with coeff literals overwritten by the head's prediction.
    cf_n = cf_io_base = cf_io_subst = 0

    for i in range(n):
        batch = _to(collate([ds[i]]), dev)
        seq = model.greedy(batch)
        gen = decode_ids(seq[0, 1:].tolist(), inv)
        rec = ds.recs[i]
        has_a = rec.get("coeff_a", -1) != -1
        has_b = rec.get("coeff_b", -1) != -1
        is_exact = gen == rec["target"]
        # canonical exact-match: credit correct `1.0 *` simplifications (tick-3
        # follow-up #1). Strictly >= raw exact; the delta is the unit-coeff
        # mis-scoring the raw metric suffered.
        is_exact_canon = canonicalize_source(gen) == canonicalize_source(rec["target"])
        exact += int(is_exact)
        exact_canon += int(is_exact_canon)

        ok = False
        stage = "compile"
        try:
            with tempfile.TemporaryDirectory() as td:
                paths = write_weight_csvs(rec["weights"], td)
                src_real = resubstitute(gen, paths)
                ns = compile_su(src_real, rec["K"])
                stage = "run"
                ok, detail = check_io(ns["apply"], ns["_VSA"], rec["io"])
        except Exception as e:  # noqa: BLE001 — measuring real failure modes
            detail = f"{stage}:{type(e).__name__}:{e}"[:160]
            if stage == "compile":
                compile_fail += 1
            else:
                run_fail += 1
            ok = False

        st = rec.get("structure") or "?"
        agg = per_structure.setdefault(st, {"n": 0, "exact": 0, "exact_canon": 0, "io_ok": 0})
        agg["n"] += 1
        agg["exact"] += int(is_exact)
        agg["exact_canon"] += int(is_exact_canon)
        agg["io_ok"] += int(ok)

        if ok:
            io_ok += 1
            if not is_exact:
                wins.append({"id": rec["id"], "gen": gen})
        else:
            fails.append({"id": rec["id"], "exact": is_exact, "detail": detail})

        # Coeff-family post-hoc substitution measurement (only for slot-carrying
        # programs). Predict coeffs via the head, overwrite the literals, recompile
        # + rerun, and compare to the raw decoder source's IO on the SAME programs.
        if has_a or has_b:
            cf_n += 1
            cf_io_base += int(ok)
            la, lb = model.coeff_logits(batch)
            pa = int(la.argmax(-1)[0].item())
            pb = int(lb.argmax(-1)[0].item())
            gen_sub = substitute_coeffs(gen, pa, pb, has_a, has_b)
            try:
                with tempfile.TemporaryDirectory() as td:
                    paths = write_weight_csvs(rec["weights"], td)
                    ns = compile_su(resubstitute(gen_sub, paths), rec["K"])
                    ok_sub, _ = check_io(ns["apply"], ns["_VSA"], rec["io"])
            except Exception:  # noqa: BLE001 — substituted source may not compile
                ok_sub = False
            cf_io_subst += int(ok_sub)

    summary = {
        "n": n,
        "exact_match": exact,
        "exact_match_rate": round(exact / n, 4),
        "exact_match_canonical": exact_canon,
        "exact_match_canonical_rate": round(exact_canon / n, 4),
        "io_reproduction": io_ok,
        "io_reproduction_rate": round(io_ok / n, 4),
        "non_exact_but_io_ok": len(wins),
        "compile_fail": compile_fail,
        "run_fail": run_fail,
        "tol": TOL,
        "per_structure": {
            k: {**v,
                "exact_rate": round(v["exact"] / v["n"], 4),
                "exact_canon_rate": round(v["exact_canon"] / v["n"], 4),
                "io_rate": round(v["io_ok"] / v["n"], 4)}
            for k, v in sorted(per_structure.items())
        },
        # post-hoc coeff substitution, measured on the cf_n coeff-slot programs
        "coeff_subst": {
            "n": cf_n,
            "io_base": cf_io_base,
            "io_base_rate": round(cf_io_base / max(1, cf_n), 4),
            "io_subst": cf_io_subst,
            "io_subst_rate": round(cf_io_subst / max(1, cf_n), 4),
        },
    }
    with open(os.path.join(HERE, "_eval_result.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "wins": wins[:25], "fails": fails[:40]}, f, indent=1)
    # single self-contained result line (survives display-relay line duplication)
    print("EVALRESULT "
          f"n={n} exact={exact} exact_canon={exact_canon} repro={io_ok} "
          f"nonexact_io_ok={len(wins)} compfail={compile_fail} runfail={run_fail} "
          f"emr={summary['exact_match_rate']} "
          f"emcr={summary['exact_match_canonical_rate']} "
          f"rpr={summary['io_reproduction_rate']} "
          f"cf_n={cf_n} cf_io_base={cf_io_base} cf_io_subst={cf_io_subst}")


if __name__ == "__main__":
    main()
