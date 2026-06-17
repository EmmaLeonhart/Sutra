//! Minimal `no_std` JSON reader for the FLAT objects the Python kernel emits in
//! checkpoints — the `manifest` and service-`identity` JSON carried (un-parsed)
//! inside `YPRC`/`YKST` blobs by the `checkpoint` codecs.
//!
//! This is **not** a general JSON parser. It reads a flat object whose values
//! are JSON strings, non-negative integers, or arrays of strings — exactly the
//! schema `kernel/checkpoint.py` writes (`_manifest_to_json` /
//! `_service_identity`). That bounded scope is what lets it stay `no_std` /
//! no-alloc: every accessor returns a BORROWED slice into the input.
//!
//! It is a *structural* scanner, not a substring search: to find a key it reads
//! each `"key": value` pair and skips over the value, so it never false-matches
//! a key name that appears inside some other value. `read_string` skips `\X`
//! escape pairs, so an escaped quote (`\"`) inside a string does not end it
//! early.
//!
//! **Escapes are left raw.** A returned string is the bytes between the quotes
//! verbatim — `"a\\b"` comes back as `a\\b`, not `a\b`. The only escaped field
//! the kernel emits is a Windows `source_path`'s `\\`; a caller that needs the
//! un-escaped form does it itself (un-escaping needs an output buffer, deferred).

fn skip_ws(b: &[u8], mut i: usize) -> usize {
    while i < b.len() && matches!(b[i], b' ' | b'\t' | b'\n' | b'\r') {
        i += 1;
    }
    i
}

/// At `b[i] == '"'`, read a JSON string. Returns `(content_start, content_end,
/// after)` — the raw bytes between the quotes (escapes left literal) and the
/// index just past the closing quote. `None` if not a well-formed string.
fn read_string(b: &[u8], i: usize) -> Option<(usize, usize, usize)> {
    if i >= b.len() || b[i] != b'"' {
        return None;
    }
    let start = i + 1;
    let mut j = start;
    while j < b.len() {
        match b[j] {
            b'\\' => j += 2, // skip the escape pair (\" \\ \n …) without interpreting it
            b'"' => return Some((start, j, j + 1)),
            _ => j += 1,
        }
    }
    None
}

/// Skip one JSON value starting at `b[i]` (after leading ws); return the index
/// just past it. Handles strings, arrays, nested objects, and bare tokens
/// (numbers / true / false / null).
fn skip_value(b: &[u8], i: usize) -> Option<usize> {
    let i = skip_ws(b, i);
    if i >= b.len() {
        return None;
    }
    match b[i] {
        b'"' => {
            let (_, _, after) = read_string(b, i)?;
            Some(after)
        }
        b'[' => {
            let mut j = i + 1;
            loop {
                j = skip_ws(b, j);
                if j >= b.len() {
                    return None;
                }
                if b[j] == b']' {
                    return Some(j + 1);
                }
                j = skip_value(b, j)?;
                j = skip_ws(b, j);
                if j < b.len() && b[j] == b',' {
                    j += 1;
                }
            }
        }
        b'{' => {
            let mut j = i + 1;
            loop {
                j = skip_ws(b, j);
                if j >= b.len() {
                    return None;
                }
                if b[j] == b'}' {
                    return Some(j + 1);
                }
                let (_, _, after) = read_string(b, j)?;
                j = skip_ws(b, after);
                if j >= b.len() || b[j] != b':' {
                    return None;
                }
                j = skip_value(b, j + 1)?;
                j = skip_ws(b, j);
                if j < b.len() && b[j] == b',' {
                    j += 1;
                }
            }
        }
        _ => {
            // bare token: read until a structural delimiter or whitespace.
            let mut j = i;
            while j < b.len() && !matches!(b[j], b',' | b'}' | b']' | b' ' | b'\t' | b'\n' | b'\r') {
                j += 1;
            }
            if j == i {
                None
            } else {
                Some(j)
            }
        }
    }
}

