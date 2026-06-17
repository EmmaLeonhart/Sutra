//! YPRC per-process cold-store codec — the next Rust orchestrator unit.
//!
//! Byte-for-byte compatible with Python `kernel/checkpoint.py::serialise_process`:
//! the self-contained blob for one cold-stored process — its manifest, service
//! identity, and queued inbox. It wraps the `YAXE` envelopes from `axon` (unit
//! 2), so this composes the lower units.
//!
//! Layout (little-endian):
//! ```text
//!   0   4    magic b"YPRC"
//!   4   1    version (= 1)
//!   5   3    reserved
//!   8   ...  u32-len-prefixed name (UTF-8)
//!       ...  u32-len-prefixed manifest JSON (UTF-8)
//!       ...  u32-len-prefixed identity JSON (UTF-8)
//!       4    inbox count (u32 LE)
//!            per axon: u32-len-prefixed YAXE envelope
//! ```
//!
//! **JSON is NOT parsed here.** The manifest and identity are returned as
//! BORROWED byte slices. `no_std` without an allocator can't build the maps a
//! JSON parse needs; parsing them is a deferred, separable unit (a hand-rolled
//! `no_std` JSON reader, or `serde_json` once the orchestrator links `std`).
//! Naming that gap plainly — this unit reads the binary framing and hands the
//! JSON through untouched, which is the honest increment, not a faked parse.

use crate::axon::{
    parse_axon_envelope, put_u32_prefixed, read_u32, read_u32_prefixed, AxonEnvelope, ParseError,
    WriteError,
};

/// Magic prefix for a per-process cold-store blob.
pub const PROC_MAGIC: [u8; 4] = *b"YPRC";
/// Cold-store blob version.
pub const PROC_VERSION: u8 = 1;
/// Header size (magic + version + 3 reserved bytes).
pub const PROC_HEADER_SIZE: usize = 8;

/// A parsed per-process cold-store blob. `name` is validated UTF-8; the JSON
/// fields are borrowed, un-parsed bytes (see the module note); the inbox is
/// walked lazily via [`ProcessBlob::inbox`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProcessBlob<'a> {
    pub name: &'a str,
    pub manifest_json: &'a [u8],
    pub identity_json: &'a [u8],
    inbox_blob: &'a [u8],
    inbox_count: u32,
}

impl<'a> ProcessBlob<'a> {
    /// Number of queued axons in the inbox.
    pub fn inbox_count(&self) -> u32 {
        self.inbox_count
    }

    /// Lazily iterate the inbox axons. Each item is a `Result` because the YAXE
    /// envelope is parsed on access (framing validated at parse time).
    pub fn inbox(&self) -> InboxIter<'a> {
        InboxIter {
            data: self.inbox_blob,
            remaining: self.inbox_count,
        }
    }
}

/// Iterator over a [`ProcessBlob`]'s inbox. See [`ProcessBlob::inbox`].
#[derive(Debug, Clone)]
pub struct InboxIter<'a> {
    data: &'a [u8],
    remaining: u32,
}

impl<'a> Iterator for InboxIter<'a> {
    type Item = Result<AxonEnvelope<'a>, ParseError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        match read_u32_prefixed(self.data, 0) {
            Ok((env_bytes, end)) => {
                self.data = &self.data[end..];
                Some(parse_axon_envelope(env_bytes))
            }
            Err(e) => {
                self.remaining = 0; // stop after a framing error
                Some(Err(e))
            }
        }
    }
}

