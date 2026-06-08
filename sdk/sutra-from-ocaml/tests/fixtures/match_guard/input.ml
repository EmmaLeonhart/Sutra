let sign n =
  match n with
  | x when x > 0 -> 1
  | 0 -> 0
  | _ -> -1

let main () = (sign 7 + 10) + ((sign 0 + 20) + (sign (-4) + 30))
