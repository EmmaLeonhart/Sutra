// Discriminated union — a type alias whose union members share a
// "kind" tag. The transpiler treats the alias as Axon-shaped (same
// as an interface), and the typical narrowing pattern
// (`if (s.kind === ...)`) collapses through the existing
// if-then-implicit-else lowering into a truth-axis blend.

type Shape =
    | { kind: "circle"; r: number }
    | { kind: "square"; side: number };

function area(s: Shape): number {
    if (s.kind === "circle") return s.r * s.r;
    return s.side * s.side;
}

function main(): number {
    const c: Shape = { kind: "circle", r: 5 };
    return area(c);
}
