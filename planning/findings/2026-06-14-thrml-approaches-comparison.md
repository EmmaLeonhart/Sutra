# Sutra → thrml: head-to-head comparison of the A–G approaches (queue.md H)

**Date:** 2026-06-14
**Status:** synthesis of the measured A–G exploration (Emma 2026-06-14: "implement
each distinct system, then compare all"). Every number below is measured on real
thrml (JAX-CPU); the per-attempt detail + method is in
`planning/open-questions/2026-06-13-sutra-to-thrml-mapping.md` and the runnable
demos under `experiments/thrml/`. This doc decides what to standardize on.

## The shared substrate (settled)

A Sutra value = an **N-bit spin register** (`SpinNode`s); a Sutra op = a **factor**
over those spins; the result is recovered by **block-Gibbs sampling**. This held
across every op tried (memory, bind/unbind, arithmetic, composed programs). The
A–G axes below are the *distinct ways* to make that work.

## The seven approaches, measured

| # | Approach | What it is | Best measured | Decode | Verdict |
|---|---|---|---|---|---|
| A | **Sample-and-verify** | op = constraint factors; sample; keep the sample satisfying the relations | adder 1.000; AND 1.000; 2×2 mult 1.000 (best-of-S); bidir add/sub 1.00/0.92 | host verifier over samples | **General method.** Universal gate set (AND+XOR+adder) → any Boolean circuit. ROBUST to a wrong-signed landscape. |
| B | **Ground-state decode** | proper-signed gadgets → answer is the strict global min; read min-energy/modal, NO verifier | multiplier 1.000 (min-energy & modal) | min-energy / modal | Cleaner decode (no verifier) **but requires correct gadget signs** — it surfaced a real XOR sign bug A had masked. |
| C | **Trainable couplings** | LEARN factor weights by contrastive divergence (`estimate_kl_grad`) | AND learned 1.000; rediscovered the analytic gadget signs | (depends) | The **constrain-train link**. Learns ops from data instead of hand-deriving; compounds with F. |
| D | **Categorical encoding** | value = one `CategoricalNode` (K states); op = a K×K factor | unary fn lookup 1.000 | modal | **Lookup-table-native.** Best for small-domain maps/tables (1 factor vs a circuit); cost O(K²). |
| E | **Joint-EBM composition** | multi-op program as ONE model, single run, no host hand-off | kv-query 1.000 @ balanced ratio | modal | Removes the host-readout boundary (purity) **but balance-sensitive** (non-monotonic, narrow window). |
| F | **Structured codes** | orthogonal (Hadamard) patterns vs random | clean to M=8 vs random ~M=2 (~4× capacity) | retrieval | Real ~4× associative-capacity lever; plain Hebbian degenerates at M=N (a learned rule, C, goes further). |
| G | **codegen_thrml** | the compiler backend: `.su` → thrml program | bind 1.000; round-trip `unbind(bind(a,b),a)=b` 1.000 | self-verify | **Productionized.** Additive `--emit-thrml`, non-destructive, 4/4 tests. Lowers bind/unbind op-graphs today. |

## Cross-cutting trade-offs

- **Decode: verifier (A) vs ground-state (B) vs learned (C).** A works even when
  the energy landscape is imperfect (it just needs the answer *reachable*, which
  is how the XOR sign bug hid for a while); B needs the answer to be the strict
  global min but then needs no host verifier; C sidesteps hand-derivation entirely.
- **Temperature.** Shallow ops want cold β (sharp); deep composed circuits want
  WARM β to mix into the global-min basin, then a verifier (A) or a correct
  ground-state (B). Naive staged annealing (B1) FAILED — annealing was unnecessary
  once gadget signs were right + β warm.
- **Composition: staged (robust) vs joint (pure).** Staged host hand-off (#5) is
  robust 100%; joint-EBM (E) is one substrate program with no readout boundary but
  only in a narrow balance window.
- **Encoding: bit-register (circuit-native) vs categorical (table-native).**
  Arithmetic/wide values → bit-registers; small-domain maps → categorical.
- **Hand-built vs learned couplings (C) and codes (F) compound** — learning beats
  the Hebbian rule's M=N degeneracy.

## Recommendation — what to standardize on

1. **Default lowering = bit-registers + sample-and-verify (A).** It is the
   general method (universal gates → arbitrary circuits), robust, and the one the
   codegen (G) already targets. Make it the `--emit-thrml` default.
2. **Use ground-state decode (B) as the verifier-free fast path** where the op's
   gadget is sign-correct and the answer is the strict global min (logic gates,
   small circuits) — cheaper decode, no host pass.
3. **Categorical (D) for small-domain unary maps** (one K×K factor beats a circuit).
4. **Structured codes (F) + trainable couplings (C) for associative memory** when
   capacity matters — F for the ~4× orthogonal-code gain, C to learn past the
   Hebbian degeneracy and to realize the constrain-train vision.
5. **Composition: prefer staged (robust); reach for joint-EBM (E) only when
   readout-purity is the goal** and you can tune the balance.

## Open / deferred (non-blocking)

- codegen G coverage: `bundle` + `unbind`+cleanup (needs a codebook-cleanup
  decode) and `==`/AND gadget lowering — deferred design points.
- **Hardware-alignment notes** (queue.md): which of the above map cleanly onto
  Extropic TSU semantics; what stays host (compositor, verifier) vs sampled.
- The FV-in-Lean item (queue.md, autonomous-last) will formally prove the B-style
  ground-state claims (answer = strict global min) that this doc measured.
