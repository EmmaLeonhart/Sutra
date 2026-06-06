//! Rust isomorph of `transformer-vm`'s `wasm/reference.py` — the deterministic
//! 35-opcode stack machine that the autoregressive transformer is isomorphic to.
//!
//! This is a faithful, opcode-for-opcode port of the *behavioural* path of
//! `reference.py::run` (output + instruction/token counts; the trace-token
//! formatting is a presentation concern and is omitted here). Memory/stack are
//! addressed with plain indices ("iterator-first" per the isomorphism program);
//! the attention-as-addressing formulation is a later step.
//!
//! Equivalence is checked behaviourally against the Python reference on the example
//! programs (see `scripts/iso_equiv.sh` and `tests/equiv.rs`).

const MEM_SIZE: usize = 10 * 1024 * 1024;

/// Result of running a program: matches reference.py's `run()` return.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RunResult {
    pub instr_count: u64,
    pub token_count: u64,
    pub output: Vec<u8>,
}

impl RunResult {
    /// Output decoded the way reference.py builds its string: each byte -> char.
    pub fn output_string(&self) -> String {
        self.output.iter().map(|&b| b as char).collect()
    }
}

/// Signed interpretation of a 32-bit value (cf. reference.py `to_signed`).
#[inline]
fn to_signed(v: u32) -> i32 {
    v as i32
}

/// Parse a `.txt` program file's contents into (program, input_str).
///
/// Format: `{ op b0 b1 b2 b3 op b0 b1 b2 b3 ... }` then an optional input section
/// (`<byte tokens...> commit(...)`). Mirrors `_parse_program_tokens` + `_extract_input`.
pub fn parse_program(text: &str) -> (Vec<(String, u32)>, String) {
    let tokens: Vec<&str> = text.split_whitespace().collect();
    assert!(!tokens.is_empty() && tokens[0] == "{", "program must start with '{{'");
    // index of the LAST '}' (reference.py uses rindex)
    let end = tokens
        .iter()
        .rposition(|&t| t == "}")
        .expect("no closing '}' in program");

    // Program body: groups of 5 (op + 4 hex bytes).
    let body = &tokens[1..end];
    let mut program = Vec::new();
    let mut i = 0;
    while i < body.len() {
        let op = body[i].to_string();
        let b: [u32; 4] = [
            u32::from_str_radix(body[i + 1], 16).unwrap(),
            u32::from_str_radix(body[i + 2], 16).unwrap(),
            u32::from_str_radix(body[i + 3], 16).unwrap(),
            u32::from_str_radix(body[i + 4], 16).unwrap(),
        ];
        let imm = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24);
        program.push((op, imm));
        i += 5;
    }

    // Input section: tokens after the last '}', drop a trailing commit(...), decode.
    let mut input_toks: Vec<&str> = tokens[end + 1..].to_vec();
    if let Some(last) = input_toks.last() {
        if last.starts_with("commit(") {
            input_toks.pop();
        }
    }
    let mut chars = String::new();
    for tok in input_toks {
        if tok.len() == 1 {
            chars.push_str(tok);
        } else if tok.len() == 2 {
            if let Ok(byte) = u8::from_str_radix(tok, 16) {
                if byte == 0 {
                    break;
                }
                chars.push(byte as char);
            } else {
                break;
            }
        } else {
            break;
        }
    }
    (program, chars)
}

