# OS-shaped multi-program axon demo

Companion to the all-vector-fillers demo (`_run.py` /
`producer.su` / `consumer.su`). This one exercises the **realistic
OS payload shape** per Emma 2026-05-10:

> "My expectation is that it's going to be usually one embedding
> maximum that comes in as an input. Maybe two, maybe two or three,
> typically in this case. … Most programmes will be just typically
> relying on classifying an embedding or something like that."

The wire payload here is one input embedding plus several scalar
and string metadata fields:

```
producer_os.su        builds an axon with:
   user     : "alice"   (string)
   tag      : "search"  (string)
   priority : 7         (int)
   retries  : 0         (int)
   query    : embedding of "find recent files about cats"
   │
   │  np.save(state_vec)   ← the boundary
   │
   ▼
consumer_os.su        reads three of five keys:
   recover_user  → string
   recover_priority → int
   recover_query → vector
                     (skips `tag` and `retries`)
```

## Run it

```
python examples/multi_program_axon/_run_os.py
```

Expected output (passes end-to-end):

```
[4/4] Consumer recovers three of five keys:
  user      -> 'alice'                       (expected 'alice')
  priority  -> 7.0                            (expected 7)
  query     -> cos(recovered, correct)=+0.2789, cos(recovered, decoy)=+0.0905, margin=+0.1884

RESULT: PASS — strings, numbers, and embedding all round-tripped
        cleanly through the OS-shaped axon wire format.
```

## What this demo proves on top of the vector-only one

The vector-only demo (`README.md`) proved cross-program wire-passing
of a single filler type works. This one proves **the typical OS
payload shape works**: mixed strings, numbers, and one embedding
keyed together, recovered per-key by a separately-compiled
consumer.

Specifically demonstrated:
- **Strings** as axon fillers round-trip cleanly through the per-
  key permutation path that landed 2026-05-10 (commit `6d25f232`).
- **Small integers** as axon fillers round-trip exactly. `recover_priority`
  returns the exact bundled value (7), not the cross-key collision
  that pre-permutation-fix gave.
- **One embedding** mixed with metadata round-trips with positive
  cosine margin against a decoy, *after* the embedding is scaled
  to match the metadata's magnitude regime.

## The scale convention you have to know about

Per-component magnitudes don't match across filler types:

| Filler type | Per-component magnitude |
|-------------|-------------------------|
| Embedding (nomic, normalized)  | ~0.03 typical |
| ASCII codepoints (string)      | 32–127 |
| Small integers / floats        | 0–1024 |

If you bundle them naively, the high-magnitude metadata's crosstalk
into the embedding's recovered axes swamps the embedding's own
signal. Empirically the cosine margin against a decoy collapsed to
+0.002 for a naive 1×-scaled embedding bundled with metadata, vs
+0.19 with the embedding scaled by 100×.

The convention this demo uses: **multiply embeddings by 100 before
adding to a mixed axon**:

```sutra
a.add("query", make_query() * 100.0);
```

Cosine is scale-invariant, so the consumer doesn't need to undo
this — it just compares cosines. The scaling only changes which
filler dominates the bundle's L2 norm, and the goal is for the
embedding to dominate (or at least be comparable to) the metadata
so its recovered signal isn't washed out.

This is an application-level convention — the runtime doesn't
auto-scale. A future enhancement could normalize each filler to
unit norm before bind+permute and let the magnitudes be implicit,
but that's a separate change to `axon_add`.

## Files

| File | Purpose |
|------|---------|
| `producer_os.su`  | Builds the OS-shaped axon (5 keys, 3 types). |
| `consumer_os.su`  | 3 `recover_*` functions for `user`, `priority`, `query`. |
| `atman.toml`      | Embedding-model config shared by both programs. |
| `_run_os.py`      | Orchestrator + verification + scale-aware decode. |

## What this demo does NOT cover

- **Lazy materialization**: still not implemented. The full 5-key
  bundle crosses the wire; producer doesn't yet prune the unread
  `tag` / `retries` keys at compile time.
- **Big numbers** (file sizes, timestamps, ports): the demo uses
  small ints to avoid crosstalk into string codepoint positions.
  Production OS payloads need either a chunked encoding (split a
  64-bit integer across multiple 16-bit synthetic axes) or per-
  filler normalization. Logged for follow-on.
- **Many-strings axons**: `string_to_python` over-reads in a
  multi-string bundle (crosstalk codepoints in the tail). The
  orchestrator works around it by reading exactly the expected
  length per string. A length-aware string decoder is the proper
  fix.
- **Type-aware return values**: `recover_priority` is declared
  `function int recover_priority(...)` in Sutra source but at
  runtime returns a vector. The orchestrator calls
  `vsa.real(...)` to extract the scalar. A future codegen pass
  can auto-insert this for `int` / `float` return types.
