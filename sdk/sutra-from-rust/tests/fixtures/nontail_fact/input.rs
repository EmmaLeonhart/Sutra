fn fact(n: i32) -> i32 {
    if n == 0 { 1 } else { n * fact(n - 1) }
}

fn main() -> i32 { fact(5) }
