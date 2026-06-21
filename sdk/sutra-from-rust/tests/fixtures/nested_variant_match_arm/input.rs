enum E { A(i32), B(i32) }

fn f(e: E, g: E) -> i32 {
    match e {
        E::A(x) => x + match g { E::A(y) => y, E::B(y) => 0 - y },
        E::B(x) => x,
    }
}

fn main() -> i32 { f(E::A(3), E::B(5)) }
