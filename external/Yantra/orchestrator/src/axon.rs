//! YAXN axon-payload wire codec — the first Rust orchestrator unit.
//!
//! Byte-for-byte compatible with Python `kernel/serialise.py`
//! (`serialise_axon_payload` / `deserialise_axon_payload`). The eventual Rust
//! orchestrator must read checkpoints the Python prototype writes (and write
//! ones it can read), so this format is shared ground truth — the tests below
//! embed the exact bytes the Python encoder emits and assert the Rust codec
//! matches in BOTH directions (decode and byte-for-byte encode).
//!
//! Format (little-endian, 12-byte header + raw body):
//!
//! ```text
//!   off  size  field
//!   0    4     magic  b"YAXN"
//!   4    1     version (= 1)
//!   5    1     dtype tag (0=f32, 1=f64, 2=complex64, 3=complex128)
//!   6    2     reserved (pads the header to 8 bytes)
//!   8    4     width (u32 LE) — number of elements
//!   12   W*S   body  W = width, S = element size
//! ```
//!
//! Pure `core`; no allocation. Parsing borrows the input body slice; writing
//! fills a caller-provided buffer.

/// Magic prefix every payload blob starts with.
pub const MAGIC: [u8; 4] = *b"YAXN";
/// Wire format version this unit reads and writes.
pub const VERSION: u8 = 1;
/// Fixed header size in bytes (magic + version + dtype + reserved + width).
pub const HEADER_SIZE: usize = 12;

/// The element dtype of an axon payload. Wire tags are fixed numbers shared
/// with Python `_DTYPE_TAGS`; never reassign an existing tag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DType {
    Float32,
    Float64,
    Complex64,
    Complex128,
}

impl DType {
    /// The byte written to / read from the wire for this dtype.
    pub const fn tag(self) -> u8 {
        match self {
            DType::Float32 => 0,
            DType::Float64 => 1,
            DType::Complex64 => 2,
            DType::Complex128 => 3,
        }
    }

    /// Inverse of [`DType::tag`]. `None` for an unknown tag.
    pub const fn from_tag(tag: u8) -> Option<DType> {
        match tag {
            0 => Some(DType::Float32),
            1 => Some(DType::Float64),
            2 => Some(DType::Complex64),
            3 => Some(DType::Complex128),
            _ => None,
        }
    }

    /// Bytes per element on the wire (complex = 2 reals).
    pub const fn element_size(self) -> usize {
        match self {
            DType::Float32 => 4,
            DType::Float64 => 8,
            DType::Complex64 => 8,
            DType::Complex128 => 16,
        }
    }
}

/// Why a blob failed to parse.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParseError {
    /// Fewer than [`HEADER_SIZE`] bytes.
    TooShort,
    /// First four bytes are not [`MAGIC`].
    BadMagic,
    /// Version byte this unit does not read.
    UnsupportedVersion(u8),
    /// dtype tag with no known [`DType`].
    UnknownDtype(u8),
    /// Body length does not equal `width * element_size`.
    BodySizeMismatch { expected: usize, actual: usize },
    /// A length-prefixed envelope field claims more bytes than remain.
    Truncated,
    /// A string field (role / from_proc / key) is not valid UTF-8.
    InvalidUtf8,
    /// A process record carried a storage-tier tag with no known `Tier`.
    UnknownTier(u8),
}

/// Why a payload failed to write.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WriteError {
    /// Output buffer smaller than `HEADER_SIZE + body.len()`.
    BufferTooSmall { needed: usize, got: usize },
    /// `body.len()` is not a whole number of elements for the dtype.
    BodyNotElementAligned,
    /// The element count would not fit in the u32 width field.
    WidthOverflow,
    /// An envelope field's length would not fit in its u32 length prefix.
    FieldTooLong,
}

/// A parsed payload: dtype + width + a borrow of the raw little-endian body.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AxonPayload<'a> {
    pub dtype: DType,
    pub width: u32,
    pub body: &'a [u8],
}

/// Parse a `YAXN` blob into its dtype, width, and body slice.
///
/// Borrows `data` — the returned `body` points into it. Validates magic,
/// version, dtype tag, and that the body length matches `width * element_size`.
pub fn parse_axon_payload(data: &[u8]) -> Result<AxonPayload<'_>, ParseError> {
    if data.len() < HEADER_SIZE {
        return Err(ParseError::TooShort);
    }
    if data[0..4] != MAGIC {
        return Err(ParseError::BadMagic);
    }
    let version = data[4];
    if version != VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    let dtype = match DType::from_tag(data[5]) {
        Some(d) => d,
        None => return Err(ParseError::UnknownDtype(data[5])),
    };
    // data[6..8] are reserved padding — ignored.
    let width = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
    let body = &data[HEADER_SIZE..];
    let expected = (width as usize) * dtype.element_size();
    if body.len() != expected {
        return Err(ParseError::BodySizeMismatch {
            expected,
            actual: body.len(),
        });
    }
    Ok(AxonPayload { dtype, width, body })
}

