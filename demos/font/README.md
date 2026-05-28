# apps/font — text-input pixel font demo

Emma's text-input demo (2026-05-26): a window where each keypress shows the
typed character as a 5×5 pixel glyph **decided on the Sutra substrate**.

## Run

```bash
python apps/font/font_demo.py            # open the window, press A-Z or 0-9
python apps/font/font_demo.py --render A  # save A.png and exit (no window)
python apps/font/font_demo.py --cell 40   # pixel cell size (default 40 -> 200x200 image)
```

First run runs Sutra's codegen on `font.su` (~5 min on this machine — 36
letter functions × 25-way `select` each + an outer 36-way `select` add up
to ~25 k AST tokens and ~172 KB of emitted Python). The output is
deterministic, so `sutra_compiler.compile_su` (Sutra ≥ v0.7.1) caches it
on disk as `apps/font/.font.compiled-sutra<ver>-<hash16>.py`; subsequent
runs skip codegen and start in ~3 s. The cache invalidates automatically
if `font.su`, Sutra's codegen source, or the lowering kwargs change. The
cache file is committed so CI and fresh clones also skip the 5-min wait.
Profiled: the slow step is the codegen pass itself — there are zero ollama
calls and zero codebook lookups for this program (no string roles, no
`axon_item`, just numbers + `select`).

To regenerate caches for every Yantra .su (e.g. after a Sutra submodule
bump), run `python scripts/precompile_all_su.py` once. See
`queue.md` § Pointers.

## What runs on the substrate

`apps/font/font.su` (1177 lines, generated — see below) defines:

- **`step(prev_state, x, y, char_code)`** — Emma's recurrent step. The current
  pixel value at (x, y) is the loop state; on a new keypress,
  `state = prev*0 + glyph_pixel(...)`. The `* 0` is the substrate's explicit
  "forget previous state"; the `+` is the substrate's "add the new input."
  Same recurrent shape as `apps/gui/toggle.su` (flip) and `apps/gui/count.su`
  (+1) — the host is the register, the arithmetic is the substrate.

- **`glyph_pixel(x, y, char_code)`** — returns 1.0 if pixel (x, y) is lit for
  the typed character, else 0.0. Decided ON the substrate via a 36-way
  defuzzified `select` over A–Z + 0–9, made one-hot by softmax saturation
  (scores `-1000*(char_code - target)^2` push `exp` to exactly 0 in float32
  AND float64, so the selected branch passes through and the others are
  zeroed by exact-zero weights — the same trick `apps/calc/switch.su` uses
  for operator dispatch).

- **`bit_<C>(pos)` × 36** — per-letter helpers, each a 25-way position select
  for character `<C>`'s bit pattern.

No host font table on the runtime path; only the displayed pixels are
host-painted (clamp + scale + tk window). Per-glyph render is 25 substrate
calls (one per cell) × ~1000 ops per call ≈ ~25k ops per keypress.

## How the font is defined

The 5×5 glyph shapes live in **`tools/font_data.py`** as Python data
(`.`/`#` strings, one entry per character). The .su file is **generated**
from that data by `tools/generate_font_su.py`, so the font shape lives in
one place and the substrate dispatch structure lives in one place.

Edit the font:

```bash
# 1. Edit tools/font_data.py
# 2. Regenerate font.su
python tools/generate_font_su.py
# 3. Re-run the demo / tests
pytest tests/test_font.py -v
```

`font.su` itself has a `DO NOT EDIT BY HAND` banner; edit the data, not the
generated .su.

## Tests

`tests/test_font.py` covers, for each of 36 glyphs:

- substrate `glyph_pixel(x, y, code)` returns the exact lit/unlit bit the
  font data oracle says (cell-by-cell, tolerance 1e-9 — defuzzified select
  saturates exactly to 0/1, no blend);
- Emma's `step()` honours the `* 0`: a non-zero `prev_state` still produces
  the right glyph (the substrate is what forgets);
- the `render_glyph` host wrapper assembles 25 substrate calls into a (5,5)
  field that matches the font data.

The live tkinter window + keypress can't be tested headlessly (same caveat
as `apps/gui/click_demo.py`), but the substrate parts ARE tested.

## Design notes

- **One step / one cell per substrate call** — like `count.su` and
  `frame.su`, this .su is scalar-in / vector-out and the host loops over
  (x, y) to assemble the field. This is a **host design choice** I copied
  from those demos, not a Sutra limitation. A `font.su` that takes a vector
  input (e.g. char_code) and returns a 25-element vector in one call is
  possible — the substrate has the primitives — and would let the demo
  re-render with one substrate call per keystroke instead of 25. Not done
  yet; flagged as a follow-up, not as "blocked."
- **Glyph lookup is one of the largest defuzzified switches in the
  codebase** — 36 outer branches × 25 inner branches per letter. The .su is
  ~1.2k lines; compile time is non-trivial (cached after first run).
- **The * 0 is degenerate but explicit** — yes, `prev*0` always discards
  prev, so `step` is mathematically equivalent to `glyph_pixel`. The point
  is that the substrate does the forgetting, not the host. Same as
  `toggle.su` (where `flip(s) = 1 - s` could also be done host-side); the
  whole demo is a load-bearing example that the recurrent loop's register is
  the substrate, not Python.
