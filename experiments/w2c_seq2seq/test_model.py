"""Deterministic guard for the weight→code seq2seq model (task #20).

No corpus / no GPU needed: builds a handful of synthetic (weights → target)
programs where the target DEPENDS on the weights (so the decoder must use
the encoder memory), trains a tiny model for a few hundred steps, and
asserts it can overfit them (train token-accuracy → high, greedy decode
reproduces a target). This guards the architecture + training loop wiring
(masks, teacher forcing, greedy decode) — not corpus-scale performance,
which model.py reports from a real run.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

torch = pytest.importorskip("torch", reason="seq2seq model requires torch")

HERE = os.path.dirname(os.path.abspath(__file__))


def _mod(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _build():
    M = _mod("w2c_model", "model.py")
    P = _mod("w2c_prepare", "prepare.py")
    # targets depend on the weight matrix -> encoder must be used
    specs = [
        ([[1., 0.], [0., 1.]], "return x;"),
        ([[2., 0.], [0., 2.]], "return 2*x;"),
        ([[0., 1.], [1., 0.]], "swap(x);"),
        ([[0., 0.], [0., 0.]], "zero();"),
    ]
    vocab = P.build_vocab([s for _, s in specs])
    recs = []
    for mat, tgt in specs:
        out = [sum(mat[i][j] * 1.0 for j in range(2)) for i in range(2)]
        recs.append({
            "weights": [mat],
            "io": [{"input": [1.0, 1.0], "output": out}],
            "target": tgt,
            "target_ids": P.encode(tgt, vocab),
        })
    return M, P, vocab, recs


def _item(M, rec):
    vals, types, slots, poss = M.build_enc(rec)
    return {
        "vals": torch.tensor(vals, dtype=torch.float32),
        "types": torch.tensor(types, dtype=torch.long),
        "slots": torch.tensor(slots, dtype=torch.long),
        "poss": torch.tensor(poss, dtype=torch.long),
        "tgt": torch.tensor(rec["target_ids"], dtype=torch.long),
        "target": rec["target"],
    }


def test_model_overfits_tiny_batch():
    M, P, vocab, recs = _build()
    torch.manual_seed(0)
    batch = M.collate([_item(M, r) for r in recs])
    model = M.W2CSeq2Seq(len(vocab), d_model=32, nhead=2, enc_layers=1,
                         dec_layers=1, dim_ff=64, dropout=0.0, max_dec=32)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    crit = torch.nn.CrossEntropyLoss(ignore_index=M.PAD_ID)

    model.train()
    for _ in range(300):
        logits = model(batch)
        tgt_out = batch["tgt"][:, 1:]
        loss = crit(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()

    model.eval()
    with torch.no_grad():
        logits = model(batch)
    ok, n = M.token_accuracy(logits, batch["tgt"][:, 1:])
    assert ok / n > 0.9, f"failed to overfit tiny batch: token_acc={ok/n:.3f}"

    # greedy decode must reproduce at least one full target string
    inv = {i: c for c, i in vocab.items()}
    seq = model.greedy(batch)
    decoded = [M.decode_ids(seq[k, 1:].tolist(), inv) for k in range(len(recs))]
    assert any(decoded[k] == recs[k]["target"] for k in range(len(recs))), decoded


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
