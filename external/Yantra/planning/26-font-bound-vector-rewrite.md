# 26 — Font rewrite: per-character bound-vector, drop the 25-way inner switch

**Status:** queued; cycle demo (Emma 2026-05-27) shipped on the old renderer
first. This is the follow-up.

**Trigger:** Emma 2026-05-27, looking at the font demo:

> I just feel like it's, I feel like you might be doing you. I don't
> understand how there would be so much branching in it.
> ...
> A 20,000-thing switch is just, it's just, it's not.

She's right. The current `apps/font/font.su` design pays **~22,500 inner-select
branches per keypress**. That is not "the cost of substrate purity" — it is
a switch-as-lookup-table antipattern. The substrate has a clean primitive for
this (rotation-binding); the current code reaches past it.

## What the existing design does

`glyph_pixel(x, y, char_code)` is two nested defuzzified selects:

1. **Outer 36-way select** over `char_code`: picks one of `bit_A(pos)` ..
   `bit_9(pos)` (where `pos = y*5 + x`).
2. **Inner 25-way select** inside each `bit_<C>(pos)`: picks the lit/unlit bit
   at position `pos` for character `<C>` from a hardcoded 25-element list.

Per cell: 36 × 25 = 900 inner-select branches (every `bit_<C>` evaluates all
25 of its branches because defuzzified select computes every branch — that's
the whole point of substrate dispatch). Per keypress (25 cells): 22,500.

The inner 25-way switch is the antipattern. A 25-bit lookup table should be
*one bound value*, not a 25-way switch over scalars.

## The bound-vector design

Each character is a **single bundle of rotation-bindings**, one binding per
position. The position acts as the role; the lit/unlit marker acts as the
filler. To read the bit at (x, y), unbind the corresponding position vector
from the glyph bundle and check cosine similarity to the lit marker.

```sutra
// Position basis vectors — 25 distinct rotation roles, one per cell.
vector p_00 = basis_vector("font_pos_00");
vector p_01 = basis_vector("font_pos_01");
...
vector p_24 = basis_vector("font_pos_24");

// Lit / unlit markers — fillers.
vector LIT   = basis_vector("font_lit");
vector UNLIT = basis_vector("font_unlit");

// Each glyph is a single bundle of 25 bindings.
vector glyph_A = bundle(
    bind(p_00, UNLIT), bind(p_01, LIT), bind(p_02, LIT), bind(p_03, LIT), bind(p_04, UNLIT),
    bind(p_05, LIT),   bind(p_06, UNLIT), ..., bind(p_24, LIT)
);
... glyph_B, glyph_C, ..., glyph_9 ...

// Outer 36-way select — pick which glyph by char_code. SAME pattern as
// today's glyph_pixel outer, just over glyph bundles instead of bit_<C> calls.
function vector lookup_glyph(scalar char_code) {
    scalar s_A = 0.0 - 1000.0 * (char_code - 65.0) * (char_code - 65.0);
    ...
    return select([s_A, s_B, ..., s_d9], [glyph_A, glyph_B, ..., glyph_9]);
}

// Per-cell: unbind the position from the picked glyph, then similarity to LIT.
function vector glyph_pixel(scalar x, scalar y, scalar char_code) {
    vector glyph = lookup_glyph(char_code);
    vector pos = lookup_position(x, y);   // 25-way select over (x, y) → p_NN
    vector bit_vec = unbind(pos, glyph);
    // Return similarity to LIT, lifted onto the real axis. Fuzzy: ~1 for lit,
    // ~0 for unlit, with rotation-binding noise at the 25-item capacity.
    scalar sim = cosine_similarity(bit_vec, LIT);
    return make_real(sim);
}
```

**Per-cell cost:**

- 1 outer 36-way select (36 branches over scalars + 36 vector picks) — same
  as today's outer.
- 1 inner 25-way select (`lookup_position`) — 25 branches over scalars + 25
  vector picks. This is the cost we couldn't get rid of: scalar `(x, y)` →
  vector `p_NN` requires *some* switch. **But the inner select is now over
  the SAME 25 position vectors for ALL 36 characters**, not 36 separate
  25-way switches per character. We pay 25 once per cell, not 25 × 36.
- 1 unbind.
- 1 cosine_similarity.

**Total per cell:** ~36 + 25 + 2 = ~63 ops. **Per keypress (25 cells):
~1,575 ops.** That's **~14× fewer than the current 22,500**.

Could go further by having the host loop over the 25 positions outside
the substrate (so the inner `lookup_position` select happens 25 times total,
not per cell) — but that's the same shape `render_glyph` already has, just
moved one level out. Marginal improvement, optional.

## What's fuzzy and what's exact

Today: `glyph_pixel` returns *exactly* 0.0 or 1.0 in float64 because the
defuzzified select uses softmax-saturation with exp(-1000) underflowing to
literal 0. Test tolerance is `1e-9`.

