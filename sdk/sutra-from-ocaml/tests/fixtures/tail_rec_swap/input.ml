let rec swaploop a b n = if n = 0 then a else swaploop b a (n - 1)
let main () = swaploop 7 9 2
