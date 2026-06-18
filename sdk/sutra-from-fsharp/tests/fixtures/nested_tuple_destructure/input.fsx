let f (t: int * (int * int)) =
    let (a, (b, c)) = t
    a + b + c

let main () =
    let p = (5, (8, 3))
    f p