/// Write a `YAXN` blob (header + `body`) into `out`. Returns the number of
/// bytes written (`HEADER_SIZE + body.len()`).
///
/// `body` must be a whole number of `dtype` elements; the width field is
/// derived from `body.len() / element_size`. No allocation — the caller owns
/// `out`.
pub fn write_axon_payload(dtype: DType, body: &[u8], out: &mut [u8]) -> Result<usize, WriteError> {
    let esize = dtype.element_size();
    if body.len() % esize != 0 {
        return Err(WriteError::BodyNotElementAligned);
    }
    let width = body.len() / esize;
    if width > u32::MAX as usize {
        return Err(WriteError::WidthOverflow);
    }
    let total = HEADER_SIZE + body.len();
    if out.len() < total {
        return Err(WriteError::BufferTooSmall {
            needed: total,
            got: out.len(),
        });
    }
    out[0..4].copy_from_slice(&MAGIC);
    out[4] = VERSION;
    out[5] = dtype.tag();
    out[6] = 0;
    out[7] = 0;
    out[8..12].copy_from_slice(&(width as u32).to_le_bytes());
    out[HEADER_SIZE..total].copy_from_slice(body);
    Ok(total)
}

// ---- YAXE: the full axon envelope (role + from_proc + keys + payload) ----

/// Magic prefix for a full axon envelope.
pub const ENV_MAGIC: [u8; 4] = *b"YAXE";
/// Envelope wire format version.
pub const ENV_VERSION: u8 = 1;
/// Envelope header size (magic + version + 3 reserved bytes).
pub const ENV_HEADER_SIZE: usize = 8;

/// A parsed axon envelope. `role` and `from_proc` are validated UTF-8 borrows;
/// `payload` is the parsed nested YAXN payload; keys are walked lazily via
/// [`AxonEnvelope::keys`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AxonEnvelope<'a> {
    pub role: &'a str,
    pub from_proc: &'a str,
    keys_blob: &'a [u8],
    keys_count: u32,
    pub payload: AxonPayload<'a>,
}

impl<'a> AxonEnvelope<'a> {
    /// Number of keys carried.
    pub fn keys_count(&self) -> u32 {
        self.keys_count
    }

    /// Lazily iterate the keys. Each item is a `Result` because the key's
    /// UTF-8 is validated on access (the length framing was validated at
    /// parse time).
    pub fn keys(&self) -> KeyIter<'a> {
        KeyIter {
            data: self.keys_blob,
            remaining: self.keys_count,
        }
    }
}

/// Iterator over an [`AxonEnvelope`]'s keys. See [`AxonEnvelope::keys`].
#[derive(Debug, Clone)]
pub struct KeyIter<'a> {
    data: &'a [u8],
    remaining: u32,
}

impl<'a> Iterator for KeyIter<'a> {
    type Item = Result<&'a str, ParseError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        match read_u32_prefixed(self.data, 0) {
            Ok((bytes, end)) => {
                self.data = &self.data[end..];
                Some(core::str::from_utf8(bytes).map_err(|_| ParseError::InvalidUtf8))
            }
            Err(e) => {
                self.remaining = 0; // stop after a framing error
                Some(Err(e))
            }
        }
    }
}

pub(crate) fn read_u32(data: &[u8], off: usize) -> Result<u32, ParseError> {
    if off + 4 > data.len() {
        return Err(ParseError::Truncated);
    }
    Ok(u32::from_le_bytes([
        data[off],
        data[off + 1],
        data[off + 2],
        data[off + 3],
    ]))
}

/// Read a u32-LE-length-prefixed byte field at `off`. Returns the field bytes
/// and the offset just past it.
pub(crate) fn read_u32_prefixed(data: &[u8], off: usize) -> Result<(&[u8], usize), ParseError> {
    let len = read_u32(data, off)? as usize;
    let start = off + 4;
    let end = start.checked_add(len).ok_or(ParseError::Truncated)?;
    if end > data.len() {
        return Err(ParseError::Truncated);
    }
    Ok((&data[start..end], end))
}

