---
name: sutra-language
description: Reproduce results from the Sutra paper — build the compiler, run the 13-program smoke test, run the rotation-vs-Hadamard capacity tables (LLM + ESM-2 protein-LM substrates), the chained-bind crosstalk experiment, and the Sutra-vs-TorchHD latency benchmark, plus the loop function decl + SutraDB codebook test suites.
allowed-tools: Bash(python *), Bash(pip *), Bash(cd *), Bash(cargo *), Bash(git *), Bash(ollama *)
---

# Sutra: reproduction skill

Sutra is a typed, purely functional programming language whose
values are vectors in a dense embedding space. The compiler emits
PyTorch tensor ops; programs execute as one tensor computation.

## Setup

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
pip install torch torchhd transformers
ollama pull nomic-embed-text
ollama pull all-minilm
ollama pull mxbai-embed-large
( cd sutraDB && cargo build --release -p sutra-ffi )   # optional
```

## Compiler + program tests

Each block is a self-contained test. Non-zero exit code means the
claim does not reproduce; the assertion captures the success
condition the paper claims.

```bash
# Smoke-test corpus: all 13 demonstration programs run end-to-end.
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

Honest negative: chain=1 100%, chain=8 at chance — scopes the
§3.1 capacity claim to single-cycle records.

### §3.1.2 — Per-call latency vs TorchHD

```bash
SUTRA_TORCH_COMPILE=1 python experiments/sutra_vs_torchhd_latency.py
test $? -eq 0 || { echo "FAIL: latency run"; exit 1; }
python -c "
import json
d = json.load(open('experiments/sutra_vs_torchhd_latency_results.json'))
sutra = d['sutra']['steady_mean_us']
torchhd = d['torchhd']['steady_mean_us']
ratio = sutra / torchhd
print(f'Sutra: {sutra:.0f} us, TorchHD: {torchhd:.0f} us, ratio: {ratio:.1f}x')
assert 5 <= ratio <= 25, f'ratio {ratio} outside expected band [5x, 25x]'
print('OK: §3.1.2 latency reproduces (~12x slower band)')
"
```

Reproduces the §3.1.2 latency table. Expected ratio band 5–25×;
typical mid-band ~12× slower per call. The 12× gap is runtime
Python scaffolding overhead (per-axis synthetic dims, slot
state, halt-cum), not architectural — both systems dispatch the
same PyTorch tensor ops underneath.