After rewrite: `glyph_pixel` returns the **cosine similarity to LIT** of an
unbound vector. With 25 items bound into a 768-d vector, the lit cells
return cos ≈ 1.0 minus binding-capacity noise; the unlit cells return cos
≈ 0.0 plus noise. Realistic measurement gap: maybe 0.7 between lit and
unlit on average, but with outliers.

**Test tolerance changes from `1e-9` to ~`1e-1`.** That's a real semantic
shift in what the test asserts. The host can still threshold to 0/1 for
display (`np.where(field > 0.5, 1.0, 0.0)`), but the substrate output is
genuinely fuzzy.

This is the Sutra philosophy — fuzzy by default, defuzzification is a
deliberate choice. The current code defuzzifies inside the substrate via
softmax-saturation; the rewrite defuzzifies via cosine threshold on the
host display layer (or substrate `is_true` if we want it truly substrate-
pure).

## Risks and unknowns

1. **Rotation-binding capacity at N=25 in 768-d.** Need to measure
   empirically. The Sutra paper covers width-k bundle decoding at small k;
   25 is bigger. If the noise floor is too high (say lit and unlit overlap),
   the design fails.
2. **`basis_vector(...)` is an Ollama embedding call.** 25 position vectors
   + LIT + UNLIT = 27 Ollama calls at module load. Cached after, but a fresh
   compile is slower. The 36 glyph bundles are computed from those, not
   embedded.
3. **`cosine_similarity` and `make_real` interaction.** Need to verify
   `make_real(cosine_similarity(...))` lifts the scalar similarity to a
   real-axis vector that the existing `step()` recurrent shape can consume.
4. **Existing tests break.** `test_font.py` asserts `1e-9` tolerance per
   cell. The rewrite makes those tolerances impossible. Either:
   - Loosen them to ~`1e-1` (acknowledging fuzziness).
   - Threshold the field via `is_true` in `glyph_pixel` to keep the 0/1
     contract; tolerance becomes "after threshold, exact." That's substrate-
     defuzzification, not host-defuzzification — feels cleaner.

## Plan when this gets done

1. **Write `apps/font/font_bound.su` as a parallel file** — do not touch
   `font.su`. Both compile.
2. **Write a smoke test** — one glyph (`A`), one cell, end-to-end through
   the new path. Measures actual cosine_lit vs cosine_unlit on this machine.
   If the gap is < 0.3, stop and rethink.
3. **If smoke passes, expand**: all 36 glyphs, all 25 cells, measured
   accuracy vs the font oracle.
4. **Decide defuzzification path**: substrate `is_true` threshold inside
   `glyph_pixel` (keeps 0/1 contract), or host threshold in `render_glyph`
   (clean separation).
5. **Plumb into `font_demo.py`** behind a `--bound` flag — old path still
   works while the new one is bedded in.
