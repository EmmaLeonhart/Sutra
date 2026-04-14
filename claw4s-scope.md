# Claw4S Submission — Concrete Scope

Deadline: **2026-04-20** (6 days from 2026-04-14).

## What this document is

A tight spec of what actually needs to exist by Apr 20. Not a pitch, not a narrative — a build list. The prior fake-brain anchor ate time because the goal was defined too ambitiously. This time the goal is *minimum viable demonstration*, with honest future-work framing for the stretch directions.

## The core claim I am actually making

The language is real and useful. What I am demonstrating in this submission is narrower than "runs on a brain": **a runtime that executes programs in the language as matrix operations on standard hardware.** That is enough. It is a concrete, reproducible technical result.

What I am *not* claiming in this submission:
- That it has been executed on a biological connectome.
- That it has been executed inside a live embedding space / LLM latent space.
- Peer review or formal publication of the supporting preprint.

The brain and latent-space directions appear only in the Future Work / Discussion section, clearly marked as directions I believe the substrate supports — not results I have obtained.

## What needs to exist by Apr 20

### 1. A working runtime that operates on matrix spaces

This is the hard requirement. Without this, there is no submission.

Minimum shape:
- Takes a program in the language as input.
- Compiles / lowers it to a sequence of matrix operations.
- Executes those operations on GPU (or CPU with a clear note that GPU execution is supported by the same code path).
- Produces output that can be compared against an expected reference.

Minimum demonstration:
- At least **two small example programs** that exercise non-trivial features of the language (branching-without-branching, some form of recursion / fixed-point, something that shows zero-control-flow is not just a toy restriction).
- Both examples run end-to-end from source → matrix ops → output.
- The output is captured as text / numbers in the paper so a reader can verify against a re-run.

Acceptance test: someone other than me clones the repo, runs a single command, and sees the examples produce the documented output. If that works, the runtime is real.

### 2. A clean, runnable repo

- One repo, public on GitHub.
- `README.md` with: one-paragraph "what this is," install command, single command to run the examples.
- `examples/` directory with the two demonstration programs.
- No dead code, no TODOs in paths the README hits.
- License file.

### 3. The Claw4S paper (assembly, not rewrite)

Pull from what already exists. Do not start over. Structure:

1. **Abstract.** The language + the runtime + the scope of what is and isn't demonstrated.
2. **Background.** Brief — VSA / hyperdimensional computing, differentiable programming. Short enough to not become a survey paper.
3. **The language.** Semantics, how control flow is eliminated, differentiability. Point to the formal bits if they exist; otherwise describe operationally.
4. **The runtime.** Compilation to matrix operations. Architecture. How programs become matmuls.
5. **Demonstrations.** The two example programs, with source, with output.
6. **Discussion / Future Work.** *Here* is where the latent-space and connectome directions go, each clearly framed as "the substrate supports this; actual execution is future work." No past tense.
7. **Limitations.** Explicit. Cannot do arithmetic directly. Future work to execute on biological substrate has not been done. Preprint, not peer-reviewed.
8. **Reproducibility appendix.** Repo URL, install steps, expected outputs.

### 4. Honesty pass

Before submission, read the paper once with a red pen specifically looking for:
- Any claim that implies the language has been run on a brain. Rewrite.
- Any claim that implies latent-space execution has been done. Rewrite.
- Any citation of a result that does not exist. Remove.
- Paper IDs. Make sure any clawRxiv reference is `2604.01127`, not the old IDs.
- "Published" vs "preprinted." Use "preprinted" for clawRxiv.

## Explicit out of scope for Apr 20

- Building a full compiler with optimization passes. If a proper compiler comes naturally out of the runtime work, good; if it would take more than a day, skip.
- Benchmarks against other systems. The demonstration is that it works, not that it's fast.
- Any attempt to execute on fly brain data.
- Any attempt to execute inside an embedding space.
- Formal proofs of Turing-completeness. A constructive demonstration (one of the example programs) is enough.

## Time budget (6 days)

Rough allocation — adjust as I learn what's hard. If something slips past its day, drop scope from it rather than from the Fellows prep that starts Apr 20.

- **Apr 14–15:** Inventory what already exists of the runtime. Identify the gap between current state and "executes two example programs end-to-end." Pick the two examples.
- **Apr 16–17:** Close the runtime gap. End-to-end execution of example 1. Then example 2.
- **Apr 18:** Repo cleanup. README. Install command. Fresh-clone reproducibility test.
- **Apr 19:** Paper assembly from existing material into the structure above. Honesty pass.
- **Apr 20:** Submit. Buffer day — no new work, only final checks and submission.

If by **end of Apr 17** the runtime is not executing at least one example end-to-end, stop trying to submit to Claw4S. A late or broken submission is worse than no submission, and the Fellows application on Apr 26 is the higher-priority target.

## What "done" looks like

- Repo is public, has a README, and runs on a fresh clone.
- Paper describes the runtime and the two demonstrations, and does not claim anything that isn't in the repo.
- Submission is in by Apr 20.
- The Fellows application has not been delayed by this work.
