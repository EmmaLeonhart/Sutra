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

## Differentiability is the access *method*, not RAM-vs-substrate

The earlier "RAM is not differentiable" framing (2026-06-01) was about a
specific **method** — the hard single-index, round-to-nearest pointer that
`ramRead`/`ramWrite` implement. That method isn't differentiable (a
discrete index has no gradient). But **differentiable RAM access is
possible** (Emma 2026-06-02): a *soft* method — read a region of RAM
cells onto the substrate and weight them by `softmax(cosine(key, cells))`
— is fully differentiable. The non-differentiable thing was the
round-to-nearest *method*, not RAM the store.

So the real axis is the **addressing method**, and it is somewhat
orthogonal to where the memory lives:

| Access method | Differentiable? | Used by |
|---|---|---|
| Hard single-index, round-to-nearest | no (discrete index) | `ramRead`/`ramWrite` (built) |
| **Soft attention** (weighted over cells) | **yes** | a DNC; *differentiable RAM access* |

A DNC uses the **soft** method. Its memory can be an **on-substrate
matrix** (the first thing to build — simplest), or equally **host RAM
contents read onto the substrate** and soft-attended (differentiable RAM
access). Either way the addressing is soft `softmax(cosine)` weighting
computed with substrate ops, trained end-to-end. The built `ramRead`/
`ramWrite` (hard index) remain the discrete-I/O method for when you want
an exact addressed cell, not a gradient.

## Why Sutra is unusually well-suited

A DNC's memory math is *already* Sutra's native mode:

- **Defuzzification is smooth — there is no internal gradient boundary
  (Emma 2026-06-02).** Sutra's defuzzification *polarizes* (sharpens
  along a target axis) but stays smooth and differentiable; it never
  binarizes. So `select`/`is_true` and friends are differentiable too —
  gradients flow through them. **DNC-based components are simply
  *smoother*** (gentler polarization). There is no point where "softness
  ends," so a Sutra-DNC is differentiable **end-to-end** with no internal
  boundary to manage. The only non-differentiable thing nearby is the
  hard single-index round-to-nearest *method* (`ramRead`); a DNC uses the
  soft attention method instead (differentiable — over an on-substrate
  matrix or RAM contents read onto the substrate; see above). The
  polarization strength (β) is just a dial: the font glyph renderer
  cranks it high for an exact bitmap; a DNC dials it gentle to keep
  addressing diffuse.
- **Content addressing = cosine + softmax + weighted readout.** Sutra has
  `similarity` / `argmax_cosine` (cosine), `select` (smooth polarized
  softmax), `bundle` (superposition = weighted sum), `dot` (inner
  product). A content read — `softmax(β · cosine(key, M)) · M` — is the
  same smooth op family as Sutra's cleanup/attractor and `select`, just
  with a gentler β. The fuzzy cosine readout the substrate is built on IS
  the DNC read head.
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
   row-wise + a gentle-β (diffuse) `select`/softmax — smooth, not
   saturated to one-hot. `β` is the sharpening dial.
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
3. **Polarization strength (β) tuning — NOT a differentiability
   boundary.** Resolved framing (Emma 2026-06-02): defuzzification is
   smooth, so there is no soft/defuzz gradient boundary — `select` etc.
   are differentiable, the DNC just uses gentler β. The real question is
   the *practical* one: what β keeps addressing diffuse enough for stable
   gradients yet sharp enough to recall a specific cell, and does it need
   to anneal over training? (Tuning, not a boundary to manage.)
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

- `planning/sutra-spec/ram-pointers.md` — the hard single-index
  round-to-nearest method (`ramRead`/`ramWrite`, non-differentiable *by
  method*); soft attention over RAM contents would be the differentiable
  alternative.
- `planning/exploratory/constrain-train-next-targets.md` — the
  every-op-trainable vision a DNC showcases.
- `non-halting-loop.md` — `recur` recurring substrate state (the home for
  `M`, `u`, `L`).
- `todo.md` § "Architectural diversification" — NTM/RAM (built), reservoir
  computing (parked), and now DNC (this doc).
