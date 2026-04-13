# CX ring-attractor spiking rotation — does not discriminate direction

**Date:** 2026-04-13
**Code:** `planning/findings/2026-04-13-cx-ring-attractor-no-direction-discrimination.py`
**Status:** Negative result. Do not import from production.

## What was tried

A Brian2 spiking simulation of the central-complex EPG/PEN/PEG/ER ring
attractor, attempting to push the Sutra `rotate` op from host-side
numpy (tier-2 per `planning/sutra-spec/02-operations.md`) onto a
spiking circuit, in response to a reviewer who read numpy rotation as
"cheating."

## What happened

The self-test showed correlation ≈ 0.97 between left-drive and
right-drive output EPG profiles. The circuit does not distinguish
direction — it produces undifferentiated activity rather than a true
rotation. "It ran and produced spikes" is not success (see CLAUDE.md
§"Forbidden shortcut behaviors").

## Why this is filed, not fixed

The reviewer framing was mistaken. Per spec, rotation R is a tier-2
algebraic op (pure math on vectors) and only tier-3 ops (snap, cone,
hop) run on the connectome. The fly-brain paper's snap+prototype-match
demo already covers tier-3 correctly. We do not need this circuit to
work; we need the tier split explained. The paper's `fly-brain-paper/paper.md`
Honest Limits section now states this directly.

The script is kept as a dated artifact so the investigation isn't
lost, but it has no role in the pipeline and was previously sitting in
`fly-brain/` with a `_` prefix — which violated the "exploratory code
goes in `planning/findings/`" rule in CLAUDE.md.
