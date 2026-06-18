fn f(b: bool) -> i64 {
    match b {
        true => 10,
        false => 20,
    }
}

fn main() -> i64 {
    f(true)
}
