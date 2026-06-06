# Experiment: learning new CPU operations on the constructed scaffold

**Thesis.** Because `transformer-vm`'s analytic weights live in a standard,
differentiable transformer, a CPU operation can be **learned by gradient descent**
as new neurons bolted onto the frozen, correct-by-construction scaffold — then
**crystallized** back to exact weights. This is the constructed+trained hybrid: a
bridge between transformer-vm (programmed) and a DNC (trained), and a concrete step
toward a Completely Neural Computer whose ISA is partly hand-built, partly learned,
and end-to-end differentiable.

**Definition of success (the whole experiment passes if):**
1. SGD recovers a *known* op (chosen so we have an exact oracle) to **100% exactness**
   on all enumerable inputs under hardmax inference.
2. A program using the op as a **single native opcode** (not the compile-time
   lowering) runs through the full transformer and matches the reference trace
   token-for-token (the existing PASS check).
3. The learned op **crystallizes**: its weights snap to the analytic DSL format and
   stay 100% exact with τ→∞ (no soft attention needed) — now indistinguishable from
   a hand-built instruction.

## Why this is well-posed (and not a raw DNC)

The scaffold — fetch (`instruction_position = 5*cursor+1`), decode (`op_dot`/
`is_op`), stack/locals/memory lookups (`fetch`), control flow, commit, carry — stays
**frozen and exact**. We learn only one op's *transfer function*: a leaf on a
known-correct tree. That is a tiny, well-conditioned supervised problem, unlike a
DNC that must discover the whole machine at once.

## Grounding (verified in the repo)

- `model/transformer.py:21` — `VanillaTransformer(nn.Module)`; params are ordinary
  `nn.Module` tensors (`tok`, `attn` in/out proj, `ff_in`, `ff_out` = the ReGLU,
  `head`). We can freeze all and mark only the new op's params `requires_grad=True`.
- `model/transformer.py:41-69` — inference forward is `@torch.no_grad()` and ends in
  `argmax` (hardmax). **Training needs a grad-enabled forward that uses softmax at
  temperature τ** in place of the cache's argmax. (The hull KV-cache is an inference
  optimization; training uses a plain batched softmax-attention forward.)
- `model/weights.py` — builds those tensors analytically from the graph; we load it
  as the frozen init.
- `wasm/interpreter.py` — the op is gated by `is_op("and")`/`op_dot`; a new op must
  honor the existing byte-sequenced I/O contract (pop operands via `stack_top`/
  `stack_second` lookups, push a 4-byte result, set `delta_stack`, advance `cursor`).

## Target ladder (de-risk → prove → novelty)

1. **`i32.and` (de-risk).** Per-byte, **no carry**: `result_byte = a_byte & b_byte`.
   Fully enumerable (65 536 byte pairs). Simplest possible "new op" — validates the
   whole harness (freeze/train split, soft/hard schedule, crystallize) on something
   that can't fail for subtle arithmetic reasons. (`i32.xor` is an equivalent alt.)
2. **`i32.mul` (prove).** Carry-bearing, 4-byte — the convincing case. Exact oracle
   exists (it's currently *lowered* into shifts/adds, so we have ground truth and can
   compare "native learned MUL" vs "lowered MUL").
3. **A genuinely new op (novelty).** The actual goal — an instruction not in WASM,
   chosen with the user (e.g. `popcount`, saturating-add, a byte-permute, or a
   Sutra/Yantra-specific primitive). Same recipe; no lowering to fall back on, so the
   learned op *is* the definition.

## Frozen vs trainable split

- **Trainable:** a small block of new ReGLU neurons (`ff_in`/`ff_out` rows) — and, if
  the op needs cross-byte routing, a small learnable lookup head — implementing the
  op's transfer function, gated by `is_op(<newop>)`. Randomly initialized.
- **Frozen:** every other parameter (all existing ops, fetch, stack/memory, commit).
- Enforced by setting `requires_grad=False` on the loaded analytic params and `True`
  only on the new block.

## Training signal (two stages)

- **Stage 1 — op-local supervision (do first).** Train the new block in isolation on
  the per-byte function over *all* inputs (AND: enumerate 65 536 pairs; MUL: stratified
  + adversarial sampling around carry boundaries 0x00/0xFF/0x80, plus random). Input =
  the operand bytes encoded exactly as the model encodes them; target = the result
  byte (256-way cross-entropy, or MSE on the integer). Clean, fast, fully verifiable.
- **Stage 2 — end-to-end trace supervision (then).** Compile a C program that uses the
  op natively, run it through the grad-enabled forward, and supervise on the output
  trace. Confirms the learned op composes with fetch/stack/commit over many steps.

