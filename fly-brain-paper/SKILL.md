---
name: sutra-fly-brain
description: Compile and run Sutra programs on a simulated Drosophila mushroom body. Reproduces the result from "Running Sutra on the Drosophila Hemibrain Connectome" — 4 program variants × 4 inputs = 16/16 decisions correct on a Brian2 spiking LIF model of the mushroom body (50 PNs → 2000 KCs → 1 APL → 20 MBONs), via the AST → FlyBrainVSA codegen pipeline.
allowed-tools: Bash(python *), Bash(pip *)
---

# Running Sutra on the Drosophila Hemibrain Connectome

**Author: Emma Leonhart**

This skill reproduces the results from *"Running Sutra on the Drosophila Hemibrain Connectome: Methodology and Results"* — the first known demonstration of a programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate. The target substrate is a Brian2 leaky-integrate-and-fire simulation of the *Drosophila melanogaster* mushroom body: 50 projection neurons → 2000 Kenyon cells → 1 anterior paired lateral neuron → 20 mushroom body output neurons, with APL-enforced 5% KC sparsity.

**Source:** `fly-brain/` (runtime), `fly-brain-paper/` (this paper), `sdk/sutra-compiler/` (the reference compiler used for codegen).

## What this reproduces

1. **A four-state conditional program compiles end-to-end to the mushroom body.** `fly-brain/permutation_conditional.su` is parsed and validated by the same Sutra compiler used for the silicon experiments, mechanically translated by a substrate-specific backend (`sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`) into Python calls against the spiking circuit, then executed.

2. **Four program variants × four input conditions = sixteen decisions, all correct.** Each variant differs only by which permutation keys multiply into the query before `snap` runs through the mushroom body — the compiled prototype table is identical across variants. The four variants yield four *distinct* permutations of the underlying behavior mapping (`approach`, `ignore`, `search`, `idle`).

3. **The fixed-frame runtime invariant.** Every `snap` call in one program execution must share the same PN → KC connectivity matrix, or prototype matching is meaningless. Measured numbers: ~0.53 cosine per-snap fidelity under rolling frames vs. 1.0 under fixed frame; 4-way discrimination requires the fixed frame.

## Prerequisites

```bash
pip install brian2 numpy scipy
```

No GPU required. Full reproduction runs in under two minutes on commodity hardware.

## One-command reproduction

```bash
python fly-brain/test_codegen_e2e.py
```

This script does the full end-to-end pipeline in one file:
1. Parses `fly-brain/permutation_conditional.su` with the Sutra SDK
2. Runs the AST → FlyBrainVSA translator (`codegen_flybrain.translate_module`)
3. `exec()`s the generated Python in a private module namespace so the compile-time `snap()` calls fire on a live mushroom body
4. Calls `program_A`, `program_B`, `program_C`, `program_D` on the four `(smell, hunger)` inputs
5. Compares results against the expected behavior table from `fly-brain-paper/paper.md`

Expected output:

```
Decisions matching expected: 16/16
Distinct program mappings:   4/4
GATE: PASS
```

## Per-demo reproduction

Use the e2e test wrapper. Prior standalone demos (`four_state_conditional.py`, `programmer_control_demo.py`, `permutation_conditional.py`) were removed as superseded during the 2026-04-13 fly-brain sprawl cleanup — the `test_codegen_e2e*` files cover the same pipeline end-to-end from `.su` source through codegen to the live MB simulation.

```bash
python sdk/sutra-compiler/test_codegen_e2e.py
python sdk/sutra-compiler/test_codegen_e2e_fuzzy.py
```

## What you should see

- **`test_codegen_e2e_fuzzy.py`**: compiles `fly-brain/fuzzy_conditional.su` through the pipeline and runs the resulting program against the live MB simulation. 16/16 pass across 4 program variants × 4 input conditions, with four distinct behavior mappings emerging from one-character `!` edits at the source level. This is the combined "programmer agency + compile-to-brain" result.

## Generating the compiled Python from the `.su` source

If you want to watch the codegen step directly:

```bash
cd sdk/sutra-compiler
python -m sutra_compiler --emit-flybrain ../../fly-brain/permutation_conditional.su > /tmp/generated.py
```

The resulting `/tmp/generated.py` is a 93-line Python module targeting `FlyBrainVSA` that you can import and run against the same mushroom-body circuit.

## Dependencies between files

- **`fly-brain/mushroom_body_model.py`** — the Brian2 circuit: PN group, KC group, APL inhibition, MBON readout, synaptic connectivity with 7-PN fan-in per KC
- **`fly-brain/spike_vsa_bridge.py`** — encode hypervectors as PN input currents, decode KC population activity back to hypervectors via pseudoinverse
- **`fly-brain/vsa_operations.py`** — `FlyBrainVSA` class exposing the Sutra VSA primitives (`bind`, `unbind`, `bundle`, `snap`, `similarity`, `permute`, `make_permutation_key`)
- **`fly-brain/permutation_conditional.{ak,py}`** — the compile-to-brain demo program (source + hand-written reference form)
- **`fly-brain/test_codegen_e2e.py`** — end-to-end parse-to-brain test
- **`sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`** — the `.su` → `FlyBrainVSA`-targeted Python translator

## Limitations stated honestly in the paper

- **50-dim hypervectors** limit bundling capacity. Biological mushroom bodies use ~2000-dim (KC count), not 50 (PN count). Scaling up the input dimensionality to match KC count would help materially.
- **Loops are intentionally unsupported** by the V1 codegen. A `while` compilation path probably needs recurrent KC → KC connections that the current circuit doesn't have. See `fly-brain/STATUS.md` §Loops for why this is framed as a research question rather than a codegen bug.
- **Non-permutation boolean composition** (`&&`, `||`) has no known VSA-to-substrate compilation scheme yet. Source-level `!` compiles cleanly because sign-flip permutation keys are involutive and distribute over `bind`; general boolean operations don't have that structure.
- **Bind / unbind / bundle run in numpy**, not on the mushroom body. The MB has no natural analogue for sign-flip multiplication — only `snap` executes on the biological substrate. The hybrid design reflects this honestly.

## Reading order for the paper

1. `fly-brain-paper/paper.md` — the paper itself (this SKILL's subject)
2. `fly-brain/STATUS.md` — honest running status, technical insights (fixed-frame invariant, negation-as-permutation, MB-as-VSA-substrate caveats)
3. `fly-brain/DEMO.md` — audience-facing summary of the programmer-agency result
4. `fly-brain/DOOM.md` — gap analysis writeup: "how far are we from playing Doom on this?"

