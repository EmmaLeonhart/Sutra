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

## Active — autonomous work loop (worked top to bottom)

Replication is COMPLETE (6/6). Learned-ops E0–E2 DONE (sat_add learned + crystallized
to 100% exact; AND a documented spectral-bias negative result). The three work-loop
crons are running this session (`57ccb9ba`/:03, `2c9174b4`/:15, `8b51cb26`/:42).

**Priority thread — the isomorphism program** (Neural WebAssembly → Rust → OCaml →
Sutra; see `notes/significance_and_isomorphism.md` and the ★ section of `todo.md`):

1. **ISO-1 — search for a reference implementation.** Search online for existing code
   (almost certainly C or C++, possibly Rust) that is an append-only / attention-
   addressed WASM machine of this shape — or a plain, small WASM interpreter simple
   enough to seed the Rust isomorph. Record candidates + an assessment (which is
   closest, license, language) in `notes/isomorphism_reference_search.md`. Commit.
2. **ISO-2 — decide the Rust seed.** From ISO-1: if a suitable Rust reference exists,
   evaluate it; otherwise write the spec for the Rust isomorph derived from
   `transformer-vm`'s `wasm/interpreter.py` semantics (cumulative-sum registers =
   PC/SP/call-depth; argmax-attention lookups = stack/locals/memory/fetch; ReGLU =
   per-step ALU; append-only autoregressive loop). Iterator-first addressing. Commit.

**Learned-ops thread:**

3. **E3 — integrate sat_add as a native opcode.** Wire crystallized `sat_add_u` into
   `wasm/interpreter.py` (is_op-gated), build weights, pass a program using it
   end-to-end vs reference (G2). Bigger build (interpreter, opcode tables,
   `compile_wasm.py`). Runs in WSL.
4. **E4 — more learned ops / findings note.** Signed sat add/sub, min/max; consolidate
   AND-negative + sat_add-positive into a short findings note.

**Optional:** hull Python path (`sudo apt install -y python3-dev`, then
`uv run wasm-eval --hull` / `pytest -m "not slow"`; quantify hull vs `--nohull`).

**Yantra OS integration** — forward goal; design in `notes/yantra_integration.md`.

---

## Pinned tail (always the last two items — autonomous-loop skill)

- **T1 — ensure the three work-loop crons are running** (`57ccb9ba` :03 work-loop,
  `2c9174b4` :15 auto-flush, `8b51cb26` :42 status-report). Restart any that a
  planning burst / queue re-fill killed; start them if this session never did.
- **T2 — run the status-report action once more, independently** — an end-of-session
  summary of everything that happened this session.

---

## Pointers
- What we're replicating + all source links + claims: `notes/sources.md`.
- Methodology / definition of done: `SKILL.md`.
- Long-horizon items: `todo.md`.
- Completed work + milestones (chronological): `devlog.md`.
