# RAM pointers — `await ramRead` / `ramWrite`, the orchestrator, and the Neural-Turing-Machine direction

> **First cut, 2026-06-01 (Emma's design).** Sutra gets pointers to
> **RAM** (host memory), distinct from the VRAM the program normally
> runs on. The mechanism is a modified `await`: a RAM access is an
> **I/O device**, serviced by an **orchestrator** that bridges
> designated VRAM mailbox slots to host RAM. This is the first
> external producer Sutra wires in — `axon-io.md` specced the slot
> protocol and explicitly left "who writes the slot" as a Yantra-side
> question; the orchestrator is that producer.
>
> Captured in Emma's framing per the spec-README rule. Genuine design
> gaps (differentiable addressing, write-ack ordering, what "RAM"
> physically is) are open questions at the bottom, not papered over.

## Why — architectural diversification toward a Neural Turing Machine

Sutra already reaches Turing completeness through the recurrence of
its substrate loops (`recur` / non-halting loops are a substrate-RNN;
see `non-halting-loop.md`). RNN-recurrence is the right tool for many
purposes and Sutra continues to side with it. RAM pointers add a
**second** architecture: explicit, addressable, *external* memory
accessed through read/write heads — the defining capability of a
**Neural Turing Machine**. The goal is a *programmable* NTM that can
later be **trained to achieve goals**, not only hand-written.

This is a deliberate widening of Sutra's architectural surface. A
companion direction — **reservoir computing** — is named in the
roadmap but explicitly **deferred to the OS era** (it is materially
more complex and is expected to land with Yantra, not now). See
`todo.md` § "Architectural diversification".

## The shape of the surface

```sutra
number x = await ramRead(pointer);   // read RAM cell at `pointer` into x
ramWrite(pointer, data);             // write `data` to RAM cell at `pointer`
```

- `pointer` is a Sutra `number` (the first-class complex-hypervector
  number; see the complex-number design). Its decoded real part is a
  RAM address (an index into a flat host memory space).
- `ramRead(pointer)` is `await`-shaped: it returns a `Promise<number>`
  that the orchestrator fulfils. The `await` unwraps it to the
  `number` stored at that address.
- `ramWrite(pointer, data)` emits a write request. By Emma's framing it
  is "a formalisation of the output axon" — it naturally sits at the
  **end of a loop or program**, where the program's output axon
  already lives. It can also be its own loop ("its own loop thing").

## The orchestrator and the VRAM mailbox

The program runs on VRAM. RAM is external. Between the two sits the
**orchestrator** — a host-side device, exactly the producer role
`axon-io.md` deferred. The bridge is a set of **VRAM mailbox slots**
the program writes to and the orchestrator reads from (and vice
versa). The program never touches host RAM directly; it only ever
writes/reads VRAM slots.

The cycle for `await ramRead(pointer)`:

1. **Program → mailbox (substrate).** The program writes `pointer`
   into the **request slot** and sets a read-request flag. Both are
   vector writes on VRAM — substrate-pure.
2. **Spin (substrate).** The program enters the `await` gated loop:
   the eigenrotation heartbeat cycles while
   `!arrived(response_slot)` (the `norm(slot) > eps` /
   `AXIS_AXON_POPULATED` check from `axon-io.md`). Pending is active
   work, not silence (per `promises.md` § "Active heartbeat").
3. **Orchestrator services RAM (host I/O).** Each turn of the
   orchestrator's own loop it inspects the request slot. If a read is
   pending, it **decodes** the pointer vector to a host address
   (decode = monitoring, allowed at the I/O boundary), reads the host
   RAM cell, **encodes** the stored value as a `number` vector, and
   writes it into the response slot with the populated flag set
   (encode = producer-side slot write, allowed — same as any axon
   producer).
4. **Resolve (substrate).** The next iteration sees `arrived`, the
   loop exits, and `x` is the response-slot vector — used downstream
   as a `number`.

`ramWrite(pointer, data)` is the mirror: the program writes
`(pointer, data)` plus a write flag into the **write mailbox**; the
orchestrator decodes the pointer, takes the `data` vector, and stores
it in host RAM at that address. Default is fire-and-forget; an
optional write-ack slot lets the program `await` ordering (open
question 2).

### Mailbox representation — an Axon with named fields (Emma 2026-06-01)

The mailbox is an **Axon** with named fields — `req.add("ptr", pointer);
req.add("data", data);` on the program side, `axon_item(req, "ptr")` /
`axon_item(req, "data")` on the orchestrator side. This is the faithful
form of "a part of the VRAM that just has the pointer thing on it": each
field is its own addressable region of the state vector.

**Measured 2026-06-01 (do not re-derive the wrong conclusion):** an
axon carrying two `number` fields recovers them *cleanly* —
`a.add("ptr", make_real(7)); a.add("data", make_real(65))` then
`real(axon_item(a,"ptr")) == 7` and `real(axon_item(a,"data")) == 65`,
exact. The earlier worry that pure-`number` fields would superpose in
the synthetic block (because bind rotation is identity there) is **wrong
by measurement** — the axon machinery separates number-valued fields.
Build the axon mailbox; don't substitute a slot / `swap_ri` workaround.

**Dim-audit note:** `axon_add` currently embeds the field *key*
(`embed("ptr")`), so a program using the axon mailbox needs an embedding
model and runs at `runtime_dim = 768` — unlike the model-free read
scan / chase. That cost is for the keys, not the number payloads. A
model-free axon-key path (hash-seeded role rotations instead of embedded
keys) would drop the mailbox back to a tiny dim; flagged as an
optimisation / open question, not a blocker.

```
  ┌─────────── VRAM (substrate) ───────────┐        ┌─── host ───┐
  │  program: encode ptr → request slot    │        │            │
  │           spin await(!arrived(resp))    │◀──────▶│ orchestr.  │──▶ RAM
  │           x ← response slot             │  slots │ (producer) │◀── RAM
  └─────────────────────────────────────────┘        └────────────┘
```

## Surface-syntax lowering — what's settled, what's gated (2026-06-01)

`await ramRead(ptr)` and `ramWrite(ptr, data)` **already parse** (verified
2026-06-01): `await` is an existing keyword and `ramRead` / `ramWrite`
parse as ordinary function calls. No lexer/parser change is needed; the
remaining work is **codegen lowering**.

**The lowering target** (the pattern the `experiments/ntm_ram` demos
hand-code today, so it is understood, not speculative): inside a `recur`
(non-halting) function, `ramRead(ptr)` builds the request Axon
(`req.add("ptr", ptr)`) and emits it as the tick output; the orchestrator
services RAM and supplies the response as the next tick's input, which the
`await` binds. `ramWrite(ptr, data)` builds `Axon{ptr, data}` and emits it
as the request; the orchestrator performs the host write. The orchestrator
is always the external producer (RAM is I/O); the compiled program is
driven by its tick loop. This explicit `recur` + axon-mailbox form **works
today** (read scan/chase + write, all measured exact).

**What is gated.** The *inline* form Emma wrote —
`number x = await ramRead(pointer);` continuing mid-function with `x`
bound — requires splitting the function at the await point into
tick-resumable continuations. That is exactly the **async/await Stage-1
desugar** (`promises.md`; `.then()`-chain rewriting), which `todo.md`
records as only partially implemented (trivial shapes). So:

- Realizable **now**: the explicit `recur` + mailbox lowering (a desugar
  that recognizes `ramRead`/`ramWrite` and emits the demo pattern, for
  programs already shaped as a non-halting tick).
- **Gated** on the async Stage-1 desugar maturing: the inline
  `x = await ramRead(...)` mid-function form. Do not fake a continuation
  transform; build the explicit form first, then lift to inline once the
  async desugar handles non-trivial bodies.

## What runs where — the honesty line (read this before implementing)

This feature touches host memory, so the substrate boundary must be
explicit and correct. The rule is the same one `axon-io.md` already
draws for any external producer.

**On the substrate (VRAM), the program does all of:** encode the
pointer to a vector, write it to a slot, the `norm > eps` arrival
check, the eigenrotation heartbeat, read the response slot, use it as
a number. All tensor ops. No host scalar extraction *inside* an
operation; no Python control flow inside an operation.

**On the host, the orchestrator does:** the actual RAM read/write, and
the decode (pointer-vector → address) / encode (value → vector) at the
slot boundary. This is **I/O, not a Sutra operation.** We never claim
`ramRead` / `ramWrite` "run on the substrate" — they are the I/O
boundary, like reading a file or awaiting a socket. The decode/encode
are the same allowed compile/monitor operations every axon producer
performs.

**What would be a breach (do not do):** the pointer being a host
integer that never becomes a VRAM vector; the orchestrator doing
arithmetic the program then claims the substrate computed; collapsing
the await into a host `for`-loop branch inside an operation. The
pointer and the value must transit VRAM as vectors; the orchestrator
only moves bytes and translates representations at the wire.

**Substrate audits that ship with the first demo** (CLAUDE.md
§ "Subtler substrate breaches"):
- **Dim audit.** The RAM demos are model-free (no `basis_vector`),
  so `runtime_dim` is small (= the number layout width), not 768.
- **State-locus audit.** If a RAM-backed program is called "stateful"
  or "RNN-like," the recurring state must be a VRAM vector surviving
  across ticks (a `recurring` slot), not a host variable. The RAM
  cell is *external* memory, deliberately host-side — that is the
  point of the NTM framing — but any *internal* state still obeys the
  state-locus rule.
- **Signal-separation audit.** If a RAM-backed program decides
  anything (e.g. "is this cell a terminator?"), it ships a measured
  `gap = min(positive) − max(negative)`.

## Relationship to existing primitives

| Primitive | Role here |
|---|---|
| `await` / `Promise` (`promises.md`) | `ramRead` is an `await` whose producer is the orchestrator. Lowers to the same gated `while_loop`. |
| Axon I/O slots (`axon-io.md`) | The mailbox slots are axon slots; arrival is the same `AXIS_AXON_POPULATED` / `norm > eps` check. |
| Output axon / `recur` (`non-halting-loop.md`) | `ramWrite` formalises the output axon at end-of-loop/program; a RAM-driven loop can be a non-halting `recur` loop. |
| Canonical layout (`AXIS_*`) | Reuse `AXIS_AXON_POPULATED=7` for arrival; mailbox payloads live in semantic/`SLOT_BASE` slots. A dedicated request/response flag axis may be added if reuse collides. |

## The experiment Emma wants

Build a program that **reads text from RAM and displays it**, then
compare it against the earlier substrate-RNN text-generation demo. One
generates text from internal recurrence; the other retrieves it from
external addressable memory. Same observable task (emit a string), two
architectures — the concrete payoff of the diversification.

## Open questions (genuine gaps — do not paper over)

1. **Differentiable / soft addressing — RESOLVED (Emma 2026-06-01): RAM
   is NOT differentiable.** I/O is outside the differentiable realm.
   Because RAM is accessed through a read/write head and RAM is
   inherently discrete, the address is **hard**: a pointer that lands
   between two memory locations **rounds to the nearest** one. There is
   no soft attention / weighted-sum-over-cells read. A *trainable* NTM
   trains its **controller** (the substrate program that computes
   pointers and consumes values); the RAM access itself stays discrete
   round-to-nearest I/O — it is not part of the differentiable graph,
   the same way reading a file or awaiting a socket is not. The current
   orchestrator already implements this exactly: `addr =
   int(round(real(pointer)))`. Further RAM design work (what the
   trainable controller needs, write-head training signals) is tracked
   in `todo.md` § "Architectural diversification", but the
   differentiability question is closed: no soft addressing.
2. **Write-ack / ordering.** Is `ramWrite` fire-and-forget, or does it
   return a `Promise<void>` the program can `await` to order a
   subsequent read after the write lands? First cut: fire-and-forget;
   ack-await is an opt-in slot. Needs Emma's call before it is load-
   bearing.
3. **What "RAM" physically is.** First cut: a flat host buffer
   (bytearray / tensor / dict) the orchestrator owns, addressed by
   integer index. Whether this later maps to real OS pages, a Yantra
   storage tier, or a device file is a Yantra-side question.
4. **Address space & bounds.** Address range, out-of-bounds behaviour
   (Sutra has "no runtime errors by mechanism" — an OOB read should
   return a semantically-meaningless-but-valid vector, e.g. the zero
   vector, not raise). Confirm against `equality-and-defuzzification`.
5. **Value width.** A RAM cell stores one `number` vector. Storing a
   whole string/axon per cell vs. one number per cell (string = array
   of cells) — first cut: one number per cell, strings span cells.

## Cross-refs

- `planning/sutra-spec/promises.md` — the `await` → `Promise` →
  `while_loop` lowering `ramRead` reuses.
- `planning/sutra-spec/axon-io.md` — the slot protocol, arrival check,
  and the producer boundary the orchestrator fills.
- `planning/sutra-spec/non-halting-loop.md` — `recur` / output-axon,
  which `ramWrite` formalises.
- `todo.md` § "Architectural diversification" — NTM (this, active) and
  reservoir computing (deferred to the OS era).
