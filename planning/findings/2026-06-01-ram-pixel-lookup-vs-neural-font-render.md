# RAM pixel-lookup rendering vs the neural font renderer (2026-06-01)

**The payoff Emma named** for the RAM-pointer / Neural-Turing-Machine
direction (`planning/sutra-spec/ram-pointers.md`): render the same glyph
pixels two ways and contrast the architectures —

- **Pure neural network** — `demos/font/font.su` `glyph_pixel(x, y, code)`
  **computes** each pixel on the substrate via a 36-way × 25-way
  defuzzified-`select` cascade. The font is baked into the program's
  logic (the lit/unlit bits are `make_real(0/1)` branches inside the
  selects). No external memory is read.
- **NTM / RAM lookup** — the glyph bitmap is stored in the external host
  RAM device; a Sutra read head emits a program-controlled pointer per
  cell and the orchestrator serves `RAM[pointer]`. The font is *data* in
  addressable external memory, fetched by pointer.

## Result — both reproduce the ground truth exactly

Ground truth is `demos/font/font_data.FONT_5x5` (the independent source
the font demo is generated from). Repro:
`python experiments/ntm_ram/run_font_compare.py`.

```
glyph 'A' (code 65):   ground       NN-compute   RAM-lookup
               .###.        .###.        .###.
               #...#        #...#        #...#
               #####        #####        #####
               #...#        #...#        #...#
               #...#        #...#        #...#
  NN==ground: True   RAM==ground: True   NN==RAM: True

glyph '7' (code 55):   ground       NN-compute   RAM-lookup
               #####        #####        #####
               ....#        ....#        ....#
               ...#.        ...#.        ...#.
               ..#..        ..#..        ..#..
               .#...        .#...        .#...
  NN==ground: True   RAM==ground: True   NN==RAM: True
```

Both architectures produce the identical 5×5 bitmap; the contrast is
*how*, not *whether*.

## Substrate posture

- **Dim audit.** The RAM read head is model-free (no `basis_vector`),
  `dim = 108` (`semantic = 8`, the same width the font demo's own
  `cycle_step` compile uses). The NN renderer is likewise model-free at
  `dim = 108`.
- **State-locus.** The read head's address is a recurring VRAM cursor
  advanced by `complex_add` each tick; the orchestrator decodes the
  emitted pointer at the I/O wire (`real()` — monitoring), then performs
  the host RAM read.
- **Discrete addressing (Emma 2026-06-01).** RAM is *not* differentiable;
  a pointer between two cells rounds to the nearest
  (`int(round(real(ptr)))`). I/O is outside the differentiable realm.

## Architectural contrast

| | Pure-NN render (`glyph_pixel`) | NTM / RAM lookup |
|---|---|---|
| Where the font lives | baked into program logic (select cascade) | data in external addressable RAM |
| Per-cell cost | a 36-way × 25-way `select` evaluation on the substrate | one pointer emit + one RAM fetch |
| Changing the font | edit/regenerate the program | overwrite RAM cells (`ramWrite`) at runtime |
| External memory | none | yes — the read/write head is the I/O boundary |
| Compile cost | heavy (1265-line `.su`; codegen cache miss ≈ minutes) | trivial (model-free read head) |

This is the distinction the architectural-diversification direction
targets: a *pure neural* computation that carries its knowledge in its
own structure, versus a *Neural Turing Machine* that separates the data
(external, mutable, addressable memory) from the mechanism that reads it
(a program-controlled pointer + an I/O orchestrator).

## What is and isn't verified here

- The **NN render == ground truth** leg is already guarded by
  `demos/font/test_font.py`
  (`test_glyph_pixel_matches_font_data_on_substrate`, all 36 glyphs).
- This finding adds the **RAM render == ground truth** leg and the
  head-to-head. The RAM leg is guarded cheaply (model-free, no `font.su`
  recompile) by `sdk/sutra-compiler/tests/test_ntm_ram.py`
  (`test_ram_lookup_render_matches_font_ground_truth`, 'A' and '7'). The
  full three-way comparison (which recompiles `font.su`, heavy) is the
  on-demand demo script `experiments/ntm_ram/run_font_compare.py`, run
  here for 'A' and '7'.

## Cross-refs

- `planning/sutra-spec/ram-pointers.md` — the RAM-pointer / NTM spec.
- `demos/font/font.su`, `demos/font/font_data.py` — the neural renderer
  and the ground-truth bitmaps.
- `experiments/ntm_ram/` — the RAM device, orchestrator, read head, and
  the comparison script.
