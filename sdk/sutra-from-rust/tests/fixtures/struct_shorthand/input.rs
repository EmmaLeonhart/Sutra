struct Point {
    x: i32,
    y: i32,
}

fn sum2(p: Point) -> i32 { p.x + p.y }

fn main() -> i32 {
    let x = 5;
    let y = 8;
    sum2(Point { x, y })
}
