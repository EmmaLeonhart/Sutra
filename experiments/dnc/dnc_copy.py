"""DNC↔code isomorphism — the CORRECT (ordered) version: temporal-link copy.

planning/exploratory/differentiable-neural-computer.md § "The correct full
version". The content-read rung (associative lookup) is cleared
(finding 2026-06-02). This is the ordered test: a faithful DNC
(Graves 2016 — allocation write + temporal-link matrix L + content/
forward/backward read + LSTM controller) trained on the COPY task, then
**defuzzed and read off** to see whether the learned policy lands on the
sequential program:
    write: loop t: p = alloc(); ramWrite(p, x_t)
    read:  p = first; loop t: emit(ramRead(p)); p = next(p)

HONEST SCOPE: host-PyTorch research prototype, NOT a substrate-pure Sutra
DNC. The ops (cosine, softmax, matmul, outer products) are Sutra's op
family; the defuzzed ops are the ram-ops. A trains-but-blurry-defuzz
outcome is the open-Q-7 finding — reported, not hidden.

Run:  python experiments/dnc/dnc_copy.py [--seq N] [--steps N]
"""
from __future__ import annotations

import argparse
import io
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BITS = 6            # payload bit-width per vector
W = BITS + 2        # memory width = bits + 2 flag channels (delimiters)
N = 16              # memory rows (>= max sequence length)
H = 64              # LSTM controller hidden size
EPS = 1e-6


def _cos(key, M):
    # key: (B, W) ; M: (B, N, W) -> (B, N) cosine of key vs each row
    k = key / (key.norm(dim=-1, keepdim=True) + EPS)
    m = M / (M.norm(dim=-1, keepdim=True) + EPS)
    return torch.einsum("bw,bnw->bn", k, m)


def _alloc_weighting(usage):
    # DNC allocation: write to the least-used row. usage: (B,N) in [0,1].
    B, n = usage.shape
    su, phi = torch.sort(usage, dim=-1)                      # ascending
    prod = torch.cumprod(su, dim=-1)
    prod = torch.cat([torch.ones(B, 1, device=usage.device), prod[:, :-1]], dim=-1)
    a_sorted = (1 - su) * prod
    a = torch.zeros_like(usage).scatter(-1, phi, a_sorted)
    return a


class DNC(nn.Module):
    def __init__(self, in_size, out_size, n=N, w=W, h=H):
        super().__init__()
        self.n, self.w = n, w
        self.ctrl = nn.LSTMCell(in_size + w, h)
        # interface: 4 w-vectors (write_key, erase, write_vec, read_key)
        # + 5 scalars (write_str, free_gate, alloc_gate, write_gate, read_str)
        # + read_mode(3) = 4w + 8.
        self.iface = nn.Linear(h, 4 * w + 8)
        self.out = nn.Linear(h + w, out_size)

    def init_state(self, B, dev):
        return dict(
            hx=torch.zeros(B, self.ctrl.hidden_size, device=dev),
            cx=torch.zeros(B, self.ctrl.hidden_size, device=dev),
            M=torch.zeros(B, self.n, self.w, device=dev),
            u=torch.zeros(B, self.n, device=dev),
            p=torch.zeros(B, self.n, device=dev),
            L=torch.zeros(B, self.n, self.n, device=dev),
            wr=torch.zeros(B, self.n, device=dev),
            ww=torch.zeros(B, self.n, device=dev),
            r=torch.zeros(B, self.w, device=dev),
        )

    def step(self, x, st, beta_scale=1.0):
        hx, cx = self.ctrl(torch.cat([x, st["r"]], dim=-1), (st["hx"], st["cx"]))
        z = self.iface(hx)
        w = self.w
        i = 0
        def take(k):
            nonlocal i
            v = z[:, i:i + k]; i += k; return v
        write_key = take(w); write_str = F.softplus(take(1)) * beta_scale
        erase = torch.sigmoid(take(w)); write_vec = take(w)
        free_g = torch.sigmoid(take(1)); alloc_g = torch.sigmoid(take(1))
        write_g = torch.sigmoid(take(1))
        read_key = take(w); read_str = F.softplus(take(1)) * beta_scale
        read_mode = F.softmax(take(3), dim=-1)

        M, u, p, L, wr_prev = st["M"], st["u"], st["p"], st["L"], st["wr"]
        # --- usage + allocation + write weighting ---
        psi = (1 - free_g * wr_prev)                         # retention (1 read head)
        u = (u + st["ww"] - u * st["ww"]) * psi
        a = _alloc_weighting(u)
        cw = F.softmax(write_str * _cos(write_key, M), dim=-1)
        ww = write_g * (alloc_g * a + (1 - alloc_g) * cw)
        # --- write (erase + add) ---
        M = M * (1 - torch.einsum("bn,bw->bnw", ww, erase)) \
            + torch.einsum("bn,bw->bnw", ww, write_vec)
        u = u + ww - u * ww
        # --- temporal links ---
        pp = p
        ww_i = ww.unsqueeze(2); ww_j = ww.unsqueeze(1)
        L = (1 - ww_i - ww_j) * L + ww_i * pp.unsqueeze(1)
        eye = torch.eye(self.n, device=M.device).unsqueeze(0)
        L = L * (1 - eye)
        p = (1 - ww.sum(-1, keepdim=True)) * p + ww
        # --- read: content + forward + backward ---
        cr = F.softmax(read_str * _cos(read_key, M), dim=-1)
        fwd = torch.einsum("bnm,bm->bn", L, wr_prev)
        bwd = torch.einsum("bmn,bm->bn", L, wr_prev)
        wr = read_mode[:, 0:1] * bwd + read_mode[:, 1:2] * cr + read_mode[:, 2:3] * fwd
        r = torch.einsum("bn,bnw->bw", wr, M)
        out = self.out(torch.cat([hx, r], dim=-1))
        st = dict(hx=hx, cx=cx, M=M, u=u, p=p, L=L, wr=wr, ww=ww, r=r)
        return out, st, dict(ww=ww, wr=wr)


