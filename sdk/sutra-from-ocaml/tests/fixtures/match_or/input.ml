let classify n =
  match n with
  | 1 | 2 | 3 -> 100
  | 7 | 8 -> 200
  | _ -> 0

let main () = classify 2 + classify 8 + classify 5
