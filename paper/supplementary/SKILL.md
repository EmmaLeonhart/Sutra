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

This is a **reproduction skill**: run the bundled tests and
examples in this archive to verify the paper's empirical
claims. Reimplementation is not required.

```bash
# 1. Working directory: the unzipped archive root (the
#    directory that contains paper/, sdk/, examples/,
#    experiments/, sutraDB/). All subsequent commands assume
#    this is the current directory.

# 2. Install Python deps and pull the embedding models.
#    nomic-embed-text is the primary substrate; all-minilm and
#    mxbai-embed-large are needed for the capacity sweep.
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
- Every shell block below runs from the archive root.

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

### §3.6 / §3.7 — Differentiable training through the compiled graph

The headline neuro-symbolic claim: **a symbolic Sutra program of
fuzzy if-then rules, compiled by the PyTorch codegen, is end-to-end
differentiable**. Standard PyTorch autograd trains the embeddings
the rules evaluate against *through the emitted graph itself* — the
symbolic source is unchanged across training; only the prototype
embeddings move. §3.7 additionally trains a scalar gain inside the
rule and writes the learned value back into the `.su` source as a
numeric literal, so the trained model is itself recompilable Sutra
source.

**§3.6 — compiled fuzzy-rule classifier (`differentiable_training_compiled.py`)**

1. The harness generates a real `.su` program (`gen_rule_su`),
   validates → lexes → parses → runs the **PyTorch codegen**, then
   `exec`s the emitted module. A build-time assertion rejects the
   run if the emitted `similarity` collapses to a host `float()`
   (Stage A0) — gradients must flow through the emitted tensor ops,
   not a reimplementation.
2. Five semantic classes, ten words each (50 inputs), embedded with
   a frozen model (canonical: `nomic-embed-text`, 768-d). Five
   learnable prototype tensors, random init, `requires_grad=True`.
3. Each class score is the **emitted** compiled rule
   `rule_i = AND(sim(x,p_i), AND_{j≠i} NOT(sim(x,p_j)))` — the
   compiler's `_VSA.similarity` composed with the Lagrange–Kleene
   AND/NOT polynomials. Full-batch cross-entropy, Adam (lr=0.01),
   30 epochs, three seeds (0–2).
4. The forward is evaluated batched via `torch.vmap` over the same
   emitted `rule`; before training the harness asserts the batched
   and per-sample evaluations agree within 1e-4 on identical
   inputs/parameters, so the fast path is provably the identical
   compiled computation.

```bash
python experiments/differentiable_training_compiled.py \
    --k 5 --per-class 10 --epochs 30 --seeds 0,1,2 --lr 0.01 --batched \
    | tee diff36.out
test $? -eq 0 || { echo "FAIL: §3.6 compiled training"; exit 1; }
python -c "
import re
t = open('diff36.out').read()
assert 'grads_through_emitted_graph=True' in t, 'gradient did not flow through the emitted graph'
m = re.search(r'before=([\d.]+).*after=([\d.]+)', t)
b, a = float(m.group(1)), float(m.group(2))
assert a > b and a > 99.0, f'did not converge: {b} -> {a}'
print(f'OK: §3.6 before={b}% after={a}% (compiled graph, equivalence-asserted)')
"
```

Reference numbers (K=5, 50 words, 3 seeds): before **18.7 ± 9.5 %**
(chance = 20 %) → after **100.0 ± 0.0 %**; gradients flow through
the emitted graph on every seed. Batched wall-clock ≈ 230 s on CPU;
the equivalent per-sample Python driver produces the bit-identical
result in ≈ 6.2 h (interpreter overhead, not a compiled-graph
cost). Accuracy is in-sample — a verification that backprop reaches
every prototype through the compiler's emitted ops, not a
generalization claim.

**§3.7 — trained weight baked back into `.su` (`differentiable_training_weighted.py`)**

Adds a `number w` gain to the rule
(`(w·sim(x,own)) && !(w·sim(x,o_j))…`), trains `w` together with
the prototypes through the emitted graph, then regenerates the rule
with the trained `w*` substituted as a numeric **literal** (the
parameter removed), recompiles that `.su` through the codegen, and
asserts the recompiled logits match the parametric model.

```bash
python experiments/differentiable_training_weighted.py \
    --k 3 --per-class 8 --epochs 30 --seeds 0,1 | tee diff37.out
test $? -eq 0 || { echo "FAIL: §3.7 weighted round-trip"; exit 1; }
python -c "
t = open('diff37.out').read()
assert 'round_trip_ok(all)=True' in t, 'baked .su did not recompile to identical logits'
print('OK: §3.7 trained w baked into .su; recompile round-trip verified')
"
```

Reference numbers (K=3, 24 words, 2 seeds): before **33.3 ± 5.9 %**
(chance = 33.3 %) → after **100.0 ± 0.0 %**; learned gain
**w\* = 1.43 ± 0.004**; the baked `.su` recompiles to logits within
≈ 2×10⁻⁷ of the parametric model (round-trip verified every seed).
A small single-scale verification of the source↔training
round-trip, not a benchmark; ≈ 2.5 min including the recompile.

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


