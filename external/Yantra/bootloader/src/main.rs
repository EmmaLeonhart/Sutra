//! Yantra bare-metal kernel v0.3 — multiboot1, 32-bit Rust, PCI scan,
//! GPU framebuffer write, long-mode transition.
//!
//! Boots in QEMU via `qemu-system-x86_64 -kernel <this-binary>`. Path:
//!
//!   1. multiboot1 hands off in 32-bit protected mode.
//!   2. `_start` (in `global_asm!`) sets ESP and calls `kernel_main`.
//!   3. `kernel_main` (32-bit Rust):
//!      a. Prints the v0.1 banner via COM1.
//!      b. Enumerates the PCI bus and prints each present device.
//!   4. After kernel_main returns (we still have a stack), we jump to
//!      `enter_long_mode` (asm) which sets up minimal paging, enables
//!      PAE, sets EFER.LME, enables long mode, and far-jumps to a
//!      64-bit code segment.
//!   5. After the jump, 64-bit asm prints "Long mode active" via COM1
//!      and halts. No Rust runs in 64-bit mode — that's v0.2 work
//!      (multiboot2 + x86_64 target migration).
//!
//! What this v0.1 demonstrates that v0.0 didn't:
//!   - We can talk to QEMU's virtualized hardware via PCI config space.
//!   - We can transition the CPU from 32-bit protected mode into
//!     64-bit long mode under our own control.
//!
//! What v0.1 still does NOT do:
//!   - No GPU init. We *see* the GPU via PCI scan but don't drive it.
//!   - No 64-bit Rust execution.
//!   - No kernel image load.
//!   - No orchestrator handoff.

#![no_std]
#![no_main]

use core::arch::{asm, global_asm};
use core::panic::PanicInfo;

mod pci;

// --- multiboot1 header ----------------------------------------------

const MULTIBOOT_MAGIC: u32 = 0x1BADB002;
const MULTIBOOT_FLAGS: u32 = 0;
const MULTIBOOT_CHECKSUM: u32 = (-((MULTIBOOT_MAGIC + MULTIBOOT_FLAGS) as i32)) as u32;

#[link_section = ".multiboot"]
#[used]
static MULTIBOOT_HEADER: [u32; 3] = [
    MULTIBOOT_MAGIC,
    MULTIBOOT_FLAGS,
    MULTIBOOT_CHECKSUM,
];

// --- entry: 32-bit asm sets stack, jumps to kernel_main; then long-mode ------
//
// kernel_main is `extern "C"` returning `()` (it doesn't return `!`)
// so we can fall through from the 32-bit `call` back into asm that
// performs the long-mode transition. The long-mode transition is the
// last thing we do; everything after the far-jump is 64-bit and there
// is no path back.

