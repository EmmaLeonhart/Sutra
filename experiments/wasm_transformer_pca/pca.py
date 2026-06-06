"""PCA / SVD analysis of the analytic WASM transformer's weights (2026-06-06).
Analysis/monitoring on the constructed weights (numpy/torch off the runtime hot
path) — allowed. Finds the genuine low-dimensional structure. KEY: the analytic
construction uses extreme-dynamic-range weights (hardmax temp ~1e10, address/
position scales), so energy-fraction rank is dominated by a few giant singular
values; a RELATIVE-threshold rank (sv > max_sv * tol) is the honest lens."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("WASM/replication_target/transformer-vm").resolve()))
import torch, numpy as np
from transformer_vm.model.weights import build_model

def rel_rank(s, tol):           # dims above a RELATIVE floor of the top sv
    s = s[s > 0]
    return int((s > s.max()*tol).sum()) if len(s) else 0

model, toks, *_ = build_model(plan_path=str(pathlib.Path(__file__).parent/"plan.yaml"))
sd = model.state_dict()
print(f"d_model=38, layers=7, vocab={len(toks)}, params=144286")
print(f"{'matrix':22s} {'shape':11s} {'full':>4s} {'r1e-3':>5s} {'r1e-6':>5s} {'dyn-range':>12s}")
mats=[]
for name,p in sd.items():
    W = p.detach().cpu().double().numpy()    # float64: 1e30 squares fine
    if W.ndim!=2: continue
    s = np.linalg.svd(W, compute_uv=False)
    mats.append((name,W,s))
    snz = s[s>0]; dr = (snz.max()/snz.min()) if len(snz) else 0
    print(f"{name:22s} {str(W.shape):11s} {min(W.shape):4d} {rel_rank(s,1e-3):5d} {rel_rank(s,1e-6):5d} {dr:12.2e}")

readers = np.concatenate([W for _,W,_ in mats if W.shape[1]==38], axis=0)
sr = np.linalg.svd(readers, compute_uv=False)
import numpy as _np
print(f"\nResidual-stream READ space (stacked 38-col, {readers.shape}):")
print(f"  full=38  rel-rank(1e-3)={rel_rank(sr,1e-3)}  rel-rank(1e-6)={rel_rank(sr,1e-6)}  rel-rank(1e-9)={rel_rank(sr,1e-9)}")
print(f"  sv dynamic range = {sr[sr>0].max()/sr[sr>0].min():.2e}  (max {sr.max():.2e}, min+ {sr[sr>0].min():.2e})")
# overall: fraction of the 38 residual dims actually spanned above tiny floors
print(f"  => the 38-d residual stream is genuinely used at rank "
      f"{rel_rank(sr,1e-6)}/38 (rel 1e-6); not naively reducible.")
