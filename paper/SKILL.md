---
name: sutra-language
description: Reproduce results from the Sutra paper — build the compiler, run the 13-program smoke test, run the rotation-vs-Hadamard capacity tables (LLM + ESM-2 protein-LM substrates), the chained-bind crosstalk experiment, plus the loop function decl + codebook test suites.
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

Honest negative: chain=1 100%, chain=8 at chance — scopes the
§3.1 capacity claim to single-cycle records.

### §3.1.3 — Sutra vs Scallop (1-hop knowledge-graph query)

```bash
# Build the Scallop image (Rust nightly + scallopy build, ~10-15 min
# first time; cached thereafter):
docker build -t sutra-scallop -f experiments/scallop_compare/Dockerfile .

# Run the side-by-side comparison (mounts the repo so source edits
# are live):
docker run --rm -v "$PWD:/work" -w /work sutra-scallop \
    python experiments/scallop_compare/run_compare.py
test $? -eq 0 || { echo "FAIL: scallop compare run"; exit 1; }
python -c "
import json
d = json.load(open('experiments/scallop_compare/results.json'))
sutra = d['sutra']
scallop = d['scallop']
assert sutra['accuracy'] == 1.0, f'Sutra accuracy {sutra[\"accuracy\"]}'
if scallop is not None:
    assert scallop['accuracy'] == 1.0, f'Scallop accuracy {scallop[\"accuracy\"]}'
    print(f'Sutra: {sutra[\"per_query_us\"]:.1f} us/q; Scallop: {scallop[\"per_query_us\"]:.1f} us/q')
print('OK: shared 1-hop KG task reproduces')
"
```

A 6-fact KG (6 entities, 3 relations) with 1-hop relational queries.
Both systems achieve 100% accuracy; the comparison is per-query
latency on a task each can express natively. Sutra encodes the KG
as a single bundled vector and decodes via unbind+argmax-cosine;
Scallop expresses it as Datalog and resolves via SLG.


