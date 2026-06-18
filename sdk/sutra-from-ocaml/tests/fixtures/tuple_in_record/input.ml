type pt = { a : int; pos : int * int }

let g (r : pt) =
  let { a; pos = (x, y) } = r in
  a + x + y

let main () = g { a = 5; pos = (8, 3) }
