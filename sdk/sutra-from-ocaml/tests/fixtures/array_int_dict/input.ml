(* Ordinary (straight-line) OCaml arrays -> per-instance dict<int,int> int-dict
   (Emma 2026-06-13). No while-loop access, so each Array.make is its own exact
   int-dict object (not the global RAM device — that's for the loop-carried
   vector accumulators in the attention-on-RAM parsers). *)
let f i v =
  let a = Array.make 8 0 in
  a.(i) <- v;
  a.(i)

let h x y =
  let a = Array.make 8 0 in
  a.(2) <- x;
  a.(5) <- y;
  a.(2) + a.(5)

let main () = f 3 42 + h 10 20
