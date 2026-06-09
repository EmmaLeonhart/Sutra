type expr = Lit of int | Neg of int

let eval (e : expr) =
  match e with
  | Lit x -> x
  | Neg x -> 0 - x

let main () = eval (Lit 7)
