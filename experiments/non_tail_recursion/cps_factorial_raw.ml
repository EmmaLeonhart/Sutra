(* RAW non-tail factorial — the thing CPS fixes. The recursive call sits inside
   `n * _`, so there is pending work on the stack. Sutra's if/then/else is a defuzz
   BLEND (both branches evaluated, no call stack), so this never halts on the
   substrate — the OCaml frontend correctly lowers it to UNSUPPORTED. Compare with
   cps_factorial.ml, the CPS/accumulator rewrite that DOES run. *)
let rec fact n = if n = 0 then 1 else n * fact (n - 1)

let main () = fact 5
