# Did the host-Python-string bug affect the NeurIPS submission?

**Date:** 2026-05-10
**Trigger:** Emma's question after reading the chronology doc:
*"I'm hoping to God that this didn't get into the NeurIPS
submission."*
**Answer:** It didn't. Detail below.

## What the NeurIPS paper actually claims about strings

The paper describes a **codebook + nearest-string boundary
model** — and that model was correct throughout. From
`paper/neurips/paper.md`:

> "A Sutra program's inputs and outputs are embeddings in the
> substrate's vector space; **a compile-time codebook handles
> string literals at the source level and nearest-string lookup at
> the output boundary**."

> "every string literal in `.su` source is embedded once at compile
> time … decoded at the program output via `nearest_string`."

The path the paper claims runs entirely through the substrate:

1. Source string literal `"hello_world"` → compile-time
   `basis_vector("hello_world")` → an embedding sitting in the
   codebook.
2. The program manipulates the embedding (cosine, argmax,
   bind/unbind, bundle) — all substrate ops.
3. At the output boundary, `nearest_string(result_vector)` decodes
   the closest codebook entry back to a host string.

The "host string at the output" step is the **monitoring boundary**
explicitly permitted by `CLAUDE.md` § "Numpy: compile and monitor
only." Decoding the substrate result back to a printable string at
the program's edge is the correct shape.

## What the bug actually was

The bug fixed in commit `895e7a78` is on a **different code path**
that the paper does not describe and does not depend on:

- The 2026-05-08 `strings.md` spec introduced a **codepoint-array
  string model** — `make_string(s)` puts codepoints in synthetic
  axes with `AXIS_STRING_FLAG` set, giving a lossless round-trip
  for strings that doesn't go through the embedding/codebook layer.
- This model was specified but not actually wired into the
  string-literal emission path. String literals stayed as host
  Python `str` values when the destination was `string`-typed.
- Today's fix wires the destination-type-driven `make_string`
  coercion at function-call args, return statements, and variable
  declarations.

**Nothing in `paper/neurips/paper.md` claims the codepoint-array
path exists.** The paper is about the codebook model. The
codepoint-array path is a 2026-05-08 addition that came AFTER the
paper's content was set, and that the paper doesn't reference.

## What `hello_world.su` (the smoke test cited by SKILL.md) does

`paper/neurips/supplementary/SKILL.md` asserts:

```
got=$(PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/hello_world.su 2>&1 | tail -1)
[ "$got" = "hello world" ] || { echo "FAIL: hello_world got '$got'"; exit 1; }
```

That program (`examples/hello_world.su`) is a pure codebook program:

```sutra
vector greeting = basis_vector("hello_world");
vector v_hello = basis_vector("hello_world");
vector v_goodbye = basis_vector("goodbye");
map<vector, string> PHRASE_NAME = {
    v_hello: "hello world",
    v_goodbye: "goodbye",
    ...
};
function string say() {
    vector winner = argmax_cosine(greeting, [v_hello, v_goodbye, v_question]);
    return PHRASE_NAME[winner];   // codebook decode at the boundary
}
function string main() { return say(); }
```

Every `basis_vector(...)` call is compile-time embedding — substrate
path. The `argmax_cosine` is a substrate op. The
`PHRASE_NAME[winner]` is the codebook decode (the `_vector_map_lookup`
runtime helper); the return value at that step is a host Python
string and that's correct — it's the monitoring boundary the paper
calls out as the exit edge.

The bug never affected this program because there is no `string`-
typed parameter being called with a string literal anywhere in the
chain. `main()` returns the result of `say()`, which is a host
string from a codebook decode, and returning it as a host string
is the correct boundary shape.

**Verified post-fix:** `python -m sutra_compiler --run
examples/hello_world.su` prints exactly `hello world`. SKILL.md's
smoke check passes.

## Where the April 30 workaround sits in the timeline

| Date | Commit | Event |
|------|--------|-------|
| 2026-04-10 | `217ecf9d` | Codegen scaffolding. `StringLiteral` → host Python `str`. The intended boundary was always the codebook decode (`_vector_map_lookup`). String literals stayed as host strings as map-value content, which is what the codebook expected. |
| 2026-04-30 | `b285dc0b` | Workaround: `'hello world' * 0.0` was raising TypeError because the return-statement codegen blindly emitted `return value * _program_halt`. Fix: skip the halt-multiply for `string`-typed returns. The fix accepted "strings are host Python at the return boundary" — which was already the design and is consistent with the paper's monitoring-boundary story. |
| 2026-05-07 | `ea6f8a01` | NeurIPS paper frozen via CLAUDE.md update. The paper's string story (codebook + nearest_string) was the only story; the codepoint-array model didn't exist yet. |
| 2026-05-08 | (strings.md first cut) | New model added: codepoint-array strings via `make_string`. Implementation lagged. The new model coexisted with the codebook model; the codebook model continued to work and the paper continued to be correct. |
| 2026-05-10 | `895e7a78` (today) | Coercion fix for the codepoint-array model's wiring. Paper claims unaffected because they were never about this path. |

The April 30 workaround was 7 days before the NeurIPS submission
freeze. It's "in" the submitted code. But it didn't break anything
the paper claimed — it just acknowledged that string returns flow
through the monitoring boundary as host strings, which is exactly
what the paper says they do.

## Direct answer to Emma's anxieties

1. **"On April 10, we added this as our way of returning things
   when we were using the argmax cosine thing instead of the
   database."** Correct hypothesis. The `_vector_map_lookup` /
   nearest_string path was always the substrate-going-to-host
   boundary for strings. String literals stayed host because they
   were map-keys / map-values being compared by cosine, not values
   being substrate-encoded as content.

2. **"April 30 must be something related to the clawRxiv deadline.
   I'm hoping to God that this didn't get into the NeurIPS
   submission."** The April 30 workaround predated the NeurIPS
   freeze by 7 days, so it IS in the submitted code. But it didn't
   break any paper claim — it accepted the paper's monitoring-
   boundary story explicitly. No correction to the NeurIPS
   submission is needed.

3. **"On the 8th… 'to produce a String value construct one through
   the string class.' I'm very confused about that."** The 2026-05-08
   spec doc introduced a NEW second string model (codepoint array)
   that the paper doesn't reference. The doc was prescriptive but
   the implementation didn't follow, creating the spec drift the
   user now correctly diagnoses as "legacy weirdness, partially
   removed but ended up getting wired back into stuff."

4. **"I don't think it would be a security risk, but it's currently
   a spec drift risk."** Correct read. It's spec drift, not a
   correctness or security failure. The drift is what today's
   commit `895e7a78` closes.

## What's left to do (none of it is paper-blocking)

- The fix has documented residue (class field initialization with
  literals, post-declaration assignment). Tracked in the chronology
  doc. These are smaller and not paper-blocking.
- Long-term reconciliation between the two string models
  (codebook embeddings vs. codepoint arrays) is a real spec
  question for the post-NeurIPS-paper revision. Right now both
  models exist; the codebook model is what the paper claims and
  what end-user programs use; the codepoint-array model is what
  the OS-shaped axon work needs. They should be unified or at
  least clearly delineated.

The NeurIPS submission stands as-is. No erratum needed for the
bug fixed today.
