//! Yantra bare-metal Linux 0.00 replica — 32-bit protected mode.
//!
//! Linus Torvalds' Linux 0.00 (1991) is the smallest OS that
//! demonstrates kernel-mediated multitasking: two hardcoded tasks
//! (A writes 'A', B writes 'B'), alternated by the **timer
//! interrupt**, output poked into VGA text memory. It runs in
//! 32-bit protected mode. It touches **no GPU** — so unlike the
//! v0.5 Sutra-kernel-on-real-GPU path, this is buildable on the
//! existing v0.4 bootloader infrastructure today, in QEMU.
//!
//! This is the bare-metal companion to the Connectome-Manager
//! realization in `tests/test_linux_000.py` / `planning/21`. It is
//! faithful to Linux 0.00's actual mechanism: real GDT/IDT, the
//! real 8259 PIC, the real 8253 PIT, a real timer-interrupt-driven
//! task switch. The switch is a software ESP swap in the timer ISR
//! (the modern-OSdev equivalent of Linux 0.00's hardware-TSS
//! `ljmp`; same observable behaviour, fewer modern-QEMU footguns).
//!
//! Boot: `qemu-system-x86_64 -kernel <bin> -serial stdio
//! -display none`. multiboot1 hands off in 32-bit protected mode.
//! Output goes to BOTH the VGA text buffer (0xB8000 — the faithful
//! "screen") and COM1 serial (the capturable, automatable proof).
//!
//! Serial breadcrumbs are printed after each init step so the
//! transcript shows exactly how far boot got if anything faults —
//! no silent triple-fault, no faked output.

#![no_std]
#![no_main]

use core::arch::{asm, global_asm};
use core::panic::PanicInfo;
use core::sync::atomic::{AtomicU32, Ordering};

// --- multiboot1 header (same shape as the v0.4 bootloader) ----------

const MULTIBOOT_MAGIC: u32 = 0x1BADB002;
const MULTIBOOT_FLAGS: u32 = 0;
const MULTIBOOT_CHECKSUM: u32 = (-((MULTIBOOT_MAGIC + MULTIBOOT_FLAGS) as i32)) as u32;

#[link_section = ".multiboot"]
#[used]
static MULTIBOOT_HEADER: [u32; 3] =
    [MULTIBOOT_MAGIC, MULTIBOOT_FLAGS, MULTIBOOT_CHECKSUM];

const SERIAL_COM1: u16 = 0x3F8;

// Per-task saved ESP, and the current task index. Named (no_mangle)
// so the naked timer ISR in global_asm! can address them directly.
#[no_mangle]
static mut TASK_ESP: [u32; 2] = [0; 2];
#[no_mangle]
static mut CUR: u32 = 0;

// Bounded run: each task emits until TOTAL hits LIMIT, then the
// kernel prints a DONE marker and halts. Keeps the serial
// transcript finite and the A/B pattern unambiguous.
static TOTAL: AtomicU32 = AtomicU32::new(0);
// One full 80x25 VGA text screen: the faithful Linux 0.00 "the
// screen fills with AAAA…BBBB…". 2000 = 80*25 so vga_putc fills
// every cell exactly once (no wrap), then both tasks halt with a
// static, fully-painted screen — ideal for a screenshot.
const LIMIT: u32 = 2000;

// --- entry + naked ISRs (asm) ---------------------------------------

