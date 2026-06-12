fn scale(x: i32) -> i32 {
    let y = x + 1;
    let z = y * 2;
    z + x
}

fn main() -> i32 { scale(5) }
