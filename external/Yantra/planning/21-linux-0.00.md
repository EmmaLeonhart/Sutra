# Replicating Linux 0.00 on Yantra

> **What this document is.** A concrete, executable design for a
> Yantra-native replica of **Linux 0.00** — Linus Torvalds' earliest
> preserved kernel. Written 2026-05-17 from a queue item the user
> added (`try to implement this
> https://computernewb.com/wiki/Linux_0.00`) so a fresh session
> (incl. the scheduled cron) can execute it without chat context.
>
> **What this document is not.** A claim that Yantra boots bare
> metal like Linux 0.00 does. The scope section below states
> exactly what maps and what does not.

## What Linux 0.00 actually is

Linux 0.00 (1991, preserved at oldlinux.org `kernel/0.00/`) is
**two assembly files**:

- `boot.s` — a 512-byte boot sector. BIOS loads it at `0x7c00`; it
  prints a load message, pulls the kernel off disk, sets up a
  minimal GDT, enters 32-bit protected mode, jumps to the kernel.
- `head.s` — the kernel. Sets up the GDT/IDT, **two TSS + two LDT**
  (one per task), programs the 8253 PIT timer and unmasks the
  timer IRQ on the 8259 PIC, installs a timer-interrupt handler
  that **hardware-task-switches** between the two tasks (far jump
  to the other task's TSS selector), and installs an `int 0x80`
  `write_char` system call that pokes a character into VGA text
  memory and advances the cursor.

Runtime behaviour: **task A loops writing `A`; task B loops writing
`B`; the timer interrupt flips between them**, so the screen fills
with `AAAA…BBBB…AAAA…`. That is the entire program. Its whole point
is *the smallest possible OS that demonstrates kernel-mediated
multitasking of two trivial output tasks*.

## The faithful Yantra mapping

Yantra's build sequence (CLAUDE.md, `planning/18`): **milestone 1
is the Connectome Manager**, whose Python v0.0 (`kernel/`) is real
and tested — `Init` admission + `AxonRouter` + `tick()` +
`SutraService` running real Sutra-compiled `.su` on torch tensors.
That is "enough built for it."

Linux 0.00 concept → Yantra-native realization:

| Linux 0.00 | Yantra |
|---|---|
| Task A (writes `A` forever) | `kernel/services/task_a.su` — `on_axon` emits a vector decoding to codepoint **65** on its output role each tick |
| Task B (writes `B` forever) | `kernel/services/task_b.su` — same, codepoint **66** |
| `write_char` syscall (`int 0x80`) → VGA memory | a console/sink service that consumes both output roles and accumulates the ordered character stream |
| Timer IRQ that flips tasks | `Init.tick()` — one tick = one timer fire; the kernel runs the admitted tasks and the router carries their output |
| Hardware TSS context switch | **(deliberately NOT replicated — see scope section)** Yantra's kernel does not context-switch (`kernel/init.py` docstring: "Does NOT schedule — the GPU runs every admitted process simultaneously"). Both tasks live in the connectome at once; the tick is the timer analogue; output interleaves under kernel mediation |

This is a *faithful translation of Linux 0.00's purpose*, not a
cargo-culted TSS. Linux 0.00 demonstrates "kernel mediates two
trivial output tasks"; the Yantra realization demonstrates exactly
that in Yantra's connectome model.

## Concrete deliverables (a fresh session executes these)

1. **`kernel/services/task_a.su`** and **`task_b.su`**. Contract:
   `function vector on_axon(vector input_axon)` returns a vector
   that decodes to codepoint 65 (`A`) / 66 (`B`) using the current
   Sutra string/number vocabulary (e.g. `make_string`/codepoint).
   **If the Sutra string vocab cannot cleanly emit a single
   codepoint vector, fall back to a distinct constant per task and
   decode by nearest-vector in the test — and say so plainly in
   this doc and the test (do not fake an `A`/`B` that isn't there).**
   Keep the body substrate-pure (no host shortcuts) per Sutra
   CLAUDE.md.
2. **`kernel/manifests/task_a.toml`, `task_b.toml`**, and a console
   manifest (reuse `sink.toml` shape if it fits). Each declares
   `axon_width`, `compute_units`, `read_roles`, `write_roles`,
   `source`.
3. **`tests/test_linux_000.py`**. Admit `task_a`, `task_b`, console
   into one `Init`; run N ticks; assert: (a) both characters reach
   the console, (b) the stream is kernel-mediated and interleaved
   (both tasks present across ticks — the `AAAA…BBBB…` analogue),
   (c) each task's emitted vector decodes to its intended codepoint.
   Real `SutraService` (use `make_shared_sutra_services` for one
   shared `_VSA`). **No weakened assertions; report measured
   decode similarity as measured** (Sutra CLAUDE.md safety rules bind
   even in a Yantra-driven session).
4. **README / queue**: note the demo under `kernel/README.md`
   "What runs today"; delete the queue item on completion.
5. Update this doc's status section with measured results.

## Two realizations (both real, both done)

This doc originally framed "the bare-metal replica" as deferred
and *"gated on GPU passthrough"*. **That was a conflation, now
corrected (2026-05-17).** There are two independent realizations:

1. **Connectome-Manager realization** (the Yantra-native mapping
   in the table above) — `kernel/services/task_{a,b}.su` +
   `tests/test_linux_000.py`. Done; measured below.
2. **Bare-metal realization** — `bootloader/src/bin/linux000.rs`.
   Linux 0.00 runs in **32-bit protected mode writing to VGA text
   memory**; it touches **no GPU at all**. So it was never
   actually GPU-gated — it builds and runs on the existing v0.4
   bootloader infrastructure (multiboot1, real 32-bit Rust in
   QEMU). Done; measured below.

The GPU-passthrough / GRUB-ISO blockers in `bootloader/README.md`
are about a **different, larger** thing: running the **Sutra
kernel itself on a real GPU at boot** (v0.5+), which needs a Linux
host + VFIO + a spare GPU and 64-bit Rust. That is unrelated to
Linux 0.00, which is pure CPU + VGA. Conflating the two is the
exact "paper over difficulty" failure CLAUDE.md warns against —
fixed here and in `bootloader/README.md`.

### Scope — what is still NOT replicated

- **No hardware TSS task switch.** Linux 0.00 used the x86
  hardware-TSS `ljmp` mechanism. The bare-metal replica uses a
  **software** ESP context switch in the timer ISR (the
  modern-OSdev equivalent — same observable behaviour, fewer
  modern-QEMU footguns). Faithfulness is to the *purpose*
  (timer-interrupt-driven multitasking of two trivial tasks), not
  the exact TSS opcode.
- **No real-hardware boot / no real disk boot sector.** It boots
  via QEMU's multiboot1 `-kernel`, not a 512-byte BIOS boot
  sector off a disk. QEMU is the dev tier; real-iron boot is a
  separate concern.
- The **Connectome-Manager** realization additionally does not
  context-switch by design (Yantra's kernel doesn't — see table);
  its faithfulness is to Linux 0.00's purpose in the connectome
  model, not the mechanism.

## Status — Connectome-Manager realization

**DONE — 2026-05-17** (executed by the scheduled cron session).

Files added:

- `kernel/services/task_a.su`, `task_b.su` — emit `real_number(65.0)`
  / `real_number(66.0)` (substrate op `_VSA.make_real`; the literal
  ASCII codepoints of `A`/`B`, not a faked constant).
- `kernel/services/console.su` — passthrough fan-in receiver (the
  VGA-memory analogue).
- `kernel/manifests/task_a.toml`, `task_b.toml`, `console.toml`.
- `tests/test_linux_000.py` — 3 tests, real shared-runtime
  `SutraService`s via `make_shared_sutra_services`.

Measured (printed by the test, not tuned):

```
[linux 0.00] stream='ABABABABABABABAB'  real(task_a)=65.0  real(task_b)=66.0
```

- `real(task_a) == 65.0` exactly, `real(task_b) == 66.0` exactly —
  decoded host-side via the `.real()` monitoring accessor. Literal
  `chr(65)=='A'` / `chr(66)=='B'`; **no fudged tolerance** (the
  1e-5 guard is float-repr only; the values are exact).
- `stream == "AB" * 8` over 8 ticks: both hardcoded tasks ran every
  tick under kernel mediation (neither starved), output interleaved
  and carried by the real `AxonRouter` — the faithful Linux-0.00
  "kernel alternates two trivial output tasks" behaviour.
- Capability check verified real (a task cannot write a role it
  doesn't hold) — this is the real Connectome Manager, not a stub.

`pytest tests/test_linux_000.py` → **3 passed**. Full kernel
regression `tests/test_kernel.py tests/test_kernel_sutra.py
tests/test_linux_000.py` → **50 passed, 1 xfailed** (the
unrelated connectome-projection strict-xfail, still correctly
xfailing — no regression from the Sutra v0.4.1 submodule bump).

The per-task-constant fallback in the deliverables note was NOT
needed: Sutra's `real_number` cleanly emits a single decodable
codepoint vector, so the A/B are genuine substrate values, not
opaque constants. Scope limits below stand unchanged.

## Status — bare-metal realization (2026-05-17)

**DONE.** `bootloader/src/bin/linux000.rs` — a 2nd binary in the
bootloader crate. 32-bit protected mode, multiboot1, **no GPU**.
Real GDT + IDT, real **8259 PIC** remap (IRQ0→vector 0x20), real
**8253 PIT** @ ~1000 Hz, two hardcoded tasks A/B each with its own
seeded stack, a naked **timer ISR** doing a software ESP context
switch round-robin. Output to the VGA text buffer (0xB8000 — the
faithful "screen") and COM1 serial (the capturable proof). Each
task emits exactly one char then `hlt`, so the timer tick drives
the switch. `LIMIT` is one full 80×25 screen (2000) so the screen
visibly fills, then both tasks halt with a static painted screen.
PIT is ~1000 Hz (vs Linux 0.00's ~100 Hz) only so a full-screen
fill takes ~2 s not ~20 s — same real 8253, same real switch.
Build: `scripts/linux000-build.{sh,bat}`; run:
`scripts/linux000-run.{sh,bat}`.

Two real bugs were found and fixed (not papered over): (1)
`nightly-2026-04-01` gates JSON target specs behind
`-Zjson-target-spec` — added `[unstable] json-target-spec` to
`bootloader/.cargo/config.toml` (also un-breaks a bare
`cargo build` of the v0.4 bootloader); (2) the `global_asm!`
lacked `.code32`, so LLVM assembled `iret` as 16-bit `iretw` →
`#GP` at the task-switch return (caught by the `[EXC]` handler,
diagnosed from the QEMU `-d int` log: `v=0d e=0010`).

**Measured QEMU serial transcript** (`-serial file:` capture, NOT
hand-written):

```
Yantra bare-metal Linux 0.00 replica - hello from bare metal
  32-bit protected mode, multiboot1, no GPU.
  [ok] GDT loaded (flat code 0x08 / data 0x10)
  [ok] IDT loaded (exc 0..31, timer @ 0x20)
  [ok] 8259 PIC remapped (IRQ0->0x20, only IRQ0 unmasked)
  [ok] 8253 PIT @ ~1000 Hz (channel 0, mode 3)
  [ok] tasks A/B seeded; jump-starting task A
  --- timer-driven A/B stream follows ---
BABABABAB … (2000 chars; one full 80x25 screen) … BABABAB
[linux000] reached LIMIT; timer-driven A/B task switch verified
[linux000 DONE]
```

The QEMU `-d int` log **independently** confirms it is genuine
hardware-timer-driven, not a busy-loop print: repeated `v=20`
(our remapped IRQ0) interrupts with `EAX` alternating `0x41`/`0x42`
('A'/'B') across the two task contexts. It leads with `B` because
the first PIT tick lands between task A's counter-increment and
its first `sputc` — a genuine one-character startup timing
artifact (this is what preemptive timing looks like), not a
correctness bug.

**Visual proof in the VM.** Captured via QEMU QMP `screendump`
(not faked): `bootloader/linux000_screen.png` — the full 80×25
VGA text screen painted with the timer-alternated `BABABA…`, the
faithful Linux 0.00 "the screen fills". This is the bare metal
running visibly in the QEMU VM, not just a serial transcript.

This is the faithful Linux 0.00 mechanism: two hardcoded tasks,
the real PIT/PIC, a real timer interrupt switching them, output
poked into VGA memory. Run it yourself: `scripts/linux000-run.sh`
(or `.bat`).

## Cross-references

- `kernel/README.md` — the v0.0 Connectome Manager API this builds on.
- `kernel/init.py` — `Init.tick()` (the timer-IRQ analogue) + the
  explicit "does NOT schedule / context-switch" design.
- `bootloader/src/bin/linux000.rs` — the bare-metal realization
  (32-bit, no GPU). `scripts/linux000-{build,run}.{sh,bat}`.
- `bootloader/README.md` — the v0.4 bootloader; its GPU-passthrough
  / GRUB-ISO blockers are about running the **Sutra kernel on a
  real GPU at boot** (v0.5+), NOT about Linux 0.00 (which is pure
  CPU+VGA and is done — see § "Two realizations").
- `planning/18-kernel-browser-readiness.md` — build-sequence context.
- Source: <https://computernewb.com/wiki/Linux_0.00>,
  oldlinux.org `Linux.old/kernel/0.00/`.
