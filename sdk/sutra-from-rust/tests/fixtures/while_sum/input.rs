fn sum_to(n: i32) -> i32 {
    let mut acc = 0;
    let mut i = 0;
    while i < n {
        i = i + 1;
        acc = acc + i;
    }
    acc
}

fn main() -> i32 {
    sum_to(5)
}
