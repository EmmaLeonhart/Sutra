let classify (s: string) = if s = "foo" then 10 else 20
let main () = classify "foo" + classify "bar"