global_asm!(
    r#"
    .intel_syntax noprefix
    .section .text
    .global _start
_start:
    /* Multiboot1 hands off in 32-bit protected mode. Magic in EAX,
     * info ptr in EBX. We don't use them in v0.1 but push to stack
     * so future code can. */
    lea esp, [stack_top]
    push ebx
    push eax
    call kernel_main
    /* kernel_main returns here (32-bit). Jump into long-mode setup. */
    jmp enter_long_mode

    /* ---- long-mode setup ----
     *
     * On entry: 32-bit protected mode, no paging.
     *
     * Steps (canonical x86_64 long-mode-entry sequence):
     *   1. Build identity-mapped page tables (PML4 -> PDP -> 2MB pages).
     *   2. Load CR3 with PML4 physical address.
     *   3. Set CR4.PAE (bit 5).
     *   4. Set EFER.LME via MSR 0xC0000080 (Long Mode Enable).
     *   5. Set CR0.PG (bit 31) + CR0.PE (already set).
     *   6. Far jump to 64-bit code segment in the GDT we set up
     *      below.
     *
     * After the jump we're in long mode, in the 64-bit code
     * segment, with paging on and the first 1 GB identity-mapped
     * via 512 huge 2-MB pages.
     */
enter_long_mode:
    /* Disable paging just in case (it's already off after multiboot). */
    mov eax, cr0
    and eax, 0x7FFFFFFF
    mov cr0, eax

    /* Step 1: build the page tables. We do this once in code rather
     * than statically initializing in .bss so the values are clear.
     * pml4[0] -> pdp; pdp[0..512] -> identity 2MB pages covering
     * the first 1 GiB. That's enough for our hello-print.
     */
    /* pml4[0] = &pdp | (writable | present) */
    mov eax, OFFSET pdp
    or eax, 0b11
    mov [pml4], eax

    /* Fill pdp[i] for i in 0..512 with i*2MB | (huge | writable | present). */
    mov ecx, 0
.pdp_loop:
    mov eax, ecx
    shl eax, 21              /* eax = i * 2 MiB */
    or eax, 0b10000011       /* huge (bit 7) | writable | present */
    mov [pdp + ecx * 8], eax
    /* high 32 bits of the entry (we're filling u64s) — zero. */
    mov DWORD PTR [pdp + ecx * 8 + 4], 0
    inc ecx
    cmp ecx, 512
    jne .pdp_loop

    /* Step 2: CR3 = phys(pml4) */
    mov eax, OFFSET pml4
    mov cr3, eax

    /* Step 3: CR4 |= PAE (bit 5) */
    mov eax, cr4
    or eax, 1 << 5
    mov cr4, eax

    /* Step 4: EFER |= LME via MSR 0xC0000080 */
    mov ecx, 0xC0000080
    rdmsr
    or eax, 1 << 8           /* LME bit */
    wrmsr

    /* Step 5: CR0 |= PG (bit 31). PE (bit 0) is already set. */
    mov eax, cr0
    or eax, 1 << 31
    mov cr0, eax

    /* Load our GDT with 32-bit + 64-bit code descriptors. */
    lgdt [gdt_descriptor]

    /* Step 6: far jump to 64-bit code segment (GDT selector 0x08).
     * Encode the far jump by hand because GAS/Intel-syntax handling
     * of `jmp seg:offset` is inconsistent across assemblers. The
     * far-jump opcode is 0xEA followed by 32-bit offset + 16-bit
     * selector. */
    .byte 0xEA
    .long long_mode_start
    .word 0x08

    /* ---- 64-bit code below ---- */
    .code64
long_mode_start:
    /* Reload data segments to null (long mode ignores most of these
     * but it's clean to zero them). */
    mov ax, 0
    mov ss, ax
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax

    /* Print "Long mode active\n" via COM1 (port 0x3F8). */
    lea rsi, [rip + long_mode_msg]
    mov rdx, 0x3F8
.print_loop:
    lodsb                    /* AL = [RSI]; RSI++ */
    test al, al
    jz .print_done
    out dx, al
    jmp .print_loop
.print_done:
    /* Halt forever in 64-bit mode. */
.halt:
    cli
    hlt
    jmp .halt

    /* ---- data ---- */
    .code32                  /* (data section is mode-agnostic but reset) */

    .section .rodata
    .align 8
long_mode_msg:
    .asciz "Long mode active\n"

    /* GDT: null, 32-bit code (unused after the jump), 64-bit code.
     * 64-bit code descriptor: limit=0, base=0, type=executable+readable,
     * S=1, DPL=0, P=1, L=1 (long mode), D=0, G=0.
     *
     * Selector 0x08 corresponds to GDT index 1 (the 64-bit code desc).
     */
    .align 8
gdt_start:
    .quad 0                          /* null descriptor */
    .quad 0x00AF9A000000FFFF         /* 64-bit code: L=1, executable+readable */
    .quad 0x00CF92000000FFFF         /* 32-bit data (unused but defined) */
gdt_end:

gdt_descriptor:
    .word gdt_end - gdt_start - 1    /* limit */
    .long gdt_start                   /* base */

    /* ---- page tables (uninitialized; filled at runtime above) ----
     *
     * Aligned to 4 KiB per the spec. PML4 has 512 entries; we only
     * use entry 0. PDP also has 512 entries; we fill all 512 with
     * identity-mapped 2 MiB pages for the first 1 GiB.
     */
    .section .bss
    .align 4096
pml4:
    .skip 4096
pdp:
    .skip 4096

    .align 16
stack_bottom:
    .skip 16384
stack_top:
    "#
);

