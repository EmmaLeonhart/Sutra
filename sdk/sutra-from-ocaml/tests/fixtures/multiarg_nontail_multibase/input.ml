let rec f a b =
  if a = 0 then b
  else if a = 1 then b + 100
  else a + f (a - 1) b

let main () = f 3 10
