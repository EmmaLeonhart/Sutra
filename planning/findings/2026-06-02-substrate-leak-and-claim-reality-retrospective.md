# 2026-06-02 — Substrate leaks and claim-vs-reality failures: retrospective + prevention strategy

**What this is.** A synthesis across every substrate-purity leak and
claim-vs-evidence gap recorded in this repo, written to extract the
*recurring causes* rather than re-list the incidents, and to turn those
causes into a coherent set of controls. Sources are the dated findings in
`planning/findings/`, the running `Audit.md` catalogue, and the
CLAUDE.md integrity rules those incidents produced. Every incident below
is anchored to a finding or commit so the claims here are checkable, not
remembered.

This is a meta-document. It does not fix anything; it maps the failure
surface and proposes where the gates should be. Concrete follow-on gate
work belongs in `queue.md`/`todo.md`, not here.

---

## 1. The two things that actually went wrong

Strip the incidents down and there are exactly two failure *kinds*. Keep
them separate — they need different controls.

**Kind A — the substrate leak.** An operation labelled "runs on the
substrate" actually does host work: it extracts a Python scalar, branches
or loops on it in Python, calls host libm, or returns a Python `float`,
then (sometimes) wraps the result back in a tensor. The math may be
numerically right. The claim about *where it ran* is false.

**Kind B — the claim-vs-reality gap.** Prose (a code comment, a finding,
a paper sentence, a demo label) asserts something the artifact does not
do. The code may be fine; the *description* overshoots. "Trains through
the compiled graph" when no `.su` is in the loop. "Recurrent" when the
state lives in a Python variable. "Substrate-pure" written directly above
a `float()`.

Almost every incident is one of these two, and the worst ones are both at
once — a leak (Kind A) wearing a comment that asserts purity (Kind B).
That pairing is the canonical anti-pattern, and it is what opened
`Audit.md`.

---

## 2. Incident catalogue

| Date | Incident | Kind | Source |
|---|---|---|---|
| 2026-04-10 → 2026-05-10 | **Host Python strings** — string literals emitted as `repr(value)`, never crossing the substrate. Present since the original SDK scaffold; a 2026-04-30 workaround made `hello_world.su` *not crash* without encoding anything. | A | `2026-05-10-host-python-string-bug-chronology.md` |
| 2026-04-30 | **Five boundary-seam leaks** enumerated (loop halt check, slot load/store, rotation cache lookup, `array_get`, loop tick counter) — written specifically to stop the paper from claiming "no Python in the runtime." | A | `2026-04-30-substrate-purity-leak-enumeration.md` |
| 2026-05-15 | **Transcendental/modulus leak** — `exp/log/sin/cos/tan/sinh/cosh/tanh/pow/sqrt` + `fmod/rotation_mod/sawtooth_mod` all did `float(x)` → host `if`/`raise` → host-float return, with a code comment claiming *"substrate-pure … no Python control flow on x"*. The 2026-05-13 finding had asserted "substrate-pure / production path measured" against this exact code. | A+B | `2026-05-15-transcendental-substrate-leak-fixed.md`; opened `Audit.md` |
| 2026-05-18 | **§3.6 differentiable training** — paper said "autograd flows through the compiled graph end-to-end"; the experiment hand-reimplemented the primitives in plain PyTorch with no `.su` compiled. A deeper probe then found the *real* compiled `similarity` returned a Python `float`, so the compiled path could not be trained as emitted at all. | B (then A) | `2026-05-18-differentiable-training-is-a-proxy-not-compiled.md` |
| 2026-05-15 → 2026-05-28 | **Ten `Audit.md` REAL-LEAK entries** — Givens `rotate_slot` (host libm trig + scalar extraction *inside* the rotation loop), `defuzzify_trit`, promise-await loop, string ops as host codepoint loops, `select` zero-norm host branch, `slot_store`, `eq`/`eq_synthetic`, `_select_softmax`. All fixed; each carries its fixing commit inline. | A | `Audit.md` #1–#10 |
| 2026-05-28 | **Autograd-detachment subclass** (`eq`/`eq_synthetic` `make_truth(float(.item()))`; `_select_softmax` `as_tensor(list_of_grad_tensors)`) — numerically identical output, but `.item()`/`as_tensor` severed the autograd graph, so `.backward()` raised. Survived the leak-sweep because the sweep greps user `.su` output, not the runtime prelude where these lived. | A+B | `Audit.md` #9, #10; `2026-05-28-defuzz-gain-grad-fixed-eq-substrate-leak.md` |
| 2026-05-28 | **The three measurement-required breaches** (from the paused Yantra OS attempt) — shipped as "substrate-pure" for weeks: (1) `runtime_dim=768` with *zero* `basis_vector` calls → 96× cost paid silently; (2) `make_real(scalar)→host→real()` per tick labelled "RNN" when the recurrence lived in a Python variable; (3) a `font_bound` classifier whose lit/unlit cosines *overlapped* at every dimension — it returned a number but did not separate the classes. | A+B | CLAUDE.md §"Subtler substrate breaches"; FV paper §4.4 |
| 2026-05-28 | **GUI host-state-shuttle** — `count.su`/`toggle.su`/`font cycle_step` labelled "Emma's recurrent step." `count`/`toggle` rewritten to true substrate-RNN; `cycle_step` rewrite attempted, hit a wall, **reverted and recorded as blocked** rather than faked. | B (state-locus) | `2026-05-28-cycle-step-rewrite-blocked.md`, `…-font-cycle-step-substrate-rnn-shipped.md` |
| (various) | **`gui_window.su` invented toy** — Emma implied a thing existed; an agent invented a substitute instead of asking. Removed. | (process) | memory `feedback-never-invent-thing-emma-implies-exists` |

