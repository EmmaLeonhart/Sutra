"""Real CUDA implementation of examples/hello_world.su.

Loads the actual codebook the PyTorch backend wrote to
~/.cache/sutra/embeddings/nomic-embed-text-d150.pt, runs three hand-
written CUDA kernels (vector norm, cosine scores, argmax) on the GPU
via CuPy/NVRTC, then cross-checks the result against the PyTorch
backend's argmax. The kernels are CUDA C — what an emitted .cu file
would contain, JIT-compiled at runtime instead of via nvcc ahead of
time.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import torch
import cupy as cp

CACHE = Path.home() / ".cache" / "sutra" / "embeddings" / "nomic-embed-text-d150.pt"
D = 150
GREETING = "hello_world"
CANDIDATES = ["hello_world", "goodbye", "are_you_there"]
PHRASE_NAMES = ["hello world", "goodbye", "are you there"]


# ---- CUDA C kernels ------------------------------------------------------
# These are compiled by NVRTC at first call. The PTX/SASS is cached; on
# subsequent runs CuPy reuses it. Same code as a .cu file would contain.

KERNEL_SRC = r"""
// One-block reduction: out = ||q||_2. Caller launches with 1 block,
// block size = power-of-two threads, shared mem = blockDim*4 bytes.
extern "C" __global__
void vector_norm(const float* __restrict__ q, float* __restrict__ out, int D) {
    extern __shared__ float sdata[];
    float local = 0.f;
    for (int i = threadIdx.x; i < D; i += blockDim.x) {
        local += q[i] * q[i];
    }
    sdata[threadIdx.x] = local;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) sdata[threadIdx.x] += sdata[threadIdx.x + s];
        __syncthreads();
    }
    if (threadIdx.x == 0) out[0] = sqrtf(sdata[0]);
}

// One block per candidate row. Each block computes both dot(M[row], q)
// and ||M[row]||, then writes scores[row] = dot / (m_norm * q_norm + eps).
// Two reductions in one block — twice the shared-mem footprint but the
// row stays in L1 across both passes.
extern "C" __global__
void cosine_scores(const float* __restrict__ M,
                   const float* __restrict__ q,
                   const float* __restrict__ q_norm,
                   float* __restrict__ scores,
                   int N, int D) {
    int row = blockIdx.x;
    if (row >= N) return;
    const float* mrow = M + row * D;

    extern __shared__ float sdata[];
    float* s_dot  = sdata;
    float* s_sqr  = sdata + blockDim.x;

    float local_dot = 0.f, local_sqr = 0.f;
    for (int i = threadIdx.x; i < D; i += blockDim.x) {
        float m = mrow[i];
        float qi = q[i];
        local_dot += m * qi;
        local_sqr += m * m;
    }
    s_dot[threadIdx.x] = local_dot;
    s_sqr[threadIdx.x] = local_sqr;
    __syncthreads();

    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) {
            s_dot[threadIdx.x] += s_dot[threadIdx.x + s];
            s_sqr[threadIdx.x] += s_sqr[threadIdx.x + s];
        }
        __syncthreads();
    }
    if (threadIdx.x == 0) {
        float m_norm = sqrtf(s_sqr[0]);
        const float eps = 1.17549435e-38f;  // FLT_TRUE_MIN — matches torch.finfo.tiny
        scores[row] = s_dot[0] / (m_norm * q_norm[0] + eps);
    }
}

// Tiny argmax over N <= 1024. Single thread; for hello_world N=3 so
// any parallel reduction would be pure overhead. A real codegen would
// dispatch this to a tiled tree reduction once N grows.
extern "C" __global__
void argmax_small(const float* __restrict__ scores,
                  int* __restrict__ out_idx, int N) {
    if (threadIdx.x != 0 || blockIdx.x != 0) return;
    int best = 0;
    float bv = scores[0];
    for (int i = 1; i < N; i++) {
        if (scores[i] > bv) { bv = scores[i]; best = i; }
    }
    out_idx[0] = best;
}
"""

mod = cp.RawModule(code=KERNEL_SRC, options=("--use_fast_math",))
k_norm = mod.get_function("vector_norm")
k_cosine = mod.get_function("cosine_scores")
k_argmax = mod.get_function("argmax_small")


def main() -> int:
    if not CACHE.exists():
        print(f"missing codebook cache {CACHE}; run the PyTorch backend "
              "once to populate it: python -m sutra_compiler --run "
              "examples/hello_world.su", file=sys.stderr)
        return 1

    codebook = torch.load(CACHE, map_location="cpu", weights_only=True)
    for name in CANDIDATES + [GREETING]:
        if name not in codebook:
            print(f"codebook missing entry for {name!r}", file=sys.stderr)
            return 1

    M_np = np.stack([codebook[n].numpy() for n in CANDIDATES]).astype(np.float32)
    q_np = codebook[GREETING].numpy().astype(np.float32)
    N = len(CANDIDATES)

    M_gpu = cp.asarray(M_np)
    q_gpu = cp.asarray(q_np)
    scores_gpu = cp.zeros(N, dtype=cp.float32)
    qnorm_gpu = cp.zeros(1, dtype=cp.float32)
    winner_gpu = cp.zeros(1, dtype=cp.int32)

    threads = 128
    shmem_norm = threads * 4
    shmem_cosine = threads * 4 * 2

    k_norm((1,), (threads,),
           (q_gpu, qnorm_gpu, np.int32(D)),
           shared_mem=shmem_norm)
    k_cosine((N,), (threads,),
             (M_gpu, q_gpu, qnorm_gpu, scores_gpu, np.int32(N), np.int32(D)),
             shared_mem=shmem_cosine)
    k_argmax((1,), (1,),
             (scores_gpu, winner_gpu, np.int32(N)))
    cp.cuda.Stream.null.synchronize()

    cuda_scores = scores_gpu.get()
    cuda_winner = int(winner_gpu.get()[0])

    # Cross-check against PyTorch's argmax_cosine on the same vectors.
    M_t = torch.from_numpy(M_np).cuda()
    q_t = torch.from_numpy(q_np).cuda()
    rn = torch.linalg.norm(M_t, dim=1)
    qn = torch.linalg.norm(q_t)
    safe = torch.where(rn > 0, rn, torch.ones_like(rn))
    torch_scores = ((M_t @ q_t) / (safe * qn)).cpu().numpy()
    torch_winner = int(torch.argmax(torch.from_numpy(torch_scores)).item())

    print(f"  CUDA scores:    {cuda_scores}")
    print(f"  PyTorch scores: {torch_scores}")
    print(f"  max |diff|:     {np.max(np.abs(cuda_scores - torch_scores)):.3e}")
    print()
    print(f"  CUDA winner:    {PHRASE_NAMES[cuda_winner]!r} (idx {cuda_winner})")
    print(f"  PyTorch winner: {PHRASE_NAMES[torch_winner]!r} (idx {torch_winner})")
    print()
    if cuda_winner == torch_winner:
        print("  MATCH — CUDA kernels produce the same answer as the PyTorch backend.")
        return 0
    print("  MISMATCH — kernels diverge from the PyTorch backend. Investigate.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