/// Parse a `YAXE` envelope: role, from_proc, keys, and the nested YAXN payload.
pub fn parse_axon_envelope(data: &[u8]) -> Result<AxonEnvelope<'_>, ParseError> {
    if data.len() < ENV_HEADER_SIZE {
        return Err(ParseError::TooShort);
    }
    if data[0..4] != ENV_MAGIC {
        return Err(ParseError::BadMagic);
    }
    let version = data[4];
    if version != ENV_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    // data[5..8] reserved.
    let (role_bytes, off) = read_u32_prefixed(data, ENV_HEADER_SIZE)?;
    let (fp_bytes, off) = read_u32_prefixed(data, off)?;
    let role = core::str::from_utf8(role_bytes).map_err(|_| ParseError::InvalidUtf8)?;
    let from_proc = core::str::from_utf8(fp_bytes).map_err(|_| ParseError::InvalidUtf8)?;

    let keys_count = read_u32(data, off)?;
    let keys_start = off + 4;
    let mut walk = keys_start;
    for _ in 0..keys_count {
        let (_k, end) = read_u32_prefixed(data, walk)?;
        walk = end;
    }
    let keys_blob = &data[keys_start..walk];

    let (payload_bytes, _off) = read_u32_prefixed(data, walk)?;
    let payload = parse_axon_payload(payload_bytes)?;

    Ok(AxonEnvelope {
        role,
        from_proc,
        keys_blob,
        keys_count,
        payload,
    })
}

/// Write a `YAXE` envelope into `out`, returning the bytes written. `keys` are
/// written in the given order — pass them sorted to reproduce Python's
/// canonical encoding. `payload_yaxn` must already be a `YAXN` blob (e.g. from
/// [`write_axon_payload`]). No allocation.
pub fn write_axon_envelope(
    role: &str,
    from_proc: &str,
    keys: &[&str],
    payload_yaxn: &[u8],
    out: &mut [u8],
) -> Result<usize, WriteError> {
    let u32_max = u32::MAX as usize;
    if role.len() > u32_max
        || from_proc.len() > u32_max
        || payload_yaxn.len() > u32_max
        || keys.len() > u32_max
        || keys.iter().any(|k| k.len() > u32_max)
    {
        return Err(WriteError::FieldTooLong);
    }
    let mut total = ENV_HEADER_SIZE + 4 + role.len() + 4 + from_proc.len() + 4;
    for k in keys {
        total += 4 + k.len();
    }
    total += 4 + payload_yaxn.len();
    if out.len() < total {
        return Err(WriteError::BufferTooSmall {
            needed: total,
            got: out.len(),
        });
    }

    out[0..4].copy_from_slice(&ENV_MAGIC);
    out[4] = ENV_VERSION;
    out[5] = 0;
    out[6] = 0;
    out[7] = 0;
    let mut off = ENV_HEADER_SIZE;
    off = put_u32_prefixed(role.as_bytes(), out, off);
    off = put_u32_prefixed(from_proc.as_bytes(), out, off);
    out[off..off + 4].copy_from_slice(&(keys.len() as u32).to_le_bytes());
    off += 4;
    for k in keys {
        off = put_u32_prefixed(k.as_bytes(), out, off);
    }
    out[off..off + 4].copy_from_slice(&(payload_yaxn.len() as u32).to_le_bytes());
    off += 4;
    out[off..off + payload_yaxn.len()].copy_from_slice(payload_yaxn);
    off += payload_yaxn.len();
    Ok(off)
}

pub(crate) fn put_u32_prefixed(bytes: &[u8], out: &mut [u8], off: usize) -> usize {
    out[off..off + 4].copy_from_slice(&(bytes.len() as u32).to_le_bytes());
    let start = off + 4;
    let end = start + bytes.len();
    out[start..end].copy_from_slice(bytes);
    end
}

#[cfg(test)]
mod tests {
    use super::*;

    // Exact bytes Python `kernel/serialise.py::serialise_axon_payload` emits for
    // torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32). Captured 2026-05-25 —
    // the cross-implementation ground truth. If the Python format changes, these
    // tests fail by design (they ARE the compatibility contract).
    const PY_F32_123: [u8; 24] = [
        89, 65, 88, 78, 1, 0, 0, 0, 3, 0, 0, 0, 0, 0, 128, 63, 0, 0, 0, 64, 0, 0, 64, 64,
    ];
    // torch.tensor([1.0, 2.0], dtype=torch.float64).
    const PY_F64_12: [u8; 28] = [
        89, 65, 88, 78, 1, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 240, 63, 0, 0, 0, 0, 0, 0, 0, 64,
    ];

