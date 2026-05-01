// Hand-written CUDA translation of examples/hello_world.su.
//
// THIS IS NOT EMITTED. Sutra has no codegen_cuda backend. This file
// shows what one would plausibly produce — kernels for cosine scoring
// and argmax over the candidate codebook, cuBLAS for the matmul, host
// glue for Ollama and the final string lookup.
//
// Layout matches codegen_pytorch.py: D = SEM + SYN, semantic block first,
// synthetic block (real/imag/truth/...) zero-initialized for hello_world.
//
// Build:
//   nvcc -O2 -lcublas hello_world.cu -o hello_world
// Run:
//   ./hello_world
//
// Embedding fetch is stubbed — replace fill_embedding_from_ollama() with
// an actual HTTP call (libcurl) or read pre-fetched .pt cache from disk
// via cnpy / your loader of choice. The PyTorch backend caches at
// ~/.cache/sutra/embeddings/<model>-d<D>.pt; reading that directly is
// the cleanest path.

#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SEM 50           // semantic_dim — matches --runtime-dim default
#define SYN 100          // synthetic_dim — fixed by codegen_pytorch
#define D   (SEM + SYN)  // 150
#define N_CANDIDATES 3

#define CK(x) do { cudaError_t e = (x); if (e != cudaSuccess) { \
    fprintf(stderr, "CUDA %s:%d: %s\n", __FILE__, __LINE__, \
            cudaGetErrorString(e)); exit(1); } } while (0)
#define CB(x) do { cublasStatus_t s = (x); if (s != CUBLAS_STATUS_SUCCESS) { \
    fprintf(stderr, "cuBLAS %s:%d: %d\n", __FILE__, __LINE__, (int)s); \
    exit(1); } } while (0)

// ---- Kernels -------------------------------------------------------------

// Mean-center + L2-normalize the semantic block in-place. One block per
// vector; threads cooperate on the reductions.
__global__ void normalize_semantic(float* V, int n_vecs) {
    extern __shared__ float scratch[];
    int row = blockIdx.x;
    if (row >= n_vecs) return;
    float* v = V + row * D;

    // sum over semantic block
    float local_sum = 0.f;
    for (int i = threadIdx.x; i < SEM; i += blockDim.x) local_sum += v[i];
    scratch[threadIdx.x] = local_sum;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) scratch[threadIdx.x] += scratch[threadIdx.x + s];
        __syncthreads();
    }
    float mean = scratch[0] / (float)SEM;
    for (int i = threadIdx.x; i < SEM; i += blockDim.x) v[i] -= mean;
    __syncthreads();

    // L2 norm over the full vector (semantic + synthetic)
    float local_sq = 0.f;
    for (int i = threadIdx.x; i < D; i += blockDim.x) local_sq += v[i] * v[i];
    scratch[threadIdx.x] = local_sq;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) scratch[threadIdx.x] += scratch[threadIdx.x + s];
        __syncthreads();
    }
    float inv = rsqrtf(scratch[0] + 1e-30f);
    for (int i = threadIdx.x; i < D; i += blockDim.x) v[i] *= inv;
}

// Cosine scores: scores[i] = (M[i] . q) / (||M[i]|| * ||q||).
// We've already L2-normalized everything, so this is just M @ q —
// done with cuBLAS sgemv, no kernel needed. Kept here for reference
// in case normalization is skipped.

// Argmax over N_CANDIDATES floats. Single block, single thread is fine
// at this size; the real codegen would launch one block-per-tile reduction
// for larger codebooks.
__global__ void argmax_small(const float* scores, int n, int* out_idx) {
    if (threadIdx.x != 0 || blockIdx.x != 0) return;
    int best = 0;
    float bv = scores[0];
    for (int i = 1; i < n; i++) {
        if (scores[i] > bv) { bv = scores[i]; best = i; }
    }
    *out_idx = best;
}

// ---- Host glue -----------------------------------------------------------

