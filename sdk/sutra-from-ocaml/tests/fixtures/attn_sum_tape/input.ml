(* Attention-on-RAM, linear (uniform-weight) regime = aggregate over the tape.
   Imperative rendering of one constructed attention head with query q = ones:
   out = sum_i scores_i * v_i = sum_i tape_i.  The tape lives in a RAM array; the
   running aggregate is held in a RAM cell (`acc`), updated each iteration.

   WHY acc lives in RAM, not in a `ref`: on the substrate the `while`->`loop`
   recurrence carries SCALAR slots, but a RAM read returns a number-VECTOR, so a
   `let acc = ref 0` accumulator can't hold `acc + tape.(i)` (scalar slot vs vector).
   Keeping acc in RAM (vector space) and carrying only the scalar index `i` as a
   loop slot is the substrate-correct shape — the same pattern the substrate
   mini_wasm_machine uses (accumulator in RAM, scalar control). See
   planning/findings/2026-06-08-attention-on-ram-substrate.md (open-Q O2).

   Cross-language oracle: reference.py sum_tape([1;2;3;4]) = 10. *)
let main () =
  let tape = Array.make 4 0 in
  let acc = Array.make 1 0 in
  tape.(0) <- 1;
  tape.(1) <- 2;
  tape.(2) <- 3;
  tape.(3) <- 4;
  acc.(0) <- 0;
  let i = ref 0 in
  while !i < 4 do
    acc.(0) <- acc.(0) + tape.(!i);
    i := !i + 1
  done;
  acc.(0)
