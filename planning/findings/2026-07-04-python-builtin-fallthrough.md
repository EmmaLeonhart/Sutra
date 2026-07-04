# Python builtins are silently callable from `.su` source (severity datum for H1)

**Date:** 2026-07-04. **Author:** queue session, usability audit round 12 (diagnostics sweep).
**Measured on:** pip `sutra-dev` 0.9.2 in a fresh venv AND repo HEAD (`PYTHONPATH=sdk/sutra-compiler`).

## The measurement

Unknown identifiers in call position lower to bare Python names in the generated module, so
they resolve against Python's builtins at runtime. All of these **run without any diagnostic**:

- `print("hi")` mid-function — prints to stdout from inside the program body
  (mid-computation host I/O, the thing the language identity forbids by design).
- `str(len("abc"))` as a return value — host computation on the hot path; returns `3`.
- By the same mechanism any builtin is reachable (`open`, `eval`, … — not demonstrated,
  same code path as the above).

A genuinely unknown name (`frobnicate(...)`) validates cleanly and fails only at runtime —
raw `NameError` on released 0.9.2; a one-line Sutra-style `runtime error:` diagnostic at
repo HEAD (unreleased fix).

## Why this matters more than the H1 framing captured

H1 (2026-06-24 finding) classified missing name-resolution as a *diagnostics* gap deferred
to the v0.2 symbol table — the cost being "typos fail late". This measurement adds a
different cost: **the accidental language surface includes all of Python's builtins**, i.e.
an undocumented host escape hatch. Per CLAUDE.md, escape hatches must be explicit and
grep-able, mid-computation host I/O is excluded by the execution model, and "a code
affordance is an invitation" — an agent or newcomer who discovers `print` works will build
on it, and what they build is neither substrate-pure nor portable to the thrml target.

## Disposition

- **The fix is still the v0.2 symbol table (H1) and still Emma's call** — a name-resolution
  pass is what can reject (or explicitly whitelist) non-Sutra names without false-positives
  on valid forward references and function-valued locals (the measured blockers in the H1
  finding). No interim hack shipped: a codegen-side builtins blacklist would be a second
  name-resolution mechanism that H1 would then have to unwind (superseded-design residue by
  construction).
- Queue's H1 blockquote updated with this severity datum so the v0.2 decision weighs it.
- The newcomer-diagnostic fixes already at HEAD (no-main message, `runtime error:` wrapper)
  reach pip users at the next `sutra-dev-v0.9.3` tag — noted in the queue.
