(* Attention-on-RAM, hard location-addressing: out = tape[j] (single read).
   The math reference uses a hardmax over location scores to pick cell j; in
   imperative form that location-addressed read IS an indexed RAM read — which is
   exactly the point ("imperative RAM-editing programs representable in this form").
   Cross-language oracle: reference.py select_field([11;22;33], 1) = 22. *)
let main () =
  let tape = Array.make 3 0 in
  tape.(0) <- 11;
  tape.(1) <- 22;
  tape.(2) <- 33;
  let j = 1 in
  tape.(j)
