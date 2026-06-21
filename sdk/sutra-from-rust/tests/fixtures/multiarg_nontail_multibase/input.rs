fn f(a: i32, b: i32) -> i32 {
    if a == 0 { b } else if a == 1 { b + 100 } else { a + f(a - 1, b) }
}
fn main() -> i32 { f(3, 10) }
