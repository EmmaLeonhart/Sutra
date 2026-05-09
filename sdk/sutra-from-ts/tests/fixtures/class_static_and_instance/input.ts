// Class with both static and instance methods. The instance method
// constructs a new Vec2 in its body via `new`; the static method
// is called as `Vec2.origin()` (class-namespace dispatch on the
// Sutra side maps to the mangled `Vec2_origin()` form).

class Vec2 {
    constructor(public x: number, public y: number) {}
    add(other: Vec2): Vec2 {
        return new Vec2(this.x + other.x, this.y + other.y);
    }
    static origin(): Vec2 {
        return new Vec2(0, 0);
    }
}

function main(): number {
    const a: Vec2 = new Vec2(3, 4);
    const b: Vec2 = Vec2.origin();
    const c: Vec2 = a.add(b);
    return c.x;
}
