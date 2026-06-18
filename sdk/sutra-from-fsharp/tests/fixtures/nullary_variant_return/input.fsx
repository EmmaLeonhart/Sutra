type Dir = North | South

let getNorth () = North

let code (d: Dir) =
    match d with
    | North -> 10
    | South -> 20

let main () =
    code (getNorth ())
