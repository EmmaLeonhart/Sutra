struct Point { x: i64, y: i64 }

fn shift(base: Point) -> i64 {
    let q = Point { x: 9, ..base };
    q.x + q.y
}

fn main() -> i64 {
    let p = Point { x: 1, y: 8 };
    shift(p)
}
