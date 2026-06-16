let addPair (t: int * int) =
    let (a, b) = t
    a + b

let main () =
    let p = (5, 8)
    addPair p