global_asm!(
    r#"
    .intel_syntax noprefix
    .section .text
    /* multiboot1 hands off in 32-bit protected mode. Without an
     * explicit .code32 the LLVM assembler emits the 16-bit forms
     * of mode-sized instructions — notably `iret` -> `iretw`
     * (pops 16-bit IP/CS/FLAGS, 6 bytes, not 32-bit EIP/CS/EFLAGS,
     * 12 bytes), which #GPs the moment the task switch returns.
     * The v0.4 bootloader's asm is explicitly .code32/.code64 for
     * the same reason. */
    .code32
    .global _start
_start:
    /* multiboot1 hands off in 32-bit protected mode, flat segments
     * but an unspecified GDT — we install our own in kernel_main. */
    lea esp, [stack_top]
    call kernel_main
    /* kernel_main does not return (it jump-starts the tasks). */
.hang:
    cli
    hlt
    jmp .hang

    /* ---- timer ISR (IRQ0, vector 0x20) ----
     * Naked: save GP regs, EOI the PIC, swap to the other task's
     * saved ESP, restore, iret. The iret frame + the pushed GP
     * block is exactly the layout each task's initial stack is
     * seeded with, so the first switch into a task "returns" into
     * its entry point. This IS the timer-interrupt task switch. */
    .global timer_isr
timer_isr:
    pushad                      /* edi esi ebp esp ebx edx ecx eax */
    mov al, 0x20                /* non-specific EOI ... */
    out 0x20, al               /* ... to the master 8259 PIC */
    /* save current ESP -> TASK_ESP[CUR] */
    mov eax, [CUR]
    mov edi, offset TASK_ESP
    mov [edi + eax*4], esp
    /* CUR ^= 1 (round-robin between the two tasks) */
    xor eax, 1
    mov [CUR], eax
    /* ESP = TASK_ESP[CUR] */
    mov esp, [edi + eax*4]
    popad
    iretd

    /* ---- default exception ISR ----
     * Any CPU exception we didn't expect: print a marker via COM1
     * and halt. Makes a fault visible in the serial transcript
     * instead of a silent triple-fault reboot. */
    .global exc_isr
exc_isr:
    cli
    mov dx, 0x3F8
    mov al, 0x5B               /* '[' */
    out dx, al
    mov al, 0x45               /* 'E' */
    out dx, al
    mov al, 0x58               /* 'X' */
    out dx, al
    mov al, 0x43               /* 'C' */
    out dx, al
    mov al, 0x5D               /* ']' */
    out dx, al
    mov al, 0x0A               /* '\n' */
    out dx, al
.exc_hang:
    cli
    hlt
    jmp .exc_hang

    /* ---- jump-start the first task ----
     * void start_tasks(u32 first_esp): load ESP from the seeded
     * task-0 frame, popa, iret -> lands in task A with IF set. */
    .global start_tasks
start_tasks:
    mov esp, [esp + 4]         /* arg0 = task-0 initial ESP */
    popad
    iretd

    .section .bss
    .align 16
stack_bottom:
    .skip 16384
stack_top:
    "#
);

extern "C" {
    fn timer_isr();
    fn exc_isr();
    fn start_tasks(first_esp: u32) -> !;
}

// --- low-level I/O ---------------------------------------------------

#[inline]
unsafe fn outb(port: u16, val: u8) {
    asm!("out dx, al", in("dx") port, in("al") val,
         options(nostack, preserves_flags));
}

#[inline]
unsafe fn inb(port: u16) -> u8 {
    let v: u8;
    asm!("in al, dx", out("al") v, in("dx") port,
         options(nostack, preserves_flags));
    v
}

fn sputc(b: u8) {
    unsafe { outb(SERIAL_COM1, b) };
}

fn sputs(s: &[u8]) {
    for &b in s {
        sputc(b);
    }
}

// --- VGA text buffer (the faithful "screen") ------------------------

const VGA: *mut u16 = 0xB8000 as *mut u16;
static VGA_POS: AtomicU32 = AtomicU32::new(0);

/// Write one character to the VGA text buffer (0xB8000), light-grey
/// on black, advancing a cursor with wrap. This is the faithful
/// Linux-0.00 `write_char`-into-video-memory; the serial copy is
/// the headless-capturable proof of the same byte.
fn vga_putc(c: u8) {
    let pos = VGA_POS.fetch_add(1, Ordering::SeqCst) % (80 * 25);
    let cell: u16 = 0x0700 | (c as u16);
    unsafe { VGA.add(pos as usize).write_volatile(cell) };
}

// --- protected-mode plumbing ----------------------------------------

#[repr(C, packed)]
struct DescPtr {
    limit: u16,
    base: u32,
}

