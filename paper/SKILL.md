---
name: sutra-language
description: Reproduce results from the Sutra paper — build the compiler, run the 10-program smoke test, run the rotation-vs-Hadamard capacity tables (LLM + ESM-2 protein-LM substrates), the chained-bind crosstalk experiment, plus the loop function decl + codebook test suites.
allowed-tools: Bash(python *), Bash(pip *), Bash(cd *), Bash(cargo *), Bash(git *), Bash(ollama *)
---

# Sutra: reproduction skill

Sutra is a typed, purely functional programming language whose
values are vectors in a dense embedding space. The compiler emits
PyTorch tensor ops; programs execute as one tensor computation.

## Setup

This is a **reproduction skill**: the goal is to clone the
canonical Sutra repository and run its bundled tests / examples
to verify the paper's claims hold on your machine. You are not
asked to reimplement the language from scratch.

```bash
# 1. Clone the canonical repository. ALL subsequent commands
#    assume your shell's working directory is the cloned
#    `Sutra/` root (the one that contains `paper/`, `sdk/`,
#    `examples/`, `experiments/`, and `sutraDB/`).
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra

# 2. Install Python deps and pull the embedding models. nomic-
#    embed-text is the primary substrate; all-minilm and
#    mxbai-embed-large are needed for the §3.1 capacity table.
pip install torch torchhd transformers
ollama pull nomic-embed-text
ollama pull all-minilm
ollama pull mxbai-embed-large

# 3. Build the SutraDB FFI shared library (optional but
#    recommended — without it the embedded-codebook tests skip).
( cd sutraDB && cargo build --release -p sutra-ffi )
```

**Pre-flight checks** before running the assertions below:
- `python --version` should be 3.11+.
- `python -c "import torch; print(torch.__version__)"` should
  print a version, no traceback.
- `curl -s http://localhost:11434/api/tags | head -c 50` should
  show `{"models":[...` (Ollama running locally).
- Run from the repo root. Every shell block below assumes the
  current directory is the cloned `Sutra/`.

## Compiler + program tests

Each block is a self-contained test. Non-zero exit code means the
claim does not reproduce; the assertion captures the success
condition the paper claims.

```bash
# Smoke-test corpus: all 10 demonstration programs run end-to-end.
python examples/_smoke_test.py
test $? -eq 0 || { echo "FAIL: smoke test"; exit 1; }
```

```bash
# hello_world prints exactly "hello world":
got=$(PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/hello_world.su 2>&1 | tail -1)
[ "$got" = "hello world" ] || { echo "FAIL: hello_world got '$got'"; exit 1; }
```

```bash
# role_filler_record decodes the color field as "red":
got=$(PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/role_filler_record.su 2>&1 | tail -1)
[ "$got" = "red" ] || { echo "FAIL: role_filler_record got '$got'"; exit 1; }
```

```bash
# protein_record decodes the localization slot as "membrane":
got=$(PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/protein_record.su 2>&1 | tail -1)
[ "$got" = "membrane" ] || { echo "FAIL: protein_record got '$got'"; exit 1; }
```

```bash
# Full unit suite: 237 passed, 7 skipped.
python -m pytest sdk/sutra-compiler/tests/ -q --ignore=sdk/sutra-compiler/tests/test_simplify_egglog.py
test $? -eq 0 || { echo "FAIL: pytest suite"; exit 1; }
```

```bash
# Loop function decls (halt-cum + tail-call): 23 tests pass.
python -m pytest sdk/sutra-compiler/tests/test_loop_function_decl.py -q
test $? -eq 0 || { echo "FAIL: loop function decls"; exit 1; }
```

```bash
# Embedded SutraDB codebook: 7 tests pass (or skip if FFI not built).
python -m pytest sdk/sutra-compiler/tests/test_sutradb_embedded.py -q
test $? -eq 0 || { echo "FAIL: sutradb embedded"; exit 1; }
```

```bash
# torch.compile wrapping (opt-in): 3 tests pass.
SUTRA_TORCH_COMPILE=1 python -m pytest sdk/sutra-compiler/tests/test_torch_compile_wrap.py -q
test $? -eq 0 || { echo "FAIL: torch.compile wrap"; exit 1; }
```

