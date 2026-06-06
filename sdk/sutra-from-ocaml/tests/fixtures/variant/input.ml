type color = Red | Green | Blue
let label c = match c with Red -> 100 | Green -> 200 | Blue -> 300
let main () = label Green
