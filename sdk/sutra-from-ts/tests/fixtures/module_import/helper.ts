// Helper module imported by input.ts. Demonstrates that a function
// exported here is callable from the importing module after the
// transpiler inlines this file's declarations at the top of the
// lowered .su output.

export function double(x: number): number {
    return x * 2;
}

export function triple(x: number): number {
    return x * 3;
}
