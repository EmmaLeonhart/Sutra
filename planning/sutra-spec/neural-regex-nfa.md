# Neural regex — the on-substrate NFA matcher (prerequisite P2 for the neural Unix utilities)

> **Design note, 2026-07-06.** The neural-Unix track (`queue.md` § "NEURAL UNIX
> UTILITIES") reaches its first matcher-hungry rung at regex `grep`/`sed`. Fixed-string
> `grep` shipped without any of this — containment is a sliding-window PRODUCT of exact
> codepoint indicators (`experiments/ntm_ram/grep_head.su`), no state machine needed.
> Regex needs more: a pattern compiled to a state machine that runs over the stream. This
> spec is the design for that machine — prerequisite **P2** in the queue. Nothing here is
> built yet; it is the target the next rung implements, written first per the queue's
> "spec it in `planning/sutra-spec/` before building" instruction.

## Why an NFA, and why on the substrate

A regex is a finite automaton. The classic, robust route is **Thompson construction**:
compile the pattern to a nondeterministic finite automaton (NFA), then simulate the NFA
over the input by tracking the SET of states it could be in after each character. That set
never needs backtracking, so matching is linear in the input length — the property that
makes `grep` fast and predictable.

Where it runs (the honesty line, mirroring `ram-pointers.md`):

- **Compiling the regex to an NFA is COMPILATION** — parsing the pattern, Thompson
  construction, numbering states, building the per-symbol transition tables. This is host
  work, and legitimately so (CLAUDE.md § "Numpy: compile and monitor only" — building
  codebooks / fused matrices / tables happens before the run). The pattern is fixed at
  invocation, exactly like `tr`'s codebook or `cut`'s ranges, which are already baked into
  a generated `.su`.
- **Simulating the NFA over the stream runs on the SUBSTRATE.** The active-state SET is a
  vector; each input character advances it by a substrate operation. This is the "argmax-
  attention state machine over the stream" the queue names, and it is where the genuine
  neural work is — the same division as every shipped rung (substrate decides, host does
  the I/O of feeding the next byte).

## Representation

- **State-set vector `s`** — an `N`-dimensional 0/1 vector over the NFA's `N` states
  (`s[q] = 1` iff state `q` is currently active). Unlike the scalar-accumulator rungs
  (wc/head/tr/…), this needs `N` independent components, so the matcher compiles with
  `runtime_dim >= N` and the state lives across `N` axes, not just the real axis. This is
  the first rung that uses a genuinely vector-valued substrate state — the reason P2 is its
  own prerequisite and not a variation on the accumulator heads.
- **Per-symbol transition matrices `T_c`** — for each input character `c`, an `N x N` 0/1
  matrix where `T_c[q', q] = 1` iff there is a `c`-labelled edge `q -> q'`. Built at compile
  time from the NFA. A character class (`.`, `[a-z]`, `[^0-9]`) contributes to `T_c` for
  every `c` in the class; the class-membership test at RUN time is the exact-indicator /
  range machinery already proven in `cut`/`tr` (`ge1(c-lo+1) * ge1(hi-c+1)`, `is_cp`).
- **Epsilon-closure matrix `E`** — the reflexive-transitive closure of the epsilon edges
  (from `*`/`+`/`?`/`|`), precomputed at compile time as an `N x N` 0/1 matrix. Applying
  `E` adds every state reachable by epsilon moves.

## Stepping (the substrate operation)

One input character advances the state set by:

```
s' = clamp01( E @ ( T_c @ s ) )
```

- `T_c @ s` — a substrate matmul: fire every `c`-labelled edge out of an active state.
- `E @ (...)` — take the epsilon-closure of the result.
- `clamp01(x) = ge1(x)` element-wise — collapse "reached by >=1 path" back to a 0/1
  indicator (the NFA cares about REACHABILITY, not path count), reusing the exact integer
  `ge1` step so no residual accumulates over a long input.

`T_c` itself is assembled on the substrate per character from the compiled class structure:
`T_c = Σ_over_classes (class_membership(c) * M_class)`, where `class_membership(c)` is the
exact 0/1 indicator that `c` is in that class and `M_class` is that class's compile-time
edge matrix. So the only per-character host input is the raw codepoint `c`; the matrix is
selected on the substrate.

**Match test.** Seed `s0 = E @ e_start` (epsilon-closure of the start state). After the last
character, the pattern MATCHES iff any accept state is active: `is_true(accept · s) `, i.e. a
substrate dot of the accept-state indicator with `s`, thresholded by `ge1`. For `grep`
(search, not full-match) the NFA is compiled with an implicit `.*` prefix and the accept
test is applied after every character, so a match anywhere in the line fires.

## Scope for the first cut

Implement the subset that covers the bulk of real `grep -E` usage, verified against Python
`re` and coreutils `grep -E` on that subset:

- literals, `.` (any char), character classes `[...]` / `[^...]` / ranges,
- quantifiers `*`, `+`, `?`,
- alternation `|`, grouping `( )`,
- anchors `^` and `$`.

Deferred (named, not silently dropped): backreferences (not regular — out of scope for an
NFA), bounded repeats `{m,n}` (desugar to concatenation at compile time — cheap follow-on),
lazy quantifiers, and Unicode class shorthands.

## Downstream

- `grep` (regex): run the matcher per line with the `.*`-prefixed search NFA; emit lines
  that reach an accept state. Reuses the line plumbing from fixed-string `grep`.
- `sed s/re/repl/`: matcher locates the span (track the start position of the accepting
  path); the substitution is a codebook splice (the `tr` codebook pattern generalised to a
  span replace).
- `awk`: a whole language — the Sutra compiler itself is the engine, not this matcher. Far
  out; listed for order only.

## Open questions

1. **Match-span extraction.** The accept test above answers YES/NO. `sed` needs the matched
   SPAN (start, end). Standard route: a parallel "start position" carried on the winning
   path (a second vector tracking the earliest start that reached each active state). Adds a
   second N-vector; needs its own design pass before `sed`.
2. **Dim cost.** `runtime_dim >= N` makes the state vector honest but the NFA can have many
   states for a big pattern. Measure `N` for representative patterns; if the matmul cost is
   real, a sparse/segmented state representation is the follow-on (dim-audit rule applies —
   don't silently run a 768-dim machine for a 12-state NFA).
3. **Leftmost-longest.** POSIX `grep`/`sed` want leftmost-longest matches; the plain
   reachability NFA gives "matches somewhere". Longest-match needs the span tracking of (1)
   plus a max over accepting positions — design alongside `sed`.