/// Execute a compiled program. Faithful port of `reference.py::run` (no-trace path).
pub fn run(program: &[(String, u32)], input_str: &str, max_tokens: u64) -> RunResult {
    let mut mem = vec![0u8; MEM_SIZE];

    let mut input_base: Option<usize> = None;
    if let Some((op0, imm0)) = program.first() {
        if op0 == "input_base" {
            input_base = Some(*imm0 as usize);
        }
    }
    if let (Some(base), false) = (input_base, input_str.is_empty()) {
        let mut bytes = input_str.as_bytes().to_vec();
        bytes.push(0);
        for (i, ch) in bytes.iter().enumerate() {
            mem[base + i] = *ch;
        }
    }

    let mut stack: Vec<u32> = Vec::new();
    let mut locals: Vec<u32> = vec![0; 256];
    let mut call_stack: Vec<(usize, Vec<u32>, u32)> = Vec::new();
    let mut pc: usize = 0;
    let mut instr_count: u64 = 0;
    let mut token_count: u64 = 0;
    let mut output: Vec<u8> = Vec::new();
    let trace = std::env::var("ISO_TRACE").is_ok();

    while pc < program.len() && token_count < max_tokens {
        let (op, imm) = (&program[pc].0, program[pc].1);
        instr_count += 1;
        let op = op.as_str();
        if trace {
            eprintln!(
                "i={} pc={} op={} imm={} top={}",
                instr_count, pc, op, imm,
                stack.last().map(|v| v.to_string()).unwrap_or_else(|| "-".into())
            );
        }

        match op {
            "input_base" => {
                let n = if input_str.is_empty() { 1 } else { input_str.as_bytes().len() + 1 };
                token_count += n as u64 + 1;
                pc += 1;
            }
            "halt" => {
                token_count += 1;
                break;
            }
            "i32.const" => {
                stack.push(imm);
                token_count += 5;
                pc += 1;
            }
            "local.get" | "global.get" => {
                stack.push(locals[imm as usize]);
                token_count += 5;
                pc += 1;
            }
            "local.set" => {
                locals[imm as usize] = stack.pop().unwrap();
                token_count += 5;
                pc += 1;
            }
            "global.set" => {
                locals[imm as usize] = stack.pop().unwrap();
                token_count += 1;
                pc += 1;
            }
            "local.tee" => {
                let v = *stack.last().unwrap();
                locals[imm as usize] = v;
                token_count += 5;
                pc += 1;
            }
            "drop" => {
                stack.pop().unwrap();
                token_count += 1;
                pc += 1;
            }
            "select" => {
                let c = stack.pop().unwrap();
                let b = stack.pop().unwrap();
                let a = stack.pop().unwrap();
                stack.push(if c != 0 { a } else { b });
                token_count += 5;
                pc += 1;
            }
            "i32.add" => {
                let bv = stack.pop().unwrap();
                let av = stack.pop().unwrap();
                stack.push(av.wrapping_add(bv));
                token_count += 5;
                pc += 1;
            }
            "i32.sub" => {
                let bv = stack.pop().unwrap();
                let av = stack.pop().unwrap();
                stack.push(av.wrapping_sub(bv));
                token_count += 5;
                pc += 1;
            }
            "i32.eqz" => {
                let v = stack.pop().unwrap();
                stack.push(if v == 0 { 1 } else { 0 });
                token_count += 5;
                pc += 1;
            }
            "i32.eq" => { cmp(&mut stack, |a, b| a == b); token_count += 5; pc += 1; }
            "i32.ne" => { cmp(&mut stack, |a, b| a != b); token_count += 5; pc += 1; }
            "i32.lt_u" => { cmp(&mut stack, |a, b| a < b); token_count += 5; pc += 1; }
            "i32.gt_u" => { cmp(&mut stack, |a, b| a > b); token_count += 5; pc += 1; }
            "i32.le_u" => { cmp(&mut stack, |a, b| a <= b); token_count += 5; pc += 1; }
            "i32.ge_u" => { cmp(&mut stack, |a, b| a >= b); token_count += 5; pc += 1; }
            "i32.lt_s" => { cmp_s(&mut stack, |a, b| a < b); token_count += 5; pc += 1; }
            "i32.gt_s" => { cmp_s(&mut stack, |a, b| a > b); token_count += 5; pc += 1; }
            "i32.le_s" => { cmp_s(&mut stack, |a, b| a <= b); token_count += 5; pc += 1; }
            "i32.ge_s" => { cmp_s(&mut stack, |a, b| a >= b); token_count += 5; pc += 1; }
            "i32.load" => {
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                let val = (mem[addr] as u32)
                    | ((mem[addr + 1] as u32) << 8)
                    | ((mem[addr + 2] as u32) << 16)
                    | ((mem[addr + 3] as u32) << 24);
                stack.push(val);
                token_count += 5;
                pc += 1;
            }
            "i32.load8_u" => {
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                stack.push(mem[addr] as u32);
                token_count += 5;
                pc += 1;
            }
            "i32.load8_s" => {
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                let v = mem[addr] as u32;
                stack.push(if v >= 128 { (v.wrapping_sub(256)) & 0xFFFF_FFFF } else { v });
                token_count += 5;
                pc += 1;
            }
            "i32.load16_u" => {
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                stack.push((mem[addr] as u32) | ((mem[addr + 1] as u32) << 8));
                token_count += 5;
                pc += 1;
            }
            "i32.load16_s" => {
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                let v = (mem[addr] as u32) | ((mem[addr + 1] as u32) << 8);
                stack.push(if v >= 32768 { v.wrapping_sub(65536) } else { v });
                token_count += 5;
                pc += 1;
            }
            "i32.store" => {
                let val = stack.pop().unwrap();
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                mem[addr] = (val & 0xFF) as u8;
                mem[addr + 1] = ((val >> 8) & 0xFF) as u8;
                mem[addr + 2] = ((val >> 16) & 0xFF) as u8;
                mem[addr + 3] = ((val >> 24) & 0xFF) as u8;
                token_count += 5;
                pc += 1;
            }
            "i32.store8" => {
                let val = stack.pop().unwrap();
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                mem[addr] = (val & 0xFF) as u8;
                token_count += 2;
                pc += 1;
            }
            "i32.store16" => {
                let val = stack.pop().unwrap();
                let addr = (stack.pop().unwrap().wrapping_add(imm)) as usize;
                mem[addr] = (val & 0xFF) as u8;
                mem[addr + 1] = ((val >> 8) & 0xFF) as u8;
                token_count += 3;
                pc += 1;
            }
            "br" => {
                let offset = to_signed(imm) as i64;
                token_count += 6;
                pc = (pc as i64 + 1 + offset) as usize;
            }
            "br_if" => {
                let cond = stack.pop().unwrap();
                if cond != 0 {
                    let offset = to_signed(imm) as i64;
                    pc = (pc as i64 + 1 + offset) as usize;
                    token_count += 6;
                } else {
                    pc += 1;
                    token_count += 1;
                }
            }
            "call" => {
                let offset = to_signed(imm) as i64;
                call_stack.push((pc + 1, locals.clone(), imm));
                locals = vec![0; 256];
                token_count += 6;
                pc = (pc as i64 + 1 + offset) as usize;
            }
            "return" => {
                let (ret_pc, ret_locals, _call_imm) = call_stack.pop().unwrap();
                token_count += 6;
                pc = ret_pc;
                locals = ret_locals;
            }
            "output" => {
                let val = (stack.pop().unwrap() & 0xFF) as u8;
                output.push(val);
                token_count += 1;
                pc += 1;
            }
            other => panic!("Unknown op: {other} at pc={pc}"),
        }
    }

    RunResult { instr_count, token_count, output }
}

#[inline]
fn cmp(stack: &mut Vec<u32>, f: impl Fn(u32, u32) -> bool) {
    let bv = stack.pop().unwrap();
    let av = stack.pop().unwrap();
    stack.push(if f(av, bv) { 1 } else { 0 });
}

#[inline]
fn cmp_s(stack: &mut Vec<u32>, f: impl Fn(i32, i32) -> bool) {
    let bv = to_signed(stack.pop().unwrap());
    let av = to_signed(stack.pop().unwrap());
    stack.push(if f(av, bv) { 1 } else { 0 });
}
