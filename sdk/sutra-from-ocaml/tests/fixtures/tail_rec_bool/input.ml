let rec f acc n =
  if (n = 0) || (acc > 100) then acc
  else f (acc + n) (n - 1)

let main () = f 0 5
