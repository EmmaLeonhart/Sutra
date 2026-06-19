let cat (a : string) (b : string) = a ^ b
let classify (s : string) = if s = "foobar" then 100 else 200
let main () = classify (cat "foo" "bar")
