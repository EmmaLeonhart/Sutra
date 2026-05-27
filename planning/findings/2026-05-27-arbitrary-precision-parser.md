# 2026-05-27 — Arbitrary-precision (calc): parse_int2 ships substrate-pure; the carry loop is the open piece

## Result summary

The first piece of the arbitrary-precision (calc) thread — a 1-2
digit substrate parser — ships and runs substrate-pure:

```
parse_int2("47") → tensor(47., device='cuda:0')
```

The harder piece — a Sutra accumulator loop that propagates carry
across an unbounded-length digit array — is **NOT** built today
because (a) the substrate has the soft-halt loop primitive, but
(b) representing a multi-digit number as a tensor of digit slots
plus carry propagation as a tensor-pure update is a design exercise
that has not yet landed, and (c) the queue.md item explicitly flags
"likely needs a Sutra-side primitive." Building without that design
would be implementing what isn't 100% understood — a HARD RAILS
violation.

This is the honest first cut, not the full feature.

## What ships

`examples/parse_int2.su`:

```sutra
function int parse_int1(Character c) {
    return c.string_char_at(0) - 48;
}

function int parse_int2(String s) {
    int d0 = s.string_char_at(0) - 48;
    int d1 = s.string_char_at(1) - 48;
    return 10 * d0 + d1;
}

function int main() {
    String s = String.make_string("47");
    return parse_int2(s);
}
```

Compiles via `translate_module` (PyTorch codegen), runs on CUDA,
result is a 0-d torch tensor `47.` (no host scalar leak). All
primitives used are existing substrate ops:

- `String.string_char_at(s, i)` — index-select + saturating mask
  per `codegen_pytorch.string_char_at` (Audit REAL LEAK #5 was fixed
  here previously; emits no host branch / raise).
- Subtraction of the constant 48 — number-axis tensor op.
- Multiplication by the constant 10 — number-axis tensor op.
- Vector add — substrate op.

No new primitives needed for parse_int2.

## What's blocked for the carry loop

The full arbitrary-precision goal needs:

1. **Multi-digit representation.** A natural shape: a sequence of
   digits, one digit per "slot" of an axon-keyed bundle, or one
   digit per synthetic axis of a number vector (cap depends on
   `synthetic_dim`). The String encoding already proves that
   axis-packed sequences work on the substrate; reusing that layout
   for a digit array is a candidate, but Strings are typed and
   intended for character codepoints — a number-typed sibling
   ("DigitArray" or similar) keeps the typing honest.

2. **Per-position digit addition with carry.** Given two N-digit
   numbers `a = [a_0, ..., a_{N-1}]` and `b = [b_0, ..., b_{N-1}]`
   little-endian, the carry chain is:

   ```
   carry_0 = 0
   sum_i = a_i + b_i + carry_i
   digit_i = sum_i mod 10
   carry_{i+1} = sum_i / 10  (integer div)
   ```

   The `mod 10` and the `div 10` are substrate ops (the `modulus.su`
   library has `rotation_mod` / `fmod` and an integer-division path
   would lift), but the LOOP structure — read prior position, compute,
   write current position — needs either:
   - a tensor-shaped "scan" primitive (associative-scan / prefix-sum
     style, which avoids the sequential dependency), or
   - the existing soft-halt loop accumulating state across positions
     (which is sequential and pays N substrate-loop iterations for
     N digits).

   Neither lands today.

3. **What primitive might be needed.** A `digit_array` substrate
   type whose addition op is the carry chain compiled into a single
   tensor scan. Without the scan primitive the operation runs
   sequentially through the substrate loop, which is correct but
   slower than the tensor budget would prefer. The "likely needs a
   Sutra-side primitive" flag in queue.md is referring to this:
   either expose `digit_array_add(a, b)` as an intrinsic that the
   runtime implements as an associative scan, or accept the
   sequential cost and use the existing soft-halt loop.

## Why I'm stopping here

Per CLAUDE.md HARD RAILS: "Don't implement what you don't 100%
understand — write spec/queue item instead." The design choice
between the two paths above (scan-primitive vs. sequential-loop)
materially affects the spec and the runtime ABI. Picking either
without Emma's sign-off would either (a) ship a sequential-loop
implementation that performs poorly and gets re-written later, or
(b) ship a scan-primitive intrinsic that hard-codes a runtime
representation Emma hasn't approved.

The right next step is a `planning/open-questions/` dossier on the
digit-array representation and the add-with-carry primitive choice.
After Emma picks a direction, the implementation is bounded: ~one
session per direction.

## What this is NOT claiming

- NOT a claim that parse_int2 is "arbitrary precision." It is
  fixed-width (2 digits).
- NOT a claim that the carry loop is impossible on the substrate;
  the soft-halt loop CAN run it, just sequentially.
- NOT a claim that the choice between scan-primitive and
  sequential-loop is obvious — both are defensible; both have costs.
- NOT a regression. parse_int2 lands as the bounded first piece
  and stays in the corpus; the carry-loop piece is the next concrete
  open obligation.

## Reproduction

```bash
python -c "
import sys
sys.path.insert(0, 'sdk/sutra-compiler')
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module
with open('examples/parse_int2.su') as f: src = f.read()
toks = Lexer(src).tokenize()
mod = Parser(toks).parse_module()
ns = {}
exec(translate_module(mod), ns)
print(ns['main']())  # tensor(47., device='cuda:0')
"
```

## Cross-refs

- `queue.md` § "Formal verification — next concrete work" #2
- `examples/parse_int2.su`
- `planning/sutra-spec/strings.md` (the axis-packed-sequence layout
  the digit-array idea would adapt)
- `sdk/sutra-compiler/sutra_compiler/stdlib/modulus.su` (mod/div primitives)
- `planning/sutra-spec/control-flow.md` (soft-halt loop, the candidate
  sequential implementation path)
