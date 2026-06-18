let f (t : int * (int * int)) =
  let (a, (b, c)) = t in
  a + b + c

let main () = f (5, (8, 3))
