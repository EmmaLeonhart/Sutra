enum Dir { North, South }

fn code(d: Dir) -> i64 {
    match d {
        Dir::North => 10,
        Dir::South => 20,
    }
}

fn main() -> i64 {
    let d = Dir::South;
    code(d)
}
