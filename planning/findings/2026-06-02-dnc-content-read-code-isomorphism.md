# DNC↔code isomorphism — first evidence (content read = associative lookup) (2026-06-02)

First test of the hypothesis Emma named (2026-06-02): does a **trained,
soft, differentiable** DNC memory access **defuzz into a clean discrete
op** — i.e. read off as written code? Design:
`planning/exploratory/differentiable-neural-computer.md` § "The point".
Scope here: the simplest case, **content-addressed read**.

**Honest scope.** Host-PyTorch research prototype
(`experiments/dnc/dnc_assoc_recall.py`), NOT a substrate-pure Sutra DNC.
The point is to test whether the β-defuzz bridge yields a clean discrete
addressing at all. The ops (cosine, softmax, matmul) are Sutra's op
family; the defuzzed op is the ram-op `M[argmax_cosine(key)]`.

## Method

Associative recall. Each example: N=8 fresh random (key, value) pairs in
memory; query = a stored key + 0.3·noise; target = that key's value. A
trainable linear controller maps query → read key; the soft read is
`w = softmax(β·cosine(read_key, M_keys))`, `recalled = w · M_values`
("attention" is the weighting **vector** `w`, not a matrix). Train at a
gentle `β=5` (MSE to target), then **defuzz** at `β=50` and compare to the
explicit discrete op `M_values[argmax_cosine(read_key, M_keys)]`. D=16,
3000 steps, **swept over 5 seeds (0–4)**; verdict taken on the worst seed
(no cherry-picking).

## Result (measured, 5-seed sweep min/mean/max)

| metric | min / mean / max |
|---|---|
| trained soft read (β=5) recalled·target cos | 0.898 / 0.901 / 0.903 |
| **defuzz cleanliness** (mean peak weight, β=50) | **0.979 / 0.980 / 0.982** (1.0 = one-hot) |
| **defuzzed-soft row == `argmax_cosine` row** | **100.0% (all 5 seeds)** |
| **defuzzed-soft read · discrete-op read cos** | **0.994 / 0.994 / 0.995** (1.0 = identical) |
| task: `M[argmax_cosine(query)]` == true row | ~93.1% (random 12.5%) |

The result is tight across seeds — not a single-seed fluke.

**The isomorphism holds for content read.** At β=50 the soft addressing
collapses to a near-perfect one-hot (peak 0.979) on the same row the
discrete `argmax_cosine` op selects (100% agreement), and the recalled
vector is numerically identical to the discrete op's output (0.994). So
the learned soft read **reads off as** the associative-lookup ram-op
`value = M[argmax_cosine(read_key)]`. This is the smallest concrete
instance of "a learned differentiable computer whose behavior decompiles
to code", and it follows directly from defuzzification being smooth
(softmax-argmax = cosine-argmax, monotone, so the β→∞ limit is exact).

The 93.1% recall is the **lookup's own accuracy under query noise** (the
discrete op scores identically — the 7% misses are noisy-nearest-
neighbour, intrinsic to a content lookup), **not** a defuzz-fidelity gap.

## Caveats (do not overclaim)

- **Easy case.** Content read = associative lookup is the cleanest op.
  The hard tests of open-Q 7 are *ordered* tasks (copy via temporal
  links) and multi-step algorithms, where a learned policy might defuzz
  to a blurry mixture. This result does NOT establish those.
- **Trivial controller.** The controller is a single linear map; the
  "learning" is mild. A real DNC controller (LSTM + allocation/temporal
  heads) is untested here.
- **Host prototype.** Not substrate-pure (the substrate Sutra-DNC is the
  follow-on if the harder rungs hold). Seed-swept (5), so not a fluke, but
  one architecture/task.

## What it unlocks

This is **weight→code for the simplest memory op**: the W2C decompiler's
job, on a DNC content read, is just "emit `M[argmax_cosine(key)]`". Next
rungs (own experiments): (1) a learned controller that must *transform*
the query non-trivially, to see if the transform stays defuzzable; (2)
add temporal links + the **copy** task — the real test of whether an
*ordered* learned policy defuzzes to a clean sequential
`ramWrite`/`ramRead` program.

## Repro / cross-refs

- `python experiments/dnc/dnc_assoc_recall.py`
- `planning/exploratory/differentiable-neural-computer.md` — design + the
  operation-correspondence table + open Q 7 (isomorphism fidelity).
- `planning/sutra-spec/ram-pointers.md` — the discrete ram-ops the
  defuzzed DNC reads off as.
