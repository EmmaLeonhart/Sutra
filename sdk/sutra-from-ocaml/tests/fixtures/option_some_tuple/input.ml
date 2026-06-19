let f (s : (int * int) option) = match s with Some (a, b) -> a + b | None -> 0
let main () = f (Some (5, 8))
