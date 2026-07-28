# Contributing to Sutra

Sutra is a geometrically compiled language: logical operations over vector spaces are
resolved at compile time into matrix multiplications. That design constrains what a
patch is allowed to do far more than in a typical compiler, so please read
[The rules that get patches rejected](#the-rules-that-get-patches-rejected) before
writing code. Most rejected changes are correct Python that quietly breaks the
substrate model.

License: **AGPL-3.0-only**. By contributing you agree your work ships under it.

## Getting set up

Requires **Python ≥ 3.11**.

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra/sdk/sutra-compiler
pip install -e ".[runtime,fv,dev]"
```

The extras matter:

| Extra | Pulls | Needed for |
|---|---|---|
| `runtime` | `torch` | the canonical backend — almost everything |
| `embed` | `sentence-transformers` | semantic programs (auto-embedding strings) |
| `fv` | `sympy` | the formal-verification tooling |
| `dev` | `pytest` | the test suite |

A CPU-only torch is fine and is the smaller download:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`.

The default substrate is `nomic-embed-text` (768-d, mean-centered), loaded **in-process**
via `sentence-transformers` — no Ollama daemon required. Ollama is an alternate backend
behind `SUTRA_EMBED_BACKEND=ollama`; the two differ slightly in geometry, so don't treat
a number measured under one as valid under the other.

## Running the tests

From `sdk/sutra-compiler`, this is the exact command CI runs:

```bash
python -m pytest tests/ -q \
  --ignore=tests/test_substrate_leak_sweep.py \
  --ignore=tests/test_simplify_egglog.py
```

The two exclusions are deliberate, not neglect:

- **`test_substrate_leak_sweep.py`** takes ~29 minutes. It is covered by the daily audit
  workflow rather than per-PR. Run it yourself before any change to codegen or the
  runtime primitives.
- **`test_simplify_egglog.py`** hangs on Windows. It runs in CI on Linux.

The examples smoke test is the only coverage of the deprecated numpy backend, and runs
from the repo root:

```bash
python examples/_smoke_test.py
```

There are ~90 test files and a number of `xfail`/`skip` markers. An `xfail` that starts
passing is a real signal — investigate it, don't just flip the marker.

## The rules that get patches rejected

These come from `CLAUDE.md`, which is the full contract. The short version:

### Every operation runs on the substrate

No host readout inside an operation. Concretely, `.item()`, `float(tensor)`, or any
Python `if`/`while` branching on a data value inside emitted code is a defect, even when
the output is numerically right. The emitted module is meant to be straight-line tensor
work. If you need a branch, it belongs in the substrate as `select`, not in Python.

There is also **no introspection** — no readout, no logging, no monitoring, no debug
prints threaded through operations. This is stricter than most projects and it is
intentional.

### No math shortcuts

Don't replace a substrate operation with a closed-form host computation because it's
faster or easier. Optimize globally through the tensor expression, not locally by
escaping it.

### Three subtler breaches that pass the obvious check

Dispatch-level cleanliness is necessary but **not sufficient**. A prior effort shipped
all three of these as "substrate-pure" for weeks. If your change touches a `.su` or the
compile path, audit for them and **put the numbers in the commit message or a planning
doc**:

1. **Dimension audit.** If a `.su` makes zero `basis_vector` calls, the LLM codebook is
   unused and `runtime_dim` can drop from the default 868 to ~108 or ~16 with no loss of
   correctness. Count the `basis_vector` calls and pick the smallest dim the task needs.
   Running at 768 with zero basis_vector calls once cost 96× silently.

2. **State-locus audit.** A `.su` function that takes a scalar, returns `make_real(v)`,
   and is called in a host loop that extracts via `vsa.real()` between calls is **not an
   RNN** — the recurrence lives in a Python variable. Any claim of "recurrent" /
   "substrate-pure state" requires the state to be a vector surviving across calls
   *without* host extraction.

3. **Signal-separation audit.** A function can return numbers that fail to separate the
   classes it claims to classify. Every substrate classifier ships with a measured
   `gap = min(positive_class) - max(negative_class)`. Without that table, "the substrate
   decides X" is an unverified claim.

### Claims are measured, not asserted

Don't describe work as "verified", "substrate-pure", or "green" against an earlier
description of it. Run it and measure. This applies to commit messages as much as to
docs — a commit that frames a result it didn't measure is the specific failure the
repo's daily audit exists to catch.

## Backends

- **`codegen_pytorch.py` — canonical.** Axons, the full `Math.*` namespace, the
  codepoint-array String model, and the rotation-hashmap `dict<K, V>` live here.
- **`codegen.py` — numpy, deprecated.** No equivalent for the newer features. Don't add
  features here; don't "fix" it to reach parity.

`Math.mod` is scalar-realm only: correct on numbers (max err 4e-6 vs floor-mod) but its
output is 0-d. Do not thread it through vector recurrent state — use complex rotation for
vector wrap/periodic behaviour.

## Workflow conventions

The repo runs a queue discipline that differs from the usual issue tracker:

- **`todo.md`** — long-horizon backlog.
- **`queue.md`** — what is being worked on now, in execution order.
- **`DEVLOG.md`** — narrative history, dated.
- **`planning/findings/`** — dated results, **including negative ones**.
- **`planning/open-questions/`** — open problems, indexed by a README.

Items migrate `todo.md` → `queue.md` → **deleted on completion**, in the same commit that
ships the work, with a `DEVLOG.md` entry. Finished items are removed, never struck
through or marked DONE — git history is the record. Don't leave a "recently shipped"
block behind.

`Audit.md` catalogues known substrate leaks. `AGENTS.md` is a file-by-file index of the
codebase and is the fastest way to find where something lives.

## Pull requests

- Branch from `main`.
- Run the CI test command above and state the actual result. If something fails, say which
  test and why rather than adjusting the test to pass — weakening or faking a test is the
  one thing guaranteed to get a patch rejected.
- Include measurements for anything touching the substrate (see the three audits above).
- Keep the numpy backend out of scope unless the change is a bug fix to existing numpy
  behaviour.

CI gates on `compiler-ci.yml`. Other workflows cover the Rust `sutraDB/`, the transpilers,
the Lean formal-verification tree, and the paper pipeline. Note that editing
`paper/paper.md` or `paper/formal-verification/paper.md` triggers a clawRxiv resubmit —
intended for real updates, not churn, so avoid incidental edits to those two files.

Lean work is verified through `fv-lean-mathlib-ci`; local Windows checkouts hit `MAX_PATH`
limits, so iterate via branch pushes rather than fighting it locally.

## Releases

Maintainer action. Bump `version` in `sdk/sutra-compiler/pyproject.toml` and
`__version__` in `sutra_compiler/__init__.py`, then:

```bash
git tag sutra-dev-vX.Y.Z && git push origin sutra-dev-vX.Y.Z
```

One tag push publishes to PyPI (`sutra-dev`, via trusted publisher) and cuts the GitHub
Release.

## Reporting bugs

Open an issue with the `.su` source that reproduces it, the backend
(`codegen_pytorch` / numpy), the `runtime_dim`, and the embedding backend. For anything
involving similarity or classification, include the measured cosines — "it returns the
wrong concept" is not reproducible without the numbers.