/// Parse a `YPRC` per-process cold-store blob.
pub fn parse_process_blob(data: &[u8]) -> Result<ProcessBlob<'_>, ParseError> {
    if data.len() < PROC_HEADER_SIZE {
        return Err(ParseError::TooShort);
    }
    if data[0..4] != PROC_MAGIC {
        return Err(ParseError::BadMagic);
    }
    let version = data[4];
    if version != PROC_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    // data[5..8] reserved.
    let (name_bytes, off) = read_u32_prefixed(data, PROC_HEADER_SIZE)?;
    let name = core::str::from_utf8(name_bytes).map_err(|_| ParseError::InvalidUtf8)?;
    let (manifest_json, off) = read_u32_prefixed(data, off)?;
    let (identity_json, off) = read_u32_prefixed(data, off)?;

    let inbox_count = read_u32(data, off)?;
    let inbox_start = off + 4;
    let mut walk = inbox_start;
    for _ in 0..inbox_count {
        let (_env, end) = read_u32_prefixed(data, walk)?;
        walk = end;
    }
    let inbox_blob = &data[inbox_start..walk];

    Ok(ProcessBlob {
        name,
        manifest_json,
        identity_json,
        inbox_blob,
        inbox_count,
    })
}

/// Write a `YPRC` blob into `out`, returning the bytes written. `manifest_json`
/// and `identity_json` are written through as opaque bytes (this unit does not
/// produce JSON — the caller supplies it); `inbox_envelopes` are each a full
/// `YAXE` blob (e.g. from `axon::write_axon_envelope`). No allocation.
pub fn write_process_blob(
    name: &str,
    manifest_json: &[u8],
    identity_json: &[u8],
    inbox_envelopes: &[&[u8]],
    out: &mut [u8],
) -> Result<usize, WriteError> {
    let u32_max = u32::MAX as usize;
    if name.len() > u32_max
        || manifest_json.len() > u32_max
        || identity_json.len() > u32_max
        || inbox_envelopes.len() > u32_max
        || inbox_envelopes.iter().any(|e| e.len() > u32_max)
    {
        return Err(WriteError::FieldTooLong);
    }
    let mut total =
        PROC_HEADER_SIZE + 4 + name.len() + 4 + manifest_json.len() + 4 + identity_json.len() + 4;
    for e in inbox_envelopes {
        total += 4 + e.len();
    }
    if out.len() < total {
        return Err(WriteError::BufferTooSmall {
            needed: total,
            got: out.len(),
        });
    }

    out[0..4].copy_from_slice(&PROC_MAGIC);
    out[4] = PROC_VERSION;
    out[5] = 0;
    out[6] = 0;
    out[7] = 0;
    let mut off = PROC_HEADER_SIZE;
    off = put_u32_prefixed(name.as_bytes(), out, off);
    off = put_u32_prefixed(manifest_json, out, off);
    off = put_u32_prefixed(identity_json, out, off);
    out[off..off + 4].copy_from_slice(&(inbox_envelopes.len() as u32).to_le_bytes());
    off += 4;
    for e in inbox_envelopes {
        off = put_u32_prefixed(e, out, off);
    }
    Ok(off)
}

// ---- YKST: the whole-kernel checkpoint (admission table + tiers + inboxes) ----

/// Storage tier of a process in a checkpoint. Tags match Python
/// `kernel/checkpoint.py` `_TIER_TAGS`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tier {
    Gpu,
    Disc,
    Ram,
}

impl Tier {
    pub const fn tag(self) -> u8 {
        match self {
            Tier::Gpu => 0,
            Tier::Disc => 1,
            Tier::Ram => 2,
        }
    }

    pub const fn from_tag(tag: u8) -> Option<Tier> {
        match tag {
            0 => Some(Tier::Gpu),
            1 => Some(Tier::Disc),
            2 => Some(Tier::Ram),
            _ => None,
        }
    }
}

/// Magic prefix for a whole-kernel checkpoint.
pub const KERNEL_MAGIC: [u8; 4] = *b"YKST";
/// Whole-kernel checkpoint version.
pub const KERNEL_VERSION: u8 = 1;
/// Header size: magic(4) + version(1) + reserved(3) + pool_total(4) +
/// pool_free(4) + process_count(4).
pub const KERNEL_HEADER_SIZE: usize = 20;

/// A parsed whole-kernel checkpoint: the compute-pool totals + a lazy iterator
/// over the admitted processes (each with its manifest/identity JSON, tier, and
/// inbox of YAXE envelopes).
#[derive(Debug, Clone, Copy)]
pub struct KernelCheckpoint<'a> {
    pub pool_total: u32,
    pub pool_free: u32,
    pub process_count: u32,
    records_blob: &'a [u8],
}

