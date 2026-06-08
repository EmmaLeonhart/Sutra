# Open question: axon string fillers don't round-trip (collapse to first codepoint)

**Opened:** 2026-06-08 (from the OCaml non-numeric-record-fields attempt).
**Status:** RESOLVED 2026-06-08 (Emma, AskUserQuestion) — **strings are NOT axon fillers.**
Axon fillers are numbers/vectors only; strings are passed as separate codepoint-array
values, not stored inside axons. The round-trip "failure" (`item("k")`→72='H') is therefore
**by design**, not a bug. Consequence: string record fields (OCaml/TS) stay UNSUPPORTED;
the axon vision/docs are updated so fillers = numbers/vectors. Option (d) of the four below
was chosen. Keeping this doc as the record; no further action beyond the doc/memory updates.

## The question

Should an axon round-trip a **string filler**, and if so, by what mechanism? Today it
does not: `a.add("k", "Hi"); a.item("k")` runs on the substrate and returns **72.0** —
the codepoint of `'H'`, the first character — not `"Hi"`. Measured raw (single-field
axon, so NOT bundle crosstalk; finding
`2026-06-08-ocaml-nonnumeric-record-fields-blocked-axon-string.md`).

## Why each side has force

- **Strings should be fillers.** The axon-as-IPC-currency design and
  [[project_axon_ipc_payload_is_strings_and_numbers]] state axon fillers are "string-flag
  codepoint arrays + complex-hypervector numbers" — i.e. strings are an intended payload.
  `axons.md` describes `add`=bundle+bind / `item`=unbind generically over fillers, not
  "numbers only." On this reading the collapse-to-first-codepoint is a **bug**.
- **Maybe numbers/vectors only, by mechanism.** `bind`/`unbind` is a rotation; a String is
  a multi-codepoint array spread across synthetic axes, and a single rotation may not
  preserve that structure the way it (approximately) preserves a single real-axis number
  (which `realvec` then cleans). On this reading, string fillers need a **different
  storage** (e.g. store the string un-rotated under the key, or a per-codepoint scheme),
  and the current behavior is a **scoped limitation** until that's designed.

## What would close it

Emma's call on the intended mechanism: (a) strings should round-trip and the fix is at the
axon/substrate layer (how a codepoint-array filler survives `bind`/`unbind`), or (b) string
fillers are out of scope for now (document the limit; OCaml/TS string record fields stay
UNSUPPORTED), or (c) a specific encoding (store string fillers without rotation, keyed
directly). Until then, numeric record fields are the supported scope; the transpiler pieces
(field-type-aware read, string param/return inference) are easy and sit on top of whichever
mechanism (a)/(c) lands.

## Pointers

- Finding: `planning/findings/2026-06-08-ocaml-nonnumeric-record-fields-blocked-axon-string.md`
- Spec: `planning/sutra-spec/axons.md` (add/item = bundle+bind / unbind), `strings.md`.
- Numeric analogue: `planning/findings/2026-06-05-axon-field-reads-need-real-projection.md`.
