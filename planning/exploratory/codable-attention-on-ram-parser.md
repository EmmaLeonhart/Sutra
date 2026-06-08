# Codable attention-on-RAM parser — design doc (NTM-archetype track)

> **Status: design, pre-implementation (Emma's reframed vision, 2026-06-08).**
> This is the design doc the queue's NTM track names as the prerequisite to
> the reframed build ("WRITE A DESIGN DOC first; don't implement what's not
> fully understood"). It works out *what* a codable attention-on-RAM parser is,
> *how* it relates to the artifacts we already have (the reduced `transformer-vm`
> core and the substrate `mini_wasm_machine`), and the Python→OCaml→Sutra path.
> Open questions are marked; nothing here is built yet.

## 0. Naming discipline (read first)

This is **NOT a Differentiable Neural Computer and NOT a Neural Turing Machine.**
Those are *trained, differentiable, recurrent* systems and serve only as
*inspiration*. What we build is a **handcrafted, constructed-weight attention
mechanism that reads/writes a RAM device** — codable by hand, deterministic.
It sits in the same Turing-completeness *ballpark* as an NTM (one of the three
archetypes: RNN / reservoir / NTM-with-external-memory) but is not labelled one.
See [[project_ram_editing_nn_framing]] and the percepta-ntm paper §0–§1, which
already establish this framing; do not contradict them. The trained/differentiable
counterpart lives in `differentiable-neural-computer.md` — that is a *different*
artifact (the SGD-grown future), explicitly not this.

## 1. What "attention on RAM" means, concretely

A single attention head is:

```
scores_i = (q · k_i) / sqrt(d)        # query against each key
weights  = softmax(scores)            # (transformer-vm uses hardmax, HARD_K=1e10)
output   = Σ_i weights_i · v_i        # weighted aggregate of the values
```

"Attention **on RAM**" means the keys `{k_i}` and values `{v_i}` are not a fixed
context window — they are **cells of a RAM region** (the tape), and the query `q`
addresses into that region. The output is a **content- or location-addressed read**
of memory, exactly as the `transformer-vm` uses attention for addressing into its
residual-stream-as-memory (stack / locals / linear memory / instruction cursor).

This is the through-line to the reduced core: the PCA work
(`2026-06-06-pca-wasm-transformer.md`) measured that the genuine attention is
**42 head-slots across 5 layers** (`[7,5,11,11,8,0,0]`), and the re-pack
(`2026-06-07-pruned-transformer-repack-reduced-core.md`) built a model with
exactly those heads, output-identical on 8/8 inputs. A *single* such head,
isolated and pointed at a RAM tape, **is** the minimal attention-on-RAM unit.
We are not inventing a new mechanism — we are isolating one head of a machine
we already reduced.

## 2. The first step: linear regression over memory

Per Emma ([[project_ram_editing_nn_framing]]), the first concrete attention-on-RAM
task is a **simple linear regression** — *not* the final mechanism, the first step.

The connection is exact. Drop the softmax (or take the linear/identity attention
limit) and the head's output is a **plain weighted sum of values read from RAM**:

```
output = Σ_i a_i · v_i        with a_i fixed by the constructed query/key geometry
```

That is a linear functional of the RAM contents — i.e. **linear regression over
memory**. The "parse" the first artifact performs is the simplest possible one:
*scan a tape of values in RAM and aggregate them into one output via a fixed linear
read*. Concrete candidate tasks, smallest first:

- **`sum_tape`** — RAM holds `[x_0 … x_{n-1}]`; the head attends uniformly and
  outputs `Σ x_i`. (Attention weights all equal → the value projection is the
  identity → output = sum. This is the degenerate, easiest-to-construct case.)
- **`dot_tape`** — RAM holds `[x_0 … x_{n-1}]`; a fixed coefficient vector `[w_i]`
  is baked into the query/key geometry; output = `Σ w_i x_i`. This is literally
  evaluating a linear model `ŷ = w·x` by attention over RAM — "linear regression."
- **`select_field`** — location-addressed read: query encodes an index `j`; the
  head attends to cell `j` (hardmax) and outputs `x_j`. The minimal *parse*
  (extract one field from a structured record in RAM).

`sum_tape` and `select_field` together are the two attention regimes the
`transformer-vm` actually uses (uniform/aggregate and hard location-addressing);
`dot_tape` is the linear-regression headline. All three have **hand-constructed
weights** — no training — which is the whole point of "codable."

## 3. Why "identical in structure" to the transformer-vm

Emma's constraint: the thing must be *identical in structure* to Percepta's
`transformer-vm`, just doing simple parsing instead of full WASM execution. We
honour this by **reusing the transformer-vm's own construction primitives**, not
writing a bespoke attention from scratch:

- Same residual-stream-as-memory convention (a fixed-width stream of cells).
- Same Q/K/V/out_proj attention block shape (the head we keep is one of the 42
  the re-pack already isolated).
- Same hardmax addressing primitive for location-addressed reads (`select_field`).
- Same constructed-from-a-graph methodology (the weights are *computed*, not fit).

The difference is scope: the transformer-vm schedules a whole WASM interpreter onto
133 nominal heads × 7 layers; our parser schedules **one parsing operation onto one
head** (plus, later, a few). It is a *strict structural sub-instance* of the machine
we already have — that is what makes it "identical in structure" and what makes the
reduction (§5) the honest validation lever.

## 4. The Python → OCaml → Sutra path

Emma named "Python→OCaml" explicitly. The pipeline, end to end:

1. **Python reference** (`experiments/attention_on_ram/`, numpy/torch). Constructs
   the one-head attention-on-RAM parser and runs the §2 tasks. This is
   compile/analysis on constructed weights, **off any Sutra runtime hot path** —
   allowed under CLAUDE.md §"Numpy: compile and monitor only". It is *not* a Sutra
   program; it is the reference oracle.
2. **OCaml port** (`WASM/iso/ocaml/`-style, or a new `attention_on_ram.ml`). The
   same parser written as imperative OCaml that reads/writes an array (the RAM tape)
   and computes the attention aggregate with explicit loops. This is the
   "Python→OCaml" conversion: the *same computation*, expressed in a language the
   Sutra frontend already ingests.
3. **Sutra substrate** via the existing `sdk/sutra-from-ocaml/` transpiler →
   `.su` → `codegen_pytorch` → the substrate. The OCaml→Sutra frontend already
   lowers arrays→RAM (`ramRead`/`ramWrite`), `while`→`loop`, tuples, records, and
   the bitwise/arithmetic stdlib — the exact primitives the
   `mini_wasm_machine.su` capstone used. The attention aggregate is a
   **reduction over RAM cells** (a `loop` accumulating `Σ a_i·v_i` from
   `ramRead`), which is structurally the same shape as the verified memory-counter
   loop in `mini_wasm_machine.su`.

The artifact thus lands **next to** `mini_wasm_machine.su` as a second substrate
machine — the difference being that this one's compute is an *attention read*, not
an opcode dispatch.

## 5. Reduction is the through-line (the validation methodology)

Per [[project_ram_editing_nn_framing]]: "gradually expand the PCA so the model
keeps passing the SAME tests at the SAME level across many Python and OCaml code
examples, while shrinking to the smallest size we can reasonably reach."

So the method is **behavioral-equivalence-under-shrinking**, not a one-shot build:

- Maintain ONE test set: `(input RAM tape) → (expected output)` for the §2 tasks.
- The test set must pass **identically in Python AND OCaml** (and eventually
  Sutra) — the same inputs, the same outputs. This is the cross-language oracle
  (the same discipline the WASM isomorphism uses: transformer ≡ reference ≡ OCaml,
  byte-identical).
- Grow the example set over time; shrink the attention core as far as it still
  passes. The reduction lever is the **schedule** (how many heads/dims the parse
  actually needs), not SVD of the weights — the PCA finding already proved
  magnitude-truncation breaks this class of machine (1e10 hardmax amplifies any
  perturbation; `2026-06-06-pca-wasm-transformer.md` §"What is NOT reducible").

A `sum_tape` or `dot_tape` parser plausibly needs **one head, soft (linear)
attention, low dimension** — far below the transformer-vm's 38-d residual stream.
Measuring *how small* it goes while holding the tests is the deliverable.

## 6. What is understood vs. what is open

**Understood (safe to build):**
- The attention math and the RAM-tape representation (§1).
- The linear-regression-as-linear-attention reduction (§2) — this is algebra.
- The constructed-weight methodology (reuse transformer-vm's, §3).
- The OCaml→Sutra landing path — the frontend + `ramRead`/`ramWrite` + `loop`
  reduction are all already verified by `mini_wasm_machine.su`.

**Open (resolve before/while building, do not paper over):**
- **O1 — soft vs hard attention on the substrate.** Hardmax (`HARD_K=1e10`)
  saturates and is not differentiable; the substrate's fuzzy ops may not represent
  it cleanly. `sum_tape`/`dot_tape` need only *linear* attention (no softmax), which
  is a plain weighted sum and almost certainly fine. `select_field` needs
  hard location-addressing — measure whether the substrate `eq_synthetic`/truth-axis
  dispatch (which the `mini_wasm_machine` opcode dispatch already does at gap +2.0,
  `2026-06-06-iso5-mini-wasm-machine-runs-on-substrate.md` §"Signal-separation")
  is the right primitive for it, or whether a softmax-on-substrate is needed.
- **O2 — the aggregate as a substrate reduction.** `Σ a_i·v_i` over N RAM cells is a
  `loop` accumulating `ramRead`s. The `mini_wasm_machine` host-drives one `step()`
  per instruction; an attention aggregate wants the sum *inside* the substrate. Need
  to confirm a single substrate `loop` can carry the running accumulator (the v1
  one-slot-`recur` limit, `non-halting-loop.md`) — the memory-counter loop suggests
  yes for a scalar accumulator; a vector accumulator may need more.
- **O3 — exact starting parse task.** `sum_tape` is the trivial floor; `dot_tape`
  is the linear-regression headline; `select_field` is the minimal structural parse.
  Recommend building in that order. **Confirm with Emma if `dot_tape` is the right
  "linear regression over memory" she means**, since that phrase is hers and carries
  design intent ([[feedback_never_invent_thing_emma_implies_exists]]).
- **O4 — does the construction reuse the re-packed 42-head core, or a fresh
  one-head construction?** Reusing a literal head from `repack_reduced.py` keeps
  "identical in structure" maximally true but drags in transformer-vm's 38-d stream;
  a fresh one-head construction is smaller but is a *new* construction. Lean: start
  fresh-but-isomorphic (same block shape, minimal dim), then show it's the limit the
  reduction of a real head converges to.

## 7. Not in scope (explicit negatives)

- **No training / no SGD** in this artifact. The weights are constructed. SGD-grown
  memory operations are a *later, optional* direction (percepta-ntm paper §7 "seed");
  not this doc.
- **Not a DNC / NTM** — see §0.
- **No new substrate primitive without measurement.** If the aggregate or the
  hard-addressing doesn't compose (O1/O2), the gap is "expose/verify a primitive",
  not "substitute a host-side variant" (CLAUDE.md §"When Emma gives an algorithmic
  explanation"). Measure on the substrate; do not declare blocked from the armchair.

## 8. First concrete steps (when this doc is greenlit)

1. `experiments/attention_on_ram/reference.py` — constructed one-head linear
   attention; implement `sum_tape` + `dot_tape`; a small `(tape → output)` test set.
2. `attention_on_ram.ml` — the OCaml port; assert the *same* test set passes
   byte-for-byte against the Python reference.
3. Transpile the OCaml → `.su` via `sdk/sutra-from-ocaml/`; run on the substrate;
   verify the same test set substrate-to-substrate (decoded output == expected,
   measured — not "ran"). Resolve O1/O2 with measurements here.
4. Write the reduction finding: smallest dim/head count that still passes, measured.

Cross-refs: [[project_ram_editing_nn_framing]],
[[feedback_never_invent_thing_emma_implies_exists]]; findings
`2026-06-06-pca-wasm-transformer.md`,
`2026-06-07-pruned-transformer-repack-reduced-core.md`,
`2026-06-06-iso5-mini-wasm-machine-runs-on-substrate.md`; paper
`paper/percepta-ntm/paper.md`; `differentiable-neural-computer.md` (the
trained/SGD counterpart, distinct from this).
