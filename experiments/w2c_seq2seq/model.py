"""Weight→code seq2seq model + training (Emma 2026-05-30: source generation).

Tick 2 of the weight→code build. A small Transformer seq2seq that maps a
program's WEIGHTS + IO behavior → its (normalized) `.su` source.

- **Encoder input** is the raw numbers of the program: every weight-matrix
  entry and every IO scalar becomes one token. A token's embedding =
  Linear(1→d) of its value  +  a TYPE embedding (weight / io-input /
  io-output)  +  a SLOT embedding (which matrix, or which IO pair)  +  a
  POS embedding (row·K+col for weights, vector index for IO). A Transformer
  encoder reads the (padded, masked) token sequence.
- **Decoder** generates the normalized source character-by-character
  (vocab 45 from prepare.py), cross-attending to the encoder memory.

This is host-side ML over the corpus — NOT a Sutra substrate op. The
substrate enters only at tick 3 (eval), where the GENERATED source is
re-substituted with the real CSV, compiled, and run to check it reproduces
the held-out program's IO. Here we report training loss + two generation
metrics measured on the held-out split:
  - **token accuracy** (teacher-forced next-char argmax vs target), and
  - **exact-match** (greedy-decoded source == target string).

Run:  py experiments/w2c_seq2seq/model.py            # train + eval
      py experiments/w2c_seq2seq/model.py --epochs 60 --d-model 192
Guarded by test_model.py (overfits a tiny synthetic batch — architecture +
training loop sanity, deterministic, no corpus needed).
"""
from __future__ import annotations

import argparse
import json
import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

PAD_ID, BOS_ID, EOS_ID = 0, 1, 2
TYPE_W, TYPE_IN, TYPE_OUT = 0, 1, 2
MAX_SLOT = 8     # >= max(#matrices, #io pairs)
MAX_POS = 300    # >= max(K*K, K) per element
N_COEFF = 5      # |COEFF_CLASSES| = {0.5,1,1.5,2,3} (prepare.COEFF_CLASSES)
COEFF_IGNORE = -1  # slot absent for this program's family


# ---------------------------------------------------------------- encoding
def build_enc(rec: dict):
    """Flatten a record's weights + IO into parallel token feature lists."""
    vals, types, slots, poss = [], [], [], []
    for s, mat in enumerate(rec["weights"]):
        K = len(mat[0]) if mat else 0
        for i, row in enumerate(mat):
            for j, v in enumerate(row):
                vals.append(float(v)); types.append(TYPE_W)
                slots.append(min(s, MAX_SLOT - 1)); poss.append(min(i * K + j, MAX_POS - 1))
    for p, pair in enumerate(rec["io"]):
        for idx, v in enumerate(pair["input"]):
            vals.append(float(v)); types.append(TYPE_IN)
            slots.append(min(p, MAX_SLOT - 1)); poss.append(min(idx, MAX_POS - 1))
        for idx, v in enumerate(pair["output"]):
            vals.append(float(v)); types.append(TYPE_OUT)
            slots.append(min(p, MAX_SLOT - 1)); poss.append(min(idx, MAX_POS - 1))
    return vals, types, slots, poss


class W2CDataset(Dataset):
    def __init__(self, path: str):
        self.recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

    def __len__(self):
        return len(self.recs)

    def __getitem__(self, i):
        r = self.recs[i]
        vals, types, slots, poss = build_enc(r)
        return {
            "vals": torch.tensor(vals, dtype=torch.float32),
            "types": torch.tensor(types, dtype=torch.long),
            "slots": torch.tensor(slots, dtype=torch.long),
            "poss": torch.tensor(poss, dtype=torch.long),
            "tgt": torch.tensor(r["target_ids"], dtype=torch.long),
            "target": r["target"],
            "coeff_a": int(r.get("coeff_a", COEFF_IGNORE)),
            "coeff_b": int(r.get("coeff_b", COEFF_IGNORE)),
        }