// --- 32-bit Rust kernel ---------------------------------------------

const HELLO: &[u8] = b"Yantra bootloader v0.4 - hello from bare metal\n";

// --- Kernel image (placeholder) --------------------------------------
//
// What this is: a sentinel byte sequence that stands in for the
// compiled Sutra kernel image. Real Sutra programs compile to
// PyTorch modules — Python source that imports torch and executes
// on a CUDA device. That cannot run on QEMU's emulated stdvga
// (the device this v0.0 bootloader knows how to drive); it needs
// real GPU passthrough (Linux host + spare GPU + VFIO config),
// which is hardware we don't have here. So v0.4 demonstrates the
// **handoff mechanism**: bootloader loads the image bytes into a
// designated GPU-memory region, hands off to a stub orchestrator.
// The orchestrator currently just prints "Orchestrator running"
// because there is nothing on the GPU it can actually drive.
//
// When real GPU passthrough is available (or when we have a
// genuine GPU compute target), the placeholder gets replaced by
// `include_bytes!("../../kernel_image.bin")` or similar, and the
// orchestrator gains real work to do.

const KERNEL_IMAGE: &[u8] = b"YANTRA_KERNEL_IMAGE_PLACEHOLDER_v0.4_compiled_Sutra_goes_here";
const KERNEL_IMAGE_BANNER: &[u8] = b"-- kernel image load --\n";
const ORCHESTRATOR_BANNER: &[u8] = b"-- orchestrator handoff --\n";
const PCI_BANNER: &[u8] = b"-- PCI scan --\n";
const PCI_END: &[u8] = b"-- end PCI scan --\n";
const GPU_BANNER: &[u8] = b"-- GPU init (framebuffer) --\n";
const SERIAL_COM1: u16 = 0x3F8;

// QEMU's default "stdvga" display device (vendor=0x1234 device=0x1111,
// class=0x03 display). We look this up dynamically rather than
// hard-coding the PCI bus/dev/func so the same code works if QEMU
// is reconfigured.
const QEMU_VGA_VENDOR: u16 = 0x1234;
const QEMU_VGA_DEVICE: u16 = 0x1111;

#[no_mangle]
pub extern "C" fn kernel_main(_multiboot_magic: u32, _multiboot_info: u32) {
    write_serial(HELLO);
    write_serial(PCI_BANNER);

    // While scanning, remember the GPU's location so we can read its
    // BAR0 immediately after.
    let mut gpu_location: Option<(u8, u8, u8)> = None;
    pci::scan(|d| {
        write_serial(b"  ");
        write_hex_u8(d.bus);
        write_serial(b":");
        write_hex_u8(d.dev);
        write_serial(b".");
        write_hex_u4(d.func);
        write_serial(b" vendor=");
        write_hex_u16(d.vendor_id);
        write_serial(b" device=");
        write_hex_u16(d.device_id);
        write_serial(b" class=");
        write_hex_u8(d.class_code);
        write_serial(b" (");
        write_serial(pci::class_name(d.class_code).as_bytes());
        write_serial(b") subclass=");
        write_hex_u8(d.subclass);
        write_serial(b"\n");

        if d.vendor_id == QEMU_VGA_VENDOR && d.device_id == QEMU_VGA_DEVICE {
            gpu_location = Some((d.bus, d.dev, d.func));
        }
    });
    write_serial(PCI_END);

    write_serial(GPU_BANNER);
    let gpu_fb_addr = if let Some((bus, dev, func)) = gpu_location {
        gpu_init(bus, dev, func)
    } else {
        write_serial(b"  GPU not found (QEMU stdvga 1234:1111 missing)\n");
        0
    };

    write_serial(KERNEL_IMAGE_BANNER);
    load_kernel_image(gpu_fb_addr);

    write_serial(ORCHESTRATOR_BANNER);
    orchestrator_stub();

    // Fall through to enter_long_mode (asm tail).
}

