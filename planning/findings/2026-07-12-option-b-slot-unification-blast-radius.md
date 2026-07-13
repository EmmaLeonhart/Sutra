# Option B (unify all slots to d-dim): the core works, but the blast radius is multi-tick

Rung 3, Emma's Option B. A prototype was built and **measured working at the core**, then
**reverted to keep the tree green** because completing it cleanly is more than one tick and it
touches the paper-cited scalar path. This finding preserves the proof and the exact consumer map
so the next attempt is a bounded checklist, not a rediscovery.

## What was built (and reverted)

- **pytorch backend:** `_slot_state` from one `dim`-vector to a dict `{idx: dim-vector}`;
  `slot_state_new()` → `{}`; `slot_store` stores the FULL vector (`_slot_value` lifts a host
  scalar to a number-vector, passes an already-`dim`-vector — String/number-vector — through
  untouched, NO `make_real` projection that would collapse a String); `slot_load` returns the
  full `dim`-vector.
- **numpy backend (parity):** same dict container, but stores the value as-is (this backend keeps
  numbers as host scalars — no `num_*`), `slot_load` defaults to `0.0`; added a passthrough
  `_scalar`.
- **shared codegen_base:** the two `_slot_state = _VSA.zero_vector()` init sites →
  `slot_state_new()`; the iterative-loop count `int({count_src})` → `int(_VSA._scalar({count_src}))`
  (the count may now be a number-vector slot param).

## MEASURED — the core is correct

- Scalar `do_while_adder` (paper-cited): `slot int x = 9; loop addNumber(x<11, x); return x;` → **11.0**.
- **String state BY REFERENCE** (the whole point — was crushed, SUT0206 / finding 2026-07-08):
  `slot String acc = make_string(""); loop build(3, acc); return acc;` → **"xxx"**.
- 2-state by-reference scalar → 5.0.
- After the iterative-count fix, `test_implicit_loop_desugar.py` (torch + numpy) fully green.

## The blast radius (why it's multi-tick)

Making `slot_load` return a `dim`-vector instead of a 0-d scalar ripples into every consumer that
assumed 0-d:

1. **codegen scalar consumers** — the iterative-loop count `int(count_src)` (FIXED via `_scalar`).
   Likely siblings not yet audited: the `foreach_loop` length/`_length` path and the tail-call
   return surface (`TestReturnTailCallSurface` failed). Each needs the same `_scalar`/`_re`
   projection at the host-count boundary.
2. **test harnesses** — ~22 tests in `test_loop_function_decl.py` do `float(main())`; a `slot int`
   return now yields a number-vector (value on AXIS_REAL), so `float()` raises "only one element
   tensors can be converted." The VALUES are correct (they decode to the right number via `_re`),
   exactly as the language already went "numbers are number-vectors" elsewhere — but each harness
   read must move to `_re` and be re-verified against ground truth (NOT blindly, per the rails).

Full pre-revert state: 251 passed, 22 failed (all the two classes above), across the broad
slot-touching sweep.

## Re-scoped plan (bounded sub-rungs, do in order; each ends green)

- **B1a** — audit + fix every codegen scalar consumer of a slot value (iterative count [done in
  prototype], foreach length, tail-call return, any while-cond scalar read) to project via
  `_scalar`/`_re`. Land this FIRST, while slots are still scalar 0-d, so it's a no-op safety net
  that keeps the suite green.
- **B1b** — update the `test_loop_function_decl.py` harnesses (and any other `float(main())` on a
  slot return) to decode via `_re`, verifying each value against ground truth. Green.
- **B1c** — flip the representation (the pytorch dict + `_slot_value` + numpy parity + the two
  init sites). Now every consumer is ready; the suite stays green.
- **B3** — full re-verify (do_while_adder + all scalar-slot programs + the String-by-ref test).
- **B5** — retire the SUT0206 crush; keep `do_while.su` working by reference.

The hard part — proving the core works and mapping the consumers — is done. The remaining work is
mechanical and ordered; it was staged rather than force-landed because the paper-cited scalar path
must not go red mid-flight.
