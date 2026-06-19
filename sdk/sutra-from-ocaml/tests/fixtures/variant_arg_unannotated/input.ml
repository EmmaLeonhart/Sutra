type expr = Lit of int | Neg of int
let eval e = match e with Lit n -> n | Neg n -> 0 - n
let main () = eval (Lit 7) + eval (Neg 5)