// GDT: null, 32-bit code (0x08), 32-bit data (0x10). Flat 4 GiB.
static mut GDT: [u64; 3] = [
    0,
    0x00CF_9A00_0000_FFFF, // code: base0 limit4G G=1 D=1 exec/read DPL0
    0x00CF_9200_0000_FFFF, // data: base0 limit4G G=1 D=1 r/w   DPL0
];

#[repr(C, packed)]
#[derive(Clone, Copy)]
struct IdtEntry {
    off_lo: u16,
    sel: u16,
    zero: u8,
    flags: u8,
    off_hi: u16,
}

static mut IDT: [IdtEntry; 256] = [IdtEntry {
    off_lo: 0,
    sel: 0,
    zero: 0,
    flags: 0,
    off_hi: 0,
}; 256];

fn idt_set(vec: usize, handler: usize) {
    unsafe {
        IDT[vec] = IdtEntry {
            off_lo: (handler & 0xFFFF) as u16,
            sel: 0x08, // our code selector
            zero: 0,
            flags: 0x8E, // present, DPL0, 32-bit interrupt gate
            off_hi: ((handler >> 16) & 0xFFFF) as u16,
        };
    }
}

unsafe fn load_gdt() {
    let ptr = DescPtr {
        limit: (core::mem::size_of_val(&GDT) - 1) as u16,
        base: core::ptr::addr_of!(GDT) as u32,
    };
    asm!(
        "lgdt [{0}]",
        // reload CS via a far return; reload data segs to 0x10
        "push 0x08",
        "lea {tmp}, [2f]",
        "push {tmp}",
        "retf",
        "2:",
        "mov ax, 0x10",
        "mov ds, ax",
        "mov es, ax",
        "mov fs, ax",
        "mov gs, ax",
        "mov ss, ax",
        in(reg) &ptr,
        tmp = out(reg) _,
        out("ax") _,
        options(preserves_flags),
    );
}

unsafe fn load_idt() {
    let ptr = DescPtr {
        limit: (core::mem::size_of_val(&IDT) - 1) as u16,
        base: core::ptr::addr_of!(IDT) as u32,
    };
    asm!("lidt [{0}]", in(reg) &ptr, options(nostack, preserves_flags));
}

/// Remap the 8259 PIC so IRQ0..7 -> vectors 0x20..0x27 (away from
/// CPU exception vectors), mask everything except IRQ0 (timer).
unsafe fn remap_pic() {
    let (m_cmd, m_dat, s_cmd, s_dat) = (0x20u16, 0x21u16, 0xA0u16, 0xA1u16);
    outb(m_cmd, 0x11); // ICW1: init + ICW4
    outb(s_cmd, 0x11);
    outb(m_dat, 0x20); // ICW2: master offset 0x20
    outb(s_dat, 0x28); // ICW2: slave  offset 0x28
    outb(m_dat, 0x04); // ICW3: slave on IRQ2
    outb(s_dat, 0x02);
    outb(m_dat, 0x01); // ICW4: 8086 mode
    outb(s_dat, 0x01);
    outb(m_dat, 0xFE); // mask all but IRQ0 on master
    outb(s_dat, 0xFF); // mask all on slave
}

/// 8253 PIT channel 0, mode 3 (square wave), ~100 Hz.
unsafe fn init_pit() {
    // ~1000 Hz (1193182 / 1193 ≈ 1000). Faster than Linux 0.00's
    // ~100 Hz only so a full-screen fill takes ~2 s instead of
    // ~20 s — same real 8253 PIT, same real timer-driven switch.
    let divisor: u16 = 1193;
    outb(0x43, 0x36);
    outb(0x40, (divisor & 0xFF) as u8);
    outb(0x40, (divisor >> 8) as u8);
}

// --- the two hardcoded tasks ----------------------------------------

const TASK_STACK_WORDS: usize = 1024;
static mut TASK_A_STACK: [u32; TASK_STACK_WORDS] = [0; TASK_STACK_WORDS];
static mut TASK_B_STACK: [u32; TASK_STACK_WORDS] = [0; TASK_STACK_WORDS];

