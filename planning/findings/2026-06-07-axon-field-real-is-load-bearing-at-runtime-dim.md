# Axon-field `.real()` is load-bearing at the runtime dim (crosstalk); RAM reads are not

**Date:** 2026-06-07
**Context:** Substrate-purity overhaul — attempting to drop `.real()` from the
OCaml transpiler's tuple/record/option field reads. Measured with Ollama serving
`nomic-embed-text` (the embedding model IS available locally — an earlier "Ollama
blocked" claim was a stale remote-container error; corrected).

## What happened

Removed `.real()` from the transpiler's axon field reads (`o.item("f").real()`
→ `o.item("f")`) so the field stays a number-vector. At **full dim (~868)** the
round-trip is clean — a 2-field tuple `_0=10`, `_1=7`, and `_0 + _1` as raw
vectors = **17** (no `.real()`). BUT the fixture **substrate-run** test
(`sutra_compiler --run` at the CLI's default dim) **failed** for `tuple_fst_snd`,
`tuple_local`, `record`: the value came back wrong.

## Why

An axon bundles multiple key→value bindings (sum of permuted rotation-binds).
Reading one field back (`axon_item` = unpermute + unbind) recovers that field's
number on the real axis PLUS crosstalk from the other bundled fields. At low/
default runtime dim the crosstalk is large enough to corrupt the value; at full
dim (~868) it averages out clean. `.real()` sidesteps this by projecting straight
to the real-axis scalar (the host readout) — which is exactly why it was there.

**RAM reads are exempt.** `array_ram` (which reads via `ramRead`, not an axon)
passed without `.real()` — RAM stores one clean number-vector per cell, no
bundling, no crosstalk. (That removal, baa0990c, stands.)

## Conclusion

Dropping `.real()` from axon field reads is NOT a bare `.item()` swap — it needs a
**substrate axon number-decode primitive** that recovers the field's number
cleanly at any dim (e.g. a cleanup/projection that suppresses cross-field
interference), returning a number-VECTOR rather than a host scalar. That is the
real A.0(a)#5 work. Until it exists, the transpiler keeps `.real()` for axon
fields (reverted the removal; fixtures restored). The full-dim cleanliness shows
the decode is feasible; the low-dim crosstalk shows a bare read is not it.

## Process note

This was caught because the fixture suite has a `test_fixture_runs_on_substrate`
case (compile AND run AND compare), not just text-match — running it surfaced the
regression that my full-dim spot-check missed. Run the substrate-run fixtures, not
just a hand probe, when touching transpiler output.
