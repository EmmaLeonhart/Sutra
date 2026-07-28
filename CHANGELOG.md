# Changelog

Notable changes to the `sutra-dev` package and the Sutra compiler.

Releases are cut by pushing a `sutra-dev-vX.Y.Z` tag, which publishes to PyPI and creates
the GitHub Release in one step. Tags before `v0.9.1` predate the PyPI trusted-publisher
setup and exist only as `vX.Y.Z`.

`DEVLOG.md` is the narrative history and is far more detailed than this file; dated
results, including negative ones, live in `planning/findings/`.

## [1.1.0] — 2026-07-20

The final release. Sutra is **on hold** after this version.

- Collapsed the case-twins left over from 1.0.0's case-insensitive resolution work — the
  deliberate loose end named in the 1.0.0 notes is now closed.

## [1.0.0] — 2026-07-19

Project closed at V1 and put on hold. No code change from 0.10.0 beyond the case-insensitive
resolution work below and the version bump; the release marks the decision, not a rewrite.

### Added
- **Case-insensitive stdlib method resolution**, in three stages: the class-namespace path,
  a deterministic tiebreak for ambiguous casefold collisions ("case twins"), and the bare
  free-call path. PascalCase remains canonical; no deprecation of the alternate spellings.
- `Math.min` / `Math.max` / `Math.clamp`, implemented substrate-pure from `abs`. Previously a
  bare `min` silently ran on the host.
- Eight previously-undocumented builtins documented in `capabilities.md`.

### Fixed
- **Axon value-slot birthday collision.** A key's scalar lands in the one synthetic slot its
  permutation sends `AXIS_REAL` to; two keys sharing a slot both read the pair's *sum*
  (p≈0.37 at 10 keys / 100 slots). Fixed with a slot registry and salted re-draw in
  `_axon_permutation_for`, with a loud warning past capacity. This had been surfacing as an
  intermittent CI flake and was misdiagnosed twice before the mechanism was pinned down —
  first as an Ollama server-version geometry shift, then correctly as byte-identical
  embeddings making the slot operator a function of the embedding hash.
- Windows `--emit` `UnicodeEncodeError`.
- Dead `Norm`/`norm` declarations removed — they validated and then raised `AttributeError`.
- `foreach` error messages now name `foreach_loop`.

### Documentation
- PyPI page installed a nonexistent `sutra-compiler` package; the package is **`sutra-dev`**.
- Homepage claims scoped to measured behaviour: loop backprop hard-fails, so the forward-only
  halt is now stated rather than implied.
- Tutorial diagnostics updated to real `sutrac` output; `paradigms.md` §3 rewritten to the
  shipped field/method reality. All 15 tutorial/cookbook/loop snippets validate on `main`.

## [0.10.0] — 2026-07-14

### Added
- **Three loop call forms** and unified d-dimensional slots.
- Compile-time warning `SUT0207` for loop-condition references to outer scope.
- `/llms.txt` and byte-exact raw markdown for every site page, making the docs
  agent-accessible.
- `cookbook.md` — verified everyday programs.

### Fixed
- **String equality** routed to `eq_synthetic`: `"cat" == "dog"` now returns `-1.0`; it had
  been returning `+0.994`, i.e. reading as approximately equal.
- **Parallel assignment** in the multi-value pass — `fibonacci` returned an exact `34.0`
  where it had been doubling to `128`.
- `select` over scalar options via `_cnum` normalization — max-of-array now exact.
- Inlined-relational cast typing; `_logical_truth` is no longer treated as type evidence
  (this was a CI-red `le`/`ge` regression).
- Transpiler test harnesses parse results from stdout only, closing a 50-run chronic CI red.

### Documentation
- `capabilities.md` corrected: a `(number)` cast yields signed ±1, not 1/0.
- `paradigms.md` §4 — Haskell/OCaml tail-recursion contrast, with running code only.

### Known limitation
- Loop backprop hard-fails; differentiability claims in the paper were scoped to match the
  measurement rather than the intent.

## Earlier releases

`v0.3.5` (2026-05-13) through `v0.9.4` (2026-07-08) are recorded in `DEVLOG.md`. Highlights
across that span include the PyTorch backend becoming canonical, axons, the codepoint-array
String model, the rotation-hashmap `dict<K, V>`, mid-function `await` with Promises/A+
rejection propagation (2026-06-20), and the in-process `sentence-transformers` substrate
that removed the Ollama daemon requirement.

[1.1.0]: https://github.com/EmmaLeonhart/Sutra/releases/tag/sutra-dev-v1.1.0
[1.0.0]: https://github.com/EmmaLeonhart/Sutra/releases/tag/sutra-dev-v1.0.0
[0.10.0]: https://github.com/EmmaLeonhart/Sutra/releases/tag/sutra-dev-v0.10.0
