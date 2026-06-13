let rec sumTo acc n =
    if n = 0 then acc
    else sumTo (acc + n) (n - 1)

let main () = sumTo 0 5
