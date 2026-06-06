"""Graph-level attention usage of the analytic WASM transformer (2026-06-06).
SVD can't reduce the attention (importance != magnitude); the real reduction
lever is the schedule — how many of the nominal 19 heads x 7 layers actually
attend. A head attends iff its Q AND K projection rows are non-zero. Analysis
on constructed weights (off the runtime hot path)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("WASM/replication_target/transformer-vm").resolve()))
import torch, numpy as np
from transformer_vm.model.weights import build_model
model, toks, *_ = build_model(plan_path=str(pathlib.Path("experiments/wasm_transformer_pca/plan.yaml")))
sd = model.state_dict()
D=38; H=19; hd=D//H   # 19 heads of dim 2
print(f"d_model={D}, nominal heads/layer={H} (dim {hd}), layers=7  -> nominal {H*7} head-slots")
used_total=0
for L in range(7):
    W = sd[f"attn.{L}.in_proj_weight"].detach().cpu().double().numpy()  # (114,38)
    Q,K,V = W[:D], W[D:2*D], W[2*D:]   # each (38,38)
    used=[]
    for h in range(H):
        qrows = Q[h*hd:(h+1)*hd]; krows = K[h*hd:(h+1)*hd]
        if np.abs(qrows).sum() > 0 and np.abs(krows).sum() > 0:
            used.append(h)
    used_total += len(used)
    print(f"  layer {L}: {len(used):2d}/19 heads attend  {('('+','.join(map(str,used))+')') if 0<len(used)<=8 else ''}")
print(f"TOTAL genuine attention heads: {used_total} / {H*7} nominal "
      f"({100*used_total/(H*7):.1f}%)")
