# Multi-program axon-passing demo

Two `.su` programs in this directory exchanging an axon vector
through a serialized wire format.

```
producer.su        builds a 5-key axon, exposes make_state()
   │
   │  np.save(state_vec)  ←  the boundary
   │
   ▼
consumer.su        receives the vector, exposes recover_animal/color/user
                   (each does one axon_item read; two of producer's
                    five keys are never referenced)
```

## Run it

```
python examples/multi_program_axon/_run.py
```

Expected output:

```
[4/4] Consumer recovers three keys from the wire-passed axon:
      recovered animal_2 vector L2=2.1386
      recovered color_1  vector L2=2.1386
      recovered user_1   vector L2=2.1386

Monitoring: cosine recovered vs correct filler vs decoy
------------------------------------------------------------
    animal_2: cos(recovered,    'dog') = +0.4001   cos(recovered, 'octopus') = +0.2004   margin = +0.1997   [OK]
     color_1: cos(recovered,    'red') = +0.4031   cos(recovered, 'violet') = +0.2052   margin = +0.1979   [OK]
      user_1: cos(recovered,  'alice') = +0.4498   cos(recovered, 'xavier') = +0.1859   margin = +0.2639   [OK]

RESULT: PASS — recovered vectors match producer-bundled fillers
        with positive cosine margin over not-bundled decoys.
        The wire-passing mechanism works end-to-end.
```

## What the demo proves

**Two separately-compiled `.su` programs can exchange substrate state
through a serialized wire format and the receiver can extract the
keys the sender bundled.**

Specifically:

1. `producer.su` is compiled to one Python module that owns its own
   `_TorchVSA` runtime instance.
2. `consumer.su` is compiled to a *different* Python module with its
   *own* `_TorchVSA` instance. The two modules never share Python
   state.
3. The producer builds a 5-key axon vector via `axon_add` and returns
   it. The orchestrator pulls it to CPU and writes it to a `.npy`
   file — that's the wire format, the *only* thing crossing the
   process-equivalent boundary.
4. The consumer module loads the `.npy`, hydrates it back into a
   torch tensor on its device, and runs `axon_item` reads for three
   of the five keys.
5. Host-side cosine analysis (per CLAUDE.md "numpy at the monitoring
   boundary is allowed") confirms each recovered vector is closer
   to the correct producer-bundled filler than to a never-bundled
   decoy filler.

Both programs declare the same embedding model in `atman.toml`
(`nomic-embed-text`, dim 768). That's how the consumer's
`embed("animal_2")` produces the same basis vector as the producer's
`embed("animal_2")` — and therefore the same rotation operator used
to bundle and unbundle the entry.

## What the demo does NOT prove (yet)

**Lazy materialization across boundaries.** Per
[`planning/sutra-spec/axons.md`](../../planning/sutra-spec/axons.md)
§ "Lazy evaluation across boundaries", the spec's claim is that
*only the keys the receiver references should actually materialize
on the wire.* The consumer here reads three keys; producer bundles
five. Lazy materialization would skip the two `axon_add` calls
producer makes for `animal_1` and `color_2` because consumer never
references them, dropping the wire's noise floor.

This MVP transmits the full bundle.

The next iteration would be a compiler pass that:
1. Walks the consumer's `axon_item` calls to collect referenced keys.
2. Rewrites the producer's `make_state` body to only call `axon_add`
   for those keys.
3. Emits a smaller bundle on the wire — same correctness, less
   work and lower wire size.

That's whole-program analysis across the import boundary. The
import machinery for it landed earlier today (`sdk/sutra-from-ts/`
inlines imports at lower-time); a Sutra-side equivalent of the
analysis is the natural follow-on.

## Important caveat about what this demo is using as fillers

This demo uses **LLM embeddings** (nomic-embed-text basis vectors
for `"dog"`, `"red"`, `"alice"`, etc.) as the axon fillers. That is
the **worst case** for axon capacity — twelve 768-d structured
embeddings squeezed into a single 868-d bundle is a high-crosstalk
regime, and an earlier draft of this file with 12 keys did fail
on cat/dog disambiguation as a consequence.

**For OS-shaped Sutra IPC (Yantra and similar), this is NOT
representative of the real wire payload.** Embeddings are
expensive; you don't pass nomic vectors around between system
processes. The IPC currency is:

- **Strings** as `AXIS_STRING_FLAG`-marked codepoint arrays —
  most of the vector is zero, content lives in the synthetic
  block. See `planning/sutra-spec/strings.md`.
- **Numbers** as complex hypervectors at `AXIS_REAL` /
  `AXIS_IMAG` / `AXIS_TRUTH` — three non-zero positions out of
  ~100 synthetic dims. See `planning/sutra-spec/types.md`.

Both filler types live in the synthetic block, away from the
semantic-block region where bundled embeddings crosstalk. The
capacity behavior is qualitatively different and much friendlier
than what this LLM-embedding demo shows. Don't take the cat/dog
12-key cap as the rule for OS-style axons — it's the worst case,
not the typical case.

A follow-on demo using strings and numbers as the fillers would
better reflect the actual OS-IPC use case.

## Why the wire format is `.npy` and not torch's `.pt`

Both work. `.npy` was picked because:
- It's host-portable (numpy is everywhere; torch isn't always).
- It's the smallest possible artifact — just the raw float32 buffer
  plus a tiny header.
- A future cross-language consumer (Rust, C, etc.) reads `.npy`
  trivially; `.pt` requires the torch runtime.

For an in-process axon hand-off (no actual cross-program), the
wire format collapses to a tensor reference and no serialization
is needed. The point of *this* demo is to exercise the boundary,
which is why we deliberately go through disk.

## Files

| File | Purpose |
|------|---------|
| `producer.su`  | Builds the 5-key axon, exposes `make_state()`. |
| `consumer.su`  | Reads three keys, exposes three `recover_*` functions. |
| `atman.toml`   | Embedding-model config shared by both programs. |
| `_run.py`      | Orchestrator: compiles both, threads the vector through `.npy`, verifies recovery. |
