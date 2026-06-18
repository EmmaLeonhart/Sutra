type Inner = { v: int }
type Outer = { a: int; inner: Inner }

let f (o: Outer) =
    let { a = aa; inner = { v = vv } } = o
    aa + vv

let main () =
    let i = { v = 8 }
    let o = { a = 5; inner = i }
    f o
