let test a b = if (a && b) || (not b) then 100 else 200
let main () = test true false