/// "Load" the Sutra kernel image into the GPU memory region. In
/// v0.4 this copies KERNEL_IMAGE bytes to the high end of the
/// framebuffer (out of the visible-pixel area we wrote to in v0.3).
/// In a real Yantra appliance this is where the bootloader would
/// place a compiled Sutra .su image at a known GPU-memory address
/// the orchestrator can find later.
///
/// Honest about what's NOT real here: KERNEL_IMAGE is a sentinel
/// byte sequence, not an actual compiled Sutra program. Real
/// Sutra programs are PyTorch modules requiring CUDA — they can't
/// execute on QEMU's emulated stdvga. We demonstrate the
/// *handoff mechanism* (bytes get copied to a known GPU-memory
/// region the orchestrator can find), not Sutra execution.
fn load_kernel_image(fb_base: u32) {
    if fb_base == 0 {
        write_serial(b"  no framebuffer; skipping image load\n");
        return;
    }
    // Copy to a region well past our v0.3 gradient (640*100 pixels
    // * 4 bytes = 256KB). Use byte offset 1 MiB into the
    // framebuffer to be safely past the visible region for any
    // reasonable resolution. The stdvga BAR0 region is 16 MiB so
    // 1 MiB offset is well within it.
    let image_dest = (fb_base as usize + 0x100000) as *mut u8;
    let n = KERNEL_IMAGE.len();
    for i in 0..n {
        unsafe { image_dest.add(i).write_volatile(KERNEL_IMAGE[i]) };
    }
    write_serial(b"  copied ");
    write_dec_u32(n as u32);
    write_serial(b" bytes to GPU memory at 0x");
    write_hex_u32(fb_base + 0x100000);
    write_serial(b"\n");
    // Read back the first 4 bytes to confirm the write took.
    let first4: u32 = unsafe { core::ptr::read_volatile(image_dest as *const u32) };
    write_serial(b"  first 4 bytes read back = 0x");
    write_hex_u32(first4);
    write_serial(b" (= 'Y','A','N','T' = 0x544E4159)\n");
}

/// Stub orchestrator. In the production design this is the Rust
/// orchestrator (`planning/01-architecture.md` § "CPU side: small,
/// Rust, orchestrator") that becomes the standing CPU-side
/// companion to the GPU — manages disc/RAM/GPU storage-tier moves,
/// wires the axon router, runs the GPU tick loop. None of that is
/// possible on QEMU's emulated stdvga because real Sutra programs
/// need CUDA. So v0.4's "orchestrator" just prints proof-of-life
/// and falls through.
///
/// When real GPU passthrough is available, this function gets
/// replaced by the actual orchestrator entry point (which would
/// loop forever rather than fall through).
fn orchestrator_stub() {
    write_serial(b"  Orchestrator running. (stub - no GPU compute target on QEMU stdvga.)\n");
    write_serial(b"  In a real Yantra appliance, this is where the Rust\n");
    write_serial(b"  orchestrator's tick loop starts and the Sutra kernel\n");
    write_serial(b"  begins executing on the GPU. Needs hardware we don't\n");
    write_serial(b"  have under QEMU emulated stdvga; ship status: handoff\n");
    write_serial(b"  mechanism demonstrated, runtime gated on real GPU\n");
    write_serial(b"  passthrough or a Yantra-shaped GPU target.\n");
}