/// Walk a flat top-level object and return the index of `key`'s value (after
/// the `:` and any whitespace), or `None` if the key is absent / the object is
/// malformed. Key comparison is against the raw key bytes (kernel keys have no
/// escapes, so raw == literal).
fn seek_key(b: &[u8], key: &str) -> Option<usize> {
    let mut i = skip_ws(b, 0);
    if i >= b.len() || b[i] != b'{' {
        return None;
    }
    i = skip_ws(b, i + 1);
    while i < b.len() && b[i] != b'}' {
        let (ks, ke, after) = read_string(b, i)?;
        i = skip_ws(b, after);
        if i >= b.len() || b[i] != b':' {
            return None;
        }
        i = skip_ws(b, i + 1); // i now at the value
        if &b[ks..ke] == key.as_bytes() {
            return Some(i);
        }
        i = skip_value(b, i)?;
        i = skip_ws(b, i);
        if i < b.len() && b[i] == b',' {
            i = skip_ws(b, i + 1);
        }
    }
    None
}

/// Get a string field's value (raw content, escapes left literal). `None` if
/// the key is absent or its value is not a string.
pub fn get_str<'a>(obj: &'a [u8], key: &str) -> Option<&'a str> {
    let i = seek_key(obj, key)?;
    if i >= obj.len() || obj[i] != b'"' {
        return None;
    }
    let (cs, ce, _) = read_string(obj, i)?;
    core::str::from_utf8(&obj[cs..ce]).ok()
}

/// Get a non-negative integer field's value. `None` if the key is absent or its
/// value is not a non-negative integer that fits in `u32`.
pub fn get_u32(obj: &[u8], key: &str) -> Option<u32> {
    let i = seek_key(obj, key)?;
    let end = skip_value(obj, i)?;
    let tok = core::str::from_utf8(&obj[i..end]).ok()?.trim();
    if tok.is_empty() || !tok.bytes().all(|c| c.is_ascii_digit()) {
        return None;
    }
    tok.parse::<u32>().ok()
}

/// Iterate a string-array field's elements (each raw, escapes literal). `None`
/// if the key is absent or its value is not an array.
pub fn get_str_array<'a>(obj: &'a [u8], key: &str) -> Option<StrArrayIter<'a>> {
    let i = seek_key(obj, key)?;
    let i = skip_ws(obj, i);
    if i >= obj.len() || obj[i] != b'[' {
        return None;
    }
    Some(StrArrayIter { b: obj, i: i + 1 })
}

/// Iterator over a JSON string array's elements (see [`get_str_array`]).
#[derive(Debug, Clone)]
pub struct StrArrayIter<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Iterator for StrArrayIter<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<&'a str> {
        self.i = skip_ws(self.b, self.i);
        if self.i >= self.b.len() || self.b[self.i] != b'"' {
            return None; // ']' or malformed → done
        }
        let (cs, ce, after) = read_string(self.b, self.i)?;
        self.i = skip_ws(self.b, after);
        if self.i < self.b.len() && self.b[self.i] == b',' {
            self.i += 1;
        }
        core::str::from_utf8(&self.b[cs..ce]).ok()
    }
}

/// Un-escape a raw JSON string (the content [`get_str`] returns) into `out`,
/// writing the resolved bytes and returning how many were written. Handles the
/// common JSON escapes (`\\`, `\"`, `\/`, `\n`, `\t`, `\r`, `\b`, `\f`) and
/// `\uXXXX` for BMP codepoints (1–3 byte UTF-8 sequences).
///
/// Returns `None` on an unknown escape, a malformed `\uXXXX` (short/non-hex), a
/// surrogate codepoint `\uD800..=\uDFFF`, a trailing `\` with no follower, or a
/// buffer too small. A buffer of `raw.len()` always suffices for the simple
/// escapes (they shrink); `\uXXXX` shrinks too (6 input bytes → at most 3 UTF-8
/// bytes for BMP), so `out.len() >= raw.len()` is a safe upper bound for any
/// well-formed input.
///
/// **Surrogate pairs (`😀` for astral plane codepoints) are NOT
/// supported** — refused, not faked. The kernel checkpoint schema doesn't emit
/// them; adding pair handling without a real consumer would be untested code.
/// If you hit this, supply the codepoint directly (as UTF-8) instead of as a
/// surrogate-pair escape.
pub fn unescape_into(raw: &[u8], out: &mut [u8]) -> Option<usize> {
    let mut i = 0;
    let mut o = 0;
    while i < raw.len() {
        if raw[i] != b'\\' {
            if o >= out.len() {
                return None;
            }
            out[o] = raw[i];
            o += 1;
            i += 1;
            continue;
        }
        if i + 1 >= raw.len() {
            return None; // trailing backslash
        }
        let c = raw[i + 1];
        if c == b'u' {
            // \uXXXX — four hex digits → BMP codepoint → UTF-8 (1–3 bytes).
            if i + 6 > raw.len() {
                return None; // truncated escape
            }
            let cp = parse_hex4(&raw[i + 2..i + 6])?;
            if (0xD800..=0xDFFF).contains(&cp) {
                return None; // surrogate codepoint — refused (see doc)
            }
            let n = utf8_encode_bmp(cp, out.get_mut(o..)?)?;
            o += n;
            i += 6;
            continue;
        }
        if o >= out.len() {
            return None;
        }
        let resolved = match c {
            b'\\' => b'\\',
            b'"' => b'"',
            b'/' => b'/',
            b'n' => b'\n',
            b't' => b'\t',
            b'r' => b'\r',
            b'b' => 0x08,
            b'f' => 0x0c,
            _ => return None,
        };
        out[o] = resolved;
        o += 1;
        i += 2;
    }
    Some(o)
}

