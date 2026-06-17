type Shape = Circle of int | Square of int

let radius (s: Shape) =
    let (Circle r) = s
    r + 1

let main () =
    let c = Circle 12
    radius c