/// Read the GPU's BAR0 (linear framebuffer address) and write a
/// recognizable pattern to it. Returns the framebuffer base
/// address so the caller can use it for v0.4's kernel-image load.
///
/// For QEMU's stdvga in default mode (640x480, 32 bpp BGRA), BAR0
/// points to the linear framebuffer. We write a horizontal gradient
/// to the first 100 scanlines so the QEMU display window (if not
/// `-display none`) shows a visible color band. With `-display none`
/// the write still happens; this function prints back the BAR0
/// address + first pixel value via serial so we can confirm the
/// write took effect even headless.
fn gpu_init(bus: u8, dev: u8, func: u8) -> u32 {
    let bar0 = pci::bar_u32(bus, dev, func, 0);
    let framebuffer_addr = (bar0 & !0xF) as u32;

    write_serial(b"  GPU PCI=");
    write_hex_u8(bus);
    write_serial(b":");
    write_hex_u8(dev);
    write_serial(b".");
    write_hex_u4(func);
    write_serial(b" BAR0=0x");
    write_hex_u32(bar0);
    write_serial(b" framebuffer=0x");
    write_hex_u32(framebuffer_addr);
    write_serial(b"\n");

    if framebuffer_addr == 0 {
        write_serial(b"  BAR0 not configured; skipping framebuffer write\n");
        return 0;
    }

    // Default QEMU stdvga is 640x480 32 bpp. Write a horizontal
    // gradient: row 0 is dark, row 100 is bright. Each pixel is
    // 4 bytes (BGRA, A unused).
    const WIDTH: usize = 640;
    const STRIPE_ROWS: usize = 100;
    let fb = framebuffer_addr as *mut u32;
    for y in 0..STRIPE_ROWS {
        // Color: a Yantra-blue gradient (B=increasing, G=0, R=0).
        let intensity = ((y * 255) / STRIPE_ROWS) as u32;
        let pixel: u32 = 0xFF000000 | intensity; // A=0xFF, R=0, G=0, B=intensity
        for x in 0..WIDTH {
            unsafe {
                fb.add(y * WIDTH + x).write_volatile(pixel);
            }
        }
    }

    write_serial(b"  wrote 100x640 pixel gradient to framebuffer\n");
    write_serial(b"  first pixel = 0x");
    let first = unsafe { fb.read_volatile() };
    write_hex_u32(first);
    write_serial(b" (should be 0xFF000000 = top-row black)\n");
    framebuffer_addr
}

fn write_dec_u32(mut v: u32) {
    if v == 0 {
        unsafe { outb(SERIAL_COM1, b'0') };
        return;
    }
    let mut buf = [0u8; 10];
    let mut n = 0;
    while v > 0 {
        buf[n] = b'0' + (v % 10) as u8;
        v /= 10;
        n += 1;
    }
    while n > 0 {
        n -= 1;
        unsafe { outb(SERIAL_COM1, buf[n]) };
    }
}

fn write_serial(bytes: &[u8]) {
    for &b in bytes {
        unsafe { outb(SERIAL_COM1, b) };
    }
}

unsafe fn outb(port: u16, val: u8) {
    asm!(
        "out dx, al",
        in("dx") port,
        in("al") val,
        options(nostack, preserves_flags),
    );
}

fn write_hex_u4(v: u8) {
    let v = v & 0xF;
    let c = if v < 10 { b'0' + v } else { b'a' + v - 10 };
    unsafe { outb(SERIAL_COM1, c) };
}

fn write_hex_u8(v: u8) {
    write_hex_u4(v >> 4);
    write_hex_u4(v & 0xF);
}

fn write_hex_u16(v: u16) {
    write_hex_u8((v >> 8) as u8);
    write_hex_u8(v as u8);
}

fn write_hex_u32(v: u32) {
    write_hex_u16((v >> 16) as u16);
    write_hex_u16(v as u16);
}

fn halt_loop() -> ! {
    loop {
        unsafe {
            asm!("cli; hlt", options(nostack, preserves_flags));
        }
    }
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    write_serial(b"\n[Yantra PANIC]\n");
    halt_loop();
}