/// Parse exactly 4 ASCII hex digits into a codepoint. `None` on any non-hex.
fn parse_hex4(b: &[u8]) -> Option<u32> {
    if b.len() != 4 {
        return None;
    }
    let mut v: u32 = 0;
    for &ch in b {
        let d = match ch {
            b'0'..=b'9' => ch - b'0',
            b'a'..=b'f' => ch - b'a' + 10,
            b'A'..=b'F' => ch - b'A' + 10,
            _ => return None,
        };
        v = (v << 4) | (d as u32);
    }
    Some(v)
}

/// Encode a BMP codepoint (0..=0xFFFF, surrogates pre-filtered) as 1–3 UTF-8
/// bytes into `out`. Returns the bytes written, or `None` if `out` is too small.
fn utf8_encode_bmp(cp: u32, out: &mut [u8]) -> Option<usize> {
    if cp < 0x80 {
        *out.get_mut(0)? = cp as u8;
        Some(1)
    } else if cp < 0x800 {
        if out.len() < 2 {
            return None;
        }
        out[0] = 0xC0 | (cp >> 6) as u8;
        out[1] = 0x80 | (cp & 0x3F) as u8;
        Some(2)
    } else {
        // cp <= 0xFFFF; surrogates D800..=DFFF were filtered upstream.
        if out.len() < 3 {
            return None;
        }
        out[0] = 0xE0 | (cp >> 12) as u8;
        out[1] = 0x80 | ((cp >> 6) & 0x3F) as u8;
        out[2] = 0x80 | (cp & 0x3F) as u8;
        Some(3)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The exact manifest JSON kernel/checkpoint.py::_manifest_to_json emits for
    // echo (sort_keys=True, ", "/": " separators).
    const MANIFEST: &[u8] = b"{\"axon_keys\": [\"stdin_text\"], \"axon_width\": 768, \
\"compute_units\": 1, \"name\": \"echo\", \"read_roles\": [\"R_stdin\"], \
\"source\": \"echo.su\", \"write_roles\": [\"R_stdout\"]}";

    #[test]
    fn manifest_string_fields() {
        assert_eq!(get_str(MANIFEST, "name"), Some("echo"));
        assert_eq!(get_str(MANIFEST, "source"), Some("echo.su"));
    }

    #[test]
    fn manifest_int_fields() {
        assert_eq!(get_u32(MANIFEST, "axon_width"), Some(768));
        assert_eq!(get_u32(MANIFEST, "compute_units"), Some(1));
    }

    #[test]
    fn manifest_string_arrays() {
        let read: Vec<&str> = get_str_array(MANIFEST, "read_roles").unwrap().collect();
        assert_eq!(read, vec!["R_stdin"]);
        let write: Vec<&str> = get_str_array(MANIFEST, "write_roles").unwrap().collect();
        assert_eq!(write, vec!["R_stdout"]);
        let keys: Vec<&str> = get_str_array(MANIFEST, "axon_keys").unwrap().collect();
        assert_eq!(keys, vec!["stdin_text"]);
    }

    #[test]
    fn absent_and_wrong_type() {
        assert_eq!(get_str(MANIFEST, "nope"), None);
        assert_eq!(get_u32(MANIFEST, "name"), None); // value is a string, not an int
        assert!(get_str_array(MANIFEST, "axon_width").is_none()); // not an array
        assert_eq!(get_str(MANIFEST, "axon_width"), None); // not a string
    }

    #[test]
    fn escaped_quote_does_not_end_string_early() {
        // JSON: {"a": "x\"y", "b": "z"} — the \" must not terminate "a"'s value,
        // and "b" must still be found after it.
        let obj: &[u8] = b"{\"a\": \"x\\\"y\", \"b\": \"z\"}";
        assert_eq!(get_str(obj, "a"), Some("x\\\"y")); // raw content, escapes literal
        assert_eq!(get_str(obj, "b"), Some("z"));
    }

    #[test]
    fn escaped_backslash_path_returns_raw() {
        // JSON: {"source_path": "..\\apps\\echo.su"} — two literal backslashes
        // per separator (Python escaped the Windows path). Returned raw.
        let obj: &[u8] = b"{\"source_path\": \"..\\\\apps\\\\echo.su\"}";
        assert_eq!(get_str(obj, "source_path"), Some("..\\\\apps\\\\echo.su"));
    }

    #[test]
    fn array_value_does_not_confuse_later_keys() {
        // A later scalar key must be found past an array value.
        assert_eq!(get_str(MANIFEST, "source"), Some("echo.su"));
        assert_eq!(get_u32(MANIFEST, "compute_units"), Some(1));
    }

    // --- unescape_into ---

    #[test]
    fn unescape_backslash_path() {
        // get_str's raw output for "..\\apps\\echo.su" → the bytes
        // `. . \ \ a p p s \ \ e c h o . s u` (every \ is a literal byte).
        // un-escape replaces each `\\` pair with one `\`.
        let raw = b"..\\\\apps\\\\echo.su";
        let mut out = [0u8; 32];
        let n = unescape_into(raw, &mut out).unwrap();
        assert_eq!(&out[..n], b"..\\apps\\echo.su");
    }

    #[test]
    fn unescape_quote_and_whitespace() {
        let raw = b"a\\\"b\\nc\\td";
        let mut out = [0u8; 16];
        let n = unescape_into(raw, &mut out).unwrap();
        assert_eq!(&out[..n], b"a\"b\nc\td");
    }

    #[test]
    fn unescape_rejects_unknown_escape() {
        let raw = b"x\\zy"; // \z is not a valid escape
        let mut out = [0u8; 16];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_unicode_ascii() {
        // A -> 'A' (1-byte UTF-8).
        let raw = b"a\\u0041b";
        let mut out = [0u8; 16];
        let n = unescape_into(raw, &mut out).unwrap();
        assert_eq!(&out[..n], b"aAb");
    }

    #[test]
    fn unescape_unicode_2_byte() {
        // é -> é (2-byte UTF-8: 0xC3 0xA9).
        let raw = b"caf\\u00E9";
        let mut out = [0u8; 16];
        let n = unescape_into(raw, &mut out).unwrap();
        assert_eq!(&out[..n], "café".as_bytes());
    }

    #[test]
    fn unescape_unicode_3_byte_bmp() {
        // 中 -> 中 (3-byte UTF-8: 0xE4 0xB8 0xAD).
        let raw = b"x\\u4E2Dy";
        let mut out = [0u8; 16];
        let n = unescape_into(raw, &mut out).unwrap();
        assert_eq!(&out[..n], "x中y".as_bytes());
    }

    #[test]
    fn unescape_rejects_surrogate_codepoint() {
        // High surrogate alone — refuse rather than fake.
        let raw = b"\\uD83D";
        let mut out = [0u8; 16];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_rejects_truncated_unicode() {
        let raw = b"\\u00"; // only 2 hex digits
        let mut out = [0u8; 16];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_rejects_non_hex_unicode() {
        let raw = b"\\uZZZZ";
        let mut out = [0u8; 16];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_rejects_trailing_backslash() {
        let raw = b"abc\\";
        let mut out = [0u8; 16];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_rejects_small_buffer() {
        let raw = b"abcd";
        let mut out = [0u8; 2];
        assert_eq!(unescape_into(raw, &mut out), None);
    }

    #[test]
    fn unescape_then_get_str_round_trip() {
        // End-to-end: get_str's raw content -> unescape_into recovers the path.
        let obj: &[u8] = b"{\"source_path\": \"..\\\\apps\\\\echo.su\"}";
        let raw = get_str(obj, "source_path").unwrap();
        let mut out = [0u8; 32];
        let n = unescape_into(raw.as_bytes(), &mut out).unwrap();
        assert_eq!(&out[..n], b"..\\apps\\echo.su");
    }
}
