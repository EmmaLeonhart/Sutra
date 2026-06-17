type Point = { x: int; y: int }
let bump (p: Point) =
    let q = { p with x = 9 }
    q.x + q.y
let main () =
    let b = { x = 1; y = 8 }
    bump b
