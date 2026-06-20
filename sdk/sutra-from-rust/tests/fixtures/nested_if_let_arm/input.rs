enum E { A(i32), B(i32) }

fn f(e: E, g: E) -> i32 {
    match e {
        E::A(x) => x + if let E::A(y) = g { y } else { 0 },
        E::B(x) => x,
    }
}

fn main() -> i32 { f(E::A(3), E::A(5)) }
