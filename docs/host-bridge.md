# Input and output

I/O is central to Sutra, not an afterthought — but it happens at **four structural
points**, never as imperative statements scattered through a function body. The four
points are the boundaries of the program and of its loops:

1. **Beginning of the program**
2. **Beginning of a loop**
3. **End of a loop**
4. **End of the program**

Everything in between is **one synchronous, all-at-once neural-network evaluation** —
massively concurrent and purely functional, with no sequential "middle" to step into. That
is *why* I/O lives only at the edges: there is no mid-computation moment to read from or
print at. The boundaries are the only places where a before-and-after exists.

## How a value crosses the boundary: axons

An input or output is an **axon** — a vector slot the program shares with the outside.
A slot starts as the **zero vector** and becomes non-zero when a value arrives. The
substrate-pure way to ask "has it arrived?" is one tensor reduction:

```
arrived = norm(slot) > eps
```

No flag, no out-of-band metadata, no host polling — the *content* of the slot answers the
question. (A value that is genuinely the zero vector sets a dedicated populated-flag axis
so it can still read as "arrived.")

- **Inputs** are slots something outside the program writes *into* before or during the
  run: top-level axon parameters written at program start, or a slot a loop waits on.
- **Outputs** are slots the program writes and something outside reads: a loop's
  per-iteration events, a loop's resolved value, and the program's overall result at the
  end. An output is just an axon with the wire pointing the other way.

## `await` is a loop

There is no separate async machinery. **`await` is a loop in disguise**: it compiles to a
loop that spins on `norm(input_slot) > eps` — pending while the slot is still zero, and
exiting the moment an external producer writes the awaited value. That value is then sitting
in the slot for the code after the loop to use. This is why "beginning/end of a loop" are
I/O points: that is where awaited inputs arrive and resolved values leave.

## Who writes the slot

From the program's view, a slot just starts at zero and at some point becomes non-zero —
it never sees the producer. *What* writes it (an OS device wrapper, a network socket, a
user-input event loop) is a host-side concern handled by the Sutra-for-Windows layer, which
keeps programs portable across substrates.

## Why there's no `print` in the middle

You cannot drop a `print(x)` halfway through a function, and you cannot pull a scalar off a
vector mid-operation (`.real()`-style) to branch or log on it. This is not a ban on I/O —
it falls straight out of how the program runs. Because the whole thing evaluates **all at
once, synchronously, as one highly-concurrent neural network**, there is no point "in the
middle" where execution has paused and a value is sitting still to be read or printed. The
program is one differentiable tensor graph; reads and writes only make sense at its
boundaries. So I/O is structured at the four edges — never smeared through the computation.
(If a program *could* read or print mid-computation, the all-at-once execution would be
broken; that's the bug to fix, not a feature.)

## See also

- [Promises and async/await](promises.md) — the loop that `await` lowers to.
- [Loops](loops.md) — the loop forms whose boundaries carry the I/O.
