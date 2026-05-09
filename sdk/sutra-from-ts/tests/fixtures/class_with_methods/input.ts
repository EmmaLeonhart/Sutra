// TS class with parameter properties + a value-returning instance
// method. The transpiler lowers parameter properties to Sutra
// `field` declarations, the constructor body is dropped (Sutra's
// `new ClassName(args)` factory handles initialization), and the
// method emits as a Sutra `method`.

class Point {
    constructor(public x: number, public y: number) {}
    distance_squared(): number {
        return this.x * this.x + this.y * this.y;
    }
}

function main(): number {
    const p: Point = new Point(3, 4);
    return p.distance_squared();
}
