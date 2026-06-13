let classify n =
    match n with
    | 0 -> 100
    | x -> x * 10

let main () = (classify 0) + (classify 6)
