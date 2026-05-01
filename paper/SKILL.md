---
name: sutra-language
description: Reproduce results from the Sutra paper — build the compiler, run the 13-program smoke test, verify the embedded SutraDB codebook, and run the loop function decl tests. PyTorch tensor-op runtime, opt-in torch.compile wrapping.
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
pip install torch
ollama pull nomic-embed-text
( cd sutraDB && cargo build --release -p sutra-ffi )   # optional
```

## Reproduce

```bash
# Smoke-test corpus (13 demonstration programs):
python examples/_smoke_test.py

# Full unit test suite (237 passed, 7 skipped):
python -m pytest sdk/sutra-compiler/tests/ -q --ignore=sdk/sutra-compiler/tests/test_simplify_egglog.py

# Run an individual .su program:
PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run examples/hello_world.su

# Optional: torch.compile wrapping
SUTRA_TORCH_COMPILE=1 python -m pytest sdk/sutra-compiler/tests/test_torch_compile_wrap.py -q
```

If the SutraDB FFI is not built, the 7 codebook tests skip
gracefully; everything else still passes.
