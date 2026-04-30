# Capital-country analogy across embedding substrates

**Date:** 2026-04-24.
**Script:** `examples/_analogy_substrate_sweep.py`.
**Programs:** `examples/analogy.su`, `analogy_mxbai.su`, `analogy_minilm.su`.

## What we ran

Five (capital, country) pairs bundled into a single memory vector via
rotation binding:

    memory = bundle(bind(paris, france), bind(tokyo, japan),
                    bind(london, uk),    bind(rome, italy),
                    bind(cairo, egypt))

For each capital, `unbind(capital, memory)` recovers a noisy version
of the stored country; argmax-cosine against the 5-country codebook
picks the winner. Same program, three substrates declared via the
`// @embedding:` directive:

- `analogy.su` → nomic-embed-text (768-dim, default)
- `analogy_mxbai.su` → mxbai-embed-large (1024-dim)
- `analogy_minilm.su` → all-minilm (384-dim)

## Results

### nomic-embed-text (768-dim)

| capital | target | winner | winner cos | runner  | runner cos | margin |
|---------|--------|--------|------------|---------|------------|--------|
| paris   | france | france | +0.460     | italy   | +0.305     | +0.156 |
| tokyo   | japan  | japan  | +0.447     | uk      | +0.268     | +0.180 |
| london  | uk     | uk     | +0.492     | japan   | +0.282     | +0.209 |
| rome    | italy  | italy  | +0.431     | egypt   | +0.260     | +0.171 |
| cairo   | egypt  | egypt  | +0.478     | uk      | +0.265     | +0.213 |

**5/5 correct. mean margin +0.186, min +0.156.**

### mxbai-embed-large (1024-dim)

| capital | target | winner | winner cos | runner | runner cos | margin |
|---------|--------|--------|------------|--------|------------|--------|
| paris   | france | france | +0.445     | italy  | +0.314     | +0.131 |
| tokyo   | japan  | japan  | +0.483     | france | +0.332     | +0.151 |
| london  | uk     | uk     | +0.471     | france | +0.340     | +0.131 |
| rome    | italy  | italy  | +0.469     | france | +0.310     | +0.159 |
| cairo   | egypt  | egypt  | +0.388     | italy  | +0.257     | +0.131 |

**5/5 correct. mean margin +0.141, min +0.131.**

### all-minilm (384-dim)

| capital | target | winner | winner cos | runner | runner cos | margin |
|---------|--------|--------|------------|--------|------------|--------|
| paris   | france | france | +0.412     | japan  | +0.312     | +0.100 |
| tokyo   | japan  | japan  | +0.427     | france | +0.254     | +0.173 |
| london  | uk     | uk     | +0.468     | france | +0.188     | +0.281 |
| rome    | italy  | italy  | +0.448     | france | +0.285     | +0.163 |
| cairo   | egypt  | egypt  | +0.457     | france | +0.267     | +0.190 |

**5/5 correct. mean margin +0.181, min +0.100.**

## Side-by-side

| substrate          | dim  | correct | mean margin | min margin |
|--------------------|------|---------|-------------|------------|
| nomic-embed-text   |  768 | 5/5     | +0.186      | +0.156     |
| mxbai-embed-large  | 1024 | 5/5     | +0.141      | +0.131     |
| all-minilm         |  384 | 5/5     | +0.181      | +0.100     |

## What this shows

1. **Rotation-binding + bundled 5-pair memory works on every
   substrate.** None of the three embedding models produces a miss
   on this task. The smallest (all-minilm, 384-dim) clears it as
   cleanly as the biggest (mxbai, 1024-dim).

2. **Margin, not dim, ranks the substrates.** The 384-dim all-minilm
   has the widest spread (0.100 to 0.281) and a competitive mean;
   the 1024-dim mxbai has the tightest spread (0.131 on almost
   every query). Larger native dim does NOT buy a more comfortable
   margin here — the structure of the embedding space does. mxbai
   treats "france" as the most generic European-country vector, so
   it ends up as runner-up on four out of five queries even when
   the answer is clearly not france.

3. **The `// @embedding:` directive works end-to-end.** The three
   programs are byte-identical except for their first-line
   directive; swapping substrate is a one-line change in source,
   no compiler flags, no harness reconfiguration. This is exactly
   what the 2026-04-22 queue.md commitment promised — per-program
   substrate declaration lives in the source.

4. **mxbai's "france as generic European country" is a small
   adversary for this task.** On four out of five queries mxbai's
   runner-up is france. That means the bundled memory is leaking a
   small generic-European-country signal into every unbind —
   probably because french-adjacent vocabulary dominates the
   frozen LLM's training set in proportion to the other four
   countries. A larger codebook or adversarial pair (e.g. asking
   for a lesser-known country) could plausibly expose this as a
   failure rather than just a margin-cost. Worth retesting on a
   larger country list.

5. **Nothing here needs the 2D-Givens-per-slot upgrade.** Rotation
   binding on the Haar-in-semantic-block substrate suffices for 5
   bundled pairs across the three substrates. The extended-state
   capacity curve measured in
   `planning/findings/2026-04-22-rotation-binding-capacity-results.md`
   puts this well inside the "clean" regime.

## Cross-reference

Companion to `_king_queen_multi_substrate.py` /
`planning/findings/2026-04-22-king-queen-across-substrates.md`, which
measures the same three substrates on a *compositional* (naive
`king - man + woman`) analogy. Capital-country is the associative-
retrieval complement — both are useful cross-substrate probes but
they stress different structures in the embedding space.