def make_copy_batch(B, T):
    # payload: T random bit vectors of width BITS; channels: [bits | go | pad]
    bits = (torch.rand(B, T, BITS) > 0.5).float()
    in_size = BITS + 2
    total = T + 1 + T
    x = torch.zeros(B, total, in_size)
    x[:, :T, :BITS] = bits
    x[:, T, BITS] = 1.0                       # go delimiter
    target = bits                              # reproduce during output phase
    return x, target, T, in_size


def run(seq=6, steps=20000, seed=0, lr=1e-3, batch=16):
    torch.manual_seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    in_size = BITS + 2
    model = DNC(in_size, BITS).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    for step in range(steps):
        # curriculum: grow length 1..seq over the first 60% of training
        T = 1 + int((seq - 1) * min(1.0, step / (0.6 * steps)))
        x, target, T, _ = make_copy_batch(batch, T)
        x, target = x.to(dev), target.to(dev)
        st = model.init_state(batch, dev)
        outs = []
        total = x.shape[1]
        for t in range(total):
            o, st, _ = model.step(x[:, t], st)
            outs.append(o)
        out = torch.stack(outs, dim=1)         # (B, total, BITS)
        pred = out[:, T + 1:T + 1 + T]          # output phase
        loss = F.binary_cross_entropy_with_logits(pred, target)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        opt.step()
        if step % max(1, steps // 10) == 0 or step == steps - 1:
            with torch.no_grad():
                acc = ((pred > 0).float() == target).float().mean().item()
            print(f"step {step:6d}  T={T}  loss {loss.item():.4f}  bit_acc {acc:.3f}")

    return model, dev


def defuzz_analysis(model, dev, seq=6, trials=200):
    """Read off the trained policy: per output step, which row does the read
    weighting peak on, and how peaked (one-hot) is it? For copy the correct
    program reads rows 0,1,2,...,T-1 in order. Also report write peakedness."""
    with torch.no_grad():
        x, target, T, _ = make_copy_batch(trials, seq)
        x = x.to(dev)
        st = model.init_state(trials, dev)
        total = x.shape[1]
        write_rows, write_peak, read_rows, read_peak = [], [], [], []
        for t in range(total):
            _, st, dbg = model.step(x[:, t], st)
            if t < T:                                   # write phase
                write_rows.append(dbg["ww"].argmax(-1))
                write_peak.append(dbg["ww"].max(-1).values)
            elif t >= T + 1:                            # read/output phase
                read_rows.append(dbg["wr"].argmax(-1))
                read_peak.append(dbg["wr"].max(-1).values)
        # copy accuracy
        st = model.init_state(trials, dev); outs = []
        for t in range(total):
            o, st, _ = model.step(x[:, t], st); outs.append(o)
        pred = torch.stack(outs, 1)[:, T + 1:T + 1 + T]
        acc = ((pred > 0).float() == target.to(dev)).float().mean().item()

    wr_rows = torch.stack(read_rows, 1)        # (trials, T) row read at each out step
    wr_pk = torch.stack(read_peak, 1).mean().item()
    ww_pk = torch.stack(write_peak, 1).mean().item()
    # Does read step t land on a distinct, monotonically advancing row?
    seq_match = (wr_rows[:, 1:] > wr_rows[:, :-1]).float().mean().item()  # advancing
    distinct = (torch.stack([wr_rows[:, t].unique().numel()
                             for t in range(T)]) if False else None)
    # fraction of trials whose read-rows are all-distinct (a clean pointer walk)
    all_distinct = torch.tensor(
        [len(set(wr_rows[b].tolist())) == T for b in range(trials)]).float().mean().item()

    print()
    print(f"DEFUZZ READ-OFF (seq={seq}, {trials} trials):")
    print(f"  copy bit-accuracy            : {acc:.3f}")
    print(f"  write weighting peak (one-hot): {ww_pk:.3f}")
    print(f"  read  weighting peak (one-hot): {wr_pk:.3f}")
    print(f"  read row advances each step   : {seq_match*100:.1f}%  "
          f"(sequential forward walk)")
    print(f"  read rows all-distinct        : {all_distinct*100:.1f}%  "
          f"(clean pointer walk over T rows)")
    print(f"  example read-row sequences    : {wr_rows[:3].tolist()}")
    clean = acc > 0.95 and wr_pk > 0.9 and seq_match > 0.9
    print()
    if clean:
        print("RESULT: the trained copy DNC DEFUZZES to a sequential pointer")
        print("walk — read step t reads a distinct, advancing row (one-hot),")
        print("reading off as  p=first; loop: emit(ramRead(p)); p=next(p).")
        print("Ordered DNC↔code isomorphism: CONFIRMED for copy.")
    else:
        print("RESULT: trained but defuzz is NOT a clean sequential walk")
        print(f"(acc={acc:.2f}, read_peak={wr_pk:.2f}, advance={seq_match:.2f}).")
        print("Open-Q-7 finding: the ordered policy does not read off as a")
        print("crisp program at these settings — needs more training / curriculum")
        print("/ β-anneal / larger N. Reported as-is, not hidden.")
    return clean


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", type=int, default=6)
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    print(f"DNC copy: BITS={BITS} W={W} N={N} H={H} seq={a.seq} steps={a.steps} seed={a.seed}")
    model, dev = run(seq=a.seq, steps=a.steps, seed=a.seed)
    clean = defuzz_analysis(model, dev, seq=a.seq)
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