def collate(batch):
    B = len(batch)
    enc_len = max(b["vals"].numel() for b in batch)
    dec_len = max(b["tgt"].numel() for b in batch)
    vals = torch.zeros(B, enc_len)
    types = torch.zeros(B, enc_len, dtype=torch.long)
    slots = torch.zeros(B, enc_len, dtype=torch.long)
    poss = torch.zeros(B, enc_len, dtype=torch.long)
    src_pad = torch.ones(B, enc_len, dtype=torch.bool)   # True = pad
    tgt = torch.full((B, dec_len), PAD_ID, dtype=torch.long)
    for i, b in enumerate(batch):
        n = b["vals"].numel()
        vals[i, :n] = b["vals"]; types[i, :n] = b["types"]
        slots[i, :n] = b["slots"]; poss[i, :n] = b["poss"]
        src_pad[i, :n] = False
        m = b["tgt"].numel()
        tgt[i, :m] = b["tgt"]
    coeff_a = torch.tensor([b.get("coeff_a", COEFF_IGNORE) for b in batch], dtype=torch.long)
    coeff_b = torch.tensor([b.get("coeff_b", COEFF_IGNORE) for b in batch], dtype=torch.long)
    return {"vals": vals, "types": types, "slots": slots, "poss": poss,
            "src_pad": src_pad, "tgt": tgt, "targets": [b["target"] for b in batch],
            "coeff_a": coeff_a, "coeff_b": coeff_b}


