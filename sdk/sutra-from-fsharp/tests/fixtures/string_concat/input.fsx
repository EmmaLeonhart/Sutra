let cat (a: string) (b: string) = a + b
let f (s: string) = if s = "foobar" then 100 else 200
let main () = f (cat "foo" "bar")
