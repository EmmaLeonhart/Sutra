type Point = { x: int; y: int }

let bump () =
    let b = { x = 1; y = 8 }
    let q = { b with x = 9 }
    q.x + q.y

let main () =
    bump ()
