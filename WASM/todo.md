# todo — long-horizon

Abstract destinations, not concrete steps. Pull an item here into `queue.md`,
decompose into executable steps, then execute. See `CLAUDE.md` workflow rules.

## Forward goal: integrate transformer-vm into the Yantra OS

Adopt `transformer-vm` as the way the user's OS **Yantra** runs WebAssembly.
Architecture decided in the 2026-06-05 interview — full design + trap-and-resume
ABI + phased roadmap in **`notes/yantra_integration.md`**. Decisions: real neural
executor · universal interpreter · per-process sandbox · full WASM MVP · syscalls
trap-and-resume to kernel · floats trap to host FPU · linear memory = real RAM.

Phases (decompose into `queue.md` one at a time; design only until then):

- **P0 — Trap substrate** (the linchpin): trap ABI + C++ engine pause/host-callback/
  resume + one round-tripping demo trap.
- **P1 — Memory as trapped real RAM** (LOAD/STORE → host RAM).
- **P2 — Syscalls / WASI** over the trap channel.
- **P3 — Floats via host-FPU trap.**
- **P4 — Integer ISA completion** (i64, native bitwise/shift, br_table, typed select).
- **P5 — Tables / indirect calls, memory.grow.**
- **P6 — Per-process lifecycle** (snapshot/restore residual+hull state; scheduling).

## Replication follow-ups (optional — core replication already done)

- **Python hull path:** with `python3-dev` installed, confirm `wasm-eval --hull`
  and `pytest -m "not slow"` pass fast; compare hull (O(log n)) vs `--nohull`
  brute-force timings to quantify the attention-scaling claim.
- **Throughput gap:** investigate the ~18K vs ~30K tok/s gap (WSL overhead,
  BLAS-free Linux matvec); try a native-Linux or BLAS-linked build.

---

## ★ The isomorphism program: Neural WebAssembly → Rust → OCaml → Sutra

Full motivation, classification, and significance in
**`notes/significance_and_isomorphism.md`**. In one line: `transformer-vm` is an
**autoregressive, deterministic Neural Turing Machine** — attention used to address
RAM, then deterministic, fully code-describable operations — the first time an
attention mechanism has been turned into deterministic, human-interpretable code. The
goal of this program is to make that code **explicit and isomorphic**, and carry the
isomorphism across languages until it reaches **Sutra**. Equivalence is established by
**arbitrary behavioural tests** (not formal verification — that is a later stage).

Worked strictly in order; each stage decomposes into `queue.md` when started:

1. **Research + write-up.** Consolidate the architectural classification (autoregressive
   deterministic NTM; attention-as-RAM-addressing; append-only WASM-in/data-out;
   relation to NTM/DNC) into finished research notes. (Seed: 
   `notes/significance_and_isomorphism.md`.)
2. **Search online for a reference implementation.** Find existing code that already
   does this — **almost certainly C or C++, possibly Rust** — a WASM interpreter of
   this append-only / attention-addressed shape, or something simple enough to seed
   from. Percepta's own repo is the primary candidate; search wider too.
3. **Rust (isomorphic).** If no Rust reference exists, **rewrite the reference in
   Rust** so we have a deterministic, imperative program **isomorphic** to the
   transformer's behaviour. Represent the read/write location with an **iterator
   first**; explore **attention-as-addressing second**.
4. **Test Rust.** Battery of **arbitrary** behavioural tests: identical traces/outputs
   to the transformer on the example programs and beyond. (Equivalence by testing.)
5. **OCaml (isomorphic).** Build a comparable **OCaml** program; establish the same
   isomorphism. OCaml is harder to express this in than Rust — which is the point: it
   is **structurally close to Sutra**, so it is the stepping stone.
6. **Test OCaml.** Same arbitrary-test battery; confirm equivalence.
7. **Sutra (end of the road).** Because OCaml ≈ Sutra structurally, port the OCaml
   realisation into **Sutra** and test how far Sutra can express this same machine.
   Harder than the imperative stages (Rust/OCaml are deterministic/imperative; Sutra
   sits differently) — hence last. **This is the final item in `todo.md`.**
