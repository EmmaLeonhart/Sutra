fn fst(p: (i64, i64)) -> i64 {
    p.0 + p.1
}

fn main() -> i64 {
    fst((5, 8))
}
