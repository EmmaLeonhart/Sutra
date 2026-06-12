type rec_t = { x : int; y : int }
type expr = Lit of int | Neg of int

let getx (r : rec_t) = r.x

let eval (e : expr) =
  match e with
  | Lit n -> n
  | Neg n -> 0 - n

let main () =
  getx { x = 7; y = 9 } + eval (Lit 5)
