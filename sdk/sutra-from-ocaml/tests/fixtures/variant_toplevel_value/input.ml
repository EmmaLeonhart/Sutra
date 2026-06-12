type expr = Zero | Pair of int * int

let z = Zero
let p = Pair (7, 9)

let sum_e (e : expr) =
  match e with
  | Zero -> 0
  | Pair (a, b) -> a + b

let main () =
  sum_e z + sum_e p