# ------------------------------------------------------------------- model
class W2CSeq2Seq(nn.Module):
    def __init__(self, vocab_size: int, d_model=128, nhead=4, enc_layers=3,
                 dec_layers=3, dim_ff=512, dropout=0.1, max_dec=320):
        super().__init__()
        self.d_model = d_model
        self.val_proj = nn.Linear(1, d_model)
        self.type_emb = nn.Embedding(3, d_model)
        self.slot_emb = nn.Embedding(MAX_SLOT, d_model)
        self.pos_emb = nn.Embedding(MAX_POS, d_model)
        self.enc_norm = nn.LayerNorm(d_model)
        enc = nn.TransformerEncoderLayer(d_model, nhead, dim_ff, dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(enc, enc_layers)

        self.tok_emb = nn.Embedding(vocab_size, d_model, padding_idx=PAD_ID)
        self.dec_pos = nn.Embedding(max_dec, d_model)
        dec = nn.TransformerDecoderLayer(d_model, nhead, dim_ff, dropout, batch_first=True)
        self.decoder = nn.TransformerDecoder(dec, dec_layers)
        self.head = nn.Linear(d_model, vocab_size)
        self.max_dec = max_dec

        # Coefficient-prediction head (tick-3 follow-up #2 diagnostic): from a
        # masked mean-pool of the encoder memory, predict the discrete
        # coefficient class for slots a and b. Trained with an auxiliary loss;
        # does NOT touch `forward` (decoder path) so the overfit guard stays
        # valid. Tells us whether the coefficient is decodable from the rep.
        self.coeff_a_head = nn.Linear(d_model, N_COEFF)
        self.coeff_b_head = nn.Linear(d_model, N_COEFF)

    def encode(self, b):
        x = (self.val_proj(b["vals"].unsqueeze(-1)) + self.type_emb(b["types"])
             + self.slot_emb(b["slots"]) + self.pos_emb(b["poss"]))
        x = self.enc_norm(x)
        return self.encoder(x, src_key_padding_mask=b["src_pad"])

    def coeff_logits(self, b, memory=None):
        """Predict coefficient class for slots a, b from a masked mean-pool of
        the encoder memory. Returns (logits_a, logits_b), each (B, N_COEFF).
        Separate from forward() — the decoder path is unchanged."""
        if memory is None:
            memory = self.encode(b)
        keep = (~b["src_pad"]).unsqueeze(-1).to(memory.dtype)   # (B, L, 1)
        pooled = (memory * keep).sum(1) / keep.sum(1).clamp_min(1.0)
        return self.coeff_a_head(pooled), self.coeff_b_head(pooled)

    def decode(self, tgt_in, memory, src_pad):
        T = tgt_in.size(1)
        pos = torch.arange(T, device=tgt_in.device).clamp_max(self.max_dec - 1)
        y = self.tok_emb(tgt_in) + self.dec_pos(pos).unsqueeze(0)
        causal = nn.Transformer.generate_square_subsequent_mask(T).to(tgt_in.device)
        tgt_pad = tgt_in.eq(PAD_ID)
        out = self.decoder(y, memory, tgt_mask=causal,
                           tgt_key_padding_mask=tgt_pad,
                           memory_key_padding_mask=src_pad)
        return self.head(out)

    def forward(self, b):
        memory = self.encode(b)
        logits = self.decode(b["tgt"][:, :-1], memory, b["src_pad"])
        return logits

    @torch.no_grad()
    def greedy(self, b, max_len=None):
        self.eval()
        memory = self.encode(b)
        B = memory.size(0)
        max_len = max_len or self.max_dec
        seq = torch.full((B, 1), BOS_ID, dtype=torch.long, device=memory.device)
        done = torch.zeros(B, dtype=torch.bool, device=memory.device)
        for _ in range(max_len):
            logits = self.decode(seq, memory, b["src_pad"])
            nxt = logits[:, -1].argmax(-1)
            seq = torch.cat([seq, nxt.unsqueeze(1)], 1)
            done = done | nxt.eq(EOS_ID)
            if bool(done.all()):
                break
        return seq


# -------------------------------------------------------------- train/eval
def _to(b, dev):
    return {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in b.items()}


def token_accuracy(logits, tgt_out):
    pred = logits.argmax(-1)
    mask = tgt_out.ne(PAD_ID)
    return (pred.eq(tgt_out) & mask).sum().item(), mask.sum().item()


def decode_ids(ids, inv):
    out = []
    for i in ids:
        i = int(i)
        if i == EOS_ID:
            break
        if i in (PAD_ID, BOS_ID):
            continue
        out.append(inv[i])
    return "".join(out)


def _coeff_acc(logits, labels):
    """(#correct, #present) for one coeff slot, ignoring absent (-1) slots."""
    mask = labels.ne(COEFF_IGNORE)
    if mask.sum().item() == 0:
        return 0, 0
    pred = logits.argmax(-1)
    return (pred.eq(labels) & mask).sum().item(), mask.sum().item()


def evaluate(model, loader, dev, inv, greedy_batches=None):
    model.eval()
    crit = nn.CrossEntropyLoss(ignore_index=PAD_ID)
    tot_loss = tok_ok = tok_n = exact_ok = exact_n = 0
    ca_ok = ca_n = cb_ok = cb_n = 0
    with torch.no_grad():
        for bi, b in enumerate(loader):
            b = _to(b, dev)
            memory = model.encode(b)
            logits = model.decode(b["tgt"][:, :-1], memory, b["src_pad"])
            tgt_out = b["tgt"][:, 1:]
            tot_loss += crit(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1)).item()
            ok, n = token_accuracy(logits, tgt_out)
            tok_ok += ok; tok_n += n
            la, lb = model.coeff_logits(b, memory)
            o, m = _coeff_acc(la, b["coeff_a"]); ca_ok += o; ca_n += m
            o, m = _coeff_acc(lb, b["coeff_b"]); cb_ok += o; cb_n += m
            if greedy_batches is None or bi < greedy_batches:
                seq = model.greedy(b)
                for k, tgt_str in enumerate(b["targets"]):
                    if decode_ids(seq[k, 1:].tolist(), inv) == tgt_str:
                        exact_ok += 1
                    exact_n += 1
    return {
        "loss": tot_loss / max(1, len(loader)),
        "token_acc": tok_ok / max(1, tok_n),
        "exact_match": exact_ok / max(1, exact_n),
        "exact_n": exact_n,
        "coeff_a_acc": ca_ok / max(1, ca_n), "coeff_a_n": ca_n,
        "coeff_b_acc": cb_ok / max(1, cb_n), "coeff_b_n": cb_n,
    }


