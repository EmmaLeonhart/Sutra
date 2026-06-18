enum E { A(i64), B(i64) }

fn f(e: E, n: i64) -> i64 {
    match e {
        E::A(x) => match n {
            0 => x,
            _ => x + 1,
        },
        E::B(y) => y,
    }
}

fn main() -> i64 {
    f(E::A(5), 0)
}
