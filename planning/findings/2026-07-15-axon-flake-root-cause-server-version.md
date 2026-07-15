# Axon-cache CI flake: root cause is ollama SERVER version, not model drift (2026-07-15)

## The symptom

`test_axon_op_cache_under_cap_never_evicts` failed on compiler-ci runs 29386156802 and
29387477961 (key "tree" read back **11.0** instead of 4.0 from a 10-key axon bundle), passed
on a rerun of the first, and passes 3/3 locally. Both failing runs were docs-only commits.

## The investigation (measured, in order)

1. **Model drift falsified.** Added digest logging to CI: `nomic-embed-text` digest is
   byte-identical local vs CI (`0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`).
2. **Probe reproduced a failure locally — but the WRONG one.** A standalone probe
   (`experiments/axon_key_crosstalk_probe.py`) showed go→9.0 / machine→9.0 deterministically,
   while pytest passed on the same machine, same sequence. The delta: pytest's
   `tests/conftest.py` pins `SUTRA_EMBED_BACKEND=ollama`; the probe (no conftest) ran on the
   in-process transformers backend — whose docstring **already documents this exact
   collision** ("short words like `go` near `telephone`" — and 9.0 is telephone's value).
   The probe's failure is the known backend-realization difference, not a bug.
3. **Remaining delta for the real CI flake: the ollama server version.** Local: 0.17.1
   (passes, the geometry the suite's thresholds were tuned against). CI: unpinned
   `install.sh` → 0.32.0 on the failing runs. Same model digest, different server → different
   embedding realization (server-side inference/batching changes), enough to tip the 10-key
   crosstalk margin. Nondeterminism across CI runs (fail/pass/fail) is consistent with
   ollama's batching-dependent embedding variation under interleaved requests.

## The fix

Pinned the CI server: `OLLAMA_VERSION=0.17.1` in compiler-ci.yml. This completes the pin the
repo already half-made — conftest.py pins the *backend* to ollama because "the correctness
gate runs on its tuned substrate"; the server version is part of that substrate. Digest +
`ollama --version` logging stays in CI so any future geometry shift is attributable.

## What this is NOT

- Not a Sutra runtime bug: bind/unbind math is consistent within any one realization.
- Not a test weakening: the assert is untouched; the substrate under it is now actually the
  substrate the thresholds were measured on.

## Follow-up (queued)

Re-measure the crosstalk margins against a modern ollama server (0.32.x) as a deliberate
re-tuning — the same class of work as the LSC paper's finding (an ollama runtime change
shifting embeddings for unchanged weights; there it silently collapsed diacritics for
mxbai-embed-large). If the modern geometry is tighter, the fix is better-separated keys or a
wider margin, measured — not a pin forever.
