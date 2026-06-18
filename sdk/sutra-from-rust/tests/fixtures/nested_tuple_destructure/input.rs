fn f(t: (i64, (i64, i64))) -> i64 {
    let (a, (b, c)) = t;
    a + b + c
}

fn main() -> i64 {
    f((5, (8, 3)))
}
