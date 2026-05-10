// Arrow function that captures an enclosing-scope local. Sutra has
// no closure, so the transpiler lifts the captured local to an
// extra parameter and threads its value through at every direct
// call site.

function main(): number {
    const multiplier: number = 5;
    const scale = (x: number): number => x * multiplier;
    return scale(7);   // expect 35
}
