# Can we play Doom on the fly brain?

*A gap analysis, grounded in the specs in `STATUS.md` and
`../fly-brain-paper/paper.md`. Written as a "showing off" piece: the point isn't
that Doom is close, it's that the blockers are nameable and the
naming itself is interesting.*

## The short version

Doom itself is far. But the *minimum viable game on a fly brain* is
Pong, and Pong is only a handful of research problems away. The
memory question — which is the first thing everyone asks — turns out
to be a red herring once you separate game logic from rendering.

## Current substrate (from STATUS.md)

- **2,071 neurons total** in the MB subset: 50 PNs → 2000 KCs → 1 APL → 20 MBONs
- **~100 active KCs per `snap`** (5% APL-enforced sparsity) — the working "register"
- **~0.5s per `snap`** wall clock (Brian2 LIF spiking simulation)
- **4-way prototype argmax** is the biggest decision we've cleanly discriminated
- **Conditionals only.** No loops yet. STATUS.md long-term question 3 flags this.
- **Only `snap` runs on the brain.** bind/unbind/bundle are numpy. "Running on the fly
  brain" today means "running the cleanup step on the fly brain."

## Doom's actual footprint

- **Total RAM target:** 4 MB (1993 minimum spec)
- **Framebuffer:** 320×200×1 byte = **64 KB** (VGA Mode 13h, 8-bit palettized)
- **WAD** (levels, textures, sprites, sounds): ~10–12 MB, paged from disk, not resident
- **Mutable game state** (player pos/angle/health/ammo, enemy positions, projectiles,
  door states): realistically **a few KB**. Call it 2–10 KB
- **Inner loop:** ~10 MIPS on a 386DX/66, 35 Hz game tick

That "a few KB" is the number that matters. Doom's brain state — everything that
*changes* tick to tick — is tiny. The 4 MB is mostly static assets (textures, level
geometry, sound samples) loaded once and treated read-only thereafter.

## Memory capacity of a VSA substrate

VSA capacity isn't "1 bit per neuron." It's associative memory capacity, roughly
`d / log(d)` distinguishable items in a `d`-dimensional hypervector before collisions
dominate.

| Substrate | Dim | Rough item capacity |
|---|---|---|
| Current MB subset | 2,000 | ~200–300 distinct prototypes |
| Full FlyWire adult *D. mel.* | ~140,000 | ~10,000–15,000 distinct prototypes |

Static data (level geometry, sprite tables, texture IDs) can be *compiled in* as
prototype tables — same trick as `permutation_conditional.py`, just bigger. Those
don't eat runtime state budget at all.

## So memory is... not the problem?

Right. If you:

1. Offload rendering to the host (brain is CPU, laptop display is GPU)
2. Compile level geometry + sprite data as prototype tables at build time
3. Keep only mutable game state in hypervector form

…then you need maybe a few KB of live state, which fits comfortably even in the
current 2000-KC model and fits with room to spare on FlyWire. The 64 KB framebuffer
was the wrong thing to compare against — that's the GPU's problem, not the CPU's.

The more interesting framing is: **"the brain is the CPU, your laptop is the GPU."**
Once you frame it that way, the memory question goes away and the actually-hard
research problems surface.

## The real binding constraints

In priority order, these are the gaps between "conditional compiles to MB" (which we
have) and "full game loop runs on MB" (which we want):

### 1. No loops

STATUS.md long-term question 3. A `while` compilation path on the MB probably needs
recurrent KC→KC connections that the current circuit doesn't have. Without loops you
can't express a game tick. This is the first hard blocker.

### 2. No arithmetic on the substrate

From ../fly-brain-paper/paper.md and the §3 caveat in STATUS.md: the MB does random projection, not
sign-flip multiplication. Bind/unbind/bundle run in numpy, not on the brain. Anything
involving real numbers — raycasting, fixed-point trig, integer position updates —
isn't on the substrate at all. Doom's inner loop is arithmetic all the way down.

### 3. No compilation path for general boolean composition

Permutation-keyed `!` works because it's an involution that distributes over bind
(STATUS.md Technical Insight §1, LT-Q1). General `a && b` / `a || !b` don't have the
same algebraic structure. Either there's a more general VSA compilation scheme nobody
has found yet, or conditionals on the brain are fundamentally limited to what
permutation keys can express. Finding out which would be a real result on its own.

### 4. Throughput

0.5s per `snap` × many snaps per tick × 35 ticks/s. Even at one snap per frame the
current runtime is ~17× too slow for Doom's target frame rate. Parallelizing snaps
across independent queries would help, but it doesn't exist today.

## Revised game-by-game table

| Game | Loop needed? | Arithmetic? | Boolean composition? | Throughput? | State fits? |
|---|---|---|---|---|---|
| Pong | yes | 1D integer position | minimal | ~10 Hz might work | trivially |
| Doom, logic only (host renders) | yes | fixed-point + trig | heavy | hard | probably |
| Doom, brain renders framebuffer | yes | heavy | heavy | impossible today | 64 KB > capacity |

## Milestone ladder

Ordered from "next session" to "PhD thesis":

| Milestone | Status |
|---|---|
| Compile a 4-way `if/else` to brain | **Done** (Demo 2, `permutation_conditional.py`) |
| Compile `&&` / `\|\|` | Open research question |
| Compile a `while` loop | Needs new MB circuit (recurrent KC→KC) |
| Run on full FlyWire (~140k neurons) | Nobody's done it for any VSA runtime |
| Hit ~10 Hz snap throughput | Parallelize snaps, or smaller circuit |
| **Pong** — 1 paddle decision, 1D state, tick loop | **Realistic "game on a fly brain" target** |
| Doom, logic-only with host rendering | Needs arithmetic compilation. Open |
| Doom, brain-rendered | Needs all of the above plus framebuffer state |

## The showing-off pitch

> The minimum viable "game on a fly brain" demo is Pong, and the blocker list is
> short enough to name: we need a loop compilation path, one-dimensional integer
> position on the substrate, and roughly 10 Hz throughput. Doom itself is five or
> six research problems further out, and two of them — general boolean compilation
> and arithmetic on the mushroom body — are currently posed as open questions with
> no known solution. The interesting reframe is that memory was never the
> bottleneck: Doom's mutable game state is a few KB, which fits inside a single
> FlyWire-sized hypervector with room to spare. The brain is the CPU; the laptop is
> the GPU; the hard parts are control flow and arithmetic, not capacity.

## See also

- `STATUS.md` — full state of the fly-brain runtime, including the long-term research
  questions this document leans on
- `../fly-brain-paper/paper.md` — circuit parameters, VSA↔MB structural mapping
- `DEMO.md` — the two working demos (programmer agency + compile-to-brain)
