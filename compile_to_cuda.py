"""End-to-end .su -> PyTorch -> CUDA pipeline.

Steps:
  1. Invoke sutra_compiler --emit on examples/hello_world.su to produce
     a self-contained PyTorch Python module.
  2. Import that module and identify the hot-path function (the cosine
     argmax over the candidate codebook).
  3. Run it through torch.compile (Inductor backend), which lowers to
     Triton, which lowers to PTX/SASS for the live GPU.
  4. Dump every artifact Inductor produces: the wrapper Python, the
     Triton kernel source, and the PTX.

Output goes to ./cuda_artifacts/ as concrete files.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent
EMITTED = REPO / "hello_world_emitted.py"
ARTIFACTS = REPO / "cuda_artifacts"
INDUCTOR_CACHE = REPO / "cuda_artifacts" / "inductor_cache"

# Inductor reads its cache dir from this env var. Pinning it inside the
# repo means we capture the artifacts deterministically — no chasing
# random %TEMP%\torchinductor_<user> paths.
ARTIFACTS.mkdir(exist_ok=True)
INDUCTOR_CACHE.mkdir(exist_ok=True)
os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(INDUCTOR_CACHE)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TORCH_LOGS"] = "output_code"


def step1_emit_pytorch() -> None:
    print("=" * 70)
    print("STEP 1: .su -> PyTorch (sutra_compiler --emit)")
    print("=" * 70)
    if EMITTED.exists():
        print(f"  reusing existing {EMITTED.name}")
        return
    sdk = REPO / "sdk" / "sutra-compiler"
    src = REPO / "examples" / "hello_world.su"
    out = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--emit", str(src)],
        cwd=sdk, capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        sys.exit(1)
    EMITTED.write_text(out.stdout, encoding="utf-8")
    print(f"  wrote {EMITTED.name} ({EMITTED.stat().st_size} bytes)")


def step2_compile_to_cuda():
    print()
    print("=" * 70)
    print("STEP 2: PyTorch -> CUDA (torch.compile -> Inductor -> Triton)")
    print("=" * 70)

    import importlib.util
    spec = importlib.util.spec_from_file_location("hello_world_emitted", EMITTED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import torch

    # The hot path: argmax over (3, 150) M against (150,) q. Recreate it
    # as a standalone function with the exact same shape and dtype the
    # emitted module uses, so torch.compile produces the kernel that
    # would dispatch when main() runs.
    def cosine_argmax(M: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
        rn = torch.linalg.norm(M, dim=1)
        qn = torch.linalg.norm(q)
        safe = torch.where(rn > 0, rn, torch.ones_like(rn))
        scores = (M @ q) / (safe * qn)
        return torch.argmax(scores)

    # Pull the actual codebook tensors from the emitted module so we
    # compile against real shapes/dtypes/device — not synthetic data.
    M = torch.stack([mod.v_hello, mod.v_goodbye, mod.v_question])
    q = mod.greeting

    print(f"  M shape: {tuple(M.shape)}, dtype={M.dtype}, device={M.device}")
    print(f"  q shape: {tuple(q.shape)}, dtype={q.dtype}, device={q.device}")

    compiled = torch.compile(cosine_argmax, backend="inductor", mode="reduce-overhead")
    # Warm up — Inductor codegens, NVRTC compiles, PTX gets cached on disk.
    for _ in range(3):
        result = compiled(M, q)
    torch.cuda.synchronize()

    print(f"  argmax result: {int(result.item())} -> "
          f"{['hello world', 'goodbye', 'are you there'][int(result.item())]}")
    print(f"  inductor cache: {INDUCTOR_CACHE}")


def step3_collect_artifacts() -> None:
    print()
    print("=" * 70)
    print("STEP 3: collected CUDA artifacts")
    print("=" * 70)

    triton_kernels = list(INDUCTOR_CACHE.rglob("*.py"))
    cubin_files = list(INDUCTOR_CACHE.rglob("*.cubin"))
    ptx_files = list(INDUCTOR_CACHE.rglob("*.ptx"))
    json_files = list(INDUCTOR_CACHE.rglob("*.json"))

    print(f"  triton kernel sources: {len(triton_kernels)}")
    for p in triton_kernels:
        print(f"    {p.relative_to(INDUCTOR_CACHE)}  ({p.stat().st_size} bytes)")
    print(f"  PTX assemblies:        {len(ptx_files)}")
    for p in ptx_files:
        print(f"    {p.relative_to(INDUCTOR_CACHE)}")
    print(f"  cubin (SASS) blobs:    {len(cubin_files)}")
    for p in cubin_files:
        print(f"    {p.relative_to(INDUCTOR_CACHE)}")

    # Surface the most interesting kernel by copying it out of the
    # nested hash dirs to a stable filename in the artifacts root.
    if triton_kernels:
        biggest = max(triton_kernels, key=lambda p: p.stat().st_size)
        dest = ARTIFACTS / "fused_triton_kernel.py"
        shutil.copy(biggest, dest)
        print(f"\n  -> {dest.name} (largest Triton kernel, copied for inspection)")
    if ptx_files:
        first_ptx = ptx_files[0]
        dest = ARTIFACTS / "kernel.ptx"
        shutil.copy(first_ptx, dest)
        print(f"  -> {dest.name} (one PTX assembly, copied for inspection)")


if __name__ == "__main__":
    step1_emit_pytorch()
    step2_compile_to_cuda()
    step3_collect_artifacts()