---

## 3. The recurring causes

These are the patterns underneath the catalogue. The same five keep
producing new incidents.

### C1 — "It ran / it didn't crash" stood in for "it ran on the substrate"

The host-string bug is the purest example: the 2026-04-30 workaround made
`hello_world.su` stop throwing a `TypeError` and the chain ended there. No
one asked whether the string was *encoded*; it wasn't. The finding's own
lesson: *"Doesn't crash is not the same as runs on the substrate."* This
is exactly what CLAUDE.md integrity rule #3 ("'It ran without errors' is
not success") is written against — the rule exists *because* this
happened.

### C2 — Prose asserting purity the code does not have

The transcendental leak shipped under a comment reading "substrate-pure …
no Python control flow on x" sitting directly above `float(x)` and a host
`if`. A *finding* then certified it ("substrate-pure / production path
measured"). The comment and the finding actively misled the next
reviewer — they read as evidence and were the opposite. Aspirational
documentation written ahead of the code, never reconciled, is worse than
no documentation.

### C3 — Withdrawn shortcuts silently reintroduced

The host-scalar-arithmetic pattern in the transcendentals was the
2026-04-29 "host scalar arithmetic" mistake that was *supposedly
withdrawn*, then silently reintroduced 2026-05-10 and re-described as
pure. This is the vibe-coded-repo failure CLAUDE.md §"Vibe-coded projects
need legacy code removed" names directly: a retired-but-not-deleted path
gets re-wired by a later session that doesn't know it was retired. The
host-string bug is the same shape at the architectural level — the
original codegen *never had* a concept of substrate strings, and that gap
persisted for a month because nothing forced it shut.

### C4 — Spec/code drift with no test spanning them

`strings.md` (2026-05-08) said strings are constructor-explicit; the
implementation stayed silent; no test exercised a function returning a
string literal, so the divergence was invisible. The §3.6 paper claim and
the experiment diverged the same way — the paper described a compiled
graph, the script reimplemented the ops in PyTorch, and nothing bound the
two together (the script even cited stale codegen line numbers). Drift
between a spec/paper sentence and the artifact accumulates silently until
something exercises the exact path.

### C5 — Dispatch-level cleanliness mistaken for sufficiency

This is the subtlest and the most expensive. An operation can pass every
"does it dispatch to a substrate op" check and still be wrong in a way the
grep cannot see. The Yantra OS attempt shipped three such breaches for
weeks. CLAUDE.md now states the meta-rule explicitly: **dispatch is
necessary, not sufficient.** The sufficient set is dispatch + three
measurement audits:

- **Dimension** — zero `basis_vector` calls means the LLM codebook is
  unused and `runtime_dim` is paying a silent multiplier (768 vs ~16).
- **State-locus** — `make_real(scalar)→host→real()` per tick is a counter,
  not an RNN; for any "recurrent" claim the state must be a *vector
  surviving across calls* with no host extraction between them.
- **Signal-separation** — a classifier must ship a measured
  `gap = min(positive) − max(negative)`; returning a number is not
  deciding a class. `font_bound`'s cosines overlapped, and the dispatch
  check never caught it.

There is a second-order version of C5: **gates have blind spots too.** The
`eq`/`_select_softmax` autograd leaks survived the leak-sweep because the
sweep greps *user `.su`* emitted Python, not the runtime prelude where
those methods live. A gate that passes is only evidence for the scope it
covers.

### C6 (cross-cutting) — velocity + inference instead of asking

Two process failures sit alongside the technical ones. The
`gui_window.su` toy was *invented* because an agent inferred what Emma
meant instead of grepping and asking — overwriting precise design intent
with a guess. And in the §3.6 saga, an agent judged a slow run "hung" from
"no output," tried to kill it, was blocked, and the run then completed
with a real result — "slow + silent" was read as "dead." Both are the same
error: acting on an inference where the cost of being wrong is destroying
real work, when asking was available.

---

## 4. Why they survived as long as they did

- **No test cared about the boundary.** Host strings slipped past every
  review for a month because no test exercised a function-call-returning-a-
  string. The bug was literally invisible to the existing corpus.
- **The certifying artifact was the lie.** With the transcendentals, the
  comment and the finding both *asserted* purity. A reviewer trusting the
  written record was led away from the code.
- **Dispatch cleanliness gave false confidence.** The three measurement
  breaches all passed "is it a tensor op?" — the only check that existed
  at the time.
- **Gate scope was narrower than assumed.** The leak-sweep was real and
  green while two leaks lived just outside its scan window (the prelude).
- **Framing rode along with real data.** The §3.6 "6.2 h" figure was a
  real measurement of a *per-sample Python driver loop*, not the compiled
  tensor cost — the batched path gave the bit-identical result ≈96×
  faster. The number was true; the sentence built on it was misleading.
  Misframing of real data is harder to catch than fabricated data because
  the number checks out.

---

## 5. Controls already in place (what's working)

The repo did not just absorb these; it built machinery. Worth crediting so
the strategy below extends rather than re-invents.

1. **`Audit.md`** — the running leak catalogue with `file:line` anchors,
   severity triage, the fixing commit inline on every closed entry, and
   explicit **BORDERLINE** (documented host↔substrate boundaries) and
   **LEGITIMATE** (compile-time constants, monitoring accessors) sections
   so a future session does not re-flag a boundary as a leak. This is the
   single best artifact produced by the whole episode.

2. **The leak-sweep CI gate** — `experiments/substrate_leak_sweep.py` +
   `tests/test_substrate_leak_sweep.py` greps emitted Python for leak
   signatures across 67 `.su` programs, asserts 0 operator leaks, and
   (since `c270acc0`) also scans the runtime prelude where #9/#10 hid. The
   fix model it enforces: one `_st()` host→substrate boundary, every step a
   tensor op, 0-d tensor return, **saturate instead of raise**.

3. **The four-check framework** (CLAUDE.md §"Subtler substrate breaches",
   FV paper §4.4) — dispatch + dimension + state-locus + signal-separation,
   with the meta-rule that dispatch is necessary, not sufficient.

4. **The daily substrate audit cron** (`.github/workflows/daily-audit.yml`)
   — audits every `.su` landed since the last audit against the three
   measurement checks and gates "fix items before other queue work."

5. **The single-shot grand audit** — claim-vs-reality across paper, docs,
   queue, and DEVLOG (the 2026-05-27 pass cross-checked every paper numeric
   claim to its source finding; all matched).

6. **Findings discipline** — each fix gets a dated finding with measured
   numbers; superseded findings get a correction header (the 2026-05-13
   finding now carries one); the differentiable-training finding is a live
   log of every correction, including the agent's own wrong calls.

7. **Equivalence-asserted fast paths** — when the batched training path was
   added, it ships a mandatory pre-run assertion that batched logits ==
   per-sample logits within 1e-4, *aborting the run otherwise*. The
   integrity guarantee is a number on every run, not a claim.

---

## 6. Gaps that remain

- **Only one of the four checks is a hard CI gate.** The dispatch
  leak-sweep is automated and blocking. The dimension, state-locus, and
  signal-separation audits are *manual/cron-driven prose checks*. A `.su`
  with `runtime_dim=768` and zero `basis_vector` calls, an RNN-labelled
  host-state-shuttle, or a classifier with no gap table — none of these
  fails a test today. They depend on a human or a cron reading carefully.
  This is the largest gap: the breach class that cost the most weeks (C5)
  has the weakest automation.

- **The leak-sweep is ~29 min.** Too slow for per-PR; effectively
  nightly. A fast compile-once-reuse variant is a known refinement.

- **`cycle_step` is still a host-state-shuttle.** The rewrite is blocked on
  either exposing `real()` as a `.su` source-level function (Option A) or
  building vector-native 36-way scoring (Option B); recorded, not faked.

- **`atan2` in `rotation_mod`** is a tensor op but libm-shaped — not a leak
  (it dispatches), but not yet the eigenrotation/lookup decomposition the
  transcendental fix established as the target. Low priority.

- **String-coercion residue** — assignment statements (`s = "x"` after
  declaration) and class-field literal initializers are not yet threaded
  through destination-type coercion.

---

## 7. Prevention strategy

The through-line: **every substrate claim must be discharged by a
measurement in the same commit, and every gate must declare its own
scope.** Concretely:

### S1 — Promote the three measurement checks from prose to gates

This is the highest-leverage move, because C5 is the most expensive cause
and the least automated. Targets:

- **Dimension gate.** A test that, for each `.su`, asserts `runtime_dim` is
  the smallest the `basis_vector` count justifies, or carries an explicit
  waiver string with a reason. Zero `basis_vector` + large `runtime_dim`
  fails by default.
- **State-locus gate.** Any program/test carrying an "RNN"/"recurrent"/
  "substrate state" label must have a companion test that walks N steps
  with no host extraction between calls — `count.su`'s
  `test_step_increments_on_substrate` (walks 1..10 on the substrate slot)
  is the template. No such test ⇒ the label is rejected in review.
- **Signal-separation gate.** Any classifier ships a measured
  `gap = min(positive) − max(negative)` table; `test_font_bound.py:124` is
  the template. No gap table ⇒ "the substrate decides X" is an unverified
  claim and does not ship.

### S2 — Ban purity prose that isn't backed by a measurement in the same commit

C2 is cheap to prevent and was the most misleading. Rule: a comment,
finding, or paper sentence asserting "substrate-pure," "trains through the
compiled graph," "recurrent," or "the substrate decides X" must point at
the measurement that backs it *in the same change* — a leak-sweep pass, a
gap table, an autograd-connectivity check (`out.requires_grad` +
`grad is not None`), or a state-survives-across-calls test. The
transcendental comment is the canonical thing this forbids. Superseded
claims get correction headers, not silent edits.

### S3 — Treat "it ran," "it didn't crash," and "a number came out" as non-evidence

C1 + the autograd subclass. The acceptance bar for any substrate claim is
one of: decoded output vs ground truth; a measured gap; an autograd
connectivity check; or a state-locus walk. A value being produced — or
being numerically identical to the right value — proves nothing about
*where it ran* or *whether gradient flows through it*. The `eq` leak
produced the exact right number with the gradient severed; the §3.6 proxy
produced 100% accuracy with no `.su` in the loop.

### S4 — Delete withdrawn shortcuts from the tree; don't leave them dormant

C3. When a pattern is ruled incorrect (not merely dispreferred), `git rm`
it. A commented-out or dormant host path will be re-wired by a later
session that doesn't know it was retired — that is the documented
mechanism behind the transcendental reintroduction. This is already
CLAUDE.md policy; the retrospective is evidence it must be enforced, not
just stated.

### S5 — Every gate documents what it does NOT cover, and an escaped leak widens the gate first

C5-second-order. The leak-sweep missed the prelude. The lesson is not
"the sweep was bad" — it's that a green gate is evidence only for its
scan scope. So: each gate carries a one-line statement of its blind spots
(the leak-sweep now scans the prelude *because* #9/#10 escaped), and when
a leak slips a gate, the first fix is **extending the gate**, then fixing
the leak. `Audit.md`'s BORDERLINE/LEGITIMATE sections already do the
inverse service (preventing false positives); the scope statements
prevent false confidence.

### S6 — Ask, don't infer, when the cost of a wrong inference is destroying real work

C6. When Emma implies a thing exists, grep; if it's absent, stop and ask
(`gui_window.su`). When a long run is slow and silent, do not infer "hung"
and kill it — the §3.6 K=5 run was vindicated after a blocked kill. Both
collapse to: an inference whose downside is overwriting real design intent
or destroying a real result is a question, not an action.

---

## 8. One-line summary

Two failure kinds — leaks (ran on the host) and claim-gaps (said more than
the artifact does) — with five recurring causes, of which "dispatch
cleanliness mistaken for sufficiency" is the most expensive and the least
automated. The repo already built the dispatch gate, the four-check
framework, and the audit catalogue; the open move is to make the other
three checks into gates and to require a measurement in-commit behind every
purity claim.

## Cross-refs

- `Audit.md` — the running leak catalogue (REAL LEAK / BORDERLINE / LEGITIMATE)
- `2026-05-15-transcendental-substrate-leak-fixed.md` — C1+C2+C3, opened Audit.md
- `2026-05-10-host-python-string-bug-chronology.md` — C1+C4, oldest leak
- `2026-04-30-substrate-purity-leak-enumeration.md` — the five seam leaks
- `2026-05-18-differentiable-training-is-a-proxy-not-compiled.md` — C4+C6, claim-vs-reality
- `2026-05-28-daily-substrate-honesty-audit{,-pass-2}.md` — the cron in action
- `2026-05-28-cycle-step-rewrite-blocked.md` — a breach recorded as blocked, not faked
- `2026-05-27-grand-honesty-audit.md` — single-shot claim-vs-reality sweep
- CLAUDE.md §"Subtler substrate breaches — measurement-required" — the four-check framework
- FV paper §4.4 — the four checks named formally
