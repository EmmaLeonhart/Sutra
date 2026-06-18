type inner = { v : int }
type outer = { a : int; inr : inner }

let f (o : outer) =
  let { a; inr = { v } } = o in
  a + v

let main () = f { a = 5; inr = { v = 8 } }