6. **Switch the default once stable**, retire `font.su` + `bit_<C>` family
   (delete; this is vibe-coded project, legacy paths cause more harm than
   benefit per Sutra's CLAUDE.md).
7. **Update the cycle_step demo** — `cycle_step` itself is unchanged
   (operates on `char_code`, doesn't care how `glyph_pixel` is implemented).

## Updated urgency after the 2026-05-27 dim drop (planning/27)

Once the font demo dropped from runtime_dim=768 to 8 (commit `e22c80a`,
96× per-op cost cut), the per-render latency improved but did NOT
collapse:

  measured 2026-05-28: render_glyph() takes ~2540 ms/call at dim=8
  (single-threaded, ~0.4 fps).

The 96× tensor-work reduction translated to only ~4-6× wall-clock
because the bottleneck is Python→torch dispatch overhead per substrate
op, not the tensor math itself. Each keypress dispatches ~22,500
substrate ops sequentially (25 cells × 36 outer × 25 inner =
22,500 selects) and pays the per-op Python/torch overhead 22,500 times.

So the bound-vector rewrite remains worthwhile: collapsing the inner
25-way switch to a single bind/unbind drops the dispatch count per cell
from ~900 to ~37, a ~24× reduction in dispatch overhead. The bigger
win (batching the 25 cells into ONE substrate call) is still upstream-
blocked on Sutra-side batched `make_real`.

## ❌ Measured-negative result for the bind(p, LIT)/bind(p, UNLIT) encoding (2026-05-28)

The first version (`tools/generate_font_bound_su.py` → `apps/font/font_bound.su`)
encoded each glyph as `bundle(bind(p_NN, LIT_or_UNLIT) for cell in 25)`. Smoke
test (compile + render 'A' + measure cosine-to-LIT per cell, compared to the
font oracle):

| `runtime_dim` | lit-cell cos mean | unlit-cell cos mean | min_lit - max_unlit gap |
|---|---|---|---|
| 16  | 0.194 | 0.160 | **-0.483 (overlap)** |
| 32  | 0.195 | 0.307 | **-0.840 (overlap)** |
| 64  | 0.169 | 0.224 | **-0.446 (overlap)** |
| 128 | 0.179 | 0.223 | **-0.295 (overlap)** |
| 256 | 0.217 | 0.194 | **-0.227 (overlap)** |

Even at dim=256, individual unlit cells return cosine ~0.35 to LIT while
some lit cells return cosine ~0.12. **There is no threshold that recovers
the oracle bit pattern.**

Why this fails: the bundle crosstalk is BIASED toward whichever filler
appears more often in the encoding. Glyph 'A' has 14 lit + 11 unlit cells,
so the bundle has a slight LIT-direction bias; when you unbind any
position, you get LIT direction + crosstalk noise from the other 24
bindings, swamping the per-cell signal.

**Two corrections to try next (separate ticks):**

1. **Antipodal filler.** Use a single MARKER basis vector; encode lit cells
   as `bind(p, MARKER)` and unlit cells as `bind(p, -MARKER)` (or via a
   negation primitive — Sutra must expose vector negation; check the
   stdlib). Crosstalk averages to ~0 instead of biasing toward LIT.
   STILL UNTRIED.

2. **Sparse-only-LIT encoding.** Only bind lit cells into the bundle;
   omit unlit. Unbinding a missing role returns noise ~0; unbinding a
   present role returns approximately MARKER. Gap is then `~MARKER_cos`
   vs `~0`, clean separation. (Same shape as `axon_item` in echo.su /
   the Sutra rotation_hashmap example.)
   **MEASURED-WORKING 2026-05-28 — see § below.**

Both reduce crosstalk by changing what the bundle stores, not its size.
Capacity is still ≤25 items per glyph; the dim just needs to support that
binding count cleanly, not to make a biased encoding work.

## ✅ Sparse-only-LIT encoding works at runtime_dim ≥ 384 (2026-05-28)

After the first encoding failed, the generator was switched to emit only
`bind(p_NN, LIT)` for lit cells (no UNLIT bindings at all; UNLIT stays a
basis-vector declaration only for the antipodal variant to use later).
Measured cosine separation across all 36 glyphs (`A..Z, 0..9`, all 25
cells each, 900 samples total):

| `runtime_dim` | lit_mean | lit_min | unlit_mean | unlit_max | gap |
|---|---|---|---|---|---|
|  16 | 0.249 | -0.364 | -0.019 |  0.472 | -0.836 |
|  32 | 0.286 | -0.197 |  0.089 |  0.448 | -0.645 |
|  64 | 0.280 | -0.031 | -0.032 |  0.270 | -0.301 |
| 128 | 0.263 |  0.063 | -0.002 |  0.142 | -0.079 |
| 256 | 0.266 |  0.147 |  0.017 |  0.185 | -0.038 |
| **384** | **0.288** | **0.182** | **-0.003** |  **0.106** | **+0.076** |
| 512 | 0.288 |  0.153 | -0.000 |  0.125 | +0.028 |
| 768 | 0.288 |  0.175 |  0.009 |  0.096 | +0.079 |

Threshold of 0.14 at runtime_dim=384 recovers **36/36 glyphs
pixel-exact** vs the font oracle (every one of the 900 cells lands on the
correct side). Speed: **91 ms/render = 11 fps** single-threaded — about
**28× faster** than the existing `font.su` defuzzified-select path
(2540 ms/render at dim=8).

The dim choice is non-obvious: at the small dims used elsewhere (8-16)
this fails completely; the rotation-binding capacity for 25 bindings genuinely
needs ~384 semantic dims. That's a real trade-off — the integer-cycle demo
uses dim=8 because it has no bound items; the bound-vector glyph demo
needs ~50× that. Different apps, different dims, both honestly named.

## What's still TODO before wiring this into the demo

- **CI-safe test.** `tests/test_font_bound.py` should measure the encoding
  end-to-end against the oracle at dim=384. The .su uses basis_vector
  calls for 63 new keys (`font_bound_p_00..p_24`, `font_bound_LIT`,
  `font_bound_UNLIT`, `font_bound_c_A..c_9`) — none of which are in the
  current `tests/fixtures/nomic-embed-text-d484.pt` (which doesn't exist
  either; only d108/d116/d868 are committed). The test needs either:
  (a) a d484 fixture with the 63 new keys generated via ollama on a dev
  machine and committed, or (b) a graceful skip when the fixture is
  missing. Picking (b) for the first version; (a) is the right fix.
- **Wire the demo.** `apps/font/font_demo.py` could optionally use
  `font_bound.su` at runtime_dim=384 for ~28× speed. NOT done in this
  tick — the existing path at dim=8 still renders the same glyphs
  correctly (just slower), and switching paths is a user-visible change
  worth deliberation.
- **Antipodal-filler variant** (the other queued correction) — STILL
  UNTRIED. Sparse-only works at ~384; antipodal might work at smaller
  dim (~64-128?) because crosstalk cancels rather than just diffusing.
  Worth measuring but not the next blocker.

## Why this is queued, not done today

The cycle demo is the user-visible work Emma asked for in this session:
shipped at commit `3d8dae4`. The bound-vector rewrite is substantial
(parallel .su file, new tests, fuzziness tolerance change, empirical
capacity measurement) — half-doing it would be worse than not doing it
because the existing demo still works and is visibly the recurrent step
Emma wanted to see.
