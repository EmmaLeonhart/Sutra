type Pt = { x: int; y: int }

let f (t: int * Pt) =
    let (a, { x = b; y = c }) = t
    a + b + c

let main () =
    let p = { x = 8; y = 3 }
    f (5, p)
