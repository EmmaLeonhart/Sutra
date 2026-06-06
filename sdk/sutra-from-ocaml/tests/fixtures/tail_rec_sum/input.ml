let rec sum_to acc n = if n = 0 then acc else sum_to (acc + n) (n - 1)
let main () = sum_to 0 5
