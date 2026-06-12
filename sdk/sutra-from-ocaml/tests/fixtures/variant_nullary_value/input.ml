type expr = Zero | Lit of int | Neg of int

let eval (e : expr) =
  match e with
  | Zero -> 0
  | Lit x -> x
  | Neg x -> 0 - x

let main () =
  let z = Zero in
  let a = Lit 7 in
  eval z + eval a
