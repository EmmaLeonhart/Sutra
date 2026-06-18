enum Shape { Circle(i64), Square(i64) }

fn radius(s: Shape) -> i64 {
    if let Shape::Circle(r) = s {
        r + 1
    } else {
        0
    }
}

fn main() -> i64 {
    radius(Shape::Circle(12))
}