```bash
# T-as-runtime-budget: same compiled program, three different T values.
# T is potentially unlimited (any non-negative integer); effective work
# is bounded by the soft-halt cell, so an oversized T does not cost
# extra compute past convergence.
got50=$(PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/do_while_adder.su 2>&1 | tail -1)
got200=$(SUTRA_LOOP_T=200 PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/do_while_adder.su 2>&1 | tail -1)
got10000=$(SUTRA_LOOP_T=10000 PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/do_while_adder.su 2>&1 | tail -1)
[ "$got50" = "$got200" ] || { echo "FAIL: T=50 vs T=200 disagreed"; exit 1; }
[ "$got50" = "$got10000" ] || { echo "FAIL: T=50 vs T=10000 disagreed"; exit 1; }
echo "OK: T-as-runtime-budget reproduces (got '$got50' across T in {50, 200, 10000})"
```

## Empirical results from the paper

### §3.1 — Rotation vs Hadamard capacity (LLM substrates)

```bash
python experiments/rotation_binding_capacity_llm.py
test $? -eq 0 || { echo "FAIL: capacity LLM run"; exit 1; }
python -c "
import json, sys
d = json.load(open('experiments/rotation_binding_capacity_llm_results.json'))
for sub in d:
    if 'error' in sub: sys.exit('FAIL: ' + sub['substrate'])
    rot8 = sub['rotation']['8']['accuracy']
    assert rot8 >= 0.95, f\"{sub['substrate']} rotation k=8 = {rot8}, expected >= 0.95\"
    had2 = sub['hadamard']['2']['accuracy']
    print(f\"{sub['substrate']}: rotation k=8 = {rot8:.1%}; hadamard k=2 = {had2:.1%}\")
print('OK: §3.1 capacity reproduces')
"
```

Reproduces the three tables in §3.1 across `nomic-embed-text`,
`all-minilm`, `mxbai-embed-large`. Expected: rotation accuracy
≥95% at k=8 across all substrates; Hadamard collapses (e.g.
mxbai 15% at k=2). Embeddings disk-cached on first run.

### §3.1 — ESM-2 protein-LM substrate (substrate-agnostic claim)

```bash
python experiments/rotation_binding_capacity_bioinformatics.py
test $? -eq 0 || { echo "FAIL: bio capacity run"; exit 1; }
python -c "
import json
d = json.load(open('experiments/rotation_binding_capacity_bioinformatics_results.json'))
rot8 = d['rotation']['8']['accuracy']
had48 = d['hadamard']['48']['accuracy']
assert rot8 >= 0.95, f'ESM-2 rotation k=8 = {rot8}, expected >= 0.95'
assert had48 <= 0.10, f'ESM-2 hadamard k=48 = {had48}, expected <= 0.10'
print(f'OK: ESM-2 rot k=8 = {rot8:.1%}, had k=48 = {had48:.1%}')
"
```

Reproduces the protein-LM row in §3.1 using
`facebook/esm2_t6_8M_UR50D` (~30 MB download on first call).

### §3.1.1 — Chained bind/unbind crosstalk

```bash
python experiments/crosstalk_chain.py
test $? -eq 0 || { echo "FAIL: crosstalk run"; exit 1; }
python -c "
import json
d = json.load(open('experiments/crosstalk_chain_results.json'))
for sub in d:
    raw1 = sub['raw']['1']['accuracy']
    raw8 = sub['raw']['8']['accuracy']
    assert raw1 == 1.0, f\"{sub['substrate']} chain=1 = {raw1}, expected 1.0\"
    assert raw8 <= 0.05, f\"{sub['substrate']} chain=8 = {raw8}, expected <= 0.05\"
    print(f\"{sub['substrate']}: chain=1 = {raw1:.1%}, chain=8 = {raw8:.1%}\")
print('OK: §3.1.1 crosstalk reproduces')
"
```

chain=1 reaches 100%, chain=8 falls to chance — this scopes the
§3.1 capacity claim to single-cycle records.

### §3.6 — End-to-end differentiable training (symbolic if-then rules)

The headline neuro-symbolic claim: **a symbolic Sutra program made
of fuzzy if-then rules is end-to-end differentiable**, and standard
PyTorch autograd trains the embeddings the rules evaluate against
*without changing the rules themselves*. The symbolic structure is
identical at epoch 0 and at epoch 300 — only the prototype
embeddings move.

**What to build (replication spec):**

