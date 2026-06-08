"""Constructed-weight attention-on-RAM parser — Python reference oracle.

Design doc: planning/exploratory/codable-attention-on-ram-parser.md (NTM-archetype
track). This is the build-sequence step (a): a single, HANDCRAFTED (untrained)
attention head that reads a RAM tape and aggregates it. It is NOT a DNC/NTM
([[project_ram_editing_nn_framing]]); it is a structural sub-instance of one
`transformer-vm` attention head pointed at memory.

This file is the cross-language ORACLE — the Python reference whose `(tape -> output)`
behavior the OCaml port and (eventually) the Sutra-substrate version must reproduce
identically (§5 "reduction is the through-line"). It runs OFF any Sutra runtime hot
path: constructed-weight analysis in torch is compile/monitor work, allowed under
CLAUDE.md §"Numpy: compile and monitor only". Nothing here is a Sutra operation.

One attention head, written exactly as a transformer head:
  - keys    K : [N, d_k] — one row per RAM cell. We use the LOCATION encoding
                 K = I_N (cell i's key is the standard basis vector e_i), so the
                 head is location-addressed, like the transformer-vm's addressing.
  - values  V : [N]      — the RAM cell values (the tape contents).
  - query   q : [d_k]    — encodes the parse. Constructed, not trained.
  - scores    = K @ q                       ( = q itself, since K = I )
  - LINEAR  : out = scores . V              (no softmax -> a plain weighted sum
                                              = linear regression over memory)
  - HARD    : w = hardmax(scores); out = w . V   (location-addressed single read)

Three parse tasks, smallest-first (design doc §2):
  - sum_tape(tape)        : q = 1  -> out = sum_i tape[i]
  - dot_tape(tape, w)     : q = w  -> out = sum_i w[i]*tape[i]   (linear regression)
  - select_field(tape, j) : q = HARD_K * e_j , hardmax -> out = tape[j]
"""

from __future__ import annotations

import torch

# Same saturating constant the transformer-vm uses for hard location addressing.
HARD_K = 1e10

# float64 throughout: the reference must be exact so the cross-language oracle is
# byte-meaningful (the constructed weights have no training noise).
DTYPE = torch.float64


def _ram(tape) -> torch.Tensor:
    """Materialize a RAM tape (a 1-D list/seq of cell values) as a tensor."""
    return torch.tensor(list(tape), dtype=DTYPE)


def _attention_head(query: torch.Tensor, values: torch.Tensor, *, hard: bool) -> torch.Tensor:
    """One attention head over a location-addressed RAM tape.

    keys K = I_N (identity), so scores = K @ q = q. `values` are V (the tape).
    LINEAR (hard=False): out = scores . V   -> a weighted sum (linear regression).
    HARD   (hard=True) : out = hardmax(scores) . V -> a single location read.
    """
    scores = query  # K @ q with K = I_N
    if hard:
        # hardmax: a one-hot at the argmax, exactly as HARD_K-saturated softmax ->
        # one-hot in the limit. Built explicitly here (the reference is exact).
        weights = torch.zeros_like(scores)
        weights[int(torch.argmax(scores))] = 1.0
    else:
        weights = scores
    return torch.dot(weights, values)


def sum_tape(tape) -> float:
    """Aggregate-attention parse: out = sum_i tape[i]. q = ones."""
    v = _ram(tape)
    q = torch.ones(v.shape[0], dtype=DTYPE)
    return float(_attention_head(q, v, hard=False))


def dot_tape(tape, coeffs) -> float:
    """Linear-regression parse: out = sum_i coeffs[i]*tape[i]. q = coeffs.

    This is literally evaluating a linear model y_hat = w . x by linear attention
    over RAM — the "linear regression over memory" first step.
    """
    v = _ram(tape)
    q = _ram(coeffs)
    assert q.shape == v.shape, "coeffs must match tape length"
    return float(_attention_head(q, v, hard=False))


def select_field(tape, index: int) -> float:
    """Minimal structural parse: location-addressed single read, out = tape[index].

    q = HARD_K * e_index; hardmax over scores picks exactly cell `index`.
    """
    v = _ram(tape)
    q = torch.zeros(v.shape[0], dtype=DTYPE)
    q[index] = HARD_K
    return float(_attention_head(q, v, hard=True))


# ── Cross-language test set: (task, args, expected). The OCaml port and the
# ── Sutra-substrate version must reproduce EXACTLY these outputs (design doc §5).
TEST_SET = [
    ("sum_tape", ([3.0, 4.0],), 7.0),
    ("sum_tape", ([5.0, 6.0, 7.0],), 18.0),
    ("sum_tape", ([1.0, 2.0, 3.0, 4.0],), 10.0),
    ("sum_tape", ([100.0, 23.0],), 123.0),
    ("dot_tape", ([3.0, 4.0], [2.0, 0.5]), 8.0),          # 3*2 + 4*0.5 = 8
    ("dot_tape", ([1.0, 2.0, 3.0], [1.0, 0.0, -1.0]), -2.0),  # 1 - 3 = -2
    ("dot_tape", ([10.0, 20.0, 30.0], [0.1, 0.2, 0.3]), 14.0),  # 1+4+9 = 14 (lin reg)
    ("select_field", ([11.0, 22.0, 33.0], 0), 11.0),
    ("select_field", ([11.0, 22.0, 33.0], 1), 22.0),
    ("select_field", ([11.0, 22.0, 33.0], 2), 33.0),
]

_DISPATCH = {"sum_tape": sum_tape, "dot_tape": dot_tape, "select_field": select_field}


def run_test_set(verbose: bool = True) -> bool:
    """Run the cross-language oracle; return True iff every case matches exactly."""
    all_ok = True
    for task, args, expected in TEST_SET:
        got = _DISPATCH[task](*args)
        ok = got == expected  # exact: constructed weights, float64, no training noise
        all_ok &= ok
        if verbose:
            mark = "OK " if ok else "XX "
            print(f"{mark}{task}{args} = {got!r}  (expected {expected!r})")
    return all_ok


if __name__ == "__main__":
    ok = run_test_set()
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'} "
          f"({sum(1 for *_, e in TEST_SET)} cases)")
    raise SystemExit(0 if ok else 1)
