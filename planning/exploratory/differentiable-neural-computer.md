# Differentiable Neural Computer (DNC) on Sutra — design exploration

> **Status: exploratory (Emma 2026-06-02, "interested but not sure how").**
> Idea not yet tried. This works out *how* a DNC could map onto Sutra's
> substrate and, crucially, how it relates to the (already-built) hard RAM
> pointers. Nothing here is implemented; open questions are marked.

## What a DNC is

The Differentiable Neural Computer (Graves et al., *Nature* 2016) is the
Neural Turing Machine's successor: a neural **controller** coupled to an
external **memory matrix**, where every memory interaction is **soft and
differentiable** so the whole system trains end-to-end by gradient
descent. Over the NTM it adds:

- **Content-based addressing** — a read/write *key* is compared (cosine)
  against every memory row; a softmax gives a soft addressing weight.
- **Dynamic memory allocation** — a *usage* vector + free-list mechanism
  picks the least-used location to write (an allocation weighting),
  letting the controller allocate/free memory like `malloc`/`free`.
- **Temporal link matrix** — a matrix L that records the *order* writes
  happened, so reads can walk memory in written-order (forward/backward),
  not just by content.

The defining property is **differentiability**: reads are weighted sums
over *all* locations, writes are soft erase+add over all locations, and
the addressing weights are smooth functions of the controller's output.

## The crucial reconciliation: DNC memory is NOT the hard RAM pointers

Sutra already has **RAM pointers** (`planning/sutra-spec/ram-pointers.md`):
external host memory, **discrete** round-to-nearest addressing, accessed
as an **I/O device**. Emma's 2026-06-01 decision is explicit: **RAM is not
differentiable** — I/O is outside the differentiable realm.

A DNC's memory is the *opposite* on both axes, and that is fine — they are
**two distinct memory architectures** in the same NTM/DNC family:

| | RAM pointers (built) | DNC memory (this doc) |
|---|---|---|
| Where | external host RAM (I/O device) | **on the substrate** (a VRAM matrix) |
| Addressing | **discrete**, round-to-nearest | **soft** content/allocation/temporal weights |
| Differentiable | no (I/O boundary) | **yes** (the whole point) |
| Trains | the *controller* only | controller **and** memory access, end-to-end |

So a Sutra-DNC does **not** use `ramRead`/`ramWrite`. Its memory lives on
the substrate as a differentiable matrix, and the addressing is soft
attention computed with substrate ops. This is the natural home for
"differentiable memory" precisely *because* Emma put the discrete host
RAM outside the differentiable realm — the DNC is the differentiable
cousin, kept on-substrate.

## Why Sutra is unusually well-suited

A DNC's memory math is *already* Sutra's native mode:

- **Content addressing = cosine + softmax + weighted readout.** Sutra has
  `similarity` / `argmax_cosine` (cosine), `select` (softmax-saturated
  one-hot), `bundle` (superposition = weighted sum), `dot` (inner
  product). A *soft* content read — `softmax(cosine(key, M)) · M` — is the
  same shape as Sutra's cleanup/attractor and `select`, just left *un*-
  saturated. The hardware-friendly fuzzy readout the substrate is built
  on IS the DNC read head.
- **The substrate is autograd-differentiable.** The PyTorch codegen
  target emits tensor ops whose loop runtime is documented "every op is
  differentiable with respect to state, target, threshold"
  (`codegen_pytorch.py`). So a DNC assembled from substrate ops is
  trainable by autograd with no extra machinery — gradients flow through
  the compiled graph (the same property the weight→code corpus exploits
  when it trains matrices *through the compiled substrate matmul*).
- **Recurring substrate state exists.** `recur` (non-halting loops) holds
  vectors/matrices on the substrate across ticks without host extraction
  (`non-halting-loop.md`) — the home for the memory matrix, the usage
  vector, and the temporal link matrix.
- **It is the showcase of the constrain-train vision.** Sutra's direction
  is "every operation back-propagatable from a learned NN"
  (`constrain-train-next-targets.md`; the equality-cosine learned
  threshold is the one shipped instance). A DNC is the natural large-scale
  demonstration: a whole differentiable program with trainable memory.

## Mechanism → substrate mapping (proposed)

