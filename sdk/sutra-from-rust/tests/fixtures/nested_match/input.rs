enum Expr {
    Lit(i32),
    Neg(i32),
}

fn evalE(e: Expr) -> i32 {
    100 + match e {
        Expr::Lit(n) => n,
        Expr::Neg(n) => 0 - n,
    }
}

fn main() -> i32 {
    evalE(Expr::Lit(7)) + evalE(Expr::Neg(5))
}
