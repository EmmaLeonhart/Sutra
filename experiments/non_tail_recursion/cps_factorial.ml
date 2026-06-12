(* CPS / accumulator form of factorial — approach 2 to non-tail recursion.
   The raw non-tail `fact n = n * fact (n-1)` has pending work (`n *`) on the call
   stack. CPS makes that pending work an accumulator carried forward, turning the
   recursion TAIL-recursive; the OCaml frontend then lowers it to a Sutra `while_loop`
   (the trampoline — a top-level loop that bounces the (n, acc) state until n = 0).
   The continuation is reified as `acc`. *)
let rec fact n acc = if n = 0 then acc else fact (n - 1) (acc * n)

let main () = fact 5 1   (* 5! = 120 *)
