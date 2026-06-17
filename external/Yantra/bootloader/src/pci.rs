//! PCI bus enumeration via the legacy config-space mechanism.
//!
//! Two I/O ports drive it:
//!   - CONFIG_ADDRESS (`0xCF8`, 32-bit write): writes a bus/dev/fn/
//!     offset triple to address the config-space register we want to
//!     read. Bit layout: `[31 enable | 30:24 reserved | 23:16 bus |
//!     15:11 dev | 10:8 fn | 7:2 reg | 1:0 zero]`.
//!   - CONFIG_DATA (`0xCFC`, 32-bit read): yields the dword at the
//!     previously-addressed config-space register.
//!
//! The shape we read at offset 0 is `vendor_id << 16 | device_id`
//! (low and high 16-bit halves respectively when little-endian).
//! At offset 8 is `class_code << 24 | subclass << 16 | prog_if << 8 |
//! revision`. We print both so the user can see what hardware QEMU
//! is presenting.
//!
//! A vendor_id of `0xFFFF` means "no device at this address" — skip
//! and continue. For multi-function devices the header at offset
//! `0x0E` has bit 7 set, indicating function 1+ should also be
//! probed; we just probe all 8 functions of every device for
//! simplicity (the absent ones return 0xFFFF anyway).
//!
//! Scope: enumeration only. Initialising a specific device (GPU or
//! otherwise) is its own work for v0.2+.

use core::arch::asm;

const CONFIG_ADDRESS: u16 = 0xCF8;
const CONFIG_DATA: u16 = 0xCFC;

unsafe fn outl(port: u16, val: u32) {
    asm!(
        "out dx, eax",
        in("dx") port,
        in("eax") val,
        options(nostack, preserves_flags),
    );
}

unsafe fn inl(port: u16) -> u32 {
    let val: u32;
    asm!(
        "in eax, dx",
        out("eax") val,
        in("dx") port,
        options(nostack, preserves_flags),
    );
    val
}

/// Read a 32-bit config-space register at `(bus, dev, fn, reg)`.
///
/// `reg` is the byte offset; only the low 8 bits matter and they
/// must be 4-byte aligned (low 2 bits are zero per the spec).
fn config_read_u32(bus: u8, dev: u8, func: u8, reg: u8) -> u32 {
    let address: u32 = 0x8000_0000
        | ((bus as u32) << 16)
        | (((dev as u32) & 0x1F) << 11)
        | (((func as u32) & 0x07) << 8)
        | ((reg as u32) & 0xFC);
    unsafe {
        outl(CONFIG_ADDRESS, address);
        inl(CONFIG_DATA)
    }
}

/// One found PCI device — enough to identify it for printing.
pub struct PciDevice {
    pub bus: u8,
    pub dev: u8,
    pub func: u8,
    pub vendor_id: u16,
    pub device_id: u16,
    pub class_code: u8,
    pub subclass: u8,
}

/// Iterator-like callback: invoke `f` for every present device.
///
/// Avoids allocating a list (we have no heap), and lets the caller
/// stream-print each device as it's found. `f` returns nothing;
/// continuation is unconditional.
pub fn scan<F: FnMut(PciDevice)>(mut f: F) {
    for bus in 0u8..=255 {
        for dev in 0u8..32 {
            for func in 0u8..8 {
                let vendor_device = config_read_u32(bus, dev, func, 0);
                let vendor_id = (vendor_device & 0xFFFF) as u16;
                if vendor_id == 0xFFFF {
                    continue;
                }
                let device_id = ((vendor_device >> 16) & 0xFFFF) as u16;
                let class_reg = config_read_u32(bus, dev, func, 8);
                let class_code = ((class_reg >> 24) & 0xFF) as u8;
                let subclass = ((class_reg >> 16) & 0xFF) as u8;
                f(PciDevice {
                    bus,
                    dev,
                    func,
                    vendor_id,
                    device_id,
                    class_code,
                    subclass,
                });
            }
        }
    }
}

/// Read BAR (Base Address Register) at index 0..=5 for a specific
/// PCI device. Returns the 32-bit BAR value. For a memory-mapped
/// BAR, low bit is 0 and `& !0xF` is the base address. For an I/O
/// BAR, low bit is 1.
///
/// BARs are at config-space offsets 0x10, 0x14, 0x18, 0x1C, 0x20,
/// 0x24 for indices 0..5 respectively.
pub fn bar_u32(bus: u8, dev: u8, func: u8, index: u8) -> u32 {
    let offset = 0x10 + (index & 0x05) * 4;
    config_read_u32(bus, dev, func, offset)
}

/// Make `config_read_u32` callable from outside this module — the
/// bootloader sometimes needs to peek at config space directly
/// (e.g., to read a BAR with sub-dword precision the helpers
/// above don't expose).
pub fn config_read(bus: u8, dev: u8, func: u8, reg: u8) -> u32 {
    config_read_u32(bus, dev, func, reg)
}

/// Human-readable name for a PCI class code (best effort, common
/// classes only). Returns "?" for unknown.
pub fn class_name(class_code: u8) -> &'static str {
    match class_code {
        0x00 => "unclassified",
        0x01 => "mass-storage",
        0x02 => "network",
        0x03 => "display",
        0x04 => "multimedia",
        0x05 => "memory",
        0x06 => "bridge",
        0x07 => "comm",
        0x08 => "system-periph",
        0x09 => "input",
        0x0A => "docking",
        0x0B => "processor",
        0x0C => "serial-bus",
        0x0D => "wireless",
        _ => "?",
    }
}
