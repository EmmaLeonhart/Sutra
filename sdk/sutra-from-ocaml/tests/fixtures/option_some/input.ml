let mk x = Some x
let get_or (o : int option) d = match o with Some x -> x | None -> d
let main () = get_or (mk 42) 0
