/* Linker script for the Yantra multiboot1 kernel.
 *
 * QEMU's `-kernel` flag loads multiboot-compatible ELF binaries
 * starting at 1MB physical (0x100000). The .multiboot section MUST
 * be in the first 8KB of the binary so the bootloader can find the
 * magic header. We put it first.
 */

ENTRY(_start)

SECTIONS {
    . = 1M;

    .multiboot : ALIGN(4) {
        KEEP(*(.multiboot))
    }

    .text : ALIGN(4K) {
        *(.text .text.*)
    }

    .rodata : ALIGN(4K) {
        *(.rodata .rodata.*)
    }

    .data : ALIGN(4K) {
        *(.data .data.*)
    }

    .bss : ALIGN(4K) {
        *(.bss .bss.*)
    }
}
