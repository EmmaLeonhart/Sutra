type Pt = { a: int; pos: int * int }

let g (r: Pt) =
    let { a = aa; pos = (x, y) } = r
    aa + x + y

let main () =
    let r = { a = 5; pos = (8, 3) }
    g r
