# Non-halting loop / `recur` primitive (Emma 2026-05-28)

> **VERDICT — RESOLVED 2026-05-28** by `planning/sutra-spec/non-halting-loop.md` (all five sub-decisions locked Emma 2026-05-28; v1 primitive shipped in `6757863d` + `6fc64c15`). Emma's verbatim explanation is preserved below as the original design intent; the canonical implementation surface is the spec doc.

**Opened:** 2026-05-28 during the demos/gui substrate-RNN rewrite (queue.md State Inventory B item D.5, Emma sweep Q5). The rewrite turned out to be larger than a code change — Emma's description of the target shape is a new language-level primitive Sutra does not currently have.

**Status:** RESOLVED 2026-05-28 by `planning/sutra-spec/non-halting-loop.md`. The five sub-decisions (function signature, initial state, caller surface, axon interaction, halt-vs-non-halt distinction) all landed via Emma's `AskUserQuestion` sweep on 2026-05-28; the spec doc is canonical and supersedes this dossier; the v1 implementation shipped same day. This file is kept for the verbatim design intent below.

## Emma's explanation (verbatim, 2026-05-28)

> Basically the way that our things work is essentially like the hidden state just kind of repeats whatever information goes through it and it sends it down. I don't know what that makes. I don't know if that makes sense.
>
> All I will say is that it's not just for the typing one. All it does is it just sends the character, which then basically becomes an integer as the input to this function. Whatever character is being displayed on the screen, because it goes into the loop, the loop is constantly shooting down the pixels and recurring.
>
> I feel like this one might actually be an example of how we're supposed to have two different types of loop in this: **the halting loop and the non-halting loop**. This is an example of a non-halting loop. I guess I might even say it would be better, I guess I might even say this might challenge a bit of the structure of the programme, as I don't think it is necessary. I think that you could do it as just an axon that connects a data point to another from the end to the beginning, and at which point that wouldn't be technically a loop even though it would be a loop. It's just because everything in Sutra is kind of a loop.
>
> This is a thing that we can do for stateful things that I think might actually be a bit of a better thing, a bit less wordy. Essentially there is one integer that's the input and then there is another integer that's the recurring integer and that's also the input. The input then replaces the recurring integer. If the input exists and it's not 0 then it first multiplies the recurrent integer by 0 and then it adds the new integer in. It adds in this integer that was the input. Once that's finished the entire rest of the programme logic is basically based upon the multiplication related to the switch statement. It then generates the array of pixels that display on the screen and it also just returns the recurrent integer. In this case I think we might make it again, like we might need to turn this into something of a programming language primitive because it's not technically being returned by the function. It's just being recurred by the function. Maybe it would be like
>
> ```
> recur(state);
> return(pixels);
> ```
>
> Yeah I think this is well in line with everything that's established in the programme but it is potentially a thing where the most elegant way to do it is actually a bit difficult. It still is fundamentally completely substrate.

## What this means in spec language

1. **Two loop types in Sutra:**
   - **Halting loop** — what Sutra currently has. Bounded iteration; halt signal saturates; terminates with a final state. Used for `for/while`-like work.
   - **Non-halting loop** — NEW. Runs indefinitely; on each tick, takes an external input (the *current* input), advances a recurring state on the substrate, and emits a per-tick output. Never terminates by mechanism; terminates only when the host shuts the program down.

2. **Two return-shaped statements inside a non-halting loop:**
   - `recur(state_expr)` — what gets fed back into the next tick's state. Substrate-resident; not extracted to the host.
   - `return(output_expr)` — what gets emitted to the caller this tick (the pixels for a render, the display value, etc.).

3. **Update rule per tick (Emma's worked example for the font/counter case):**
   - There is one "external input" integer (e.g. the char code typed this tick, or 0 if no typing).
   - There is one "recurring" integer (the previously emitted state).
   - The update: `if input != 0 then recur_state := 0 * recur_state + input else recur_state := recur_state` (the multiply-by-0-then-add structure she described — a substrate-pure conditional select via the switch-statement / Kleene polynomial form).
   - The rest of the program logic computes the pixel array from `recur_state` and emits it.

4. **Substrate posture:**
   - State lives on the substrate as a vector across ticks (CLAUDE.md "Subtler substrate breaches" #2 satisfied — the recurrence is substrate-resident, not host-shuttle).
   - Substrate-pure: the recur update + the output computation are all tensor ops.

5. **Axon-only alternative Emma mentioned:**
   > *"you could do it as just an axon that connects a data point to another from the end to the beginning"* — i.e., an axon explicitly wires the function's output back into its input. That's strictly less new-syntax (no `recur`/`return` split), but the connection has to be explicit at the call site, which is more wordy. Emma's leaning toward the `recur`/`return` primitive as the cleaner surface.

## What needs to be decided to ship this

The dossier-style options below are what need Emma-input via `AskUserQuestion` once this open-question doc settles. NOT being silently picked here.

**Open sub-decisions:**

a. **Function signature.** Does a non-halting-loop function declare itself with a keyword (`recurring function ...`)? Or is the presence of `recur(...)` syntax sufficient? Or does it live under a `loop` keyword at the function/module level?

b. **Initial state.** Where does the non-halting loop's state start? An explicit `init` clause? The first call's input? A `make_real(0.0)` default?

c. **Caller surface.** How does the host invoke a non-halting-loop function? `mod.count.tick(input_value)` returning the per-tick output? Or does the host hold a handle that internally pumps the recur?

d. **Interaction with axons.** If axons can also wire output→input, does this primitive subsume axons for this case, or do they coexist (axon = explicit cross-program wiring; `recur` = within-function wiring)?

e. **Halt-loop vs non-halt-loop syntactic distinction.** Two `loop` keywords? Same keyword with different body shapes? A separate keyword entirely (e.g. `recur` makes the whole function a non-halting loop)?

## Why this is parked (not built today)

Per CLAUDE.md HARD RAILS "Don't implement what you don't 100% understand — write the spec/queue item instead": the design is a real language extension. The right move is the planning doc now, sub-decisions to Emma via `AskUserQuestion`, then spec + implementation.

Per CLAUDE.md "When Emma gives an algorithmic explanation, IMPLEMENT it": *that rule applies once the algorithm is fully specified*. Emma's explanation above is dense and rich but leaves implementation-level choices open (a–e above). Implementing my guess at those choices would be exactly the failure mode the "never invent" rule (`feedback-never-invent-thing-emma-implies-exists`) warns against.

## Cross-refs

- `queue.md` State Inventory B item D.5 (Emma sweep Q5).
- `planning/findings/2026-05-28-demos-gui-substrate-audit.md` — the PARTIAL state-locus audit that motivated the rewrite.
- `CLAUDE.md` §"Subtler substrate breaches" #2 — the host-state-shuttle rule this primitive resolves.
- `paper/formal-verification/paper.md` §3.3 — the existing (halting) loop's termination obligation; the non-halting loop will need its own obligation family (not termination — by definition non-halting — but something like "the recur update is substrate-pure" + "the output emission is substrate-pure").
- Memory: `feedback-never-invent-thing-emma-implies-exists` (one of the most critical rules).
- Memory: `feedback-gui-stateful-must-be-substrate-rnn-not-host-shuttle`.
