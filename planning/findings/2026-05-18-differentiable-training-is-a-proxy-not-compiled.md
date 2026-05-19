# 2026-05-18 — §3.6 differentiable training trains a hand-reimplementation, not the compiled graph

**Status: integrity finding / claim-vs-evidence gap. Surfaced to
Emma; paper NOT edited pending her decision (pre-submission).**

Emma asked, plainly: is the §3.6 classifier appropriate, or did we
either describe it wrong or implement something unrelated to the
language? Investigated against source. The honest answer: it is
**not unrelated**, but the paper **overstates** it.

## Verified facts (read, not assumed)

- `experiments/differentiable_training.py` imports only
  `json, os, sys, torch, torch.nn.functional, ollama`. It does
  **not** import the Sutra compiler, does **not** parse/compile
  any `.su`, does **not** use `codegen_pytorch`.
- It **hand-reimplements** the primitives in plain PyTorch:
  `fuzzy_and = (a+b+ab-a²-b²+a²b²)/2`, `fuzzy_or = (a+b-ab+a²+b²-a²b²)/2`,
  `fuzzy_not = -a`; `classify_batch` is hand-written torch.
- `codegen_pytorch.py` (≈line 2193) emits the **same** Lagrange
  polynomials. The script's math is algebraically **identical** to
  what the compiler emits → it is a *faithful proxy* of the
  compiled forward pass's op-set. (Caveat: faithful *by
  inspection* only — the script's docstring cites stale line
  numbers "963-964" and there is **no automated parity test**
  binding the script to codegen output.)
- No `.su` fuzzy-rule trainable classifier is compiled and trained
  anywhere. `examples/classifier.su` is a different program
  (bundle-prototype + argmax, no fuzzy AND/NOT, no learnable
  params, no training).

## Verdict

- **Not a "random unrelated experiment."** It exercises Sutra's
  exact fuzzy-logic polynomial math. Emma's worst-case fear is
  unfounded.
- **The paper overstates it.** These claims are NOT supported by
  the artifact as implemented:
  - Abstract: "PyTorch autograd flows through **the compiled
    graph** end-to-end".
  - §3.6 L521: "This experiment isolates gradient flow through
    **the compiled symbolic graph**".
  - §3.6 L591–592: "backprop reaches every learnable parameter
    through **the same compiled graph that runs at inference**".
  - §3.6 L456–460: "the compiled graph supports standard
    `loss.backward()` … a fuzzy-logic classifier built entirely
    from Sutra operations" — the ops match Sutra's; the *graph*
    is not the compiler's output.
  What is actually demonstrated: gradient descent through the
  **exact polynomial operations the compiler emits**, re-expressed
  directly in PyTorch — a proxy, not a compiled `.su` trained
  end-to-end. "without any modification to the symbolic source"
  is misleading: there is no Sutra source in the loop.
- Prior assistant edits (the n=5 pass, the §3.6 framing sentence,
  the abstract) **reinforced** the overstatement. Owned.

## Resolution options (Emma's call — not executed)

1. **Reword to exactly what's shown** + state plainly it is a
   faithful PyTorch proxy of the compiler-emitted ops, not a
   compiled-program run. Lowest effort; makes the paper accurate;
   the (weaker) claim still has value. Also fix the stale codegen
   line-ref and ideally add a parity test so "exact ops the
   compiler emits" is enforced, not asserted.
2. **Make the strong claim true**: compile an actual `.su`
   fuzzy-rule classifier through the real pipeline and train *that*
   graph. Strongest, real engineering, must not be faked.
3. **Demote/cut §3.6** if neither the strong claim nor the weaker
   one earns a headline.

Do not silently amend. CLAUDE.md: spec/impl disagreement →
resolve explicitly; negative results required.

## Deeper result (2026-05-18, Stage-A probe): the compiled graph is non-differentiable as emitted

Probed the real PyTorch codegen with a minimal `.su`
(`rule(x,own,other) = similarity(x,own) && !similarity(x,other)`),
generated + executed the emitted Python, ran a grad test:

- Emitted `_TorchVSA.similarity` (codegen_pytorch.py ~L1133):
  `return float(_torch.dot(a,b) / (na*nb + tiny))`. The bare-dot
  variant (~L1160) also `float()`s.
- Calling the emitted `rule(...)` with `requires_grad` tensor args
  returns a **Python `float`** (`requires_grad=None`, no
  `grad_fn`); `.backward()` impossible. The Lagrange fuzzy-AND
  polynomial is then evaluated in host float arithmetic.

Implications:
1. The §3.6 proxy was not merely an unused shortcut — the real
   compiled path **cannot be trained as emitted**. The paper's
   "autograd flows through the compiled graph end-to-end / the
   same compiled graph that runs at inference" is contradicted at
   the implementation level, not just over-described.
2. `similarity` collapsing to `float()` while used *inside* a
   composed op also violates the project's own substrate-purity
   invariant (CLAUDE.md NO MATH SHORTCUTS: "scalar extraction
   inside an operation breaks the invariant"). Distinct from the
   legitimate monitoring/accessor `float()`s (promise/component
   reads) which are not inside another operation.

Consequence for Stage A: making the strong claim true requires a
**compiler change** — emit a substrate-pure, tensor-returning
`similarity` (and likely `eq`/`==` when composed) so composed
expressions stay autograd-friendly — fully test-gated. This is
load-bearing (changes a core primitive's return semantics; ripple
risk to callers/printing/defuzzify/tests) and is pre-submission.
Harness-side monkeypatching of `similarity` would be faking the
result and is explicitly rejected. Surfaced to Emma for an
explicit go-ahead on the compiler-semantics change before doing
it.
