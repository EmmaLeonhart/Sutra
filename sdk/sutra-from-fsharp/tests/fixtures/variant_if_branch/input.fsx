type Dir = North | South

let pick (n: int) =
    if n > 0 then North else South

let code (d: Dir) =
    match d with
    | North -> 10
    | South -> 20

let main () =
    code (pick 5)
