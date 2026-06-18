type point = { x : int; y : int }

let sum (p : point) =
  let { x; y } = p in
  x + y

let main () = sum { x = 5; y = 8 }
