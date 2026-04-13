# Findings

Experimental results with reasoning. One file per finding. This is the
write-up layer between raw commit messages and `STATUS.md`:

- `STATUS.md` has the one-line truth-table summary ("3/5 seeds spiking
  rotation, noise characterized").
- Commit messages have the what-and-why of a specific diff.
- A finding here has the full story: what we ran, what we measured,
  why we got that number, what it tells us about the substrate /
  language / pipeline.

Write a finding when an experiment produces a result you want future
sessions (or future you on a different machine) to be able to reason
about without re-running the code or re-reading every commit.

## Naming

`YYYY-MM-DD-short-slug.md`. The date is for ordering; the slug is for
grep. Multiple findings per day is fine.

## Structure

Each file should answer, in this order:

1. **What was measured.** One sentence. The result number goes here.
2. **Setup.** Scripts run, seeds, parameters, wall clock. Enough that
   someone can reproduce without guessing.
3. **Raw numbers.** Paste the relevant output. Don't summarize away
   the detail that matters.
4. **Interpretation.** Why this number and not another. What
   mechanism produces it. What would move it.
5. **Implications.** What this means for the project — for the paper,
   the language, the substrate, the next experiment. Does it close a
   question, open a new one, or just characterize a gap?

Keep it honest. Negative results and mixed results belong here too —
especially those, since they're the ones that get lost if we don't
write them up.

## Relationship to sibling folders

- `planning/open-questions/` is for design questions where the
  implementation made a choice the spec doesn't yet justify. Findings
  can *resolve* an open question — when they do, note it here and
  remove (or update) the corresponding question doc.
- `planning/exploratory/` is a parking lot for ideas not yet tried.
  Findings are the opposite: we tried it. When an exploratory doc
  produces a finding, move the idea out (closed, implemented, or
  parked for a real reason).