def train(args):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    vocab = json.load(open(os.path.join(DATA, "vocab.json"), encoding="utf-8"))
    inv = {i: c for c, i in vocab.items()}
    tr = DataLoader(W2CDataset(os.path.join(DATA, "train.jsonl")),
                    batch_size=args.batch, shuffle=True, collate_fn=collate)
    va = DataLoader(W2CDataset(os.path.join(DATA, "val.jsonl")),
                    batch_size=args.batch, shuffle=False, collate_fn=collate)

    torch.manual_seed(0)
    model = W2CSeq2Seq(len(vocab), d_model=args.d_model, enc_layers=args.layers,
                       dec_layers=args.layers).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss(ignore_index=PAD_ID)
    coeff_crit = nn.CrossEntropyLoss(ignore_index=COEFF_IGNORE)
    nparams = sum(p.numel() for p in model.parameters())
    print(f"device={dev}  params={nparams:,}  vocab={len(vocab)}  "
          f"train={len(tr.dataset)} val={len(va.dataset)}  "
          f"coeff_aux_w={args.coeff_aux_w}", flush=True)

    for ep in range(1, args.epochs + 1):
        model.train()
        run = 0.0
        for b in tr:
            b = _to(b, dev)
            # one encode shared by decoder + coeff head (forward() unchanged;
            # re-implemented here to add the auxiliary coeff loss without a
            # second encode pass).
            memory = model.encode(b)
            logits = model.decode(b["tgt"][:, :-1], memory, b["src_pad"])
            tgt_out = b["tgt"][:, 1:]
            loss = crit(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1))
            if args.coeff_aux_w > 0:
                la, lb = model.coeff_logits(b, memory)
                aux = coeff_crit(la, b["coeff_a"]) + coeff_crit(lb, b["coeff_b"])
                # coeff_crit returns nan if a batch has zero present slots; guard.
                if torch.isfinite(aux):
                    loss = loss + args.coeff_aux_w * aux
            opt.zero_grad(); loss.backward(); opt.step()
            run += loss.item()
        if ep % args.eval_every == 0 or ep == args.epochs:
            m = evaluate(model, va, dev, inv, greedy_batches=args.greedy_batches)
            print(f"epoch {ep:3d}  train_loss {run/len(tr):.4f}  "
                  f"val_loss {m['loss']:.4f}  tok_acc {m['token_acc']:.4f}  "
                  f"exact {m['exact_match']:.4f} (n={m['exact_n']})  "
                  f"coeff_a {m['coeff_a_acc']:.4f} (n={m['coeff_a_n']})  "
                  f"coeff_b {m['coeff_b_acc']:.4f} (n={m['coeff_b_n']})", flush=True)
        else:
            print(f"epoch {ep:3d}  train_loss {run/len(tr):.4f}", flush=True)

    final = evaluate(model, va, dev, inv, greedy_batches=None)
    print(json.dumps({"final_val": final}, indent=2), flush=True)
    ckpt = os.path.join(DATA, "model.pt")
    torch.save({"model": model.state_dict(), "args": vars(args),
                "vocab": vocab}, ckpt)
    print(f"saved {ckpt}", flush=True)
    return final


def main():
    import io as _io
    import sys
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--eval-every", type=int, default=5)
    ap.add_argument("--greedy-batches", type=int, default=2,
                    help="batches to greedy-decode during periodic eval (full at the end)")
    ap.add_argument("--coeff-aux-w", type=float, default=0.0,
                    help="weight of the auxiliary coefficient-head loss. Default 0 "
                         "(OFF): the 2026-05-30 ablation found it hurts decoder "
                         "exact-match monotonically (0.669@0 -> 0.508@0.5). Set 0.5 "
                         "to train the diagnostic head; see the coeff-head finding.")
    train(ap.parse_args())


if __name__ == "__main__":
    main()
