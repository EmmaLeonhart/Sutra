type point = Origin | Pair of int * int

let sum_pt (p : point) =
  match p with
  | Origin -> 0
  | Pair (a, b) -> a + b

let main () =
  let q = Pair (7, 9) in
  let r = Origin in
  sum_pt q + sum_pt r
