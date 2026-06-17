# Yantra repo content audit — 2026-06-16

Question driving this audit: *what real, valuable content lives in the Yantra
repo, how much was already moved to Sutra, what could still move, and is the
bootloader the only real content?*

Short answer: **the bootloader is the strongest piece of original, working
systems code — but it is not the only real Yantra content.** The Python kernel
(Connectome Manager), the Rust orchestrator codecs, and the test suite are also
genuinely Yantra-specific and tested. Only a small amount (a couple of `apps/`
demos) really belongs on the Sutra side.

## Verdict by directory

| Directory | What it is | Real? | Verdict |
|-----------|-----------|-------|---------|
| `bootloader/` | ~1,070 lines Rust + x86 asm. Hand-rolled multiboot1 bootloader; boots in QEMU, PCI scan, GPU framebuffer write, kernel-image handoff, 32→64-bit long mode. Plus a bare-metal **Linux 0.00 replica** (`linux000`) with measured timer-driven context switching. Zero external crates. | **Real, verified, original** | **KEEP — crown jewel** |
| `kernel/` | ~2,322 lines Python. Connectome Manager: admission control, axon router, capability checks, GPU/RAM/disc tier moves, checkpointing — orchestrating **real** Sutra-compiled services on real torch tensors. | **Real, tested** | **KEEP — core** |
| `orchestrator/` | ~1,865 lines Rust. Byte-for-byte port of the kernel's wire codecs (YAXN/YAXE/YPRC/YKST) + no_std JSON reader + `dump-checkpoint`. Incremental, each unit tested against Python output. | **Real, tested, incomplete** | **KEEP — Rust port foundation** |
| `tests/` | ~3,733 lines, 14 files. 206 passing, 1 xfail. Covers kernel, real-Sutra integration, GPU/RAM tiers, codec round-trip, apps. | **Production-grade** | **KEEP** |
| `planning/` | 30 design docs (vision → substrate-honesty audit). Load-bearing; code references them. | 100% Yantra | **KEEP** |
| `paper/` | Position paper + clawRxiv reviews (auto-submitted). | 100% Yantra | **KEEP** |
| `scripts/`, `tools/` | Cache priming, paper submission, fixture regen, QEMU/Docker build wrappers. | Real, lightweight | **KEEP** |
| `apps/echo` | First native-Sutra userspace utility, kernel-admitted. Minimal by design. | Real | **KEEP** |
| `apps/terminal` | Multi-utility kernel-routing demo. | Real | **KEEP** |
| `apps/calc` | `.su` services exercise Sutra language features (exact arithmetic, defuzzified select, strings); Python host is a demo harness. A copy already exists at `external/Sutra/demos/calc/`. | Real but mostly language-level | **MOVE the `.su` to Sutra**, keep only the thin kernel-routing wrapper as a Yantra demo (or drop) |
| `apps/gui-rust` | Thin Rust `minifb` window that subprocess-calls `external/Sutra/demos/gui/`. Real work lives in Sutra. | Thin wrapper | **DELETE — use Sutra's demo directly** |
| `site/` | Single-page `yantraos.org` landing site. Being replaced by a redirect to noldor.tech. | n/a | Redirect (see PR #1) |

## Already moved to Sutra

`apps/font/` and `apps/gui/` (tkinter demos) migrated to `external/Sutra/demos/`
on 2026-05-28 — they were language-level, not OS-level. That migration is done
and documented in `apps/README.md`.

## What is NOT here (named plainly)

- No production Rust orchestrator (the codecs exist; router/init not yet ported).
- No real Sutra-on-GPU at boot (gated on GPU passthrough / VFIO; bootloader
  kernel-image is a sentinel placeholder).
- No userspace utilities beyond `echo` (cat/ls/grep planned, not started).
- No GUI (gated on the browser/TS layer).

## Bottom line

~4,000 lines of genuinely Yantra-specific working code (kernel + orchestrator +
bootloader + a couple of apps), backed by a real 206-test suite and a thorough
planning corpus. It is a small but coherent, honestly-scoped codebase — not a
bootloader sitting alone in an empty repo. The only real "move to Sutra"
candidates are `apps/calc` (the `.su` half) and `apps/gui-rust`.
