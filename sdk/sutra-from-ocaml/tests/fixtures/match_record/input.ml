type pt = { x : int; y : int }
let mk a b : pt = { x = a; y = b }
let sum (p : pt) = match p with { x; y } -> x + y
let main () = sum (mk 7 9)