    #[test]
    fn parse_python_f32_blob() {
        let p = parse_axon_payload(&PY_F32_123).unwrap();
        assert_eq!(p.dtype, DType::Float32);
        assert_eq!(p.width, 3);
        assert_eq!(p.body.len(), 12);
        let vals = [
            f32::from_le_bytes([p.body[0], p.body[1], p.body[2], p.body[3]]),
            f32::from_le_bytes([p.body[4], p.body[5], p.body[6], p.body[7]]),
            f32::from_le_bytes([p.body[8], p.body[9], p.body[10], p.body[11]]),
        ];
        assert_eq!(vals, [1.0f32, 2.0, 3.0]);
    }

    #[test]
    fn parse_python_f64_blob() {
        let p = parse_axon_payload(&PY_F64_12).unwrap();
        assert_eq!(p.dtype, DType::Float64);
        assert_eq!(p.width, 2);
        let v0 = f64::from_le_bytes([
            p.body[0], p.body[1], p.body[2], p.body[3], p.body[4], p.body[5], p.body[6], p.body[7],
        ]);
        let v1 = f64::from_le_bytes([
            p.body[8], p.body[9], p.body[10], p.body[11], p.body[12], p.body[13], p.body[14],
            p.body[15],
        ]);
        assert_eq!([v0, v1], [1.0f64, 2.0]);
    }

    #[test]
    fn write_matches_python_f32_byte_for_byte() {
        // Body = the payload bytes after the Python blob's 12-byte header.
        let body = &PY_F32_123[HEADER_SIZE..];
        let mut out = [0u8; 24];
        let n = write_axon_payload(DType::Float32, body, &mut out).unwrap();
        assert_eq!(n, 24);
        assert_eq!(out, PY_F32_123);
    }

    #[test]
    fn write_matches_python_f64_byte_for_byte() {
        let body = &PY_F64_12[HEADER_SIZE..];
        let mut out = [0u8; 28];
        let n = write_axon_payload(DType::Float64, body, &mut out).unwrap();
        assert_eq!(n, 28);
        assert_eq!(out, PY_F64_12);
    }

    #[test]
    fn write_then_parse_round_trips() {
        let body = 1234567.0f64.to_le_bytes(); // one f64 element
        let mut out = [0u8; HEADER_SIZE + 8];
        let n = write_axon_payload(DType::Float64, &body, &mut out).unwrap();
        let p = parse_axon_payload(&out[..n]).unwrap();
        assert_eq!(p.dtype, DType::Float64);
        assert_eq!(p.width, 1);
        assert_eq!(p.body, &body);
    }

    #[test]
    fn parse_rejects_bad_magic() {
        let mut b = PY_F32_123;
        b[0] = b'X';
        assert_eq!(parse_axon_payload(&b), Err(ParseError::BadMagic));
    }

    #[test]
    fn parse_rejects_short() {
        assert_eq!(parse_axon_payload(&[89, 65, 88]), Err(ParseError::TooShort));
    }

    #[test]
    fn parse_rejects_unsupported_version() {
        let mut b = PY_F32_123;
        b[4] = 2;
        assert_eq!(
            parse_axon_payload(&b),
            Err(ParseError::UnsupportedVersion(2))
        );
    }

    #[test]
    fn parse_rejects_unknown_dtype() {
        let mut b = PY_F32_123;
        b[5] = 9;
        assert_eq!(parse_axon_payload(&b), Err(ParseError::UnknownDtype(9)));
    }

    #[test]
    fn parse_rejects_body_size_mismatch() {
        // width says 3 f32 (12 body bytes); truncate the body to 8.
        let b = &PY_F32_123[..HEADER_SIZE + 8];
        assert_eq!(
            parse_axon_payload(b),
            Err(ParseError::BodySizeMismatch {
                expected: 12,
                actual: 8
            })
        );
    }

    #[test]
    fn write_rejects_small_buffer() {
        let body = [0u8; 4];
        let mut out = [0u8; 8];
        assert_eq!(
            write_axon_payload(DType::Float32, &body, &mut out),
            Err(WriteError::BufferTooSmall { needed: 16, got: 8 })
        );
    }

    #[test]
    fn write_rejects_unaligned_body() {
        let body = [0u8; 5]; // not a multiple of 4 (f32)
        let mut out = [0u8; 32];
        assert_eq!(
            write_axon_payload(DType::Float32, &body, &mut out),
            Err(WriteError::BodyNotElementAligned)
        );
    }

    #[test]
    fn dtype_tag_round_trips() {
        for d in [
            DType::Float32,
            DType::Float64,
            DType::Complex64,
            DType::Complex128,
        ] {
            assert_eq!(DType::from_tag(d.tag()), Some(d));
        }
    }

