struct Outer { a: i64, pos: (i64, i64) }

fn g(o: Outer) -> i64 {
    let Outer { a, pos: (x, y) } = o;
    a + x + y
}

fn main() -> i64 {
    g(Outer { a: 5, pos: (8, 3) })
}
