let classify (s : string) = match s with "foo" -> 10 | "bar" -> 20 | _ -> 30
let main () = classify "foo" + classify "bar" + classify "baz"
