# Filesystem bridge

## Why the file system stays conventional

A connectionist file system would be a nightmare. If you pulled the drive
out of a Yantra box, a forensics or recovery tool would see "a bunch of
matrices" and have nothing to work with. Persistent state should be
**legible** — both for safety-critical certification and for ordinary
human reasons like "I want to read my files on a different machine."

So the file system on a Yantra box is a normal modern Linux-style
filesystem (ext4, btrfs, zfs — pick one, ship one, support one). Files are
bytes on disk. Directory structure is trees. Permissions are POSIX-ish.

The interesting part is the **bridge** between that legible byte-shaped
world and the connectionist world the rest of the OS lives in.

## Two reading modes

A Yantra application asking the file system for a file gets back an axon.
The file's metadata determines which of two reading modes the bridge
uses:

### `verbatim` mode — lossless byte transport

For executables, configs, binaries, and anything where the application
needs the exact bytes:

- Bytes are encoded into a deterministic Sutra-compiled axon.
- Decoding the axon back to bytes is exact (lossless).
- The axon width grows linearly with file size — this is the costly mode,
  reserved for things that need it.

### `semantic` mode — embedded representation

For documents, source code, datasets, anything where the application
wants to consume meaning rather than literal bytes:

- The bridge runs the file through a configured embedding model
  (`nomic-embed-text`, `mxbai-embed-large`, `ESM-2`, etc.) and returns
  the resulting embedding as the axon's primary filler.
- Cheap, bounded-width regardless of file size.
- The same file can have multiple semantic representations cached on
  disk, keyed by which embedding model produced them.

The two modes coexist on the same file. A program that needs the bytes
asks for `verbatim`; a program that needs the meaning asks for
`semantic`. The metadata for "what default applies" is part of the file's
xattrs, set at creation time by whatever wrote the file.

## Syscall surface

```
read_file       : { R_path, R_mode } -> { R_axon, R_metadata, R_status }
write_file      : { R_path, R_payload, R_mode } -> { R_status }
open_dir        : { R_path } -> { R_listing_axon, R_status }
stat            : { R_path } -> { R_metadata, R_status }
unlink          : { R_path } -> { R_status }
move            : { R_src, R_dst } -> { R_status }
mount           : { R_device, R_path, R_fstype } -> { R_status }
chmod / chown / chcap : self-explanatory, capability-based
```

`R_status` is always present — it's a small axon role that carries error
information. Yantra does not reuse a magic numeric return value the way
POSIX does; the status axon can carry richer structured info that the
caller can pattern-match on.

## Where the file system code actually runs

The userspace process that talks to the disk hardware is itself a Sutra
program that init admits at boot. It owns:

- The block-device-side conversation (which on conventional hardware is a
  CPU-side shim — the disk doesn't speak axons natively).
- The translation between byte ranges and axons.
- The embedding model orchestration for `semantic` mode.

If this process crashes, init restarts it. While it's down, syscalls that
touch storage block until it's back; other parts of the system continue
to run, which is unusual for an OS but works because the kernel only
talks to the FS via the same axon channel anyone else does.

## Caching

Two caches live in the bridge:

1. **Verbatim chunk cache** in GPU memory — when a process is repeatedly
   reading the same file, the encoded axons stay resident. Standard LRU.
2. **Semantic embedding cache** in storage — embeddings are expensive to
   compute, so the bridge writes them to a sidecar file (`.foo.embed.bin`
   next to `foo`). Stat, mtime, embedding model id, and width are part of
   the key. If any change, the cache misses.

## What this gives us

- Disks are recoverable on any standard Linux machine. Pull the drive,
  mount it, your data is there. This matters for defense and aerospace
  certification *and* for ordinary trust.
- Embeddings are not the storage format — they are a *projection* of the
  storage format. If your embedding model gets better, your files don't
  rot; you regenerate the cache and move on.
- Capabilities for files are the same machinery as capabilities for IPC.
  Granting a process access to `/etc/secrets` is bundling the
  appropriate role into its launch axon.

## Open questions

- **Mounting embedded representations as virtual files.** A useful
  pattern would be: `cat /docs/report.md.embed` returns the bytes of the
  cached embedding, so external tooling can introspect. Probably worth
  shipping.
- **Sparse storage of `verbatim` axons.** A 10 GB log file in `verbatim`
  mode would generate a huge axon. Streaming/chunked semantics need to
  be designed for; the syscall surface above doesn't yet account for
  chunked reads.
- **Cross-FS mounts and network filesystems.** NFS, S3-style object
  stores. Probably the same userspace-process trick (a different
  storage-handler service), but each adds embedding cache complications.
