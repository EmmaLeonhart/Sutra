type expr = Lit of int | Neg of int

let lit n = Lit n
let neg n = Neg n

let eval (e : expr) =
  match e with
  | Lit x -> x
  | Neg x -> 0 - x

let main () =
  let a = lit 7 in
  let b = neg 5 in
  eval a + eval b
