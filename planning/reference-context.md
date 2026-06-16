# Reference-context notes

This file holds **committable context notes** about external reference material we base
research directions on. The reference sources themselves (PDFs, web pages) are **NOT
committed** — copyright; they are reference material, not repo content. They live in the
gitignored `references/` directory and are re-downloaded fresh each session by
`scripts/fetch_reference_pdfs.py` (registry of slug → URL; arXiv `/abs/` is normalized to
the PDF endpoint; non-PDF sources are saved as `.html`; transient fetches retry).

To (re)download the seed references below:

```
python scripts/fetch_reference_pdfs.py schmidhuber-fki-126-90 arxiv-1802-08864 \
    arxiv-2604-06425 metauto-neuralcomputer
```

## Seed references (Emma 2026-06-16) — the "network as a differentiable computer" lineage

The four seed references trace one through-line, largely Schmidhuber's: **the neural network
is itself a general-purpose, differentiable computer** — which is exactly the frame Sutra's
substrate sits in (a program compiled to tensor ops over a vector substrate; the GUI demo
renders every pixel on that substrate and backprops preference through it).

- **`schmidhuber-fki-126-90`** — Schmidhuber, FKI-126-90 (revised), 1990: *"Making the World
  Differentiable: On Using Self-Supervised Fully Recurrent Neural Networks for Dynamic
  Reinforcement Learning and Planning in Non-Stationary Environments."* The origin of the
  differentiable world-model idea: a recurrent **model** network made differentiable so a
  **controller** can plan/learn by backprop through it. Directly relevant to the
  GUI-steering demo's "backprop the preference through the differentiable render" structure
  and to the broader "every op trainable" substrate direction.

- **`arxiv-1802-08864`** — Schmidhuber, 2018: *"One Big Net For Everything"* (the "ONE"
  network). A single recurrent net as an **incrementally trained, increasingly general
  problem solver** that learns new tasks without forgetting and may grow/prune neurons and
  connections. Relevant to the long-horizon "one substrate program that accretes
  capability" / constrain-train direction.

- **`arxiv-2604-06425`** — Zhuge, Zhao, … Schmidhuber (Meta AI / KAUST), 2026: *"Neural
  Computers."* Proposes **Neural Computers (NCs)** that unify computation, memory, and I/O in
  a single **learned runtime state**, with the "Completely Neural Computer (CNC)" as the
  long-term general-purpose form (stable execution, explicit reprogramming, durable
  capability reuse). Initial step: learn elementary NC primitives from I/O traces alone,
  instantiated as video models. This is the closest contemporary peer to Sutra's "the
  substrate *is* the machine" thesis and is the most directly relevant of the four. (Large
  PDF, ~27 MB.)

- **`metauto-neuralcomputer`** (HTML) — *"Neural Computer: A New Machine Form Is Emerging."*
  The Neural Computers project essay: how an NC differs from agents, world models, and
  conventional computers; what a runtime and the CNC would mean; what current prototypes
  show. Companion to `arxiv-2604-06425`.

### How this informs Sutra's directions

- The GUI Adam-RLHF demo (differentiable substrate render + preference backprop) is a
  concrete, small instance of the "make the world/render differentiable and steer by
  gradient" idea from FKI-126-90.
- The Neural-Computer framing (computation+memory+I/O in a learned state) is the peer to
  cite/contrast when positioning Sutra's substrate-as-computer claim — note the contrast:
  Sutra's substrate ops are **compiled and analytic** (fixed-weight base case), not learned
  from I/O traces; the learned-decoder direction (EMMA-GATED) is where the two frames meet.

> These are reading notes for orientation, not claims in any paper. Anything that lands in
> `paper/` must be independently grounded and measured.