State carried in `recur` slots (all VRAM tensors):
- **Memory** `M` : an `N × dim` matrix.
- **Usage** `u` : an `N`-vector (how used each row is).
- **Temporal links** `L` : an `N × N` matrix (write-order).
- **Precedence** `p` : an `N`-vector (last write weighting).
- Per read head: previous read weighting `w_r`; the write head: previous
  write weighting `w_w`.

Per tick, from a controller-emitted interface (keys, gates, modes):
1. **Content weighting** `c = softmax(β · cosine(key, M))` — `similarity`
   row-wise + a soft (un-saturated) `select`/softmax. `β` is a sharpening
   gate.
2. **Write** — allocation `a` from `u` (least-used), blended with content
   `c_w` by an allocation gate, scaled by a write gate → `w_w`; then
   `M ← M ⊙ (1 − w_w ⊗ e) + w_w ⊗ v` (erase + add), all element-wise
   tensor ops.
3. **Usage update** `u ← (u + w_w − u ⊙ w_w) ⊙ ψ` (ψ = retention from
   free gates) — tensor ops.
4. **Temporal links** `L ← (1 − w_w⊕) ⊙ L + w_w ⊗ p`; `p ← (1 − Σw_w)·p +
   w_w` — tensor ops on the `N×N` matrix.
5. **Read** — for each head, mix content `c_r`, forward `L · w_r`, and
   backward `Lᵀ · w_r` by a soft 3-way read-mode gate → `w_r`; read
   `r = w_rᵀ · M` (weighted readout = a `bundle`-shaped sum).
6. **Controller** — a Sutra function mapping (input, prev reads) → the
   interface vector + the output. Trainable (matrices via the
   substrate-matmul GD path).

Every step is element-wise / matmul / cosine / softmax — all existing
substrate op shapes, all differentiable.

## Open questions (do not paper over)

1. **Controller expression.** Is the controller a hand-written Sutra
   function with trainable `load_matrix` weights, or learned end-to-end?
   How is the interface vector (many gates/keys) carved out of the state
   layout — synthetic slots, or a wider semantic block?
2. **`N × N` link matrix at scale.** The temporal link matrix is `O(N²)`
   state. What `N` is feasible on the substrate, and is the sparse-link
   approximation (Graves' follow-up) needed?
3. **Soft vs the snap/cleanup tension.** Sutra often *defuzzifies*
   (`is_true`, `select` saturation). A DNC needs the addressing to stay
   *soft* (un-saturated) for gradients. Where exactly does softness end
   and readout begin? (This is the differentiability boundary the RAM
   pointers sit outside; the DNC sits inside.)
4. **Training harness.** What loss / task drives the gradients, and does
   the existing autograd-through-compiled-substrate path (the w2c
   precedent) carry `N×N`-state DNC graphs without blowing up?
5. **Relation to reservoir computing** (the other parked diversification
   item, `todo.md`): both are "memory + dynamics" architectures; is there
   shared substrate machinery, or are they orthogonal?
6. **Dim audit.** Memory rows are `dim`-wide; a content key needs the same
   width. Model-free numeric DNCs want a small `dim`; an
   embedding-content DNC wants 768. Pick per task (CLAUDE.md dim audit).

## Minimal first experiment (when we try it)

Strip to **content addressing only** (no allocation, no temporal links):
a memory matrix `M`, a soft content read/write, a trainable controller.
Train on the canonical **copy task** (read a sequence in, reproduce it
from memory) — the standard NTM/DNC benchmark — and measure recall
accuracy as `N` and sequence length scale. If the soft read/write trains
through the compiled substrate (autograd), add allocation, then temporal
links. Report the measured recall curve; a negative result (gradients
don't flow / recall stuck) is a finding, not a failure to hide.

## Cross-refs

- `planning/sutra-spec/ram-pointers.md` — the discrete host-RAM I/O
  pointers (the non-differentiable cousin); the differentiability decision.
- `planning/exploratory/constrain-train-next-targets.md` — the
  every-op-trainable vision a DNC showcases.
- `non-halting-loop.md` — `recur` recurring substrate state (the home for
  `M`, `u`, `L`).
- `todo.md` § "Architectural diversification" — NTM/RAM (built), reservoir
  computing (parked), and now DNC (this doc).
