struct Inner { v: i64 }
struct Outer { a: i64, inner: Inner }

fn f(o: Outer) -> i64 {
    let Outer { a, inner: Inner { v } } = o;
    a + v
}

fn main() -> i64 {
    f(Outer { a: 5, inner: Inner { v: 8 } })
}
