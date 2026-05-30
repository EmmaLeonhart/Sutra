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

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch  # noqa: E402

import re  # noqa: E402

TOL = 1e-3
_LM = re.compile(r'load_matrix\("([^"]+)"\)')


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
    exact = io_ok = compile_fail = run_fail = 0
    wins, fails = [], []

    for i in range(n):
        batch = _to(collate([ds[i]]), dev)
        seq = model.greedy(batch)
        gen = decode_ids(seq[0, 1:].tolist(), inv)
        rec = ds.recs[i]
        is_exact = gen == rec["target"]
        exact += int(is_exact)

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

        if ok:
            io_ok += 1
            if not is_exact:
                wins.append({"id": rec["id"], "gen": gen})
        else:
            fails.append({"id": rec["id"], "exact": is_exact, "detail": detail})

    summary = {
        "n": n,
        "exact_match": exact,
        "exact_match_rate": round(exact / n, 4),
        "io_reproduction": io_ok,
        "io_reproduction_rate": round(io_ok / n, 4),
        "non_exact_but_io_ok": len(wins),
        "compile_fail": compile_fail,
        "run_fail": run_fail,
        "tol": TOL,
    }
    with open(os.path.join(HERE, "_eval_result.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "wins": wins[:25], "fails": fails[:40]}, f, indent=1)
    # single self-contained result line (survives display-relay line duplication)
    print("EVALRESULT "
          f"n={n} exact={exact} repro={io_ok} nonexact_io_ok={len(wins)} "
          f"compfail={compile_fail} runfail={run_fail} "
          f"emr={summary['exact_match_rate']} rpr={summary['io_reproduction_rate']}")


if __name__ == "__main__":
    main()
