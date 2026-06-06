# ISO-1 — reference-implementation search (for the Rust isomorph seed)

Goal: find existing code to seed a **Rust isomorph** of the autoregressive
deterministic Neural Turing Machine (`transformer-vm`). See
`notes/significance_and_isomorphism.md` for the program.

## Headline finding: the seed already exists in the repo

**`replication_target/transformer-vm/transformer_vm/wasm/reference.py` is a plain,
readable, imperative stack-machine interpreter** of the *exact* 35-opcode semantics
the transformer implements. Its `run(program, input_str, ...)` keeps an explicit
`stack = []`, `call_stack`, `locals_`, byte-level memory, and an instruction loop
with per-opcode push/pop/arith handlers — i.e. it is already the **behavioural spec**
in ordinary imperative form, and it is exactly what the transformer's traces are
checked against (the reference generator).

**Implication:** the Rust isomorph should port **`reference.py`** (Apache-2.0), not an
external full-MVP WASM interpreter. reference.py matches `transformer-vm`'s specific
byte-level / append-only / 35-opcode subset; external interpreters implement full
WASM MVP and a different state shape. This is the most faithful, lowest-risk seed and
keeps the isomorphism tight (Rust ≡ reference.py ≡ the transformer's traces). The
attention-addressed structure (cumulative-sum registers, argmax lookups) lives in
`wasm/interpreter.py` and is the *second* representation to mirror (iterator-first,
attention-as-addressing second — per the program).

## Secondary references (cross-check opcode semantics; full-MVP direction)

Small, readable WASM interpreters worth consulting for correctness and for the later
full-MVP push (Yantra), but **not** the primary seed:

| Project | Lang | Notes |
|---|---|---|
| [DLR-FT/wasm-interpreter](https://github.com/DLR-FT/wasm-interpreter) | Rust | Minimal, in-place, almost no deps (log, libm); passes the core testsuite. Closest "minimal readable Rust" candidate. |
| [tinywasm](https://github.com/explodingcamera/tinywasm) | Rust | Tiny interpreted runtime; passes all MVP tests; `no_std`. |
| [nanowasm](https://github.com/icefoxen/nanowasm) | Rust | Small standalone interpreter. |
| [wain](https://github.com/rhysd/wain) | Rust | Single-author, readable Rust WASM interpreter (well-known). |
| [kanaka/wac](https://github.com/kanaka/wac) | C | Minimal WASM interpreter in C, REPL. |
| [wasm3](https://github.com/wasm3/wasm3) | C | Fast M3 interpreter; more complex (perf-oriented). |
| [WebAssembly from the Ground Up](https://wasmgroundup.com/blog/wasm-vm-part-1/) | tutorial | Pedagogical from-scratch interpreter — readable explanation of the stack-machine semantics. |

## Literature validating the thesis (cite in significance notes)

The search confirms the framing in `notes/significance_and_isomorphism.md` is
recognised in the literature:

- **"Weights to Code: Extracting Interpretable Algorithms from the Discrete
  Transformer"** ([arXiv:2601.05770](https://arxiv.org/html/2601.05770)) — compiles
  transformer attention into closed-form algorithmic expressions; explicitly
  conceptualises **attention as a deterministic pointer doing NTM-style addressing**
  (location-based + content-based modes). Directly adjacent to our thesis.
- **"Attention is Turing Complete"** ([JMLR 22:20-302](https://jmlr.org/papers/volume22/20-302.pdf))
  — theoretical foundation: transformers can simulate any computation.

These support the claim that `transformer-vm` is attention-as-RAM-addressing rendered
as deterministic code — and that extracting interpretable code from attention is a
live research direction (we are doing the *constructed*, exact version of it).

## Recommendation (→ ISO-2)

Seed the Rust isomorph by **porting `wasm/reference.py`** opcode-for-opcode (it is the
exact spec), addressing memory/stack with an **iterator first**; keep one of the
minimal Rust interpreters (DLR-FT or wain) on hand only to cross-check opcode edge
cases. Validate by running identical programs through both and diffing
outputs/traces (arbitrary behavioural tests, not formal verification yet).
