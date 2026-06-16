type Point = { x: int; y: int }

let sum (p: Point) =
    let { x = a; y = b } = p
    a + b

let main () =
    let p = { x = 5; y = 8 }
    sum p
