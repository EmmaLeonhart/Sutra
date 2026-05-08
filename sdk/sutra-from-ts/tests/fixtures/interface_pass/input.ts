// TypeScript interface + typed function: standard structural-typing
// pattern. Should lower to an Axon with the interface's fields as
// keys, exactly like the C struct case.

interface Point {
    x: number;
    y: number;
}

function distance_squared(p: Point): number {
    return p.x * p.x + p.y * p.y;
}

function main(): number {
    const p: Point = { x: 3, y: 4 };
    return distance_squared(p);
}
