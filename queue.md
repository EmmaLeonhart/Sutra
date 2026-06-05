# replicating-pertepta — Work Queue

**This file is a queue of concrete, executable steps, not a state snapshot.**
Finished work lives in `devlog.md` (dated entries) and `git log`;
longer-horizon items live in `todo.md`. **When an item is done, delete it
from this file AND append a dated entry to `devlog.md` in the same commit,
then push.** No checkmarks, no status indicators in place.

---

## Target (READ FIRST)

We are **not** replicating the arXiv paper "Neural Computers" (2604.06425) — the
scaffolder downloaded it only because the flow expects an arXiv ID, and it is kept
as *related work only*. The **real target** is Percepta's **`transformer-vm`**: a
standard softmax-ReGLU transformer with **analytically-computed (untrained)
weights** that **correctly simulates a WebAssembly VM on arbitrary programs**. It
has no arXiv — only a GitHub repo (which ships the reproduction recipe), a blog
post, a LinkedIn post, and a Medium write-up. Full details + claims live in
`notes/sources.md`. Remote name requested: **`replicating-pertepta`**.

This is a **recipe-first** replication: the repo ships `uv run wasm-run`. Run it
first, then verify its output against the blog's headline claims.

---

## Active

10. **Confirm the deliverables are green.** Push (done) triggers `pages.yml`
    (themed FINDINGS site + PDF, status badge now `replicated`), `package.yml`
    (ZIP), and the new `ci.yml` (runs `scripts/run.py` end-to-end). Watch the runs;
    fix any red. The repo is already public; `pages.yml` auto-enables Pages.

## Optional / nice-to-have (replication already succeeds without these)

- **First Futamura projection (C6):** run `uv run wasm-specialize
  transformer_vm/data/collatz.txt --save-weights=collatz.bin` then
  `uv run wasm-run --model collatz.bin transformer_vm/data/collatz_spec.txt`;
  record the result in `notes/claims.md` / `FINDINGS.md`.
- **Hull Python path:** `sudo apt install -y python3-dev`, then `uv run wasm-eval`
  (hull) and `uv run pytest -m "not slow"` should pass fast. CI already installs
  `python3-dev`.

---

## Pointers
- What we're replicating + all source links + claims: `notes/sources.md`.
- Methodology / definition of done: `SKILL.md`.
- Long-horizon items: `todo.md`.
- Completed work + milestones (chronological): `devlog.md`.
