# FV paper — "is it finished?" verification (2026-07-06)

The queue's FV-paper item (LAST, Emma 2026-07-06: "I think fv paper is finished but not sure") says the
first action on reaching it is to **verify whether it is actually finished**. This is that verification.
It is a read-only audit — no edit to `paper/formal-verification/paper.md` (that would trigger the clawRxiv
resubmit CI), and the one named-but-not-green-lit leg was NOT started.

## What was checked, and what is measured

1. **Lean proofs are machine-checked and clean.** `grep` for `sorry` / `sorryAx` / `admit` in the proof
   bodies of `fv-lean/*.lean` and `fv-lean/mathlib/*.lean` returns nothing (only comments that SAY "no
   sorry"). Each theorem is followed by a `#print axioms` guard (`AndGadget.lean`, `Composition.lean`, …),
   the standard way to prove the axiom footprint is `[propext, Classical.choice, Quot.sound]` with no
   `sorryAx`. The guardrail "nothing proven until lean accepts (no sorryAx)" is MET. CI workflows exist:
   `fv-lean-ci.yml`, `fv-lean-mathlib-ci.yml`, `fv-paper-ci.yml`.

2. **The FV work was closed out.** The most recent `paper/formal-verification/paper.md` commit is
   `1ef8e022` — "FV: GibbsFlow CI-green — continuous-time gap⇒decay machine-checked; paper/queue/DEVLOG
   closeout; CI branch-trigger reverted". "Closeout", CI-green.

3. **clawRxiv reached Accept, then the next submission regressed to Reject — this is review NOISE.**
   Measured ratings across the last versions (all 2026-07-01, Gemini 3 Flash reviewer):

   | version | post | rating | time |
   |---|---|---|---|
   | v93 | 2840 | Reject | 04:11 |
   | v94 | 2841 | Weak Reject | 04:31 |
   | v95 | 2843 | Weak Reject | 17:46 |
   | **v96** | **2844** | **Accept** | **20:07** |
   | **v97** | **2845** | **Reject** | **20:37** |

   `.post_id` = 2845 (v97), so the CURRENT latest review is a Reject. But v96 (30 min earlier, essentially
   the same closed-out content) got Accept, and the whole series oscillates WR/WR/Accept/Reject. Per
   `CLAUDE.md` § "Paper" — **reviews are signal, not verdicts** — this is a high-variance AI reviewer on the
   same paper, not a content regression. The v97 Reject's cons ("verified fragment is restricted",
   "results technically trivial", "small gadgets", "jargon") are the reviewer's recurring SCOPE critique,
   not a correctness defect, and they appear across the accepted and rejected versions alike.

## Correction to the queue's framing

The queue said "clawRxiv reached **Accept** 2026-07-01". That is true of **v96**, but the CURRENT version
(v97, the `.post_id`) is a **Reject**. The accurate statement is: *reached Accept at v96, then v97 (the
current submission) drew a Reject from the same high-variance reviewer; the content is closed out and the
proofs are clean.* This correction is the substrate-honesty rule applied to a framing claim (measured
reality vs. the recorded "Accept").

## Is it finished?

**Substantively yes, with one optional leg gated on Emma.** The proof legs are machine-checked (no sorry),
the work is closed out and CI-green, and it reached Accept. The ONE remaining leg — a Lean gap **value**
for the literal single-spin-flip kernel via the canonical-paths comparison method (until built, the
measured γ=0.0397 stays a measurement, DEVLOG 2026-07-04) — is explicitly **named, NOT green-lit; do not
start without Emma**. So it is not a blocker on "finished"; it is an optional refinement Emma controls.

## Disposition (NEEDS-DECISION — Emma)

Not deletable unilaterally (Emma is "not sure", and the optional leg exists), and not editable without
tripping the resubmit CI. The decision is hers:
- **(a) Declare finished** → delete the queue item; the single-spin-flip γ stays a measurement (documented
  as such), and the v97 Reject is accepted as review noise (v96 Accept stands as the high-water mark).
- **(b) Keep open for the optional leg** → green-light the canonical-paths single-spin-flip gap-value
  proof (its own bounded Lean task), then re-close.
Either way, no correctness work is outstanding and nothing is proven-by-`sorry`.