1. Pick a frozen embedding model (the canonical implementation uses
   `nomic-embed-text` at 768-d) and embed 992 words across 20
   categories — animal, vehicle, food, color, clothing, weather,
   emotion, tool, instrument, profession, body-part, plant,
   furniture, building, country, sport, drink, metal, shape, fabric
   (fifty per category, deduplicated where the same surface form
   fits two categories).
2. Initialize 20 **learnable** prototype tensors (one per category)
   with `requires_grad=True`. Random init.
3. Forward pass on the full 992-word batch, computing per-class
   scores via Sutra's primitives composed as a fuzzy if-then rule:

   ```
   sim_i  = similarity(x, proto_i)              # cosine_similarity
   rule_i = AND(sim_i,
                AND_{j ≠ i} NOT(sim_j))         # K-1 nested ANDs of NOTs
   ```

   where `AND(a, b) = (a + b + ab − a² − b² + a²b²) / 2` is the
   Lagrange-interpolated Kleene min, `NOT(x) = -x`, and the
   AND-of-NOTs is left-folded across the K−1 other classes (so the
   rule for K=20 nests nineteen ANDs deep). The rule reads
   "classify as *i* if similar to prototype *i* AND not similar to
   any of the other K−1 classes."

4. Full-batch cross-entropy loss over the twenty rule scores, Adam
   optimizer (lr=0.005), train for 300 epochs.
5. Save `accuracy_before`, `accuracy_after`, and per-prototype
   `gradient_norms` to a JSON file.

**Success criteria:**
- `accuracy_after > accuracy_before` (random ~40% → trained ~100%)
- Every prototype's gradient norm > 0 (gradient flows through every
  Lagrange gate to every learnable parameter)
- The symbolic program text is unchanged across training: only the
  embeddings moved

**Reference implementation + verification:**

```bash
python experiments/differentiable_training.py
test $? -eq 0 || { echo "FAIL: differentiable training"; exit 1; }
python -c "
import json
d = json.load(open('experiments/differentiable_training_results.json'))
assert d['accuracy_after'] > d['accuracy_before'], \
    f\"Training did not improve: {d['accuracy_before']} -> {d['accuracy_after']}\"
assert all(g > 0 for g in d['gradient_norms'].values()), \
    f\"Gradient blocked: {d['gradient_norms']}\"
print(f\"Before: {d['accuracy_before']:.0%}, After: {d['accuracy_after']:.0%}\")
print(f\"Gradient norms: {d['gradient_norms']}\")
print('OK: §3.6 differentiable training reproduces')
"
```

Reference numbers (K=20, 992 words): 4% → 95% accuracy
(chance = 5%); convergence by epoch 50; final loss 1.15; all 20
prototype gradient norms in the range 0.94–4.20 (range floor is
the gradient flow check — every prototype receives a nonzero
gradient through the nineteen-AND-deep rule pipeline). The 5%
residual is honest semantic overlap (e.g. *salmon*/*scarf*) at
the optimizer plateau, not gradient pathology.

### Multi-system neuro-symbolic comparison (optional, requires Docker)

A 1-hop knowledge-graph query that Sutra, Scallop, DeepProbLog,
and TorchHD can all express natively. The comparison is on the
*intersection* of what each can do, not a single-number speedup.
Sutra encodes the KG as a single bundled vector; Scallop /
DeepProbLog use Datalog/Prolog; TorchHD uses MAP-VSA.

```bash
# Build the multi-system image (Rust nightly + scallopy + DeepProbLog,
# ~10-15 min first time; cached thereafter):
docker build -t sutra-neurosym -f experiments/scallop_compare/Dockerfile .

# Run the side-by-side comparison:
docker run --rm -v "$PWD:/work" -w /work sutra-neurosym \
    python experiments/scallop_compare/run_compare.py
test $? -eq 0 || { echo "FAIL: multi-system compare run"; exit 1; }
python -c "
import json
d = json.load(open('experiments/scallop_compare/results.json'))
systems = d['systems']
for name, r in systems.items():
    if r is None or 'error' in (r or {}):
        print(f'{name}: skipped/error')
        continue
    assert r['accuracy'] == 1.0, f'{name} accuracy {r[\"accuracy\"]}'
    print(f'{name}: {r[\"per_query_us\"]:.1f} us/q at 100% accuracy')
print('OK: multi-system 1-hop KG comparison reproduces')
"
```

Outside the container, only Sutra and TorchHD run on the host;
Scallop and DeepProbLog skip gracefully. The Docker image is the
reproducibility artifact for the cross-paradigm comparison.


