struct Point {
    x: i32,
    y: i32,
}

fn getx(p: Point) -> i32 { p.x }

fn sum2(p: Point) -> i32 { p.x + p.y }

fn main() -> i32 {
    let a = Point { x: 7, y: 9 };
    getx(a) + sum2(Point { x: 2, y: 3 })
}
