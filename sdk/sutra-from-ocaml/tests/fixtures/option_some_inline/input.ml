let f (s : int option) = match s with Some v -> v + 1 | None -> 0
let main () = f (Some 5)
