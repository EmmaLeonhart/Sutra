type inner = { v : int }
type wrap = Wrap of inner

let f (w : wrap) =
  let (Wrap { v }) = w in
  v + 1

let main () = f (Wrap { v = 12 })