## The soft/hard schedule (the one real catch)

Hardmax (argmax) attention has no usable gradient. So:
- **Train** with softmax attention at finite temperature τ; **anneal τ upward**
  (curriculum from soft→sharp), optionally straight-through (hard forward / soft
  backward). ReGLU/relu is piecewise-linear → gradients fine.
- **Infer/verify** at τ→∞ (the existing argmax path) and require exactness there. An op
  that's only correct while soft has not actually been learned.

## Crystallization (learn → understand → re-compile)

After training: enumerate the new block's behavior, snap/quantize the learned weights
to exact integer weights in the `reglu`/`persist`/`lookup` DSL, re-verify 100% exact
under hardmax. The op becomes a first-class constructed instruction — *discovered by
gradient, but now exact like ADD*. This is the payoff and what makes the result
permanent rather than an approximate net.

## Metrics & gates

| Gate | Criterion |
|------|-----------|
| G1 op-local exactness | 100% of enumerable/stratified inputs correct at τ→∞ |
| G2 end-to-end | a program using the native op → `wasm-run` PASS vs reference |
| G3 crystallized | exact after snapping to DSL, no soft τ, deterministic |
| G4 frozen integrity | all *other* ops still PASS (no regression from the new block) |

## Risks / unknowns

- **Grad-enabled forward**: the shipped forward is inference-only (no_grad, cache).
  Need a plain batched softmax-attention forward for training — bounded engineering,
  but the first thing to build/verify.
- **Relaxation stability** over multi-step traces (Stage 2) — mitigated by doing
  op-local (Stage 1) first.
- **Crystallization fidelity**: only clean functions snap exactly (AND/MUL are clean).
  A learned op that resists exact snapping tells us something interesting too.
- **Scope/representation**: bytes are integers in dims; bitwise ops may want a frozen
  bit-decomposition feature. Decide whether to expose bits (makes AND trivial) or
  force learning from integer bytes (more convincing). Recommend: force integer-byte
  learning for the demo, so SGD genuinely discovers the function.

## Where it lives

Build the training harness in **`src/learned_ops/`** in this repo (next to the
replication, reusing the submodule's torch model). The eventual *productized* hybrid
graduates to its own project (Sutra/Yantra). Code is gated on user approval of this
design — nothing implemented yet.

## Findings so far (2026-06-05)

Two results from the first build reshaped the target choice:

1. **Bitwise AND is not learnable from raw integers by SGD (spectral bias).**
   Training `i32.and` op-local from the two integer operand values plateaus ~23%
   exact and crawls. The low result bits are the highest-frequency functions of the
   inputs (`bit0(a&b) = [a odd]&[b odd]`, a period-2 square wave over 0..255), and
   MLPs are low-frequency-biased. Exact-match needs zero errors across 524 288
   bit-decisions. This is meaningful — it's *why* the paradigm constructs weights
   rather than training them.

2. **The architecture has no runtime bit decomposition.** `lower.py` only handles
   bitwise ops against a *compile-time constant* mask (per-bit, statically); runtime
   `a & b` of two variables is unsupported (except a boolean `select` special-case).
   So integration would NOT rescue AND — the within-byte spectral wall persists. The
   scaffold deliberately avoids runtime bitwise ops.

3. **Learnability depends on op nature × output representation.** Arithmetic ops are
   *value-natured* and **low-frequency**: e.g. unsigned saturating add
   `min(a+b,255) = a+b - relu(a+b-255)` is piecewise-linear (one ReLU) and exactly
   representable, so it learns to bit-exactness when output as a **value** (regress
   the byte), not as 8 thresholded bits (which re-introduces the LSB parity wall).
   The scaffold itself represents bytes as values — so arithmetic ops are its natural
   learnable extensions; bitwise ops are not.

**Retarget:** make **saturating arithmetic** (the user's E4 north star) the first
learned op — value-output, low-frequency, scaffold-natural, and a genuinely new
instruction. AND is kept as a documented negative result.

## Phases (→ queue.md)

- **E0** — grad-enabled softmax-attention forward over the loaded analytic weights;
  prove it reproduces the argmax forward at high τ on an existing op (sanity).
- **E1** — freeze/trainable split + op-local trainer; learn `i32.and` to G1.
- **E2** — crystallize AND to exact DSL weights (G3); confirm G4 (no regressions).
- **E3** — repeat E1–E2 for `i32.mul` (carry); add the native MUL opcode end-to-end (G2).
- **E4** — pick the novel op with the user; learn + crystallize it; write up findings.
