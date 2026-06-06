type pt = { x : int; y : int }
let mk a b : pt = { x = a; y = b }
let getx (p : pt) : int = p.x
let main () = getx (mk 7 9)
