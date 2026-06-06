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

ISO-1/2/3 DONE: the Rust isomorph (`iso/rust/`, port of `reference.py`) is
behaviourally equivalent to the reference executor — 6/6 example programs produce
byte-identical output (cargo test + `scripts/iso_equiv.sh` → ISO_EQUIV_OK).

1. **ISO-4 — OCaml isomorph.** ⛔ BLOCKED ON USER: OCaml + dune are missing and need
   sudo — please run `sudo apt install -y ocaml ocaml-dune m4` in WSL (on Ubuntu 24.04
   the package is `ocaml-dune`, not `dune`; system OCaml means no opam needed). Then:
   build an OCaml port of the same
   35-opcode machine under `iso/ocaml/` and establish behavioural equivalence (OCaml
   vs Python reference / Rust, diff outputs). OCaml ≈ Sutra structurally — the
   stepping stone. Commit.
2. **ISO-5 — Sutra.** Port the OCaml realisation into **Sutra** and test how far Sutra
   can express this same machine. The end of the road (and of `todo.md`). Hardest —
   plan carefully; this likely needs user input on Sutra specifics.

**Learned-ops thread** (E4 DONE: sat_add/sat_sub/min/max all learned to 100% exact,
value-output; AND a documented negative result; findings in
`notes/learned_ops_findings.md`):

3. **E3 — integrate a learned op as a native opcode (SPEC FIRST).** Wire a learned
   arithmetic op (e.g. `sat_add_u`) into `wasm/interpreter.py` (is_op-gated) +
   `reference.py` + `compile_wasm.py`, build weights, pass a program using it
   end-to-end vs reference (G2). Deep build into the analytic construction — per the
   hard rails, **write the spec first** (what changes in each file, the byte-level
   semantics) before implementing; do not blind-hack the construction. Runs in WSL.

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
