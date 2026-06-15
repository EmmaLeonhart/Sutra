fn sum_to(n: i32) -> i32 {
    let mut acc = 0;
    let mut i = 0;
    loop {
        if i >= n { break; }
        acc = acc + i;
        i = i + 1;
    }
    acc
}

fn main() -> i32 {
    sum_to(6)
}