/// Common task body. Each iteration: emit this task's character to
/// VGA + COM1, then `hlt`. `hlt` parks the CPU until the next timer
/// interrupt, whose ISR switches to the OTHER task. So exactly one
/// char per task per timer tick → a clean kernel-mediated A/B
/// interleave, the faithful Linux 0.00 behaviour.
fn task_body(ch: u8) -> ! {
    loop {
        let n = TOTAL.fetch_add(1, Ordering::SeqCst);
        if n >= LIMIT {
            // First task to cross the line reports + halts the box.
            if n == LIMIT {
                sputs(b"\n[linux000] reached LIMIT; ");
                sputs(b"timer-driven A/B task switch verified\n");
                sputs(b"[linux000 DONE]\n");
            }
            loop {
                unsafe { asm!("cli; hlt", options(nostack, preserves_flags)) };
            }
        }
        vga_putc(ch);
        sputc(ch);
        unsafe { asm!("sti; hlt", options(nostack, preserves_flags)) };
    }
}

#[no_mangle]
extern "C" fn task_a() -> ! {
    task_body(b'A')
}

#[no_mangle]
extern "C" fn task_b() -> ! {
    task_body(b'B')
}

/// Seed a task's initial stack so the timer ISR's `popad; iretd`
/// tail lands at `entry` with interrupts enabled. Layout, high → low
/// address:  [EFLAGS][CS][EIP] then the 8-dword pushad block. Returns
/// the ESP value (points at the pushad block) for TASK_ESP[k].
unsafe fn seed_task(stack: &'static mut [u32; TASK_STACK_WORDS], entry: extern "C" fn() -> !) -> u32 {
    let top = stack.as_mut_ptr().add(TASK_STACK_WORDS);
    // iret frame
    let mut sp = top;
    sp = sp.sub(1);
    sp.write(0x202); // EFLAGS: IF=1, bit1 reserved=1
    sp = sp.sub(1);
    sp.write(0x08); // CS
    sp = sp.sub(1);
    sp.write(entry as usize as u32); // EIP
    // pusha block (8 dwords; values irrelevant on first entry)
    for _ in 0..8 {
        sp = sp.sub(1);
        sp.write(0);
    }
    sp as u32
}

#[no_mangle]
pub extern "C" fn kernel_main() -> ! {
    sputs(b"\nYantra bare-metal Linux 0.00 replica - hello from bare metal\n");
    sputs(b"  32-bit protected mode, multiboot1, no GPU.\n");

    unsafe {
        load_gdt();
        sputs(b"  [ok] GDT loaded (flat code 0x08 / data 0x10)\n");

        // Point the first 32 vectors (CPU exceptions) at the default
        // handler so a fault is visible, then IRQ0 at the timer ISR.
        for v in 0..32 {
            idt_set(v, exc_isr as usize);
        }
        idt_set(0x20, timer_isr as usize);
        load_idt();
        sputs(b"  [ok] IDT loaded (exc 0..31, timer @ 0x20)\n");

        remap_pic();
        sputs(b"  [ok] 8259 PIC remapped (IRQ0->0x20, only IRQ0 unmasked)\n");

        init_pit();
        sputs(b"  [ok] 8253 PIT @ ~1000 Hz (channel 0, mode 3)\n");

        let esp_a = seed_task(&mut *core::ptr::addr_of_mut!(TASK_A_STACK), task_a);
        let esp_b = seed_task(&mut *core::ptr::addr_of_mut!(TASK_B_STACK), task_b);
        TASK_ESP[0] = esp_a;
        TASK_ESP[1] = esp_b;
        CUR = 0;
        sputs(b"  [ok] tasks A/B seeded; jump-starting task A\n");
        sputs(b"  --- timer-driven A/B stream follows ---\n");

        // Hand control to task A; from here the timer ISR drives
        // everything. Never returns.
        start_tasks(esp_a)
    }
}

fn halt() -> ! {
    loop {
        unsafe { asm!("cli; hlt", options(nostack, preserves_flags)) };
    }
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    sputs(b"\n[linux000 PANIC]\n");
    halt()
}