impl<'a> KernelCheckpoint<'a> {
    /// Lazily iterate the admitted processes (in the checkpoint's order, which
    /// Python writes sorted by name).
    pub fn processes(&self) -> ProcessIter<'a> {
        ProcessIter {
            data: self.records_blob,
            remaining: self.process_count,
        }
    }
}

/// One admitted process inside a [`KernelCheckpoint`]. Like a [`ProcessBlob`]
/// but with the storage [`Tier`] (the whole-kernel record interleaves the tier
/// tag between the manifest and identity sections).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProcessRecord<'a> {
    pub name: &'a str,
    pub manifest_json: &'a [u8],
    pub tier: Tier,
    pub identity_json: &'a [u8],
    inbox_blob: &'a [u8],
    inbox_count: u32,
}

impl<'a> ProcessRecord<'a> {
    pub fn inbox_count(&self) -> u32 {
        self.inbox_count
    }

    /// Lazily iterate the inbox, parsing each YAXE envelope on access.
    pub fn inbox(&self) -> InboxIter<'a> {
        InboxIter {
            data: self.inbox_blob,
            remaining: self.inbox_count,
        }
    }

    /// Lazily iterate the inbox as RAW (un-parsed) YAXE byte slices — useful to
    /// re-frame a record without re-serialising each envelope.
    pub fn inbox_raw(&self) -> InboxRawIter<'a> {
        InboxRawIter {
            data: self.inbox_blob,
            remaining: self.inbox_count,
        }
    }
}

/// Iterator over a [`ProcessRecord`]'s inbox as raw YAXE byte slices.
#[derive(Debug, Clone)]
pub struct InboxRawIter<'a> {
    data: &'a [u8],
    remaining: u32,
}

impl<'a> Iterator for InboxRawIter<'a> {
    type Item = Result<&'a [u8], ParseError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        match read_u32_prefixed(self.data, 0) {
            Ok((bytes, end)) => {
                self.data = &self.data[end..];
                Some(Ok(bytes))
            }
            Err(e) => {
                self.remaining = 0;
                Some(Err(e))
            }
        }
    }
}

/// Iterator over a [`KernelCheckpoint`]'s process records. See
/// [`KernelCheckpoint::processes`].
#[derive(Debug, Clone)]
pub struct ProcessIter<'a> {
    data: &'a [u8],
    remaining: u32,
}

impl<'a> Iterator for ProcessIter<'a> {
    type Item = Result<ProcessRecord<'a>, ParseError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        match parse_one_record(self.data) {
            Ok((rec, consumed)) => {
                self.data = &self.data[consumed..];
                Some(Ok(rec))
            }
            Err(e) => {
                self.remaining = 0; // stop after a framing error
                Some(Err(e))
            }
        }
    }
}

/// Parse a single process record at the start of `data`, returning the record
/// and the number of bytes it consumed.
fn parse_one_record(data: &[u8]) -> Result<(ProcessRecord<'_>, usize), ParseError> {
    let (name_bytes, off) = read_u32_prefixed(data, 0)?;
    let name = core::str::from_utf8(name_bytes).map_err(|_| ParseError::InvalidUtf8)?;
    let (manifest_json, off) = read_u32_prefixed(data, off)?;
    // tier tag (1 byte) + 3 pad
    if off + 4 > data.len() {
        return Err(ParseError::Truncated);
    }
    let tier = Tier::from_tag(data[off]).ok_or(ParseError::UnknownTier(data[off]))?;
    let off = off + 4;
    let (identity_json, off) = read_u32_prefixed(data, off)?;
    let inbox_count = read_u32(data, off)?;
    let inbox_start = off + 4;
    let mut walk = inbox_start;
    for _ in 0..inbox_count {
        let (_env, end) = read_u32_prefixed(data, walk)?;
        walk = end;
    }
    let inbox_blob = &data[inbox_start..walk];
    Ok((
        ProcessRecord {
            name,
            manifest_json,
            tier,
            identity_json,
            inbox_blob,
            inbox_count,
        },
        walk,
    ))
}

