struct Point { x: i64, y: i64 }

fn sum(p: Point) -> i64 {
    let Point { x, y } = p;
    x + y
}

fn main() -> i64 {
    let p = Point { x: 5, y: 8 };
    sum(p)
}
