struct Inner { v: i64 }

fn f(t: (i64, Inner)) -> i64 {
    let (a, Inner { v }) = t;
    a + v
}

fn main() -> i64 {
    f((5, Inner { v: 8 }))
}
