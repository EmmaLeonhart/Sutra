fn sum_to(acc: i32, n: i32) -> i32 {
    if n == 0 { acc } else { sum_to(acc + n, n - 1) }
}

fn main() -> i32 { sum_to(0, 5) }
