let main () =
  let r = ref 0 in
  r := !r + 5;
  r := !r + 10;
  !r
