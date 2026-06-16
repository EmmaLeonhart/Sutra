type Point = { x: int; y: int }

let sum2 (p: Point) = p.x + p.y

let main () =
    let q = { x = 5; y = 8 }
    sum2 q
