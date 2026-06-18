type pt = { x : int; y : int }

let f (t : int * pt) =
  let (a, { x; y }) = t in
  a + x + y

let main () = f (5, { x = 8; y = 3 })
