enum Expr {
    Lit(i32),
    Neg(i32),
    Pair(i32, i32),
}

fn eval(e: Expr) -> i32 {
    match e {
        Expr::Lit(x) => x,
        Expr::Neg(x) => 0 - x,
        Expr::Pair(a, b) => a + b,
    }
}

fn main() -> i32 { eval(Expr::Lit(7)) + eval(Expr::Neg(5)) }
