type box = Box of int

let unbox (b : box) =
  let (Box x) = b in
  x + 1

let main () = unbox (Box 12)
