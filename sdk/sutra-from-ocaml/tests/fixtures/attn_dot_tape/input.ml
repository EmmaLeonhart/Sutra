(* Attention-on-RAM, linear regime with a constructed query = coefficients:
   out = sum_i coeffs_i * tape_i  — linear regression over memory (y_hat = w . x).
   Tape and coefficient vector live in RAM arrays; the running weighted aggregate
   is held in a RAM cell (`acc`).  acc is in RAM, not a `ref`, for the same reason
   as attn_sum_tape (scalar loop slot can't hold a vector RAM read; O2). The loop
   carries only the scalar index `i`.

   Cross-language oracle: reference.py dot_tape([1;2;3], [1;0;-1]) = -2. *)
let main () =
  let tape = Array.make 3 0 in
  let w = Array.make 3 0 in
  let acc = Array.make 1 0 in
  tape.(0) <- 1;
  tape.(1) <- 2;
  tape.(2) <- 3;
  w.(0) <- 1;
  w.(1) <- 0;
  w.(2) <- (-1);
  acc.(0) <- 0;
  let i = ref 0 in
  while !i < 3 do
    acc.(0) <- acc.(0) + (w.(!i) * tape.(!i));
    i := !i + 1
  done;
  acc.(0)
