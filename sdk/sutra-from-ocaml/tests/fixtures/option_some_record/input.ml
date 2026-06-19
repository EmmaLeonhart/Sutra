type pt = { x : int; y : int }
let f (s : pt option) = match s with Some {x; y} -> x + y | None -> 0
let main () = f (Some {x = 5; y = 8})
