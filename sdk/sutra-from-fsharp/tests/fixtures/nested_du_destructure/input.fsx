type Inner = { v: int }
type Wrap = Wrap of Inner

let f (w: Wrap) =
    let (Wrap { v = vv }) = w
    vv + 1

let main () =
    let x = Wrap { v = 12 }
    f x