// Stub: fill h_vec with the embedding for `name`.
//
// Real implementation: HTTP POST to http://localhost:11434/api/embed with
// {"model":"nomic-embed-text","input":"<name>"}, parse response, copy the
// first SEM dims into h_vec[0..SEM), zero out h_vec[SEM..D).
//
// For now, deterministic stub so the binary at least runs end-to-end.
static void fill_embedding_from_ollama(const char* name, float* h_vec) {
    // NOT a real embedding — replace with libcurl + JSON parse.
    unsigned int seed = 1469598103u;
    for (const char* p = name; *p; ++p) seed = seed * 16777619u ^ (unsigned char)*p;
    for (int i = 0; i < SEM; i++) {
        seed = seed * 1664525u + 1013904223u;
        h_vec[i] = ((float)(seed & 0xFFFF) / 32768.f) - 1.f;
    }
    for (int i = SEM; i < D; i++) h_vec[i] = 0.f;
}

int main(void) {
    cublasHandle_t cublas;
    CB(cublasCreate(&cublas));

    // Codebook: greeting (== v_hello), v_hello, v_goodbye, v_question.
    // greeting and v_hello share the same name so we deduplicate.
    const char* phrase_names[N_CANDIDATES] = {
        "hello world", "goodbye", "are you there"
    };
    const char* embed_names[N_CANDIDATES] = {
        "hello_world", "goodbye", "are_you_there"
    };
    const char* greeting_name = "hello_world";

    // ---- Build host-side codebook (one Ollama round-trip per name) ----
    float h_M[N_CANDIDATES * D];
    for (int i = 0; i < N_CANDIDATES; i++) {
        fill_embedding_from_ollama(embed_names[i], h_M + i * D);
    }
    float h_q[D];
    fill_embedding_from_ollama(greeting_name, h_q);

    // ---- Upload to device ----
    float *d_M, *d_q, *d_scores;
    int *d_argmax;
    CK(cudaMalloc(&d_M, sizeof(float) * N_CANDIDATES * D));
    CK(cudaMalloc(&d_q, sizeof(float) * D));
    CK(cudaMalloc(&d_scores, sizeof(float) * N_CANDIDATES));
    CK(cudaMalloc(&d_argmax, sizeof(int)));
    CK(cudaMemcpy(d_M, h_M, sizeof(float) * N_CANDIDATES * D,
                  cudaMemcpyHostToDevice));
    CK(cudaMemcpy(d_q, h_q, sizeof(float) * D, cudaMemcpyHostToDevice));

    // ---- Mean-center + L2-normalize on device ----
    size_t shmem = 128 * sizeof(float);
    normalize_semantic<<<N_CANDIDATES, 128, shmem>>>(d_M, N_CANDIDATES);
    normalize_semantic<<<1, 128, shmem>>>(d_q, 1);

    // ---- Cosine scores: scores = M @ q (vectors are unit-norm) ----
    // cuBLAS is column-major; we treat d_M as a (D, N_CANDIDATES) column-
    // major matrix, which is the same memory as a (N_CANDIDATES, D) row-
    // major matrix. sgemv with op=N then computes scores = M^T_col @ q,
    // which equals M_row @ q — exactly what we want.
    const float alpha = 1.f, beta = 0.f;
    CB(cublasSgemv(cublas, CUBLAS_OP_T,
                   D, N_CANDIDATES,
                   &alpha, d_M, D,
                   d_q, 1,
                   &beta, d_scores, 1));

    // ---- Argmax ----
    argmax_small<<<1, 1>>>(d_scores, N_CANDIDATES, d_argmax);

    int winner_idx = -1;
    CK(cudaMemcpy(&winner_idx, d_argmax, sizeof(int), cudaMemcpyDeviceToHost));
    CK(cudaDeviceSynchronize());

    // ---- Final lookup is host-side: vector -> string ----
    printf("%s\n", phrase_names[winner_idx]);

    cudaFree(d_M); cudaFree(d_q); cudaFree(d_scores); cudaFree(d_argmax);
    cublasDestroy(cublas);
    return 0;
}
