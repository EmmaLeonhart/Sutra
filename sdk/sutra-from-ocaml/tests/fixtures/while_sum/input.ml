let main () =
  let i = ref 0 in
  let sum = ref 0 in
  while !i < 5 do
    sum := !sum + !i;
    i := !i + 1
  done;
  !sum
