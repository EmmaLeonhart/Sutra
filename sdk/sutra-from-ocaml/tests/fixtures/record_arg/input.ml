type pt = { x : int; y : int }
let sum2 (p : pt) : int = p.x + p.y
let main () = sum2 { x = 7; y = 9 }