/// Parse a `YKST` whole-kernel checkpoint header; processes are walked lazily
/// via [`KernelCheckpoint::processes`].
pub fn parse_kernel_checkpoint(data: &[u8]) -> Result<KernelCheckpoint<'_>, ParseError> {
    if data.len() < KERNEL_HEADER_SIZE {
        return Err(ParseError::TooShort);
    }
    if data[0..4] != KERNEL_MAGIC {
        return Err(ParseError::BadMagic);
    }
    let version = data[4];
    if version != KERNEL_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    // data[5..8] reserved.
    let pool_total = read_u32(data, 8)?;
    let pool_free = read_u32(data, 12)?;
    let process_count = read_u32(data, 16)?;
    Ok(KernelCheckpoint {
        pool_total,
        pool_free,
        process_count,
        records_blob: &data[KERNEL_HEADER_SIZE..],
    })
}

/// One process to write into a kernel checkpoint (the input side of
/// [`write_kernel_checkpoint`]).
pub struct KernelProcess<'a> {
    pub name: &'a str,
    pub manifest_json: &'a [u8],
    pub tier: Tier,
    pub identity_json: &'a [u8],
    pub inbox_envelopes: &'a [&'a [u8]],
}

/// Write a `YKST` whole-kernel checkpoint into `out`. Processes are written in
/// the given order (pass them sorted by name to match Python's canonical form).
/// No allocation.
pub fn write_kernel_checkpoint(
    pool_total: u32,
    pool_free: u32,
    processes: &[KernelProcess],
    out: &mut [u8],
) -> Result<usize, WriteError> {
    let u32_max = u32::MAX as usize;
    if processes.len() > u32_max {
        return Err(WriteError::FieldTooLong);
    }
    let mut total = KERNEL_HEADER_SIZE;
    for p in processes {
        if p.name.len() > u32_max
            || p.manifest_json.len() > u32_max
            || p.identity_json.len() > u32_max
            || p.inbox_envelopes.len() > u32_max
            || p.inbox_envelopes.iter().any(|e| e.len() > u32_max)
        {
            return Err(WriteError::FieldTooLong);
        }
        total += 4 + p.name.len() + 4 + p.manifest_json.len() + 4 /*tier+pad*/
            + 4 + p.identity_json.len() + 4 /*inbox count*/;
        for e in p.inbox_envelopes {
            total += 4 + e.len();
        }
    }
    if out.len() < total {
        return Err(WriteError::BufferTooSmall {
            needed: total,
            got: out.len(),
        });
    }

    out[0..4].copy_from_slice(&KERNEL_MAGIC);
    out[4] = KERNEL_VERSION;
    out[5] = 0;
    out[6] = 0;
    out[7] = 0;
    out[8..12].copy_from_slice(&pool_total.to_le_bytes());
    out[12..16].copy_from_slice(&pool_free.to_le_bytes());
    out[16..20].copy_from_slice(&(processes.len() as u32).to_le_bytes());
    let mut off = KERNEL_HEADER_SIZE;
    for p in processes {
        off = put_u32_prefixed(p.name.as_bytes(), out, off);
        off = put_u32_prefixed(p.manifest_json, out, off);
        out[off] = p.tier.tag();
        out[off + 1] = 0;
        out[off + 2] = 0;
        out[off + 3] = 0;
        off += 4;
        off = put_u32_prefixed(p.identity_json, out, off);
        out[off..off + 4].copy_from_slice(&(p.inbox_envelopes.len() as u32).to_le_bytes());
        off += 4;
        for e in p.inbox_envelopes {
            off = put_u32_prefixed(e, out, off);
        }
    }
    Ok(off)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::axon::{write_axon_envelope, write_axon_payload, DType, HEADER_SIZE};

    /// Build a small YAXE envelope (payload f32[1,2]) into `buf`, return its len.
    fn make_envelope(role: &str, from_proc: &str, keys: &[&str], buf: &mut [u8]) -> usize {
        let mut body = [0u8; 8];
        body[0..4].copy_from_slice(&1.0f32.to_le_bytes());
        body[4..8].copy_from_slice(&2.0f32.to_le_bytes());
        let mut yaxn = [0u8; HEADER_SIZE + 8];
        let pn = write_axon_payload(DType::Float32, &body, &mut yaxn).unwrap();
        write_axon_envelope(role, from_proc, keys, &yaxn[..pn], buf).unwrap()
    }

    #[test]
    fn write_then_parse_round_trips() {
        let mut env = [0u8; 128];
        let en = make_envelope("R_in", "proc1", &["k"], &mut env);
        let mut out = [0u8; 512];
        let n = write_process_blob(
            "p1",
            b"{\"m\":1}",
            b"{\"kind\":\"sutra\"}",
            &[&env[..en]],
            &mut out,
        )
        .unwrap();

        let pb = parse_process_blob(&out[..n]).unwrap();
        assert_eq!(pb.name, "p1");
        assert_eq!(pb.manifest_json, b"{\"m\":1}");
        assert_eq!(pb.identity_json, b"{\"kind\":\"sutra\"}");
        assert_eq!(pb.inbox_count(), 1);
        let envs: Result<Vec<_>, _> = pb.inbox().collect();
        let envs = envs.unwrap();
        assert_eq!(envs.len(), 1);
        assert_eq!(envs[0].role, "R_in");
        assert_eq!(envs[0].from_proc, "proc1");
        assert_eq!(envs[0].payload.width, 2);
    }

    #[test]
    fn write_then_parse_empty_inbox() {
        let mut out = [0u8; 64];
        let n = write_process_blob("p", b"{}", b"{}", &[], &mut out).unwrap();
        let pb = parse_process_blob(&out[..n]).unwrap();
        assert_eq!(pb.name, "p");
        assert_eq!(pb.inbox_count(), 0);
        assert_eq!(pb.inbox().count(), 0);
    }

    // The exact bytes Python `kernel/checkpoint.py::serialise_process` emits for
    // the echo process with one queued axon (payload f32[1,2,3]). Captured
    // 2026-05-25 as a fixed test vector (regenerate: admit echo, push an Axon
    // with that payload, serialise_process). The identity JSON carries a
    // machine-relative source_path, so the test asserts FRAMING (name + manifest
    // bytes + the parsed envelope), not the path content.
    const PY_YPRC: &[u8] = include_bytes!("../tests/fixtures/echo_process.yprc");

    #[test]
    fn parse_python_process_blob() {
        let pb = parse_process_blob(PY_YPRC).unwrap();
        assert_eq!(pb.name, "echo");

        // manifest JSON slice — exact ends pin the slice boundaries.
        assert_eq!(pb.manifest_json.len(), 161);
        assert!(pb.manifest_json.starts_with(b"{\"axon_keys\": [\"stdin_text\"]"));
        assert!(pb.manifest_json.ends_with(b"\"write_roles\": [\"R_stdout\"]}"));

        // identity JSON slice (path content is machine-relative; check framing).
        assert_eq!(pb.identity_json.len(), 173);
        assert!(pb.identity_json.starts_with(b"{\"entry_point\": \"on_axon\""));
        assert_eq!(pb.identity_json.last(), Some(&b'}'));

        // inbox: one YAXE envelope, parsed by unit 2.
        assert_eq!(pb.inbox_count(), 1);
        let envs: Result<Vec<_>, _> = pb.inbox().collect();
        let envs = envs.unwrap();
        assert_eq!(envs.len(), 1);
        let e = &envs[0];
        assert_eq!(e.role, "R_stdin");
        assert_eq!(e.from_proc, "external");
        let keys: Result<Vec<_>, _> = e.keys().collect();
        assert_eq!(keys.unwrap(), vec!["stdin_text"]);
        assert_eq!(e.payload.width, 3);
        let b = e.payload.body;
        let vals = [
            f32::from_le_bytes([b[0], b[1], b[2], b[3]]),
            f32::from_le_bytes([b[4], b[5], b[6], b[7]]),
            f32::from_le_bytes([b[8], b[9], b[10], b[11]]),
        ];
        assert_eq!(vals, [1.0f32, 2.0, 3.0]);
    }

    #[test]
    fn rust_write_reproduces_python_framing() {
        // Re-wrap the SAME pieces Python emitted and confirm the bytes match,
        // proving the writer is byte-compatible with serialise_process.
        let pb = parse_process_blob(PY_YPRC).unwrap();
        // Pull the single inbox envelope's raw bytes back out. Compute the
        // length-prefix offset from the parsed field lengths (no magic numbers):
        // header + each u32-prefixed section + the inbox-count u32.
        let env_prefix_off = PROC_HEADER_SIZE
            + 4
            + pb.name.len()
            + 4
            + pb.manifest_json.len()
            + 4
            + pb.identity_json.len()
            + 4;
        let env_len = u32::from_le_bytes(
            PY_YPRC[env_prefix_off..env_prefix_off + 4].try_into().unwrap(),
        ) as usize;
        let env_bytes = &PY_YPRC[env_prefix_off + 4..env_prefix_off + 4 + env_len];
        let mut out = vec![0u8; PY_YPRC.len()];
        let n = write_process_blob(
            pb.name,
            pb.manifest_json,
            pb.identity_json,
            &[env_bytes],
            &mut out,
        )
        .unwrap();
        assert_eq!(n, PY_YPRC.len());
        assert_eq!(&out[..n], PY_YPRC);
    }

    #[test]
    fn parse_rejects_bad_magic() {
        let mut b = PY_YPRC.to_vec();
        b[0] = b'X';
        assert_eq!(parse_process_blob(&b), Err(ParseError::BadMagic));
    }

    #[test]
    fn parse_rejects_short() {
        assert_eq!(parse_process_blob(&[89, 80, 82]), Err(ParseError::TooShort));
    }

    // --- YKST whole-kernel checkpoint ---

    // Real Python kernel/checkpoint.py::serialise_kernel_state output for a
    // 2-process kernel: echo (GPU, one queued f32[1,2,3] axon) + echo2 (DISC,
    // empty). Committed fixed test vector; identity paths are machine-relative
    // so the test asserts framing + tiers, not path content.
    const PY_YKST: &[u8] = include_bytes!("../tests/fixtures/kernel_state.ykst");

    #[test]
    fn tier_tag_round_trips() {
        for t in [Tier::Gpu, Tier::Disc, Tier::Ram] {
            assert_eq!(Tier::from_tag(t.tag()), Some(t));
        }
    }

    #[test]
    fn parse_python_kernel_checkpoint() {
        let cp = parse_kernel_checkpoint(PY_YKST).unwrap();
        assert_eq!(cp.pool_total, 10);
        assert_eq!(cp.pool_free, 8);
        assert_eq!(cp.process_count, 2);

        let recs: Result<Vec<_>, _> = cp.processes().collect();
        let recs = recs.unwrap();
        assert_eq!(recs.len(), 2);

        // echo — GPU, one queued axon (payload f32[1,2,3]).
        assert_eq!(recs[0].name, "echo");
        assert_eq!(recs[0].tier, Tier::Gpu);
        assert!(recs[0].manifest_json.starts_with(b"{\"axon_keys\""));
        assert_eq!(recs[0].inbox_count(), 1);
        let envs: Result<Vec<_>, _> = recs[0].inbox().collect();
        let envs = envs.unwrap();
        assert_eq!(envs[0].role, "R_stdin");
        assert_eq!(envs[0].from_proc, "external");
        assert_eq!(envs[0].payload.width, 3);

        // echo2 — DISC, empty inbox.
        assert_eq!(recs[1].name, "echo2");
        assert_eq!(recs[1].tier, Tier::Disc);
        assert_eq!(recs[1].inbox_count(), 0);
        assert_eq!(recs[1].inbox().count(), 0);
    }

    #[test]
    fn rust_write_reproduces_python_kernel_byte_for_byte() {
        let cp = parse_kernel_checkpoint(PY_YKST).unwrap();
        let recs: Vec<_> = cp.processes().map(|r| r.unwrap()).collect();
        let echo_inbox: Vec<&[u8]> = recs[0].inbox_raw().map(|r| r.unwrap()).collect();
        let echo2_inbox: Vec<&[u8]> = recs[1].inbox_raw().map(|r| r.unwrap()).collect();
        let procs = [
            KernelProcess {
                name: recs[0].name,
                manifest_json: recs[0].manifest_json,
                tier: recs[0].tier,
                identity_json: recs[0].identity_json,
                inbox_envelopes: &echo_inbox,
            },
            KernelProcess {
                name: recs[1].name,
                manifest_json: recs[1].manifest_json,
                tier: recs[1].tier,
                identity_json: recs[1].identity_json,
                inbox_envelopes: &echo2_inbox,
            },
        ];
        let mut out = vec![0u8; PY_YKST.len()];
        let n = write_kernel_checkpoint(cp.pool_total, cp.pool_free, &procs, &mut out).unwrap();
        assert_eq!(n, PY_YKST.len());
        assert_eq!(&out[..n], PY_YKST);
    }

    #[test]
    fn write_then_parse_kernel_round_trips() {
        let mut env = [0u8; 128];
        let en = make_envelope("R_stdin", "external", &["k"], &mut env);
        let procs = [
            KernelProcess {
                name: "a",
                manifest_json: b"{\"name\":\"a\"}",
                tier: Tier::Gpu,
                identity_json: b"{\"kind\":\"sutra\"}",
                inbox_envelopes: &[&env[..en]],
            },
            KernelProcess {
                name: "b",
                manifest_json: b"{\"name\":\"b\"}",
                tier: Tier::Disc,
                identity_json: b"{\"kind\":\"sutra\"}",
                inbox_envelopes: &[],
            },
        ];
        let mut out = [0u8; 512];
        let n = write_kernel_checkpoint(10, 8, &procs, &mut out).unwrap();

        let cp = parse_kernel_checkpoint(&out[..n]).unwrap();
        assert_eq!(cp.pool_total, 10);
        assert_eq!(cp.pool_free, 8);
        assert_eq!(cp.process_count, 2);
        let recs: Vec<_> = cp.processes().map(|r| r.unwrap()).collect();
        assert_eq!(recs[0].name, "a");
        assert_eq!(recs[0].tier, Tier::Gpu);
        assert_eq!(recs[0].inbox_count(), 1);
        assert_eq!(recs[1].name, "b");
        assert_eq!(recs[1].tier, Tier::Disc);
        assert_eq!(recs[1].inbox_count(), 0);
    }

    #[test]
    fn parse_kernel_rejects_bad_magic() {
        let mut b = PY_YKST.to_vec();
        b[0] = b'X';
        assert!(matches!(
            parse_kernel_checkpoint(&b),
            Err(ParseError::BadMagic)
        ));
    }

    #[test]
    fn parse_kernel_rejects_short() {
        assert!(matches!(
            parse_kernel_checkpoint(&[89, 75, 83, 84, 1]),
            Err(ParseError::TooShort)
        ));
    }

    #[test]
    fn manifest_and_identity_json_read_via_json_module() {
        // End-to-end: the codec hands back manifest_json / identity_json as
        // opaque bytes; crate::json turns them into typed fields. Parse the real
        // YKST fixture, take echo's record, and read its manifest + identity.
        use crate::json;
        let cp = parse_kernel_checkpoint(PY_YKST).unwrap();
        let rec = cp.processes().next().unwrap().unwrap();
        assert_eq!(rec.name, "echo");
        assert_eq!(json::get_str(rec.manifest_json, "name"), Some("echo"));
        assert_eq!(json::get_u32(rec.manifest_json, "axon_width"), Some(768));
        assert_eq!(json::get_u32(rec.manifest_json, "compute_units"), Some(1));
        let read: Vec<&str> =
            json::get_str_array(rec.manifest_json, "read_roles").unwrap().collect();
        assert_eq!(read, vec!["R_stdin"]);
        assert_eq!(json::get_str(rec.identity_json, "kind"), Some("sutra"));
        assert_eq!(json::get_str(rec.identity_json, "entry_point"), Some("on_axon"));
    }
}