    // --- YAXE envelope ---

    // Exact bytes Python `kernel/serialise.py::serialise_axon` emits for an Axon
    // with role="R_stdin", from_proc="external", keys={"b","stdin_text"} (sorted),
    // payload=torch.tensor([1.0,2.0,3.0], float32). Captured 2026-05-25.
    const PY_YAXE: [u8; 82] = [
        89, 65, 88, 69, 1, 0, 0, 0, 7, 0, 0, 0, 82, 95, 115, 116, 100, 105, 110, 8, 0, 0, 0, 101,
        120, 116, 101, 114, 110, 97, 108, 2, 0, 0, 0, 1, 0, 0, 0, 98, 10, 0, 0, 0, 115, 116, 100,
        105, 110, 95, 116, 101, 120, 116, 24, 0, 0, 0, 89, 65, 88, 78, 1, 0, 0, 0, 3, 0, 0, 0, 0,
        0, 128, 63, 0, 0, 0, 64, 0, 0, 64, 64,
    ];

    #[test]
    fn parse_python_envelope() {
        let e = parse_axon_envelope(&PY_YAXE).unwrap();
        assert_eq!(e.role, "R_stdin");
        assert_eq!(e.from_proc, "external");
        assert_eq!(e.keys_count(), 2);
        let keys: Result<Vec<&str>, _> = e.keys().collect();
        assert_eq!(keys.unwrap(), vec!["b", "stdin_text"]);
        assert_eq!(e.payload.dtype, DType::Float32);
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
    fn write_envelope_matches_python_byte_for_byte() {
        // The nested YAXN payload is the final 24 bytes of PY_YAXE.
        let payload = &PY_YAXE[58..82];
        let mut out = [0u8; 82];
        let n =
            write_axon_envelope("R_stdin", "external", &["b", "stdin_text"], payload, &mut out)
                .unwrap();
        assert_eq!(n, 82);
        assert_eq!(out, PY_YAXE);
    }

    #[test]
    fn write_then_parse_envelope_round_trips() {
        let body = 7.0f32.to_le_bytes();
        let mut yaxn = [0u8; HEADER_SIZE + 4];
        let pn = write_axon_payload(DType::Float32, &body, &mut yaxn).unwrap();
        let mut out = [0u8; 128];
        let n = write_axon_envelope("R_out", "proc1", &["k1", "k2"], &yaxn[..pn], &mut out).unwrap();

        let e = parse_axon_envelope(&out[..n]).unwrap();
        assert_eq!(e.role, "R_out");
        assert_eq!(e.from_proc, "proc1");
        let keys: Result<Vec<&str>, _> = e.keys().collect();
        assert_eq!(keys.unwrap(), vec!["k1", "k2"]);
        assert_eq!(e.payload.width, 1);
        let b = e.payload.body;
        assert_eq!(f32::from_le_bytes([b[0], b[1], b[2], b[3]]), 7.0);
    }

    #[test]
    fn parse_envelope_empty_keys_round_trips() {
        let body = 1.5f32.to_le_bytes();
        let mut yaxn = [0u8; HEADER_SIZE + 4];
        let pn = write_axon_payload(DType::Float32, &body, &mut yaxn).unwrap();
        let mut out = [0u8; 64];
        let n = write_axon_envelope("R", "p", &[], &yaxn[..pn], &mut out).unwrap();
        let e = parse_axon_envelope(&out[..n]).unwrap();
        assert_eq!(e.keys_count(), 0);
        assert_eq!(e.keys().count(), 0);
    }

    #[test]
    fn parse_envelope_rejects_bad_magic() {
        let mut b = PY_YAXE;
        b[0] = b'Z';
        assert_eq!(parse_axon_envelope(&b), Err(ParseError::BadMagic));
    }

    #[test]
    fn parse_envelope_rejects_short() {
        assert_eq!(parse_axon_envelope(&[89, 65, 88]), Err(ParseError::TooShort));
    }

    #[test]
    fn parse_envelope_rejects_truncated_role() {
        // role_len = 7 but only 2 role bytes present.
        let b = &PY_YAXE[..14];
        assert_eq!(parse_axon_envelope(b), Err(ParseError::Truncated));
    }

    #[test]
    fn write_envelope_rejects_small_buffer() {
        let payload = &PY_YAXE[58..82];
        let mut out = [0u8; 10];
        assert!(matches!(
            write_axon_envelope("R_stdin", "external", &["b", "stdin_text"], payload, &mut out),
            Err(WriteError::BufferTooSmall { .. })
        ));
    }
}
