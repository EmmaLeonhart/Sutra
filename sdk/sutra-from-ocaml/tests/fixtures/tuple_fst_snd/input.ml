let pair a b = (a, b)
let sum2 (t : int * int) = fst t + snd t
let main () = sum2 (pair 7 9)
