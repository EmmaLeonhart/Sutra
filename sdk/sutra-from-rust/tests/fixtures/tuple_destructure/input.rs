fn add_pair(t: (i64, i64)) -> i64 {
    let (a, b) = t;
    a + b
}

fn main() -> i64 {
    add_pair((5, 8))
}
