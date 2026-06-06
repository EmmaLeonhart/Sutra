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

## Active — NEW THREAD: learn new CPU operations on the scaffold

The replication is complete (REPLICATED, 6/6). New research direction (user's
vision): train *new CPU operations* on the frozen analytic scaffold, then
crystallize them to exact weights — the constructed+trained hybrid toward a
Completely Neural Computer. Full design + grounding + metrics in
`notes/experiment_learned_ops.md`. **Gated on user approval of the design + choice
of the novel op (E4).** No code until approved.

- **E0** — build a grad-enabled softmax-attention forward over the loaded analytic
  weights (the shipped forward is inference-only `@torch.no_grad()` + argmax,
  `model/transformer.py:41-69`); prove it matches the argmax forward at high τ on an
  existing op. Lives in `src/learned_ops/`.
- **E1** — freeze/trainable split + op-local trainer; learn `i32.and` to 100% exact
  (G1) on all 65 536 byte pairs at τ→∞.
- **E2** — crystallize AND to exact DSL weights (G3); confirm no regression on the
  other ops (G4).
- **E3** — repeat for `i32.mul` (carry-bearing); wire it as a native opcode and pass
  end-to-end vs reference (G2).
- **E4** — pick the genuinely *new* op with the user; learn + crystallize; write up.

## Optional / nice-to-have (replication already succeeds without these)

- **Hull Python path:** `sudo apt install -y python3-dev`, then `uv run wasm-eval`
  (hull) and `uv run pytest -m "not slow"` should pass fast. CI already installs
  `python3-dev`. (Quantify hull vs `--nohull` timings for the O(log n) claim.)

---

## Pointers
- What we're replicating + all source links + claims: `notes/sources.md`.
- Methodology / definition of done: `SKILL.md`.
- Long-horizon items: `todo.md`.
- Completed work + milestones (chronological): `devlog.md`.
