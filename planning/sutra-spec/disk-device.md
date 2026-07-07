# Disk device — persistent named storage for the neural filesystem (prerequisite P1)

> **Design note, 2026-07-06.** The neural-Unix track (`queue.md` § "NEURAL UNIX
> UTILITIES") reaches Tier D — the filesystem tools (`cat FILE`, `ls`, `cp`/`mv`/`rm`,
> `find`) — and they need something the RAM device does not provide: **named, persistent
> files**. This spec is the design for that store, prerequisite **P1** in the queue,
> written first (like `neural-regex-nfa.md` was for P2) per the queue's "spec it in
> `planning/sutra-spec/` before building" instruction.

## Why a disk, distinct from RAM

`ram_device.py` is a flat, volatile buffer: integer-addressed cells holding VRAM
vectors, gone when the process ends (`ram-pointers.md`). The filesystem tools need two
things it lacks:

1. **A namespace** — files are addressed by PATH (`report.txt`, `dir/a.log`), not by a
   bare integer. `ls` lists the namespace; `cat FILE`, `cp`, `mv`, `rm`, `find` all
   resolve a path to content.
2. **Persistence** — a file written by one invocation is readable by the next. The RAM
   buffer is per-run scratch; a disk survives.

## Where it lives (the honesty line, mirroring `ram-pointers.md`)

The disk is an **I/O device**, exactly as RAM is. `ram-pointers.md` is explicit that RAM
access is host I/O and never a Sutra operation; the same holds here, more so — a real
filesystem IS host storage. So:

- **The disk is backed by real host storage** — a host directory on the machine's actual
  filesystem (the `DiskDevice` maps a neural path to a host path under a sandbox root).
  Reading a file's bytes, listing a directory, creating/renaming/removing an entry are
  **host I/O at the wire**, serviced by the orchestrator — the same role it plays for RAM.
- **The substrate work is the byte processing**, unchanged from Tiers A–C. `cat FILE`
  loads the file's bytes into an addressable region and drives the SAME substrate read
  head (`text_scan.su`) that streamed stdin for `cat`; `ls` streams the directory entries
  through the same scan/emit; a future `grep FILE` runs the on-substrate NFA over the
  file's bytes. The disk changes only WHERE the bytes come from (a named, persistent
  region instead of stdin), not what the substrate does with them.

This keeps the division every rung has held: **substrate transforms the bytes, host does
the I/O** — and path resolution / directory mutation are I/O, so they are host, like the
pointer↔address translation the orchestrator already does at the RAM wire.

## Model

- **`DiskDevice(root)`** — a persistent store rooted at a host sandbox directory. API
  mirrors `RamDevice` where it can:
  - `list()` → the directory entries (names), sorted — the namespace. Backs `ls`.
  - `read_region(path)` → an addressable region (a `RamDevice`-like view, or a cell list)
    holding the file's codepoints, so the substrate read head can scan it. Backs
    `cat FILE`. Out-of-namespace path → the empty region (Sutra's "no runtime errors by
    mechanism": a meaningless-but-valid empty read, not an exception — same as RAM's OOB).
  - `write_region(path, cells)` / `copy(src, dst)` / `move(src, dst)` / `remove(path)` —
    mutation, backing `cp` / `mv` / `rm`. Each is a host directory op at the wire.
  - `exists(path)`, `is_dir(path)` — for `find` recursion and `ls -l`.
- **path→region map** — for the first cut a FLAT namespace (filenames → regions) is
  enough for `cat FILE` and `ls` in one directory. Nested directories (needed by `find`
  and `ls dir/`) are a tree of `DiskDevice` views — deferred to the `find` rung.

## Tier D rungs on top of P1

- `cat FILE [FILE2 …]` — resolve each path→region (I/O), stream its cells through the
  substrate read head, concatenating; decoded emit-stream == the files' bytes. The only
  change from stdin `cat` is the byte source.
- `ls [DIR]` — stream `DiskDevice.list()` entries through the substrate scan/emit (one
  name per record); == coreutils `ls -1`. `-a` includes dotfiles; `-l` adds metadata (host).
- `cp` / `mv` / `rm` — namespace mutations (host directory ops); verify by reading back.
- `find [DIR] [-name PAT]` — recursive directory walk; `-name` filters entries with the
  on-substrate NFA (fnmatch → regex). Needs the nested-directory tree above.

## Open questions

1. **Nested directories.** The flat namespace suffices for `cat FILE`/`ls` in one dir;
   `find` and `ls dir/` need a directory tree and path parsing. Design the tree + a
   substrate-vs-host split for path resolution alongside the `find` rung.
2. **Is path resolution substrate or host?** It is host I/O here (a directory lookup at
   the wire, like the RAM pointer decode). A more ambitious design could make path lookup
   a content-addressed argmax over a directory codebook (the `WASM/` argmax-attention RAM
   dispatch, `2026-06-06-iso5-ram-based-machine-dispatch-works.md`) — noted, not built.
3. **Persistence boundary.** The sandbox root is a real host directory; deciding its
   lifetime/location (temp vs project-relative) is an operational call, made when `cp`/`mv`
   /`rm` land (they mutate real files).
