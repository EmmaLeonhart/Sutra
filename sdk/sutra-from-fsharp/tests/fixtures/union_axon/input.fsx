type Shape =
    | Circle of int
    | Square of int

let area (s: Shape) =
    match s with
    | Circle r -> r * r * 3
    | Square w -> w * w

let main () =
    let c = Circle 4
    area c
