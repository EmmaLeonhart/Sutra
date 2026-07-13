"""AST -> PyTorch/CUDA Python source translator.

The GPU path. Emits self-contained Python modules that depend only on
torch (numpy is still imported for a single bridge at ingestion time —
Ollama hands us lists of floats and we construct tensors from them).
Ops run as torch tensors; when CUDA is available the module picks
`cuda` as its device automatically, falling back to `cpu` otherwise.

Relationship to the CPU codegen:

    BaseCodegen                     ← backend-agnostic AST walker
        └── Codegen                 ← canonical CPU path (numpy ndarrays)
                └── PyTorchCodegen  ← GPU path (torch tensors)

PyTorchCodegen inherits the translator from `Codegen` (same AST walk,
same bundle-of-binds fusion, same vector-accessor lowering, same
extended-state-vector layout) and only overrides the prelude so the
emitted runtime class is `_TorchVSA` operating on tensors. The fused
shapes that the simplifier and codegen produce (stacked Q matmul via
einsum, stacked candidate matmul for argmax_cosine) collapse O(N)
small kernel launches into O(1) large ones on GPU — which is the
reason this backend exists.

Extended state vector and canonical axis allocation are preserved
exactly: every tensor is `[semantic (semantic_dim) | synthetic
(synthetic_dim)]`, bind rotation is block-diagonal with identity on
the synthetic block, `synthetic[0..2]` are the canonical real/imag/
truth axes per the 2026-04-23 design.
"""

from __future__ import annotations

from . import ast_nodes as ast
from .codegen_base import CodegenNotSupported
from .codegen import Codegen


class PyTorchCodegen(Codegen):
    """Emits a self-contained torch module.

    Inherits the entire translator from `Codegen` and only overrides the
    prelude. Vector accessor methods (`.component()`, `.real()`, etc.)
    still route through `_VSA.*` calls — the runtime method names match
    the CPU codegen so the translator needs no divergence.

    Bool literal lowering is inherited from `Codegen` (true/false →
    make_truth(±1)); logical ops (`!`, `&&`, `||`) likewise inherit the
    base override and resolve against the torch runtime's make_truth /
    _as_truth_vector.
    """

    # The torch runtime carries the numeric↔truth cast helpers
    # (cast_number_to_truth / cast_truth_to_number / _cnum), so `(Type)`
    # cast lowering is live on this backend (types.md § Casting).
    supports_cast_lowering = True

    # The torch runtime carries the substrate String ops (make_string /
    # string_concat), so InterpolatedString lowering is live here.
    supports_string_runtime = True

    # The numpy `Codegen` lists the immutable list ops (array_concat /
    # array_map / array_filter) as unsupported — it has no runtime methods
    # for them. The PyTorch runtime DOES implement them (Emma 2026-06-20),
    # so drop them from the unsupported set on this backend. snap /
    # make_rotation / compile_prototypes / geometric_loop remain
    # unsupported on both backends.
    _UNSUPPORTED_BUILTINS = Codegen._UNSUPPORTED_BUILTINS - frozenset({
        "array_concat",
        "array_map",
        "array_filter",
    })

    def _is_pytorch_backend(self) -> bool:
        """Override: this backend emits torch tensor ops, so try/catch
        uses _torch.tanh for the polarizer."""
        return True

    def _arith_op_src(self, expr, op: str,
                      left_src: str, right_src: str) -> str:
        """Lower `+ - * /` on number-axis operands to the substrate
        number-axis runtime methods (num_add / num_sub / num_mul /
        num_div).

        queue §C "all numbers on the substrate": int / number / scalar
        arithmetic is a substrate operation on the canonical number axis
        (AXIS_REAL), NOT host Python float arithmetic. The runtime
        methods coerce both operands onto the real axis and compute
        there, returning a clean number-vector tensor — substrate-pure,
        no `.item()` mid-computation. See `make_real` / `num_*` in the
        prelude.
        """
        method = self._ARITH_OP_METHODS[op]
        return f"_VSA.{method}({left_src}, {right_src})"

    def _emit_select_helper(self) -> None:
        """Torch-based softmax for the Sutra `select` primitive.

        Same numerical shape as the numpy version (subtract max for
        stability, exp, normalize, weighted sum), all on tensors so the
        whole path stays on the chosen device.
        """
        self._emit("def _select_softmax(scores, options):")
        self._indent += 1
        self._emit('"""Softmax-weighted superposition of option vectors (torch)."""')
        # _torch.as_tensor on a Python list of 0-d grad-tracked tensors
        # detaches them (forces scalar conversion). Use _torch.stack on
        # tensor scores so the autograd graph survives — required for
        # the select-T constrain-train ship (task #21). Non-tensor
        # scores (raw Python numbers) still go through as_tensor.
        self._emit("if scores and _torch.is_tensor(scores[0]):")
        self._indent += 1
        self._emit("s = _torch.stack([sc.to(dtype=_DTYPE, device=_DEVICE) for sc in scores])")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("s = _torch.as_tensor(scores, dtype=_DTYPE, device=_DEVICE)")
        self._indent -= 1
        # Numbers-on-substrate: an arithmetic score expression (e.g.
        # `-1000*(pos-t)^2`) is now a real-axis number-VECTOR — the scalar
        # value on AXIS_REAL, zeros elsewhere (num_add/sub/mul/div) — not a
        # 0-d scalar. Stacking N of those gives a 2-D (N, d) tensor, which
        # would make `(w[:,None]*opts).sum(0)` collapse to a 2-D result (a
        # broken role for unbind). Project each score onto its AXIS_REAL
        # component to recover the N scalar weights the softmax needs. This
        # is a substrate tensor slice (NOT a host `.item()`), so autograd
        # survives — the select-T constrain-train path stays differentiable.
        # 0-d scalar scores stack to 1-D (N,) and skip the projection.
        self._emit("if s.ndim == 2:")
        self._indent += 1
        self._emit("s = s[:, _VSA.semantic_dim + _VSA.AXIS_REAL]")
        self._indent -= 1
        self._emit("s = s - _torch.amax(s)")
        self._emit("w = _torch.exp(s)")
        self._emit("w = w / _torch.sum(w)")
        # Options get the MIRROR normalization of the scores fix above
        # (2026-07-13 reach-audit): a 0-d / host-scalar option (e.g.
        # `select([...], [e, best])` with int-typed loop state) used to
        # stack to a 1-D (N,) opts, and `(w[:, None] * opts)` broadcast
        # (N,1)x(N,) into (N,N) — .sum(dim=0) then returned an N-element
        # garbage "value" (measured: best became tensor([3., 0.])).
        # `_VSA._cnum` lifts a scalar onto the real axis as a d-dim
        # number-vector and passes an already-d-dim option (String /
        # vector / number-vector) through untouched, so the blend below
        # is uniformly (N, d) -> (d,) and d-dim options are bit-identical
        # to the old path.
        self._emit("opts = _torch.stack([")
        self._indent += 1
        self._emit("_VSA._cnum(_torch.as_tensor(o, dtype=_DTYPE, device=_DEVICE))")
        self._emit("for o in options")
        self._indent -= 1
        self._emit("])")
        self._emit("return (w[:, None] * opts).sum(dim=0)")
        self._indent -= 1

    def _translate_var_decl_zero_init(self, decl):  # pragma: no cover — helper
        # Not actually used by the parent directly; the parent inlines
        # the `_np.zeros(_VSA.dim)` string. We patch at translate time
        # by string replacement below.
        pass

    def translate(self, module: ast.Module) -> str:
        """Translate and then patch any `_np.zeros(_VSA.dim)` emissions.

        The parent class hard-codes `_np.zeros(_VSA.dim)` for
        uninitialized-vector declarations. The pytorch backend has no
        `_np` symbol in scope, so any such emission would crash at
        module init. We post-process the output to swap those specific
        string occurrences to the torch equivalent. Everything else is
        emitted directly as torch via `_emit_prelude`.

        Then optionally appends a `torch.compile` wrapping block for
        every loop function. Gated on env var SUTRA_TORCH_COMPILE=1 —
        default off because the first call pays a graph-capture cost
        that dwarfs the runtime for tiny loops; opt-in for the cases
        where the speedup pays back the warmup.
        """
        out = super().translate(module)
        out = out.replace(
            "_np.zeros(_VSA.dim)",
            "_torch.zeros(_VSA.dim, dtype=_DTYPE, device=_DEVICE)",
        )
        # Append torch.compile wrapping for each loop function. Each
        # wrap is guarded by env var SUTRA_TORCH_COMPILE. The wrap
        # fuses the T-step soft-halt cell + body tensor ops into a
        # single graph; substantial speedup on GPU for hot loops, but
        # graph-capture overhead can dominate cold-start for small T.
        if self._loop_decls:
            wrap_lines = [
                "",
                "",
                "# Optional torch.compile wrapping for loop functions.",
                "# Enable via SUTRA_TORCH_COMPILE=1.",
                "import os as _sutra_compile_os",
                "if _sutra_compile_os.environ.get('SUTRA_TORCH_COMPILE'):",
                "    try:",
            ]
            for loop_name in self._loop_decls.keys():
                # backend='eager' does graph capture (Dynamo trace) without
                # requiring Triton. The default 'inductor' backend produces
                # fused CUDA kernels but needs Triton, which isn't bundled
                # in standard torch installs. Eager is correct + portable;
                # users who want fused kernels can rebuild with Triton and
                # set SUTRA_TORCH_COMPILE_BACKEND=inductor.
                # Class-bodied loops have dotted registry keys
                # (`Greeter.run`); the emitted Python identifier mangles
                # `.` to `_` so it's a valid Python attribute name.
                py_loop_name = f"_loop_{loop_name.replace('.', '_')}"
                wrap_lines.append(
                    f"        {py_loop_name} = _torch.compile("
                    f"{py_loop_name}, "
                    f"backend=_sutra_compile_os.environ.get("
                    f"'SUTRA_TORCH_COMPILE_BACKEND', 'eager'))"
                )
            wrap_lines.extend([
                "    except Exception:",
                "        pass  # torch.compile not available or trace failed",
                "",
            ])
            out = out + "\n".join(wrap_lines)
        return out

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen_pytorch. Do not edit by hand."""')
        self._emit("from __future__ import annotations")
        self._emit()
        self._emit("import torch as _torch")
        self._emit()
        self._emit("# Pick device and dtype once at module import. CUDA is preferred")
        self._emit("# because the whole reason for this backend is to collapse the")
        self._emit("# fused bind / bundle / argmax_cosine shapes into single big")
        self._emit("# kernel launches on GPU. CPU fallback keeps the module usable")
        self._emit("# on machines without CUDA — the numerics are identical.")
        self._emit("_DEVICE = _torch.device('cuda' if _torch.cuda.is_available() else 'cpu')")
        self._emit("# float32 on GPU is the fast path; keep dtype consistent across")
        self._emit("# every tensor so einsum / matmul don't trigger implicit upcasts.")
        self._emit("# Selectable via Codegen(runtime_dtype=...): float64 extends the")
        self._emit("# exact-integer range on the real/synthetic axis from ~2^24 to 2^53.")
        self._emit(f"_DTYPE = _torch.{self._runtime_dtype}")
        self._emit()
        self._emit()
        self._emit("class SutraMathOverflow(Exception):")
        self._indent += 1
        self._emit('"""RETAINED FOR BACKWARD COMPATIBILITY — no longer raised.')
        self._emit('')
        self._emit('The 2026-05-10 design raised this when a transcendental input')
        self._emit('fell outside the lookup-table range. That was a substrate')
        self._emit('leak (a host `if`/`raise` on a scalar pulled off the')
        self._emit('substrate) AND a violation of the core "no runtime errors')
        self._emit('by mechanism" rule. Out-of-range now saturates at the table')
        self._emit('edge via a tensor clamp — the mathematically-valid limit.')
        self._emit('The class is kept so existing `except SutraMathOverflow`')
        self._emit('sites still import; it is simply never thrown anymore.')
        self._emit('"""')
        self._emit("pass")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit("class _TorchVSA:")
        self._indent += 1
        self._emit('"""Torch-backed VSA runtime. Rotation binding, normalized bundle.')
        self._emit('')
        self._emit('State tensors carry the extended layout:')
        self._emit('`[semantic (semantic_dim) | synthetic (synthetic_dim)]`. The')
        self._emit('semantic block is filled by `embed()` from the frozen LLM; the')
        self._emit('synthetic block is reserved computational/symbolic space with')
        self._emit('canonical axes at synthetic[0..2] (real, imag, truth). See')
        self._emit('planning/findings/2026-04-21-extended-state-and-rotation-binding.md.')
        self._emit('')
        self._emit('Bind is role-seeded Haar-random orthogonal rotation applied to')
        self._emit('filler: bind(filler, role) = Q_role @ filler. The rotation is')
        self._emit('block-diagonal — Haar in the semantic block, identity in the')
        self._emit('synthetic block — so rotation acts only on semantic content and')
        self._emit('the synthetic block is preserved through bind/unbind.')
        self._emit('"""')
        self._emit()
        self._emit("# Canonical synthetic-axis allocation — real, imag, truth at")
        self._emit("# synthetic[0..2], string-flag at synthetic[3], loop-done at")
        self._emit("# synthetic[4]. Mirrored from the CPU runtime so the two agree")
        self._emit("# bit-for-bit on layout. AXIS_LOOP_DONE is the substrate-side")
        self._emit("# completion flag set by the RNN-style branchless loop.")
        self._emit("# AXIS_STRING_FLAG marks a vector as a String value (a")
        self._emit("# packed array of codepoints — 1-character strings are the")
        self._emit("# new home for what was formerly the `char` type). See")
        self._emit("# planning/sutra-spec/strings.md.")
        self._emit("AXIS_REAL = 0")
        self._emit("AXIS_IMAG = 1")
        self._emit("AXIS_TRUTH = 2")
        self._emit("AXIS_STRING_FLAG = 3")
        self._emit("# Backwards-compat alias for code that still references")
        self._emit("# AXIS_CHAR_FLAG. New code should use AXIS_STRING_FLAG.")
        self._emit("AXIS_CHAR_FLAG = 3")
        self._emit("AXIS_LOOP_DONE = 4")
        self._emit("# Promise channel axes — see planning/sutra-spec/promises.md")
        self._emit("# §'The three states' and planning/sutra-spec/axon-io.md.")
        self._emit("# A Promise is a vector with one of these flags set; a")
        self._emit("# pending promise has both at 0 and is still actively")
        self._emit("# cycling (per the eigenrotation-as-active-heartbeat rule).")
        self._emit("AXIS_PROMISE_FULFILLED = 5")
        self._emit("AXIS_PROMISE_REJECTED = 6")
        self._emit("# Axon populated flag — producers writing a genuinely-zero")
        self._emit("# value (int 0, trit unknown) set this to 1.0 so the consumer's")
        self._emit("# `arrived?` check distinguishes a zero resolution from `not")
        self._emit("# yet arrived`. See planning/sutra-spec/axon-io.md §'The")
        self._emit("# all-zeros edge case'.")
        self._emit("AXIS_AXON_POPULATED = 7")
        self._emit()
        self._emit("def __init__(self, semantic_dim, synthetic_dim, seed, llm_model):")
        self._indent += 1
        self._emit("self.semantic_dim = semantic_dim")
        self._emit("self.synthetic_dim = synthetic_dim")
        self._emit("self.dim = semantic_dim + synthetic_dim")
        self._emit("self.seed = seed")
        self._emit("self.llm_model = llm_model")
        self._emit("self.device = _DEVICE")
        self._emit("self.dtype = _DTYPE")
        self._emit("self._codebook = {}")
        self._emit("# FV key-usage trace (OFF by default = None -> zero hot-path")
        self._emit("# cost). Set to {'read': set(), 'bound': set()} to record the")
        self._emit("# axon keys touched at runtime, for the formal-verification")
        self._emit("# key-soundness check (runtime keys subset of static AXON_KEYS_*).")
        self._emit("# Monitoring only: a host-side set.add of a compile-time key")
        self._emit("# string around the substrate op, never inside the tensor math.")
        self._emit("self._fv_key_trace = None")
        self._emit("# load_matrix path -> frozen 2-D tensor (file-backed matrix")
        self._emit("# constants are read once and reused; see load_matrix).")
        self._emit("self._matrix_cache = {}")
        self._emit("# Optional external RAM device (planning/sutra-spec/ram-pointers.md):")
        self._emit("# a host-attached list of number-vectors that ram_read/ram_write")
        self._emit("# bridge to. None until the host (orchestrator) attaches one.")
        self._emit("self.ram = None")
        self._emit("# Rotation matrix cache: role-hash -> tensor on self.device.")
        self._emit("# Generating a 768x768 Haar rotation is O(d^3) on CPU (seeded")
        self._emit("# via numpy for Haar-uniformity). Cached on the GPU after the")
        self._emit("# first draw so repeated bind/unbind with the same role is a")
        self._emit("# lookup + one matmul, no transfer.")
        self._emit("self._rot_cache = {}")
        self._emit("# Bound the d x d role-keyed caches (_rot_cache + _axon_op_cache)")
        self._emit("# so a program with a pathologically large axon-key / role vocabulary")
        self._emit("# cannot grow them without limit (each entry is a d x d tensor, ~6MB")
        self._emit("# at d=868 float64). FIFO eviction (oldest-built first), NOT move-to-")
        self._emit("# end LRU, to keep ZERO extra Python on the cache-hit hot path the")
        self._emit("# perf work optimized (finding 2026-06-20). Eviction is correctness-")
        self._emit("# safe: every value is a deterministic function of its key (seeded Haar")
        self._emit("# rotation / fixed permutation), so a recomputed entry is bit-identical")
        self._emit("# to the evicted one. The cap is generous: real programs use a handful")
        self._emit("# to a few dozen distinct keys, far under it, so they never evict and")
        self._emit("# are unaffected; only pathological key sets trade recompute for memory.")
        self._emit("self._role_cache_cap = 1024")
        self._emit("# On-disk embedding cache. Keyed by (model, dim) so switching")
        self._emit("# embedding model OR changing the extended-state dim invalidates")
        self._emit("# automatically (different filename). Torch cache uses .pt so")
        self._emit("# it doesn't collide with the numpy backend's .npz.")
        self._emit("import os as _os")
        self._emit("self._cache_dir = _os.path.join(")
        self._indent += 1
        self._emit("_os.environ.get('XDG_CACHE_HOME', _os.path.expanduser('~/.cache')),")
        self._emit("'sutra', 'embeddings')")
        self._indent -= 1
        self._emit("_os.makedirs(self._cache_dir, exist_ok=True)")
        self._emit("_safe_model = llm_model.replace('/', '_').replace(':', '_')")
        self._emit("# Backend-aware: in-process (transformers) and ollama realize the")
        self._emit("# same model with slightly different geometry, so they must not")
        self._emit("# share a cache file or one backend reads the other's vectors.")
        self._emit("_emb_backend = _os.environ.get('SUTRA_EMBED_BACKEND', 'auto').strip().lower() or 'auto'")
        self._emit("self._cache_path = _os.path.join(")
        self._indent += 1
        self._emit("self._cache_dir, f'{_safe_model}-d{self.dim}-{_emb_backend}.pt')")
        self._indent -= 1
        self._emit("self._load_disk_cache()")
        self._emit("# Transcendental lookup codebooks — read by _lerp's crosstalk")
        self._emit("# kernel into continuous functions (the rotational-binding")
        self._emit("# readout). Stored as constants so every call reuses the same")
        self._emit("# tensor (no per-call rebuild). Out-of-range inputs SATURATE")
        self._emit("# at the table edge via tensor clamp — never a host raise.")
        self._emit("# N=16384 chosen empirically: drops pow(2,10) from ~1% error to")
        self._emit("# ~0.06% by tightening the log-table dx 4x. Memory cost is tiny")
        self._emit("# (4 * 16384 * 4 bytes per table). True precision fix is range-")
        self._emit("# reduction (ln(x) = ln(x/2^k) + k*ln(2)) — follow-on, not MVP.")
        self._emit("self._EXP_LO, self._EXP_HI, self._EXP_N = -10.0, 10.0, 16384")
        self._emit("self._EXP_XS = _torch.linspace(self._EXP_LO, self._EXP_HI, self._EXP_N, dtype=self.dtype, device=self.device)")
        self._emit("self._EXP_VALUES = _torch.exp(self._EXP_XS)")
        self._emit("self._EXP_DX = (self._EXP_HI - self._EXP_LO) / (self._EXP_N - 1)")
        self._emit("self._LN_LO, self._LN_HI, self._LN_N = 1e-3, 1e3, 16384")
        self._emit("self._LN_XS = _torch.linspace(self._LN_LO, self._LN_HI, self._LN_N, dtype=self.dtype, device=self.device)")
        self._emit("self._LN_VALUES = _torch.log(self._LN_XS)")
        self._emit("self._LN_DX = (self._LN_HI - self._LN_LO) / (self._LN_N - 1)")
        self._emit("# Trig tables — same architecture, periodic so modulo-reduce")
        self._emit("# the input to [-π, π] before lookup. No overflow exception")
        self._emit("# because every real input maps in-range. cos shares the table")
        self._emit("# layout via cos(x) = sin(x + π/2) — but we store both for")
        self._emit("# clarity and a single fused matvec per call.")
        self._emit("import math as _math")
        self._emit("self._TRIG_LO, self._TRIG_HI, self._TRIG_N = -_math.pi, _math.pi, 4096")
        self._emit("self._TRIG_XS = _torch.linspace(self._TRIG_LO, self._TRIG_HI, self._TRIG_N, dtype=self.dtype, device=self.device)")
        self._emit("self._SIN_VALUES = _torch.sin(self._TRIG_XS)")
        self._emit("self._COS_VALUES = _torch.cos(self._TRIG_XS)")
        self._emit("self._TRIG_DX = (self._TRIG_HI - self._TRIG_LO) / (self._TRIG_N - 1)")
        self._emit("self._TWO_PI = 2.0 * _math.pi")
        self._emit("# Math namespace constants. PI and TAU = 2*PI are true scalars.")
        self._emit("# E is NOT cached here — every Math.E reference beta-reduces at")
        self._emit("# the call site to `_VSA.exp(1.0)`, so the substrate's lookup")
        self._emit("# table is visibly the source of E (Emma 2026-05-10).")
        self._emit("self.PI = float(_math.pi)")
        self._emit("self.TAU = 2.0 * float(_math.pi)")
        self._indent -= 1
        self._emit()
        self._emit("def _load_disk_cache(self):")
        self._indent += 1
        self._emit('"""Populate self._codebook from disk if the cache file exists.')
        self._emit('')
        self._emit("Tolerant of missing or corrupt files — a failed load just leaves")
        self._emit("the codebook empty and lets Ollama repopulate it.")
        self._emit('"""')
        self._emit("import os as _os")
        self._emit("if not _os.path.exists(self._cache_path):")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("try:")
        self._indent += 1
        self._emit("data = _torch.load(self._cache_path, map_location=self.device, weights_only=True)")
        self._emit("for key, tensor in data.items():")
        self._indent += 1
        self._emit("self._codebook[key] = tensor.to(dtype=self.dtype)")
        self._indent -= 1
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("# Corrupt cache: ignore and let Ollama repopulate.")
        self._emit("self._codebook = {}")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def _write_disk_cache(self):")
        self._indent += 1
        self._emit('"""Persist self._codebook to disk via tempfile + atomic rename.')
        self._emit('')
        self._emit("A partial write (crash, SIGKILL) leaves the old cache intact")
        self._emit("rather than corrupted.")
        self._emit('"""')
        self._emit("import os as _os, tempfile as _tempfile")
        self._emit("if not self._codebook:")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("fd, tmp = _tempfile.mkstemp(")
        self._indent += 1
        self._emit("dir=self._cache_dir, prefix='.tmp-', suffix='.pt')")
        self._indent -= 1
        self._emit("_os.close(fd)")
        self._emit("try:")
        self._indent += 1
        self._emit("# Save tensors on CPU so the cache file is portable — the")
        self._emit("# next run can load on any device. Reload will move them.")
        self._emit("cpu_codebook = {k: v.detach().cpu() for k, v in self._codebook.items()}")
        self._emit("_torch.save(cpu_codebook, tmp)")
        self._emit("_os.replace(tmp, self._cache_path)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("try:")
        self._indent += 1
        self._emit("_os.unlink(tmp)")
        self._indent -= 1
        self._emit("except OSError:")
        self._indent += 1
        self._emit("pass")
        self._indent -= 1
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def embed(self, name):")
        self._indent += 1
        self._emit('"""Frozen-LLM embedding via Ollama. Returns a tensor on self.device.')
        self._emit('')
        self._emit("Extended-state layout: `[semantic (semantic_dim) | zeros (synthetic_dim)]`.")
        self._emit("No random fallback — if Ollama is unavailable this raises.")
        self._emit('"""')
        self._emit("if name not in self._codebook:")
        self._indent += 1
        self._emit("if self.llm_model in (None, 'none', ''): raise RuntimeError("
                   "\"embed(\" + repr(name) + \") needs an embedding model, but \""
                   " \"compile_su llm_model is 'none'. Pass "
                   "llm_model='nomic-embed-text' to embed semantic content; \""
                   " \"programs using only make_real / matrices / arithmetic "
                   "need no model.\")")
        self._emit("from sutra_compiler.embedding import embed_texts as _embed_texts")
        self._emit("r = _embed_texts([name], self.llm_model)")
        self._emit("v = _torch.tensor(r[0], dtype=self.dtype, device=self.device)")
        self._emit("# Mean-center; raw LLM embeddings cluster in a cone and centering")
        self._emit("# keeps rotation/bind algebra well-behaved.")
        self._emit("v = v - _torch.mean(v)")
        self._emit("n = _torch.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("# Fit to semantic block.")
        self._emit("if v.shape[0] > self.semantic_dim:")
        self._indent += 1
        self._emit("v = v[:self.semantic_dim]")
        self._indent -= 1
        self._emit("elif v.shape[0] < self.semantic_dim:")
        self._indent += 1
        self._emit("pad = _torch.zeros(self.semantic_dim - v.shape[0], dtype=self.dtype, device=self.device)")
        self._emit("v = _torch.cat([v, pad])")
        self._indent -= 1
        self._emit("# Append synthetic block — reserved, starts zero.")
        self._emit("syn = _torch.zeros(self.synthetic_dim, dtype=self.dtype, device=self.device)")
        self._emit("v = _torch.cat([v, syn])")
        self._emit("n = _torch.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("self._codebook[name] = v")
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit("return self._codebook[name].clone()")
        self._indent -= 1
        self._emit()
        self._emit("def embed_batch(self, names):")
        self._indent += 1
        self._emit('"""Batched Ollama embed: one HTTP round-trip for many names.')
        self._emit('')
        self._emit("Same layout as embed(). Writes back to disk once after all")
        self._emit("fetches to amortize the save.")
        self._emit('"""')
        self._emit("missing = [n for n in names if n not in self._codebook]")
        self._emit("if not missing:")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("if self.llm_model in (None, 'none', ''): raise RuntimeError("
                   "\"embed_batch needs an embedding model, but compile_su \""
                   " \"llm_model is 'none'. Pass llm_model='nomic-embed-text' "
                   "to embed semantic content; programs using only make_real / \""
                   " \"matrices / arithmetic need no model. Tried: \" + repr(missing))")
        self._emit("from sutra_compiler.embedding import embed_texts as _embed_texts")
        self._emit("r = _embed_texts(missing, self.llm_model)")
        self._emit("for i, name in enumerate(missing):")
        self._indent += 1
        self._emit("v = _torch.tensor(r[i], dtype=self.dtype, device=self.device)")
        self._emit("v = v - _torch.mean(v)")
        self._emit("n = _torch.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("if v.shape[0] > self.semantic_dim:")
        self._indent += 1
        self._emit("v = v[:self.semantic_dim]")
        self._indent -= 1
        self._emit("elif v.shape[0] < self.semantic_dim:")
        self._indent += 1
        self._emit("pad = _torch.zeros(self.semantic_dim - v.shape[0], dtype=self.dtype, device=self.device)")
        self._emit("v = _torch.cat([v, pad])")
        self._indent -= 1
        self._emit("syn = _torch.zeros(self.synthetic_dim, dtype=self.dtype, device=self.device)")
        self._emit("v = _torch.cat([v, syn])")
        self._emit("n = _torch.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("self._codebook[name] = v")
        self._indent -= 1
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Embedded SutraDB (compile-time string codebook) ----")
        self._emit("# Every embedded string in a Sutra program goes into SutraDB")
        self._emit("# at compile time. The embeddings live in the .sdb file SutraDB")
        self._emit("# manages, not in the Python module's data section. The runtime")
        self._emit("# decodes a query vector back to a string via nearest_string()")
        self._emit("# (the inverse of embed()). Strings declared but not used in")
        self._emit("# expressions are still inserted so they remain decodable.")
        self._emit()
        self._emit("def _ensure_sutradb(self):")
        self._indent += 1
        self._emit('"""Lazy-init the SutraDB handle on first use. Returns None if the')
        self._emit("FFI DLL isn't built (caller decides what to do).")
        self._emit('')
        self._emit("Path resolution:")
        self._emit("  1. env var SUTRA_DB_PATH if set (persistent across runs)")
        self._emit("  2. else a tempdir (ephemeral; freed at process exit)")
        self._emit('')
        self._emit("Full atman.toml [vector_db] section is deferred until there's a")
        self._emit("concrete config requirement — env var covers the immediate")
        self._emit("'persistent codebook' use case.")
        self._emit('"""')
        self._emit("if hasattr(self, '_sutradb') and self._sutradb is not None:")
        self._indent += 1
        self._emit("return self._sutradb")
        self._indent -= 1
        self._emit("try:")
        self._indent += 1
        self._emit("import importlib, tempfile, os as _os2")
        self._emit("mod = importlib.import_module('sutra_compiler.sutradb_embedded')")
        self._emit("env_path = _os2.environ.get('SUTRA_DB_PATH')")
        self._emit("if env_path:")
        self._indent += 1
        self._emit("path = env_path")
        self._emit("self._sutradb_tmpdir = None")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("self._sutradb_tmpdir = tempfile.mkdtemp(prefix='sutra_codebook_')")
        self._emit("path = _os2.path.join(self._sutradb_tmpdir, 'codebook.sdb')")
        self._indent -= 1
        self._emit("self._sutradb = mod.SutraDBEmbedded(path)")
        self._emit("return self._sutradb")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("self._sutradb = None  # mark attempted-and-failed")
        self._emit("return None")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def populate_sutradb(self):")
        self._indent += 1
        self._emit('"""Push every codebook entry into SutraDB.')
        self._emit('')
        self._emit("Called from the codegen prelude after embed_batch finishes")
        self._emit("populating self._codebook. Each (name, vec) becomes a triple")
        self._emit('<urn:sutra:label:NAME> <urn:sutra:embedding> "VEC"^^<f32vec> .')
        self._emit('"""')
        self._emit("db = self._ensure_sutradb()")
        self._emit("if db is None:")
        self._indent += 1
        self._emit("return  # FFI unavailable; nearest_string will return None")
        self._indent -= 1
        self._emit("for name, vec in self._codebook.items():")
        self._indent += 1
        self._emit("# Skip non-URL-safe characters in label by URL-quoting.")
        self._emit("import urllib.parse as _urllib_parse")
        self._emit("safe = _urllib_parse.quote(name, safe='')")
        self._emit("vec_list = vec.tolist() if hasattr(vec, 'tolist') else list(vec)")
        self._emit("try:")
        self._indent += 1
        self._emit("db.add(safe, vec_list)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("pass  # one bad insert shouldn't kill the rest")
        self._indent -= 1
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def prewarm_rotation_cache(self):")
        self._indent += 1
        self._emit('"""Pre-compute rotation matrices for every codebook entry.')
        self._emit('')
        self._emit("The runtime never pays the QR construction cost on the hot")
        self._emit("path: pre-warming at module init means every bind/unbind hits")
        self._emit("the cache. Conservative over the codebook (some entries are")
        self._emit("fillers, not roles); the cost is one-time and proportional")
        self._emit("to codebook size.")
        self._emit('"""')
        self._emit("for name, vec in self._codebook.items():")
        self._indent += 1
        self._emit("try:")
        self._indent += 1
        self._emit("self._rotation_for(vec)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("pass  # one bad rotation shouldn't kill the rest")
        self._indent -= 1
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit("def nearest_string(self, query):")
        self._indent += 1
        self._emit('"""Inverse of embed(): given a query vector, return the nearest')
        self._emit("string from the compile-time-populated SutraDB codebook. None")
        self._emit("if SutraDB is unavailable. The query vector is the full extended-")
        self._emit("state vector; only the semantic block is consulted by SutraDB.")
        self._emit('"""')
        self._emit("db = self._ensure_sutradb()")
        self._emit("if db is None:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("q_list = query.tolist() if hasattr(query, 'tolist') else list(query)")
        self._emit("try:")
        self._indent += 1
        self._emit("labels = db.nearest(q_list, k=1)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("if not labels:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("import urllib.parse as _urllib_parse")
        self._emit("return _urllib_parse.unquote(labels[0])")
        self._indent -= 1
        self._emit()
        self._emit("def _role_hash(self, role_vec, role_key=None):")
        self._indent += 1
        self._emit('"""Deterministic uint32 seed from a role tensor.')
        self._emit('')
        self._emit("Computed from the CPU bytes of the tensor so numerical bit-")
        self._emit("identity across runs gives the same rotation.")
        self._emit('')
        self._emit("Bytes via `.view(torch.uint8)` + `bytes()` — pure torch, no")
        self._emit("numpy. The previous `.numpy().tobytes()` form pulled numpy")
        self._emit("onto the runtime hot path (this method is called every")
        self._emit("bind() — including cache hits — to compute the rot_cache")
        self._emit("key), which violated the 'numpy is compile-and-monitor only,")
        self._emit("never on the runtime hot path' rule in CLAUDE.md.")
        self._emit('')
        self._emit("When the caller knows the role's KEY STRING (axon_add / axon_item")
        self._emit("/ a keyed bind), pass `role_key` to MEMOIZE the hash by that")
        self._emit("string: embed(key) is deterministic, so the hash is a pure")
        self._emit("function of the key, and the memo skips the per-call .cpu()")
        self._emit("transfer + tolist that otherwise dominates a binding tick (the")
        self._emit("next hot-spot after the .tolist() fix; finding 2026-06-20).")
        self._emit("role_key=None (bind/unbind builtins, bundle) computes from the")
        self._emit("vector as before. The memo is keyed by string only, so a wrong")
        self._emit("key cannot collide a different vector onto a cached hash.")
        self._emit('"""')
        self._emit("if role_key is not None:")
        self._indent += 1
        self._emit("if not hasattr(self, '_role_hash_by_key'):")
        self._indent += 1
        self._emit("self._role_hash_by_key = {}")
        self._indent -= 1
        self._emit("_cached = self._role_hash_by_key.get(role_key)")
        self._emit("if _cached is not None:")
        self._indent += 1
        self._emit("return _cached")
        self._indent -= 1
        self._indent -= 1
        self._emit("import hashlib")
        self._emit("# View as uint8 reinterprets the underlying bytes without copying,")
        self._emit("# then `.tolist()` (a torch C++ bulk conversion, NOT numpy and NOT")
        self._emit("# element-wise Python) materializes them; `bytes(list_of_ints)` is")
        self._emit("# the hashable buffer. IDENTICAL bytes to `bytes(tensor.view(uint8))`")
        self._emit("# (verified) — but ~66x faster: `bytes(tensor)` calls the tensor's")
        self._emit("# `__iter__`, which `unbind`s the d-vector into d 0-d tensors")
        self._emit("# (~6.4ms/call at dim 868); `.tolist()` is ~0.1ms. This method runs")
        self._emit("# 6x per axon_add tick to compute the rotation/permutation cache keys")
        self._emit("# (it was measured at 98% of the per-tick runtime — finding")
        self._emit("# 2026-06-20-tick-all-no-speedup-python-bound.md). Still no numpy on")
        self._emit("# the path (the prior .numpy().tobytes() removal stands); just not the")
        self._emit("# pathologically slow per-element iteration `bytes(tensor)` introduced.")
        self._emit("b = bytes(role_vec.detach().cpu().contiguous().view(_torch.uint8).tolist())")
        self._emit("h = hashlib.blake2b(b, digest_size=8).digest()")
        self._emit("_val = int.from_bytes(h, 'little') & 0xFFFFFFFF")
        self._emit("if role_key is not None:")
        self._indent += 1
        self._emit("self._role_hash_by_key[role_key] = _val")
        self._indent -= 1
        self._emit("return _val")
        self._indent -= 1
        self._emit()
        self._emit("def _rotation_for(self, role_vec, role_key=None):")
        self._indent += 1
        self._emit('"""Block-diagonal Haar rotation seeded by the role tensor.')
        self._emit('')
        self._emit("Haar-uniform in the semantic block, identity in the synthetic")
        self._emit("block — same layout as the numpy backend so rotation-binding")
        self._emit("semantics are identical. The Haar draw uses numpy because")
        self._emit("numpy's RandomState(seed) is the canonical bit-reproducible")
        self._emit("generator; we move the result to the torch device before")
        self._emit("caching.")
        self._emit('')
        self._emit("Cached per role-hash so the same role always produces the same")
        self._emit("rotation — required for bind/unbind round-trip.")
        self._emit('"""')
        self._emit("key = self._role_hash(role_vec, role_key)")
        self._emit("if key not in self._rot_cache:")
        self._indent += 1
        self._emit("import numpy as _np_bridge")
        self._emit("rng = _np_bridge.random.RandomState(key)")
        self._emit("A = rng.randn(self.semantic_dim, self.semantic_dim)")
        self._emit("Q_sem_np, R_np = _np_bridge.linalg.qr(A)")
        self._emit("d = _np_bridge.sign(_np_bridge.diag(R_np))")
        self._emit("d[d == 0] = 1.0")
        self._emit("Q_sem_np = Q_sem_np * d")
        self._emit("Q_sem = _torch.as_tensor(Q_sem_np, dtype=self.dtype, device=self.device)")
        self._emit("# Block-diagonal embedding: Q_sem on the semantic block,")
        self._emit("# identity everywhere else.")
        self._emit("Q = _torch.eye(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("Q[:self.semantic_dim, :self.semantic_dim] = Q_sem")
        self._emit("self._rot_cache[key] = Q")
        self._emit("if len(self._rot_cache) > self._role_cache_cap:")
        self._indent += 1
        self._emit("# FIFO evict the oldest-built rotation (deterministic recompute).")
        self._emit("del self._rot_cache[next(iter(self._rot_cache))]")
        self._indent -= 1
        self._indent -= 1
        self._emit("return self._rot_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def bind(self, role, filler, role_key=None):")
        self._indent += 1
        self._emit("# Rotation binding. bind(role, filler) = Q_role @ filler. Role-")
        self._emit("# first convention (matches numpy backend and the .su demos).")
        self._emit("Q = self._rotation_for(role, role_key)")
        self._emit("# Defensively coerce filler to runtime device + dtype so a")
        self._emit("# host-side caller passing a CPU tensor doesn't device-mismatch")
        self._emit("# Q (which lives on self.device). No-op when filler is already")
        self._emit("# on the right device — matches the pattern bundle() uses.")
        self._emit("filler = _torch.as_tensor(filler, dtype=self.dtype, device=self.device)")
        self._emit("return Q @ filler")
        self._indent -= 1
        self._emit()
        self._emit("def unbind(self, role, record, role_key=None):")
        self._indent += 1
        self._emit("# Q is orthogonal so unbind(role, record) = Q_role^T @ record.")
        self._emit("# Round-trip: unbind(r, bind(r, v)) = Q^T @ Q @ v = v exactly.")
        self._emit("Q = self._rotation_for(role, role_key)")
        self._emit("# Same device-coherence defence as bind(): tolerate a CPU")
        self._emit("# record from a host-side caller without crashing.")
        self._emit("record = _torch.as_tensor(record, dtype=self.dtype, device=self.device)")
        self._emit("return Q.T @ record")
        self._indent -= 1
        self._emit()
        self._emit("def bundle(self, *vectors):")
        self._indent += 1
        self._emit("s = _torch.stack([")
        self._indent += 1
        self._emit("_torch.as_tensor(v, dtype=self.dtype, device=self.device)")
        self._emit("for v in vectors")
        self._indent -= 1
        self._emit("]).sum(dim=0)")
        self._emit("n = _torch.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("def zero_vector(self):")
        self._indent += 1
        self._emit('"""Zero vector in the runtime dim. Emitted by simplifier identities."""')
        self._emit("return _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def vector_from_floats(self, values):")
        self._indent += 1
        self._emit('"""Substrate-side tensor literal — bake-back source form for')
        self._emit("trained vector-valued parameters. `values` is a Python list of")
        self._emit("numeric literals emitted by the codegen for a `.su` source line")
        self._emit("`vector v = vector_literal(0.123, -0.045, ...);`. Built on the")
        self._emit('runtime device+dtype; no numpy on the hot path."""')
        self._emit("return _torch.tensor(values, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def matrix_from_rows(self, rows):")
        self._indent += 1
        self._emit('"""Substrate-side 2-D tensor literal — the matrix generalization')
        self._emit("of vector_from_floats. `rows` is a Python list of 1-D row tensors")
        self._emit("(each typically a vector_literal) emitted by the codegen for a")
        self._emit("`.su` source line `matrix M = matrix_literal(row0, row1, ...);`.")
        self._emit("Rows are stacked into an (nrows, ncols) tensor on the runtime")
        self._emit("device+dtype; no numpy on the hot path. Consumed by Tensor.MatrixMul")
        self._emit('(e.g. a frozen permutation matrix for a substrate-RNN advance)."""')
        self._emit("stacked = _torch.stack([_torch.as_tensor(r, dtype=self.dtype, device=self.device) for r in rows], dim=0)")
        self._emit("return stacked")
        self._indent -= 1
        self._emit()
        self._emit("def load_matrix(self, path):")
        self._indent += 1
        self._emit('"""Load a matrix CONSTANT from a CSV file (comma-separated')
        self._emit("floats, one matrix row per line; blank lines and lines starting")
        self._emit("with '#' skipped) into a 2-D tensor on the runtime device+dtype.")
        self._emit("The file-backed form of matrix_literal, for LARGE matrices —")
        self._emit("trained weights in a weights store rather than a giant inline")
        self._emit("literal (Emma 2026-05-29). General path: absolute, or relative to")
        self._emit("the process CWD. Cached by path (it is a frozen constant), so")
        self._emit('repeat calls reuse the loaded tensor. Consumed by Tensor.MatrixMul."""')
        self._emit("if path not in self._matrix_cache:")
        self._indent += 1
        self._emit("rows = []")
        self._emit("with open(path, 'r', encoding='utf-8') as _fh:")
        self._indent += 1
        self._emit("for _line in _fh:")
        self._indent += 1
        self._emit("_line = _line.strip()")
        self._emit("if not _line or _line.startswith('#'): continue")
        self._emit("rows.append([float(_x) for _x in _line.split(',')])")
        self._indent -= 1
        self._indent -= 1
        self._emit("self._matrix_cache[path] = _torch.tensor(rows, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("return self._matrix_cache[path].clone()")
        self._indent -= 1
        self._emit()
        self._emit("def bundle_of_binds(self, *role_filler_pairs):")
        self._indent += 1
        self._emit('"""Fused bind+sum+normalize over N role-filler pairs.')
        self._emit('')
        self._emit("This is the GPU-shaped primitive: stack roles into (N, d, d),")
        self._emit("stack fillers into (N, d), one batched einsum + reduce. On")
        self._emit("CUDA, N small bind+bundle kernel launches collapse into O(1)")
        self._emit("big launches. Same numerics as sequential bind + bundle.")
        self._emit('"""')
        self._emit("if not role_filler_pairs:")
        self._indent += 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit("roles = [rf[0] for rf in role_filler_pairs]")
        self._emit("fillers = [rf[1] for rf in role_filler_pairs]")
        self._emit("Q_stack = _torch.stack([self._rotation_for(r) for r in roles])")
        self._emit("F_stack = _torch.stack([")
        self._indent += 1
        self._emit("_torch.as_tensor(f, dtype=self.dtype, device=self.device)")
        self._emit("for f in fillers")
        self._indent -= 1
        self._emit("])")
        self._emit("# Batched bind: element-i is Q_i @ f_i; shape (N, d).")
        self._emit("bound = _torch.einsum('nij,nj->ni', Q_stack, F_stack)")
        self._emit("s = bound.sum(dim=0)")
        self._emit("n = _torch.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Rotation-hashmap (same shape as numpy backend) ----")
        self._emit()
        self._emit("def hashmap_new(self):")
        self._indent += 1
        self._emit("return _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_set(self, acc, key_vec, val_vec):")
        self._indent += 1
        self._emit("return acc + self.bind(key_vec, val_vec)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_get(self, acc, key_vec):")
        self._indent += 1
        self._emit("return self.unbind(key_vec, acc)")
        self._indent -= 1
        self._emit()
        # ---- Scalar-keyed dict (dict<int,int>) — Emma 2026-06-13 ----
        # Integers get a SEPARATE dict object: a preallocated block of `cap`
        # scalar slots, one synthetic-space dimension per integer key. The
        # rotation-hashmap can't back this (rotations are identity on the
        # synthetic axes where numbers live, so it returns Σ-of-values for every
        # key — measured, finding 2026-06-06-dict-int-keys-broken). Dedicated
        # slots make each key address its own dimension: no rotation, no
        # crosstalk, exact. Addressing is substrate-pure (round + one-hot ==,
        # no host .item()); the compiler routes dict<int,int> here at compile
        # time (key type is statically a scalar).
        self._emit("def int_dict_new(self, cap=256):")
        self._indent += 1
        self._emit('"""A scalar-keyed dict: `cap` preallocated zero slots, one per key."""')
        self._emit("return _torch.zeros(int(cap), dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def _int_dict_axis(self, x):")
        self._indent += 1
        self._emit('"""Real-axis scalar of a number-vector (or a 0-d scalar as-is) —')
        self._emit('a tensor, never a host float (no .item())."""')
        self._emit("xt = self._st(x)")
        self._emit("return xt if xt.ndim == 0 else xt[self.semantic_dim + self.AXIS_REAL]")
        self._indent -= 1
        self._emit()
        self._emit("def _int_dict_onehot(self, d, key):")
        self._indent += 1
        self._emit('"""One-hot selector over the slots for the rounded integer key."""')
        self._emit("k = _torch.round(self._int_dict_axis(key))")
        self._emit("idx = _torch.arange(d.shape[0], dtype=self.dtype, device=self.device)")
        self._emit("return (idx == k).to(self.dtype)")
        self._indent -= 1
        self._emit()
        self._emit("def int_dict_set(self, d, key, val):")
        self._indent += 1
        self._emit('"""Functional update: write val\'s real-axis scalar into the key slot.')
        self._emit('Out-of-range keys select no slot (no-op), like RAM OOB."""')
        self._emit("oh = self._int_dict_onehot(d, key)")
        self._emit("v = self._int_dict_axis(val)")
        self._emit("return d * (1.0 - oh) + v * oh")
        self._indent -= 1
        self._emit()
        self._emit("def int_dict_get(self, d, key):")
        self._indent += 1
        self._emit('"""Read the key slot, lifted to a number-vector (real axis = slot).')
        self._emit('Gather via one-hot dot product; absent/OOB keys read 0."""')
        self._emit("oh = self._int_dict_onehot(d, key)")
        self._emit("slot = (d * oh).sum()")
        self._emit("real_axis = self.semantic_dim + self.AXIS_REAL")
        self._emit("dimmask = (_torch.arange(self.dim, device=self.device) "
                   "== real_axis).to(self.dtype)")
        self._emit("return dimmask * slot")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Promise runtime methods ----")
        self._emit("# Promise<T> is a vector wearing one of two synthetic-axis flags.")
        self._emit("# resolve(v) sets AXIS_PROMISE_FULFILLED to 1; reject(r) sets")
        self._emit("# AXIS_PROMISE_REJECTED to 1. The semantic block carries the")
        self._emit("# resolved value or rejection reason. See planning/sutra-spec/")
        self._emit("# promises.md §'The three states' for the channel semantics.")
        self._emit()
        self._emit("def resolve(self, value):")
        self._indent += 1
        self._emit('"""Promise.resolve(value) — already-fulfilled promise.')
        self._emit("Sets AXIS_PROMISE_FULFILLED on a clone of `value` so the")
        self._emit("input is not mutated. The clone keeps the value vector's")
        self._emit("semantic block; downstream readers see the value back via")
        self._emit("`Promise.value(p)`.")
        self._emit('"""')
        self._emit("v = _torch.as_tensor(value, dtype=self.dtype, device=self.device).clone()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 1.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def reject(self, reason):")
        self._indent += 1
        self._emit('"""Promise.reject(reason) — already-rejected promise."""')
        self._emit("v = _torch.as_tensor(reason, dtype=self.dtype, device=self.device).clone()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 1.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def isFulfilled(self, p):")
        self._indent += 1
        self._emit('"""Read AXIS_PROMISE_FULFILLED as a fuzzy/bool scalar."""')
        self._emit("return float(p[self.semantic_dim + self.AXIS_PROMISE_FULFILLED])")
        self._indent -= 1
        self._emit()
        self._emit("def isRejected(self, p):")
        self._indent += 1
        self._emit('"""Read AXIS_PROMISE_REJECTED as a fuzzy/bool scalar."""')
        self._emit("return float(p[self.semantic_dim + self.AXIS_PROMISE_REJECTED])")
        self._indent -= 1
        self._emit()
        self._emit("def isPending(self, p):")
        self._indent += 1
        self._emit('"""Both promise channels at zero ⇒ still pending.')
        self._emit("Per the eigenrotation-as-active-heartbeat rule, a pending")
        self._emit("promise's enclosing loop is genuinely cycling.")
        self._emit('"""')
        self._emit("f = float(p[self.semantic_dim + self.AXIS_PROMISE_FULFILLED])")
        self._emit("r = float(p[self.semantic_dim + self.AXIS_PROMISE_REJECTED])")
        self._emit("return 1.0 - max(f, r)")
        self._indent -= 1
        self._emit()
        self._emit("def value(self, p):")
        self._indent += 1
        self._emit('"""Read the resolved value — valid only when isFulfilled().')
        self._emit("Returns the promise vector with the channel flags zeroed,")
        self._emit("so downstream consumers see a clean value-shaped vector.")
        self._emit('"""')
        self._emit("v = p.clone()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def reason(self, p):")
        self._indent += 1
        self._emit('"""Read the rejection reason — valid only when isRejected()."""')
        self._emit("v = p.clone()")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_FULFILLED] = 0.0")
        self._emit("v[self.semantic_dim + self.AXIS_PROMISE_REJECTED] = 0.0")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def await_value(self, p):")
        self._indent += 1
        self._emit('"""await — the exact reduction of the spec-2 lowering.')
        self._emit("")
        self._emit("promises.md Stage 2: a Promise<T> is a while_loop with a")
        self._emit("two-channel halt (fulfilled, rejected) fed by an input")
        self._emit("axon; await is the loop's terminal value read. In the")
        self._emit("current runtime the halt channels are set ONLY by")
        self._emit("resolve/reject at construction (synchronous); no external")
        self._emit("axon producer mutates p mid-spin (no Yantra I/O yet).")
        self._emit("So while_loop spin(isPending(p), slot p){ pass p; } has")
        self._emit("an empty body that yields p unchanged every tick — it")
        self._emit("terminates with p at its initial value. Its terminal read")
        self._emit("is therefore exactly value(p), algebraically, for every")
        self._emit("input (resolved or pending). This is that reduction, not")
        self._emit("an approximation.")
        self._emit("")
        self._emit("Audit REAL LEAK #3 removed here: the prior body was a")
        self._emit("host Python bounded poll loop with a host branch on the")
        self._emit("pending predicate (and host scalar extraction inside")
        self._emit("that predicate). value(p) is pure tensor ops (clone +")
        self._emit("zero two axes), no host scalar, no branch. (Phrased")
        self._emit("without the literal old signature so the leak-sweep")
        self._emit("gate does not false-positive on this docstring.)")
        self._emit("When Yantra wires an external axon")
        self._emit("producer the gate becomes a real substrate while_loop on")
        self._emit("the slot-arrival flag (promises.md Stage 2 / axon-io.md)")
        self._emit("— a future extension, deliberately NOT a no-op loop")
        self._emit("added here to mimic the shape.")
        self._emit('"""')
        self._emit("return self.value(p)")
        self._indent -= 1
        self._emit()
        self._emit("def propagate(self, awaited, result):")
        self._indent += 1
        self._emit('"""Rejection propagation — promises.md §"Rejection propagation".')
        self._emit("")
        self._emit("`vector v = await awaited; ... return result` must reject when")
        self._emit("`awaited` rejected, carrying awaited's reason, WITHOUT running the")
        self._emit("post-await code's fulfilment. The spec says: the surrounding loop")
        self._emit("checks the awaited input's rejected channel; if set, the")
        self._emit("surrounding loop rejects with the same reason and the post-await")
        self._emit("result is discarded.")
        self._emit("")
        self._emit("Substrate-pure blend, no host branch / no .item():")
        self._emit("  rej = tanh(k * awaited[AXIS_PROMISE_REJECTED])   # ~1 if rejected")
        self._emit("  reject_branch = reject(reason(awaited))          # same reason")
        self._emit("  return (1 - rej) * result + rej * reject_branch")
        self._emit("The tanh(k=50) polarizer mirrors the try/catch blend so a")
        self._emit("rejected=1 input selects the reject branch entirely and a")
        self._emit("rejected=0 input selects the fulfilled `result` entirely. Both")
        self._emit("branches are evaluated (no early exit) — the blend decides which")
        self._emit("survives. The reject branch's AXIS_PROMISE_REJECTED is 1 and")
        self._emit("AXIS_PROMISE_FULFILLED is 0, so the blended promise's channels")
        self._emit("polarize correctly: a rejected await yields rejected≈1, fulfilled≈0.")
        self._emit('"""')
        self._emit("rej = _torch.tanh(50.0 * "
                   "awaited[self.semantic_dim + self.AXIS_PROMISE_REJECTED])")
        self._emit("reject_branch = self.reject(self.reason(awaited))")
        self._emit("return (1.0 - rej) * result + rej * reject_branch")
        self._indent -= 1
        self._emit()
        # ---- Axon runtime methods ----
        # Axons share the substrate operations of the rotation hashmap
        # (an axon is a bundle of bind(role, value) terms over a
        # codebook of role-by-string-name) but are a distinct
        # user-facing class — see planning/sutra-spec/axons.md. The
        # methods below implement the substrate operations the
        # `Axon` stdlib class declares as `static intrinsic method`.
        self._emit("# ---- Axon runtime methods ----")
        self._emit("# Per the 2026-05-10 axon-of-scalars-and-strings finding")
        self._emit("# (planning/open-questions/axon-bind-needs-permutation-for-")
        self._emit("# synthetic-fillers.md): rotation bind alone is identity in")
        self._emit("# the synthetic block, so synthetic-axis fillers (numbers via")
        self._emit("# make_real, strings via make_string) collide on bundle and")
        self._emit("# don't separate per key. The fix layers a per-key permutation")
        self._emit("# of the synthetic block on top of rotation. Free-standing")
        self._emit("# bind/unbind are unchanged — only axon_add/axon_item route")
        self._emit("# through the permutation path so loop carriers and the")
        self._emit("# rotation hashmap aren't touched.")
        self._emit("def axon_new(self):")
        self._indent += 1
        self._emit("return _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def _axon_permutation_for(self, role_vec, role_key=None):")
        self._indent += 1
        self._emit('"""Per-key deterministic permutation of the synthetic block.')
        self._emit('Cached per role-hash, just like _rotation_for. Returns a')
        self._emit('long tensor of synthetic_dim indices on the device.')
        self._emit('"""')
        self._emit("key = self._role_hash(role_vec, role_key)")
        self._emit("if not hasattr(self, '_perm_cache'):")
        self._indent += 1
        self._emit("self._perm_cache = {}")
        self._indent -= 1
        self._emit("if key not in self._perm_cache:")
        self._indent += 1
        self._emit("import numpy as _np_bridge")
        self._emit("# Distinct seed from rotation cache so the two are")
        self._emit("# uncorrelated draws.")
        self._emit("rng = _np_bridge.random.RandomState(key ^ 0xA50A_F00D)")
        self._emit("perm_np = rng.permutation(self.synthetic_dim).astype('int64')")
        self._emit("self._perm_cache[key] = _torch.as_tensor(perm_np, device=self.device)")
        self._indent -= 1
        self._emit("return self._perm_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def _axon_permute_synthetic(self, vec, perm):")
        self._indent += 1
        self._emit('"""Apply permutation to the synthetic block of vec, leave')
        self._emit('semantic block unchanged. Returns a new tensor."""')
        self._emit("out = vec.clone()")
        self._emit("syn = vec[self.semantic_dim:]")
        self._emit("out[self.semantic_dim:] = syn[perm]")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def _axon_unpermute_synthetic(self, vec, perm):")
        self._indent += 1
        self._emit('"""Inverse of _axon_permute_synthetic for the same perm."""')
        self._emit("out = vec.clone()")
        self._emit("syn = vec[self.semantic_dim:]")
        self._emit("# Build inverse permutation on the fly. Cheap (length")
        self._emit("# synthetic_dim, ~100) and we already have perm in hand.")
        self._emit("inv = _torch.empty_like(perm)")
        self._emit("inv[perm] = _torch.arange(perm.shape[0], device=perm.device)")
        self._emit("out[self.semantic_dim:] = syn[inv]")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def _axon_op_for(self, role_vec, role_key=None):")
        self._indent += 1
        self._emit('"""The FUSED per-key axon write operator M = blockdiag(Q_sem, P_perm):')
        self._emit('a single d x d matrix that does bind+permute in ONE matmul, i.e.')
        self._emit('M @ value == _axon_permute_synthetic(bind(role, value), perm) (verified')
        self._emit('bit-identical). Q_sem is the semantic rotation block; P_perm is the')
        self._emit('synthetic-block permutation as a matrix (P_perm @ syn == syn[perm]).')
        self._emit('Cached per role-hash (d x d; bounded by the axon key vocabulary).')
        self._emit('Collapsing axon_add to ONE op is what the concurrent tick_all path')
        self._emit('needs: CUDA streams overlap fewer/bigger kernels, so reducing op COUNT')
        self._emit('(not op size) is the win (finding 2026-06-20). Falls out of the existing')
        self._emit('_rotation_for / _axon_permutation_for caches, so no new Haar/perm draw."""')
        self._emit("key = self._role_hash(role_vec, role_key)")
        self._emit("if not hasattr(self, '_axon_op_cache'):")
        self._indent += 1
        self._emit("self._axon_op_cache = {}")
        self._indent -= 1
        self._emit("if key not in self._axon_op_cache:")
        self._indent += 1
        self._emit("Q = self._rotation_for(role_vec, role_key)")
        self._emit("perm = self._axon_permutation_for(role_vec, role_key)")
        self._emit("sem = self.semantic_dim")
        self._emit("dsyn = self.dim - sem")
        self._emit("P_perm = _torch.eye(dsyn, dtype=self.dtype, device=self.device)[perm]")
        self._emit("M = _torch.zeros(self.dim, self.dim, dtype=self.dtype, device=self.device)")
        self._emit("M[:sem, :sem] = Q[:sem, :sem]")
        self._emit("M[sem:, sem:] = P_perm")
        self._emit("self._axon_op_cache[key] = M")
        self._emit("if len(self._axon_op_cache) > self._role_cache_cap:")
        self._indent += 1
        self._emit("# FIFO evict the oldest-built op (deterministic recompute).")
        self._emit("del self._axon_op_cache[next(iter(self._axon_op_cache))]")
        self._indent -= 1
        self._indent -= 1
        self._emit("return self._axon_op_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def axon_add(self, axon, key, value):")
        self._indent += 1
        self._emit("# Defensively coerce caller-provided tensors to the runtime")
        self._emit("# device + dtype. axon may arrive on CPU when constructed by")
        self._emit("# host-side orchestration (e.g. a Python kernel passing in a")
        self._emit("# fresh accumulator); without coercion the final `axon +")
        self._emit("# permute(...)` mismatches once permute returns a CUDA tensor.")
        self._emit("axon = _torch.as_tensor(axon, dtype=self.dtype, device=self.device)")
        self._emit("# Key may arrive as a Python string (compile-time")
        self._emit("# identifier) or as an already-embedded vector.")
        self._emit("# Strings are auto-embedded into a basis vector.")
        self._emit("if isinstance(key, str):")
        self._indent += 1
        self._emit("key_vec = self.embed(key)")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("key_vec = _torch.as_tensor(key, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("# FV key-soundness trace: record the key actually bound at")
        self._emit("# runtime. A str key is named; a non-str (pre-embedded vector)")
        self._emit("# key the static analysis could not name is recorded as")
        self._emit("# '<dynamic>' so the checker flags it as escaping AXON_KEYS_BOUND.")
        self._emit("if self._fv_key_trace is not None:")
        self._indent += 1
        self._emit("self._fv_key_trace['bound'].add(key if isinstance(key, str) else '<dynamic>')")
        self._indent -= 1
        self._emit("# Scalar fillers (Python int / float) are promoted to")
        self._emit("# a real-axis vector via make_real. Python str fillers")
        self._emit("# are promoted to the codepoint-array form via make_string.")
        self._emit("# Both encodings put their content in the synthetic block,")
        self._emit("# which the permutation step then separates per key.")
        self._emit("if isinstance(value, (int, float)):")
        self._indent += 1
        self._emit("value = self.make_real(float(value))")
        self._indent -= 1
        self._emit("elif isinstance(value, str):")
        self._indent += 1
        self._emit("value = self.make_string(value)")
        self._indent -= 1
        self._emit("# Memoize the rotation/permutation hash by the KEY STRING when we")
        self._emit("# have it (a str key, embedded deterministically) — skips the")
        self._emit("# per-call .cpu() hash. A non-str key (pre-embedded vector) has no")
        self._emit("# stable string, so role_key=None falls back to hashing the vector.")
        self._emit("_rk = key if isinstance(key, str) else None")
        self._emit("# One fused matmul (M = blockdiag(Q_sem, P_perm)) instead of bind +")
        self._emit("# permute (matmul + clone + gather) — ONE op, the op-count reduction the")
        self._emit("# concurrent tick_all path needs. Bit-identical (finding 2026-06-20).")
        self._emit("value = _torch.as_tensor(value, dtype=self.dtype, device=self.device)")
        self._emit("return axon + self._axon_op_for(key_vec, role_key=_rk) @ value")
        self._indent -= 1
        self._emit()
        self._emit("def axon_build(self, axon, keys, values):")
        self._indent += 1
        self._emit('"""BATCHED axon_add: bind N (key, value) pairs in ONE bmm instead of')
        self._emit('N separate matmuls. Folds `axon_add` over the pairs and is BIT-IDENTICAL')
        self._emit('to that fold (verified) — but it stacks the cached per-key fused operators')
        self._emit('M_key (= blockdiag(Q_sem, P_perm)) into one (N,d,d) batch and does a single')
        self._emit('`bmm` + sum, collapsing N kernel launches to 1. That op-count reduction is')
        self._emit('what the concurrent tick_all path wants (CUDA streams overlap fewer/bigger')
        self._emit('kernels; finding 2026-06-20). Use for a KNOWN set of bindings (record/struct')
        self._emit('construction); the per-pair `axon_add` stays for incremental writes."""')
        self._emit("axon = _torch.as_tensor(axon, dtype=self.dtype, device=self.device)")
        self._emit("if not keys:")
        self._indent += 1
        self._emit("return axon")
        self._indent -= 1
        self._emit("Ms = []")
        self._emit("Vs = []")
        self._emit("for k, val in zip(keys, values):")
        self._indent += 1
        self._emit("if isinstance(k, str):")
        self._indent += 1
        self._emit("kv = self.embed(k); rk = k")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("kv = _torch.as_tensor(k, dtype=self.dtype, device=self.device); rk = None")
        self._indent -= 1
        self._emit("# FV key-soundness trace (mirror axon_add): the batched build is")
        self._emit("# where the .add-run peephole lands record bindings, so it MUST")
        self._emit("# record too or the checker goes vacuous for fused programs.")
        self._emit("if self._fv_key_trace is not None:")
        self._indent += 1
        self._emit("self._fv_key_trace['bound'].add(k if isinstance(k, str) else '<dynamic>')")
        self._indent -= 1
        self._emit("if isinstance(val, (int, float)):")
        self._indent += 1
        self._emit("val = self.make_real(float(val))")
        self._indent -= 1
        self._emit("elif isinstance(val, str):")
        self._indent += 1
        self._emit("val = self.make_string(val)")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("val = _torch.as_tensor(val, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("Ms.append(self._axon_op_for(kv, role_key=rk))")
        self._emit("Vs.append(val)")
        self._indent -= 1
        self._emit("Mstack = _torch.stack(Ms)")
        self._emit("Vstack = _torch.stack(Vs).unsqueeze(-1)")
        self._emit("return axon + _torch.bmm(Mstack, Vstack).sum(0).squeeze(-1)")
        self._indent -= 1
        self._emit()
        self._emit("def axon_project(self, axon, requested_keys):")
        self._indent += 1
        self._emit('"""Per-receiver projection: rebuild an axon containing only the listed keys.')
        self._emit('')
        self._emit("Used by host-side routers / orchestrators that want to slim a")
        self._emit("multi-key axon down to just the keys a specific receiver")
        self._emit("declared interest in (per the axon_keys static analysis +")
        self._emit("the receiver's manifest). Equivalent to:")
        self._emit('')
        self._emit("    result = zero_vector()")
        self._emit("    for key in requested_keys:")
        self._emit("        result = axon_add(result, key, axon_item(axon, key))")
        self._emit('')
        self._emit("Empty requested_keys returns a zero axon. requested_keys")
        self._emit("with elements not present in the source axon still 'work' in")
        self._emit("the sense that axon_item returns ~zero for unbound keys —")
        self._emit("the projection just adds zero contributions for them.")
        self._emit('"""')
        self._emit("# Defensive device coercion — same rationale as axon_add /")
        self._emit("# axon_item: tolerate a CPU axon from a host-side caller.")
        self._emit("axon = _torch.as_tensor(axon, dtype=self.dtype, device=self.device)")
        self._emit("result = self.zero_vector()")
        self._emit("for key in requested_keys:")
        self._indent += 1
        self._emit("value = self.axon_item(axon, key)")
        self._emit("result = self.axon_add(result, key, value)")
        self._indent -= 1
        self._emit("return result")
        self._indent -= 1
        self._emit()
        self._emit("def axon_item(self, axon, key):")
        self._indent += 1
        self._emit("# Defensive device coercion — same rationale as axon_add:")
        self._emit("# host-side callers may pass CPU tensors; the unpermute +")
        self._emit("# unbind chain is fully on self.device, so the input must")
        self._emit("# join it.")
        self._emit("axon = _torch.as_tensor(axon, dtype=self.dtype, device=self.device)")
        self._emit("if isinstance(key, str):")
        self._indent += 1
        self._emit("key_vec = self.embed(key)")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("key_vec = _torch.as_tensor(key, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("# FV key-soundness trace: record the key actually read at runtime")
        self._emit("# (str -> named; non-str -> '<dynamic>', flagged by the checker).")
        self._emit("if self._fv_key_trace is not None:")
        self._indent += 1
        self._emit("self._fv_key_trace['read'].add(key if isinstance(key, str) else '<dynamic>')")
        self._indent -= 1
        self._emit("_rk = key if isinstance(key, str) else None")
        self._emit("# Fused read (symmetric to axon_add's M_key write): unbind(key, unpermute(axon))")
        self._emit("# == cat(Q_sem^T @ axon[:sem], P_perm^T @ axon[sem:]) == M_key^T @ axon. ONE matmul,")
        self._emit("# reusing the cached blockdiag operator (Q orthogonal, P_perm a permutation, so")
        self._emit("# the inverse is the transpose). Bit-identical (finding 2026-06-20); op-count 3 -> 1.")
        self._emit("return self._axon_op_for(key_vec, role_key=_rk).T @ axon")
        self._indent -= 1
        self._emit()
        # ---- 2D-Givens-per-slot rotation binding (synthetic subspace) ----
        # Mirrors the numpy backend's slot block. See codegen.py for the
        # block; this is the pytorch realization, with `_torch.zeros`
        # and `tensor.clone()` instead of `_np.copy()`.
        self._emit("# ---- 2D-Givens-per-slot rotation binding (synthetic subspace) ----")
        self._emit("# Mirrors the numpy backend slot block; see codegen.py.")
        self._emit("# SLOT_BASE = 8 to leave room for AXIS_LOOP_DONE at [4],")
        self._emit("# AXIS_PROMISE_FULFILLED at [5], AXIS_PROMISE_REJECTED at [6],")
        self._emit("# AXIS_AXON_POPULATED at [7].")
        self._emit("SLOT_BASE = 8")
        self._emit()
        self._emit("def _slot_plane(self, slot_idx):")
        self._indent += 1
        self._emit("n_planes = (self.synthetic_dim - self.SLOT_BASE) // 2")
        self._emit("if n_planes <= 0:")
        self._indent += 1
        self._emit("raise RuntimeError(")
        self._indent += 1
        self._emit('"synthetic subspace has no room for slot planes; "')
        self._emit('"increase synthetic_dim or SLOT_BASE budget")')
        self._indent -= 1
        self._indent -= 1
        self._emit("s = int(slot_idx) % n_planes")
        self._emit("base = self.semantic_dim + self.SLOT_BASE + 2 * s")
        self._emit("return (base, base + 1)")
        self._indent -= 1
        self._emit()
        self._emit("def _slot_cell(self, scalar):")
        self._indent += 1
        self._emit('"""Coerce a number value to the 0-d real-axis scalar a slot')
        self._emit('plane stores. A d-dim number-vector (the make_real / num_*')
        self._emit('form) projects to its AXIS_REAL component via `_re` (a dot —')
        self._emit('substrate-pure, no host readout); a 0-d tensor or host literal')
        self._emit('passes through `_st`. queue §C "all numbers on the substrate":')
        self._emit('arithmetic now yields number-vectors, so the slot subsystem')
        self._emit('must accept them as well as the historical 0-d form."""')
        self._emit("if _torch.is_tensor(scalar) and scalar.ndim >= 1 "
                   "and scalar.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return self._num_re(scalar)")
        self._indent -= 1
        self._emit("return self._st(scalar)")
        self._indent -= 1
        self._emit()
        self._emit("def slot_state_new(self):")
        self._indent += 1
        self._emit('"""A fresh slot store: `{slot_idx: dim-vector}`. Vector-loop-state')
        self._emit('rung 3 (Emma Option B, 2026-07-12): slots hold FULL dim-vectors')
        self._emit('under ONE representation, so String/vector state survives the')
        self._emit('by-reference `loop` form (the old 2-axis scalar plane crushed it —')
        self._emit('SUT0206 / finding 2026-07-08). Orchestration container: the keys are')
        self._emit('compile-time slot indices, the values are on-device tensors — the')
        self._emit('same host-threaded-state category as the old single-vector plane,')
        self._emit('just holding whole vectors. No op reads a slot off the host."""')
        self._emit("return {}")
        self._indent -= 1
        self._emit()
        self._emit("def _slot_value(self, v):")
        self._indent += 1
        self._emit('"""Coerce a value to the FULL dim-vector a slot stores. An already-')
        self._emit('dim-vector (String / vector / number-vector) passes through untouched')
        self._emit('— crucially NOT projected (make_real would collapse a String to its')
        self._emit('real axis). A host scalar / 0-d tensor is lifted onto AXIS_REAL as a')
        self._emit('number-vector, with NO host readout (the 0-d tensor is scattered in')
        self._emit('directly, not float()-ed)."""')
        self._emit("if _torch.is_tensor(v) and v.ndim >= 1 and v.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return v")
        self._indent -= 1
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_REAL] = "
                   "v if _torch.is_tensor(v) else float(v)")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def slot_store(self, state, slot_idx, scalar):")
        self._indent += 1
        self._emit('"""Store the FULL dim-vector for slot `slot_idx`. Functional update')
        self._emit('(returns a new dict — same copy-on-write shape the old plane had via')
        self._emit('`state.clone()`), so callers keep threading `_slot_state ='
                   ' slot_store(...)`. Substrate-pure: `_slot_value` never reads a value')
        self._emit('off the host."""')
        self._emit("new = dict(state)")
        self._emit("new[int(slot_idx)] = self._slot_value(scalar)")
        self._emit("return new")
        self._indent -= 1
        self._emit()
        self._emit("def slot_load(self, state, slot_idx):")
        self._indent += 1
        self._emit('"""Read the slot FULL dim-vector (a zero vector if never stored,')
        self._emit('the moral equivalent of the old zero-initialised plane). Scalars come')
        self._emit('back as number-vectors (value on AXIS_REAL); downstream `num_*` ops')
        self._emit('accept those natively."""')
        self._emit("v = state.get(int(slot_idx))")
        self._emit("return v if v is not None else self.zero_vector()")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Binding-array primitive (substrate-stored ordered list) ----")
        self._emit("# Layout: arr[0] = length scalar, arr[1..length] = elements. Used by")
        self._emit("# foreach_loop. Pure tensor reads/writes; no Python list, no heap")
        self._emit("# allocation beyond the initial tensor.")
        self._emit()
        self._emit("def array_from_literal(self, *values):")
        self._indent += 1
        self._emit('"""Build an array from compile-time-known scalar values."""')
        self._emit("arr = _torch.zeros(len(values) + 1, dtype=self.dtype, device=self.device)")
        self._emit("arr[0] = float(len(values))")
        self._emit("for i, v in enumerate(values):")
        self._indent += 1
        self._emit("arr[1 + i] = float(v)")
        self._indent -= 1
        self._emit("return arr")
        self._indent -= 1
        self._emit()
        self._emit("def array_length(self, arr):")
        self._indent += 1
        self._emit('"""Read the length prefix as an int (used for Python loop bound)."""')
        self._emit("return int(arr[0].item())")
        self._indent -= 1
        self._emit()
        self._emit("def array_get(self, arr, i):")
        self._indent += 1
        self._emit('"""Read element at index i (0-based). Returns torch 0-dim tensor."""')
        self._emit("return arr[1 + int(i)]")
        self._indent -= 1
        self._emit()
        # ---- Immutable higher-order list ops (Emma 2026-06-20) ----
        # concat / map / filter build a NEW length-prefixed binding-array
        # from pieces and NEVER mutate an argument (pure-functional, fits
        # the substrate). Inputs may be a binding-array tensor (the
        # foreach_loop / array_from_literal form) OR a plain Python list
        # (a bare `[...]` array literal lowers to a list); _as_binding_array
        # normalizes either to a length-prefixed tensor so the ops have one
        # representation to reason about.
        self._emit("def _as_binding_array(self, arr):")
        self._indent += 1
        self._emit('"""Coerce a Python list OR a binding-array tensor to a')
        self._emit('length-prefixed binding-array tensor. A 1-D tensor whose')
        self._emit('[0] entry is its own (len-1) length is already a binding')
        self._emit('array and passes through; a Python list is packed via')
        self._emit('array_from_literal."""')
        self._emit("if _torch.is_tensor(arr):")
        self._indent += 1
        self._emit("return arr")
        self._indent -= 1
        self._emit("return self.array_from_literal(*arr)")
        self._indent -= 1
        self._emit()
        self._emit("def array_concat(self, a, b):")
        self._indent += 1
        self._emit('"""Immutable concat: NEW array = a\'s elements then b\'s.')
        self._emit('Allocates a fresh tensor; a and b are unchanged."""')
        self._emit("a = self._as_binding_array(a)")
        self._emit("b = self._as_binding_array(b)")
        self._emit("# No host length read (.item()): the new length is a[0]+b[0]")
        self._emit("# (0-d tensor) and the element tails a[1:]/b[1:] cat directly")
        self._emit("# (arrays are exactly sized). Pure tensor ops.")
        self._emit("return _torch.cat([(a[0] + b[0]).reshape(1), a[1:], b[1:]])")
        self._indent -= 1
        self._emit()
        self._emit("def array_map(self, f, arr):")
        self._indent += 1
        self._emit('"""Immutable map: NEW array where element i = f(arr[i]).')
        self._emit('f is a function value (Python callable). Same length as')
        self._emit('arr; arr is unchanged."""')
        self._emit("arr = self._as_binding_array(arr)")
        self._emit("# No host length read (.item()): clone (immutable — preserves")
        self._emit("# the arr[0] length slot) and walk the element tail arr[1:]")
        self._emit("# directly. f returns a host scalar (numbers are host floats")
        self._emit("# today) or a 0-d/real-axis tensor; coerce to a real scalar.")
        self._emit("out = arr.clone()")
        self._emit("for i, elem in enumerate(arr[1:]):")
        self._indent += 1
        self._emit("v = f(elem)")
        self._emit("if _torch.is_tensor(v) and v.dim() > 0:")
        self._indent += 1
        self._emit("v = self._re(v)")
        self._indent -= 1
        self._emit("out[1 + i] = v")
        self._indent -= 1
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def array_filter(self, pred, arr):")
        self._indent += 1
        self._emit('"""Immutable filter: NEW array of the elements where')
        self._emit('pred(element) is true. pred returns a Sutra truth value')
        self._emit('(a vector / 0-d tensor on the truth axis); truth_axis')
        self._emit('decodes it and the element is kept when truth > 0')
        self._emit('(unknown / 0 is dropped). arr is unchanged."""')
        self._emit("arr = self._as_binding_array(arr)")
        self._emit("# No host length read (.item()): walk the element tail arr[1:].")
        self._emit("kept = []")
        self._emit("for elem in arr[1:]:")
        self._indent += 1
        self._emit("t = self.truth_axis(pred(elem))")
        # truth_axis returns a 0-d tensor on AXIS_TRUTH; keep when > 0.
        # This host bool read is the filter decision point, the analogue
        # of a `while` halt check — not a per-element substrate readout of
        # the data.
        self._emit("if float(t) > 0.0:")
        self._indent += 1
        self._emit("kept.append(elem)")
        self._indent -= 1
        self._indent -= 1
        self._emit("out = _torch.zeros(len(kept) + 1, dtype=self.dtype, device=self.device)")
        self._emit("out[0] = float(len(kept))")
        self._emit("for j, elem in enumerate(kept):")
        self._indent += 1
        self._emit("out[1 + j] = elem")
        self._indent -= 1
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Substrate scalar primitives (boundary-leak reductions) ----")
        self._emit()
        self._emit("def truth_axis(self, vec_or_scalar):")
        self._indent += 1
        self._emit('"""Read AXIS_TRUTH from a fuzzy-vector result, or pass scalars through.')
        self._emit('')
        self._emit("Returns a torch 0-dim tensor; substrate-pure loop halt checks consume")
        self._emit("the result without crossing the Python boundary.")
        self._emit('"""')
        # A torch tensor: a 0-d truth scalar (e.g. from truth_and/truth_or on
        # a compound loop halt) passes straight through; a full fuzzy-vector
        # (dim >= 1) yields AXIS_TRUTH. Check is_tensor BEFORE len() because
        # len() of a 0-d tensor raises.
        self._emit("if _torch.is_tensor(vec_or_scalar):")
        self._indent += 1
        self._emit("if vec_or_scalar.dim() == 0:")
        self._indent += 1
        self._emit("return vec_or_scalar")
        self._indent -= 1
        self._emit("return vec_or_scalar[self.semantic_dim + self.AXIS_TRUTH]")
        self._indent -= 1
        self._emit("if hasattr(vec_or_scalar, '__len__') and len(vec_or_scalar) > 1:")
        self._indent += 1
        self._emit("return vec_or_scalar[self.semantic_dim + self.AXIS_TRUTH]")
        self._indent -= 1
        self._emit("return _torch.tensor(vec_or_scalar, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def heaviside(self, x):")
        self._indent += 1
        self._emit('"""Step function: 1.0 where x > 0, else 0.0. Torch 0-dim tensor."""')
        self._emit("if not _torch.is_tensor(x):")
        self._indent += 1
        self._emit("x = _torch.tensor(x, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("zero = _torch.zeros((), dtype=self.dtype, device=self.device)")
        self._emit("return _torch.heaviside(x.to(self.dtype), zero)")
        self._indent -= 1
        self._emit()
        self._emit("def saturate_unit(self, x):")
        self._indent += 1
        self._emit('"""min(x, 1.0) implemented as torch.minimum. Torch 0-dim tensor."""')
        self._emit("if not _torch.is_tensor(x):")
        self._indent += 1
        self._emit("x = _torch.tensor(x, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("one = _torch.ones((), dtype=self.dtype, device=self.device)")
        self._emit("return _torch.minimum(x, one)")
        self._indent -= 1
        self._emit()
        # ── Signed-truth Zadeh AND/OR/NOT for compound loop halts ──────────
        # Comparison ops (gt, eq_synthetic, neq_synthetic) return SIGNED
        # truth in [-1, 1] (positive = true) and the loop halt thresholds
        # that at 0 via heaviside. The general `&&`/`||` operator inlines to
        # the Zadeh POLYNOMIAL, which is only correct on [0, 1] truth — fed
        # signed truth it gives the wrong sign, so a compound `(a) && (b)`
        # loop halt was honored only on its first conjunct (finding
        # 2026-06-17-while-loop-halt-is-single-condition-only.md). On signed
        # truth, Zadeh AND/OR ARE min/max: min(a, b) > 0 iff a > 0 and b > 0;
        # max(a, b) > 0 iff a > 0 or b > 0 — exactly the right halt. The
        # while_loop / do_while condition lowers `&&`/`||`/`!` through these
        # (see _translate_loop_condition); each returns a 0-d truth tensor
        # that truth_axis passes straight to heaviside.
        self._emit("def truth_and(self, a, b):")
        self._indent += 1
        self._emit('"""Signed-truth Zadeh AND = element-wise minimum of the two')
        self._emit('truth-axis values. 0-d tensor; min(a,b) > 0 iff both > 0."""')
        self._emit("return _torch.minimum(self.truth_axis(a), self.truth_axis(b))")
        self._indent -= 1
        self._emit()
        self._emit("def truth_or(self, a, b):")
        self._indent += 1
        self._emit('"""Signed-truth Zadeh OR = element-wise maximum of the two')
        self._emit('truth-axis values. 0-d tensor; max(a,b) > 0 iff either > 0."""')
        self._emit("return _torch.maximum(self.truth_axis(a), self.truth_axis(b))")
        self._indent -= 1
        self._emit()
        self._emit("def truth_not(self, a):")
        self._indent += 1
        self._emit('"""Signed-truth NOT = negate the truth-axis value. 0-d tensor;')
        self._emit('(-a) > 0 iff a < 0 — flips the heaviside-at-0 decision."""')
        self._emit("return -self.truth_axis(a)")
        self._indent -= 1
        self._emit()
        self._emit("def rotate_slot(self, state, slot_idx, angle):")
        self._indent += 1
        self._emit('"""Givens rotation of the (i, j) slot plane by `angle` — the')
        self._emit('eigenrotation `loop(cond)` lowers to, so it MUST be substrate-')
        self._emit('pure (Audit.md REAL LEAK #1; was host _math.cos(float(angle)) +')
        self._emit('float(state[i])). c/s come from the verified substrate-pure')
        self._emit('cos/sin (0-d tensors); xi/xj are 0-d tensor element views (NOT')
        self._emit('float()); the plane update is tensor arithmetic + scatter. i, j')
        self._emit('are structural layout indices (like AXIS_REAL), not data."""')
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("c = self._cos_s(angle)")
        self._emit("s = self._sin_s(angle)")
        self._emit("new = state.clone() if hasattr(state, 'clone') else state.copy()")
        self._emit("xi = state[i]")
        self._emit("xj = state[j]")
        self._emit("new[i] = c * xi - s * xj")
        self._emit("new[j] = s * xi + c * xj")
        self._emit("return new")
        self._indent -= 1
        self._emit()
        self._emit("def similarity(self, a, b):")
        self._indent += 1
        self._emit("na = _torch.linalg.norm(a)")
        self._emit("nb = _torch.linalg.norm(b)")
        self._emit("# eps-guarded divide — zero-norm case evaluates to 0 without branch.")
        self._emit("# Substrate-pure: returns a 0-d tensor (NOT float()) so the value")
        self._emit("# stays on-graph when similarity is composed inside another op")
        self._emit("# (fuzzy AND/NOT, soft-mux, training). Host collapse happens only")
        self._emit("# at the monitoring/decode boundary (real()/truth()/output).")
        self._emit("return _torch.dot(a, b) / (na * nb + _torch.finfo(self.dtype).tiny)")
        self._indent -= 1
        self._emit()
        # General-purpose tensor operations — see codegen.py for the
        # numpy-backend equivalent and stdlib/tensor.su for the Sutra
        # surface (`Tensor.MatrixMul` etc.).
        self._emit("def matmul(self, a, b):")
        self._indent += 1
        self._emit('"""Matrix multiplication (torch matmul / `a @ b`)."""')
        self._emit("return _torch.matmul(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def tensor_product(self, a, b):")
        self._indent += 1
        self._emit('"""Tensor / Kronecker product."""')
        self._emit("return _torch.kron(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def outer(self, a, b):")
        self._indent += 1
        self._emit('"""Vector outer product → rank-2 tensor."""')
        self._emit("return _torch.outer(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def dot(self, a, b):")
        self._indent += 1
        self._emit('"""Inner / dot product → 0-d tensor (substrate-pure, no float())."""')
        self._emit("return _torch.dot(a, b)")
        self._indent -= 1
        self._emit()
        self._emit("def hadamard(self, a, b):")
        self._indent += 1
        self._emit('"""Elementwise (Hadamard) product of two number-VECTORS / buffers.')
        self._emit("Each component multiplied independently — the buffer-arithmetic")
        self._emit("multiply, distinct from complex_mul (which is the d-dim complex")
        self._emit("number product on the real/imag axes and collapses a multi-component")
        self._emit("buffer to one number). Lets a whole frame be computed in ONE substrate")
        self._emit("op over coordinate buffers: 1 - hadamard(X,X) - hadamard(Y,Y).")
        self._emit('Substrate-pure: a single elementwise tensor op, autograd-preserving."""')
        self._emit("return _torch.mul(a, b)")
        self._indent -= 1
        self._emit()
        # ===================================================================
        # Transcendental + modulus intrinsics — SUBSTRATE-PURE.
        #
        # The contract every method below honors (CLAUDE.md "every op runs
        # on the substrate", and the NO-host-scalar rule the 2026-04-29
        # withdrawal was about):
        #   * exactly ONE host→substrate boundary, `self._st(x)`, which
        #     coerces an incoming literal/arg to a device tensor (the same
        #     class of boundary as embed() turning a string into a vector);
        #   * every step after that is a tensor op;
        #   * the return value is a 0-d device tensor — NEVER `float(...)`;
        #   * NO `if`/`raise` on a scalar predicate, NO Python `for` over
        #     scalars. Out-of-range saturates via tensor `clamp` (a
        #     mathematically-valid output per the "no runtime errors by
        #     mechanism" core rule — which the old SutraMathOverflow raise
        #     violated, on top of being a host-control-flow leak).
        #
        # Architecture (Emma's authoritative voice design — see todo.md
        # "Transcendental functions — design absorbed from voice chat";
        # this overrides the spec where they disagree). Two real lookup
        # primitives, `_exp_table` and `log`, read by `_lerp` — a
        # crosstalk-weighted continuous readout (triangular soft-index
        # over the codebook, the rotational-binding kernel: nearby table
        # nodes leak into the readout, which is exactly what makes the
        # discrete table a continuous function). Everything else BETA-
        # REDUCES onto those two plus the eigenrotation (cos, sin):
        #
        #   cexp(a, b)  = exp(a) · (cos b + i·sin b)   complex exp
        #   exp(x)      = cexp(x, 0)                    real part; sin0=0
        #   cos / sin   = real / imag of the unit eigenrotation by θ
        #                 (sin is cos with the signs flipped — same table)
        #   pow(x,y)    = exp(y · log x)
        #   sqrt(x)     = exp(0.5 · log x)
        #   sinh/cosh/tanh from exp(x), exp(-x)
        #   *_mod       = the same eigenrotation around a circle of
        #                 circumference m
        #
        # `_st` / `_lerp` / `cexp` are the visible substrate primitives;
        # stdlib/math.su and stdlib/modulus.su carry the same chain in
        # readable Sutra so the beta reduction is legible at source level.
        # ===================================================================
        self._emit("def _st(self, x):")
        self._indent += 1
        self._emit('"""The single host→substrate entry boundary. Coerces an')
        self._emit('incoming literal / argument to a 0-d device tensor. A no-op')
        self._emit('view when x is already a device tensor. Nothing past this')
        self._emit('point touches a host scalar."""')
        self._emit("return _torch.as_tensor(x, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def _scalar(self, x):")
        self._indent += 1
        self._emit('"""Scalar-math entry boundary: coerce a NUMBER to its 0-d')
        self._emit('real-axis value. queue §C "all numbers on the substrate": int /')
        self._emit('number arithmetic now yields a d-dim number-vector (value on')
        self._emit('AXIS_REAL), so a scalar-domain op (floor / round / mod / pow /')
        self._emit('the transcendentals) handed `n / place` receives that vector and')
        self._emit('must read its real axis (a dot — substrate-pure, NO host readout)')
        self._emit('before computing, or it would run element-wise over the whole')
        self._emit('vector and corrupt the result. A 0-d tensor / host literal takes')
        self._emit('the plain `_st` boundary. This is `_st` specialised for the')
        self._emit('scalar-valued math library, distinct from `_st` which several')
        self._emit('genuine-vector call sites (realvec, digit-array, bigint) rely on')
        self._emit('to pass a full vector through unchanged."""')
        self._emit("if _torch.is_tensor(x) and x.ndim >= 1 and x.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return _torch.dot(x, self._num_e_real(x))")
        self._indent -= 1
        self._emit("return self._st(x)")
        self._indent -= 1
        self._emit()
        self._emit("def _lerp(self, xt, xs, values, dx):")
        self._indent += 1
        self._emit('"""Crosstalk-weighted continuous readout of a codebook.')
        self._emit('w = (1 - |xs - xt| / dx) clamped at 0 is the triangular')
        self._emit('soft-index kernel: the two table nodes bracketing xt leak')
        self._emit('into the dot product proportionally to proximity. That')
        self._emit('crosstalk is what turns the discrete `values` table into')
        self._emit('a continuous function of xt. All tensor ops; 0-d result."""')
        self._emit("d = (xs - xt).abs() / dx")
        self._emit("w = (1.0 - d).clamp(min=0.0)")
        self._emit("return _torch.matmul(w, values)")
        self._indent -= 1
        self._emit()
        # =================================================================
        # Transcendentals — the documented vision (todo.md "Transcendental
        # functions — design absorbed from voice chat"):
        #   exp(z) = exp(re z) · (cos(im z) + i·sin(im z))
        #   sin(θ) = imag(exp(iθ))    cos(θ) = real(exp(iθ))
        # Two lookup leaves (exp table, ln table); everything else
        # beta-reduces. The canonical complex number is the d-dim
        # synthetic-axis form (real on AXIS_REAL, imag on AXIS_IMAG) —
        # THE SAME representation complex literals + complex_mul use.
        # (The earlier length-2 [re,im] `cexp` stack was an ad-hoc
        # deviation from this vision and disagreed with complex_mul;
        # removed.) Scalar-typed call sites receive the real-axis 0-d
        # tensor — that is `real(exp(iθ))`, the documented projection,
        # not a representational deviation. Axis read/write is a pure
        # one-hot dot / scaled-one-hot add (matmul-class), no host
        # scalar. "There is no scalar, only complex with imag 0."
        # =================================================================
        self._emit("def _e_real(self):")
        self._indent += 1
        self._emit('"""Cached one-hot selector for AXIS_REAL (d-dim, 1.0 at the')
        self._emit('real slot). dot(v, _e_real) = the real component as a 0-d')
        self._emit('tensor - substrate-pure axis read, no .item()/float()."""')
        self._emit("if not hasattr(self, '_e_real_cache') or self._e_real_cache is None:")
        self._indent += 1
        self._emit("e = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("e[self.semantic_dim + self.AXIS_REAL] = 1.0")
        self._emit("self._e_real_cache = e")
        self._indent -= 1
        self._emit("return self._e_real_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _e_imag(self):")
        self._indent += 1
        self._emit('"""Cached one-hot selector for AXIS_IMAG."""')
        self._emit("if not hasattr(self, '_e_imag_cache') or self._e_imag_cache is None:")
        self._indent += 1
        self._emit("e = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("e[self.semantic_dim + self.AXIS_IMAG] = 1.0")
        self._emit("self._e_imag_cache = e")
        self._indent -= 1
        self._emit("return self._e_imag_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _cnum(self, x):")
        self._indent += 1
        self._emit('"""Coerce anything to the canonical d-dim complex vector. An')
        self._emit('already-d-dim vector passes through; a 0-d tensor / host')
        self._emit('literal becomes [x, 0] on the real axis via a scaled one-hot')
        self._emit('(pure tensor; the host->substrate entry boundary). There is')
        self._emit('no scalar - a real is a complex with imag 0."""')
        self._emit("if _torch.is_tensor(x) and x.ndim >= 1 and x.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("return self._st(x) * self._e_real()")
        self._indent -= 1
        self._emit()
        self._emit("def _re(self, z):")
        self._indent += 1
        self._emit('"""Real component of a complex vector as a 0-d tensor:')
        self._emit('dot with the real one-hot (matmul-class, substrate-pure)."""')
        self._emit("return _torch.dot(self._cnum(z), self._e_real())")
        self._indent -= 1
        self._emit()
        self._emit("def _im(self, z):")
        self._indent += 1
        self._emit('"""Imag component as a 0-d tensor (dot with the imag one-hot)."""')
        self._emit("return _torch.dot(self._cnum(z), self._e_imag())")
        self._indent -= 1
        self._emit()
        self._emit("def _mk(self, r0, i0):")
        self._indent += 1
        self._emit('"""Build a d-dim complex vector from 0-d real/imag tensors:')
        self._emit('r0*e_real + i0*e_imag. Pure tensor (scaled one-hot adds)."""')
        self._emit("return self._st(r0) * self._e_real() + self._st(i0) * self._e_imag()")
        self._indent -= 1
        self._emit()
        self._emit("def _exp_table(self, x):")
        self._indent += 1
        self._emit('"""Real exponential lookup leaf: e^x for a 0-d tensor x.')
        self._emit('Out-of-range saturates at the table edge (tensor clamp),')
        self._emit('not a raise. The crosstalk _lerp readout is the only')
        self._emit('non-trivial op; all tensor."""')
        self._emit("xt = self._scalar(x).clamp(self._EXP_LO, self._EXP_HI)")
        self._emit("return self._lerp(xt, self._EXP_XS, self._EXP_VALUES, self._EXP_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def _ln_table(self, x):")
        self._indent += 1
        self._emit('"""Natural-log lookup leaf: ln(x) for a 0-d tensor x.')
        self._emit('Non-positive / out-of-range saturates at the table edge')
        self._emit('(ln near LN_LO = a large negative - the valid limit)."""')
        self._emit("xt = self._scalar(x).clamp(self._LN_LO, self._LN_HI)")
        self._emit("return self._lerp(xt, self._LN_XS, self._LN_VALUES, self._LN_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def _trig_reduce(self, x):")
        self._indent += 1
        self._emit('"""Reduce a 0-d angle to (-pi, pi] via x - 2pi*round(x/2pi).')
        self._emit('rotation is periodic so this is the angle it actually turns')
        self._emit('Periodic, so mod 2pi comes for free. Pure tensor."""')
        self._emit("xt = self._scalar(x)")
        self._emit("return xt - self._TWO_PI * _torch.round(xt / self._TWO_PI)")
        self._indent -= 1
        self._emit()
        self._emit("def _cos0(self, theta):")
        self._indent += 1
        self._emit('"""cos of a 0-d angle via the eigenrotation lookup (the')
        self._emit('x-coordinate of the rotated unit vector)."""')
        self._emit("return self._lerp(self._trig_reduce(theta), self._TRIG_XS, self._COS_VALUES, self._TRIG_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def _sin0(self, theta):")
        self._indent += 1
        self._emit('"""sin of a 0-d angle - same eigenrotation, y-coordinate."""')
        self._emit("return self._lerp(self._trig_reduce(theta), self._TRIG_XS, self._SIN_VALUES, self._TRIG_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def realExp(self, z):")
        self._indent += 1
        self._emit('"""e^(Re z) - the rotational crosstalk lookup leaf, as a')
        self._emit('canonical complex [e^a, 0]. The math.su realExp leaf."""')
        self._emit("return self._mk(self._exp_table(self._re(z)), 0.0)")
        self._indent -= 1
        self._emit()
        self._emit("def imaginaryExp(self, z):")
        self._indent += 1
        self._emit('"""e^(i*Im z) - the eigenrotation: [cos(Im z), sin(Im z)],')
        self._emit('the unit vector at that angle. The math.su imaginaryExp leaf;')
        self._emit('cos/sin are its real/imag projections (cos is its own')
        self._emit('transcendental - the real coordinate of this rotation)."""')
        self._emit("ang = self._im(z)")
        self._emit("return self._mk(self._cos0(ang), self._sin0(ang))")
        self._indent -= 1
        self._emit()
        self._emit("def cexp(self, z):")
        self._indent += 1
        self._emit('"""Complex exponential, the documented keystone:')
        self._emit('exp(a+b*i) = e^a*(cos b + i*sin b) = realExp(z) (x) imaginaryExp(z),')
        self._emit('(x) = complex_mul (the canonical d-dim complex product, verified')
        self._emit('substrate-pure). Returns a canonical complex vector."""')
        self._emit("return self.complex_mul(self.realExp(z), self.imaginaryExp(z))")
        self._indent -= 1
        self._emit()
        self._emit("def _exp_s(self, x):")
        self._indent += 1
        self._emit('"""exp as a 0-d (scalar) tensor = real(cexp(x)). The internal')
        self._emit('scalar primitive used by every derived transcendental (pow,')
        self._emit('sqrt, sinh, cosh, tanh) and by defuzzify_trit, whose downstream')
        self._emit('arithmetic (division, weighted sums) needs a scalar not a')
        self._emit('number-vector. This 0-d form is the alias; public exp() below')
        self._emit('returns the full number-vector (Emma 2026-05-29)."""')
        self._emit("return self._re(self.cexp(self._cnum(x)))")
        self._indent -= 1
        self._emit()
        self._emit("def exp(self, x):")
        self._indent += 1
        self._emit('"""e^x as the full number-vector [e^x, 0, ...] - a number IS a')
        self._emit('vector, the real axis carries e^x. The 0-d projection is no')
        self._emit('longer applied here (Emma 2026-05-29: drop the 0-d projection on')
        self._emit('exp/cos/sin); decode with real()/_re at the monitoring boundary,')
        self._emit('or call _exp_s for the scalar alias."""')
        self._emit("return self._mk(self._exp_s(x), 0.0)")
        self._indent -= 1
        self._emit()
        self._emit("def ccos(self, z):")
        self._indent += 1
        self._emit('"""Complex-argument cosine, the documented reduction')
        self._emit('cos(z) = (e^(i*z) + e^(-i*z)) / 2. Substrate-pure: built')
        self._emit('only from the verified-pure cexp keystone + complex_mul /')
        self._emit('complex_add (no new leaf, no host branch, no scalar')
        self._emit('extraction). i*z and -i*z are complex products with the')
        self._emit('imaginary unit; the /2 is a complex product with [0.5,0]')
        self._emit('so the whole op stays in canonical-complex-vector space.')
        self._emit('For real z (imag 0): i*z = [0, a], cexp = [cos a, sin a],')
        self._emit('-i*z = [0,-a], cexp = [cos a,-sin a], sum/2 = [cos a, 0] -')
        self._emit('identical to the scalar cos() eigenrotation, so the')
        self._emit('paper-cited real cos path is unaffected. For z = a+bi it')
        self._emit('yields cos a*cosh b - i*sin a*sinh b. Canonical complex')
        self._emit('vector out."""')
        self._emit("zc = self._cnum(z)")
        self._emit("iz = self.complex_mul(zc, self._mk(0.0, 1.0))")
        self._emit("miz = self.complex_mul(zc, self._mk(0.0, -1.0))")
        self._emit("half = self._mk(0.5, 0.0)")
        self._emit("return self.complex_mul(self.complex_add(self.cexp(iz), self.cexp(miz)), half)")
        self._indent -= 1
        self._emit()
        self._emit("def csin(self, z):")
        self._indent += 1
        self._emit('"""Complex-argument sine, the documented reduction')
        self._emit('sin(z) = (e^(i*z) - e^(-i*z)) / (2i). Substrate-pure: built')
        self._emit('only from the verified-pure cexp keystone + complex_mul /')
        self._emit('complex_sub (no new leaf, no host branch, no scalar')
        self._emit('extraction) - the csin follow-on to ccos. The 1/(2i)')
        self._emit('factor is the complex constant -i/2 = [0, -0.5], applied')
        self._emit('as a complex product so the whole op stays in canonical-')
        self._emit('complex-vector space. For real z (imag 0): i*z = [0, a],')
        self._emit('cexp = [cos a, sin a]; -i*z = [0,-a], cexp = [cos a,-sin a];')
        self._emit('diff = [0, 2 sin a]; (x)[0,-0.5] = [sin a, 0] - identical')
        self._emit('to the scalar sin() eigenrotation, so the paper-cited real')
        self._emit('sin path is unaffected. For z = a+bi it yields')
        self._emit('sin a*cosh b + i*cos a*sinh b. Canonical complex vector out."""')
        self._emit("zc = self._cnum(z)")
        self._emit("iz = self.complex_mul(zc, self._mk(0.0, 1.0))")
        self._emit("miz = self.complex_mul(zc, self._mk(0.0, -1.0))")
        self._emit("inv_two_i = self._mk(0.0, -0.5)")
        self._emit("return self.complex_mul(self.complex_sub(self.cexp(iz), self.cexp(miz)), inv_two_i)")
        self._indent -= 1
        self._emit()
        self._emit("def log(self, x):")
        self._indent += 1
        self._emit('"""Natural log. Real positive x: ln(x) via the ln leaf. (Full')
        self._emit('complex log - imag part = angle via atan2 - is the documented')
        self._emit('deferred piece, not faked here; real-axis ln matches the')
        self._emit('existing contract and tests.) 0-d tensor out."""')
        self._emit("return self._ln_table(self._re(self._cnum(x)))")
        self._indent -= 1
        self._emit()
        self._emit("ln = log")
        self._emit()
        self._emit("def _cos_s(self, x):")
        self._indent += 1
        self._emit('"""cos(theta) as a 0-d scalar = real(eigenrotation). Internal')
        self._emit('scalar primitive (used by tan, _rotor, modulus atan2). The')
        self._emit('eigenrotation turns through theta; its real coordinate is cos."""')
        self._emit("itheta = self._mk(0.0, self._st(x))")
        self._emit("return self._re(self.imaginaryExp(itheta))")
        self._indent -= 1
        self._emit()
        self._emit("def cos(self, x):")
        self._indent += 1
        self._emit('"""cos(theta) as the full number-vector [cos theta, 0, ...]. 0-d')
        self._emit('projection dropped (Emma 2026-05-29); _cos_s is the scalar alias')
        self._emit('used internally and at the monitoring boundary."""')
        self._emit("return self._mk(self._cos_s(x), 0.0)")
        self._indent -= 1
        self._emit()
        self._emit("def _sin_s(self, x):")
        self._indent += 1
        self._emit('"""sin(theta) as a 0-d scalar = imag(eigenrotation). Internal')
        self._emit('scalar primitive (used by tan, _rotor, modulus atan2)."""')
        self._emit("itheta = self._mk(0.0, self._st(x))")
        self._emit("return self._im(self.imaginaryExp(itheta))")
        self._indent -= 1
        self._emit()
        self._emit("def sin(self, x):")
        self._indent += 1
        self._emit('"""sin(theta) as the full number-vector [sin theta, 0, ...]. 0-d')
        self._emit('projection dropped (Emma 2026-05-29); _sin_s is the scalar alias."""')
        self._emit("return self._mk(self._sin_s(x), 0.0)")
        self._indent -= 1
        self._emit()
        # ===================================================================
        # Elementwise transcendentals over a FIELD BUFFER (Emma 2026-06-17
        # "Make the compiler primitive"). The scalar sin/cos above act on the
        # canonical d-dim complex NUMBER (one angle in / one number out); they
        # do NOT map elementwise over an arbitrary length-N activation buffer
        # — `cexp`/`complex_mul` evaluate against the canonical dim and raise a
        # dim-mismatch on a length-N buffer (finding 2026-06-17-substrate-
        # transcendentals-canonical-only.md). `sin_buf`/`cos_buf` are the
        # buffer counterparts: the SAME substrate-pure table readout the scalar
        # trig uses (wrap to (-π,π] then a triangular soft-index crosstalk
        # matmul against the cached sin/cos table), but BROADCAST over the N
        # elements — the exact (N, T) weight-matrix pattern sawtooth_mod already
        # ships. One fused tensor op, autograd-preserving, PERIODIC by
        # construction (no polynomial high-frequency divergence — a length-N
        # `cos = realvec(cexp(iθ))` was the blocked path). Unblocks an
        # on-substrate Fourier-feature encoding and SIREN-style sin activations.
        # ===================================================================
        self._emit("def sin_buf(self, x):")
        self._indent += 1
        self._emit('"""Elementwise sin over a length-N field buffer (the buffer')
        self._emit('counterpart to scalar sin). Wrap each element to (-π,π], then a')
        self._emit('triangular soft-index crosstalk readout of the cached sin table,')
        self._emit('broadcast over the N elements (the (N, T) matmul sawtooth_mod uses).')
        self._emit('Substrate-pure, periodic, autograd-preserving; length-N in/out."""')
        self._emit("xt = self._st(x)")
        self._emit("ar = xt - self._TWO_PI * _torch.round(xt / self._TWO_PI)")
        self._emit("d = (self._TRIG_XS.unsqueeze(0) - ar.unsqueeze(-1)).abs() / self._TRIG_DX")
        self._emit("w = (1.0 - d).clamp(min=0.0)")
        self._emit("return _torch.matmul(w, self._SIN_VALUES)")
        self._indent -= 1
        self._emit()
        self._emit("def cos_buf(self, x):")
        self._indent += 1
        self._emit('"""Elementwise cos over a length-N field buffer — the cos counterpart')
        self._emit('to sin_buf, same broadcast soft-index readout against the cached cos')
        self._emit('table. Substrate-pure, periodic, autograd-preserving; length-N in/out."""')
        self._emit("xt = self._st(x)")
        self._emit("ar = xt - self._TWO_PI * _torch.round(xt / self._TWO_PI)")
        self._emit("d = (self._TRIG_XS.unsqueeze(0) - ar.unsqueeze(-1)).abs() / self._TRIG_DX")
        self._emit("w = (1.0 - d).clamp(min=0.0)")
        self._emit("return _torch.matmul(w, self._COS_VALUES)")
        self._indent -= 1
        self._emit()
        self._emit("def pow(self, x, y):")
        self._indent += 1
        self._emit('"""x^y = exp(y*ln x) - change-of-base identity. 0-d tensor."""')
        self._emit("return self._exp_s(self._scalar(y) * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def sqrt(self, x):")
        self._indent += 1
        self._emit('"""sqrt(x) = exp(0.5*ln x) - the y=1/2 case of pow."""')
        self._emit("return self._exp_s(0.5 * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def tan(self, x):")
        self._indent += 1
        self._emit('"""tan = sin/cos. cos->0 gives +/-inf (valid limit; no host if)."""')
        self._emit("return self._sin_s(x) / self._cos_s(x)")
        self._indent -= 1
        self._emit()
        self._emit("def sinh(self, x):")
        self._indent += 1
        self._emit('"""(e^x - e^-x)/2."""')
        self._emit("xt = self._scalar(x)")
        self._emit("return (self._exp_s(xt) - self._exp_s(-xt)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def cosh(self, x):")
        self._indent += 1
        self._emit('"""(e^x + e^-x)/2."""')
        self._emit("xt = self._scalar(x)")
        self._emit("return (self._exp_s(xt) + self._exp_s(-xt)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def tanh(self, x):")
        self._indent += 1
        self._emit('"""(e^2x - 1)/(e^2x + 1) [stable]; large |x| => exp saturates')
        self._emit('so tanh -> +/-1, the correct limit, no host range check."""')
        self._emit("e2x = self._exp_s(2.0 * self._scalar(x))")
        self._emit("return (e2x - 1.0) / (e2x + 1.0)")
        self._indent -= 1
        self._emit()
        # =================================================================
        # Modulus library — see stdlib/modulus.su. floor/ceil/round/
        # trunc/abs/sign ARE native substrate (GPU) instructions, kept as
        # one-tensor-op bodies. fmod/rotation_mod/sawtooth_mod derive from
        # the same eigenrotation as the trig family. atan2-via-lookup is
        # the one remaining libm-shaped follow-on (audit task).
        # =================================================================
        self._emit("def floor(self, x):")
        self._indent += 1
        self._emit('"""Round toward -∞. Substrate: torch.floor (GPU instruction)."""')
        self._emit("return _torch.floor(self._scalar(x))")
        self._indent -= 1
        self._emit()
        self._emit("def ceil(self, x):")
        self._indent += 1
        self._emit('"""Round toward +∞. Substrate: torch.ceil."""')
        self._emit("return _torch.ceil(self._scalar(x))")
        self._indent -= 1
        self._emit()
        self._emit("def round(self, x):")
        self._indent += 1
        self._emit('"""Nearest integer, ties-to-even (torch default). JS Math.round')
        self._emit('is half-up — mismatch tracked in the substrate-purity audit."""')
        self._emit("return _torch.round(self._scalar(x))")
        self._indent -= 1
        self._emit()
        self._emit("def trunc(self, x):")
        self._indent += 1
        self._emit('"""Truncate toward zero. Substrate: torch.trunc."""')
        self._emit("return _torch.trunc(self._scalar(x))")
        self._indent -= 1
        self._emit()
        self._emit("def abs(self, x):")
        self._indent += 1
        self._emit('"""|x|. Substrate: torch.abs."""')
        self._emit("return _torch.abs(self._scalar(x))")
        self._indent -= 1
        self._emit()
        self._emit("def sign(self, x):")
        self._indent += 1
        self._emit('"""-1 / 0 / +1. Substrate: torch.sign."""')
        self._emit("return _torch.sign(self._scalar(x))")
        self._indent -= 1
        self._emit()
        # =================================================================
        # Bitwise — 32-bit AND / OR / XOR via a substrate bit-plane
        # decomposition (stdlib/bitwise.su). NOT scalar extraction: the
        # number-vector is broadcast against a (32,) powers tensor to get a
        # (32, dim) bit-plane stack (only the real axis carries a value, so
        # every other axis decomposes to all-zero bits), the per-bit logic
        # is element-wise tensor arithmetic, and the planes are recombined
        # by a powers-weighted sum back into a number-vector. All torch ops,
        # no host scalar / numpy. Domain: non-negative integers < 2^32 (the
        # WASM machine's unsigned 32-bit values). Shifts (`lsl`/`lsr`) are
        # exact arithmetic identities (×2^k / floor(/2^k)) emitted directly
        # by callers, not here.
        # =================================================================
        self._emit("def _bit_powers(self):")
        self._indent += 1
        self._emit("if getattr(self, '_bit_pow_cache', None) is None:")
        self._indent += 1
        self._emit("self._bit_pow_cache = (2.0 ** _torch.arange("
                   "32, dtype=self.dtype, device=self.device)).reshape(-1, 1)")
        self._indent -= 1
        self._emit("return self._bit_pow_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _bits_of(self, x):")
        self._indent += 1
        self._emit('"""(32, dim) bit-plane decomposition of number-vector x: '
                   'bit i = floor(x/2^i) - 2·floor(x/2^(i+1)). Other axes -> 0."""')
        self._emit("v = self._st(x).reshape(1, -1)")
        self._emit("p = self._bit_powers()")
        self._emit("return _torch.floor(v / p) - 2.0 * _torch.floor(v / (2.0 * p))")
        self._indent -= 1
        self._emit()
        self._emit("def _recombine_bits(self, bits):")
        self._indent += 1
        self._emit('"""(32, dim) bit-planes -> number-vector (powers-weighted sum)."""')
        self._emit("return (bits * self._bit_powers()).sum(dim=0)")
        self._indent -= 1
        self._emit()
        self._emit("def band(self, a, b):")
        self._indent += 1
        self._emit('"""Bitwise AND (32-bit). bit = a_bit · b_bit."""')
        self._emit("return self._recombine_bits(self._bits_of(a) * self._bits_of(b))")
        self._indent -= 1
        self._emit()
        self._emit("def bor(self, a, b):")
        self._indent += 1
        self._emit('"""Bitwise OR (32-bit). bit = a + b - a·b."""')
        self._emit("ab = self._bits_of(a); bb = self._bits_of(b)")
        self._emit("return self._recombine_bits(ab + bb - ab * bb)")
        self._indent -= 1
        self._emit()
        self._emit("def bxor(self, a, b):")
        self._indent += 1
        self._emit('"""Bitwise XOR (32-bit). bit = a + b - 2·a·b."""')
        self._emit("ab = self._bits_of(a); bb = self._bits_of(b)")
        self._emit("return self._recombine_bits(ab + bb - 2.0 * ab * bb)")
        self._indent -= 1
        self._emit()
        self._emit("def fmod(self, x, m):")
        self._indent += 1
        self._emit('"""Truncation modulus (JS / C / C# / Rust / TS `%`): result')
        self._emit('has the sign of x. x - m·trunc(x/m). Divisor 0 yields a NaN')
        self._emit('tensor — the mathematically-valid degenerate result, not a')
        self._emit('host ZeroDivisionError (no scalar control flow)."""')
        self._emit("xt = self._scalar(x)")
        self._emit("mt = self._scalar(m)")
        self._emit("return xt - mt * _torch.trunc(xt / mt)")
        self._indent -= 1
        self._emit()
        self._emit("def rotation_mod(self, x, m):")
        self._indent += 1
        self._emit('"""Floor modulus via the eigenrotation: walk a circle whose')
        self._emit('circumference is m. θ = 2π·x/m, the eigenrotation gives')
        self._emit('(cos θ, sin θ), atan2 reads the phase back, re-wrapped to')
        self._emit('[0, 2π) and scaled by m/2π. Always non-negative for m > 0')
        self._emit('(`rotation_mod(-0.1, 1) == 0.9`); discontinuous at integer')
        self._emit('multiples of m (the atan2 branch cut). Divisor 0 → NaN')
        self._emit('tensor, not a host raise.')
        self._emit('')
        self._emit('Substrate chain (all tensor ops):')
        self._emit('  θ      = 2π · x / m')
        self._emit('  (c, s) = cos θ, sin θ            (eigenrotation readout)')
        self._emit('  φ      = atan2(s, c)             (tensor; lookup follow-on)')
        self._emit('  φ_pos  = φ - 2π·floor(φ / 2π)    (re-wrap to [0, 2π))')
        self._emit('  result = m · φ_pos / (2π)')
        self._emit('"""')
        self._emit("xt = self._scalar(x)")
        self._emit("mt = self._scalar(m)")
        self._emit("theta = self._TWO_PI * xt / mt")
        self._emit("phi = _torch.atan2(self._sin_s(theta), self._cos_s(theta))")
        self._emit("phi_pos = phi - self._TWO_PI * _torch.floor(phi / self._TWO_PI)")
        self._emit("return mt * phi_pos / self._TWO_PI")
        self._indent -= 1
        self._emit()
        self._emit("def sawtooth_mod(self, x, m, n_terms=16):")
        self._indent += 1
        self._emit('"""Floor modulus via the Fourier sawtooth — smooth, fully')
        self._emit('differentiable, ~9% Gibbs ring near integer multiples of m.')
        self._emit('mod_floor(x,m) ≈ m/2 - (m/π)·Σ_{k=1..N} sin(2πkx/m)/k.')
        self._emit('The k-sum is a single vectorized tensor reduction (a (K,N)')
        self._emit('crosstalk-weight matmul against the sin table) — NOT a')
        self._emit('Python for-loop over scalars. n_terms is a compile-time')
        self._emit('structural constant, not substrate data."""')
        self._emit("xt = self._scalar(x)")
        self._emit("mt = self._scalar(m)")
        self._emit("k = _torch.arange(1, int(n_terms) + 1, dtype=self.dtype, device=self.device)")
        self._emit("ang = self._TWO_PI * k * xt / mt")
        self._emit("ar = ang - self._TWO_PI * _torch.round(ang / self._TWO_PI)")
        self._emit("d = (self._TRIG_XS.unsqueeze(0) - ar.unsqueeze(1)).abs() / self._TRIG_DX")
        self._emit("w = (1.0 - d).clamp(min=0.0)")
        self._emit("sines = _torch.matmul(w, self._SIN_VALUES)")
        self._emit("total = (sines / k).sum()")
        self._emit("return 0.5 * mt - (mt / 3.141592653589793) * total")
        self._indent -= 1
        self._emit()
        self._emit("# `mod` is the canonical floor-mod alias — today the")
        self._emit("# eigenrotation form (Emma-preferred default).")
        self._emit("mod = rotation_mod")
        self._emit()
        self._emit("def transpose(self, m):")
        self._indent += 1
        self._emit('"""Transpose (last two dims for 2-D+; identity for 1-D)."""')
        self._emit("if m.ndim < 2:")
        self._indent += 1
        self._emit("return m")
        self._indent -= 1
        self._emit("return _torch.transpose(m, -2, -1)")
        self._indent -= 1
        self._emit()
        # `norm` (a float-returning host readout) removed 2026-06-07 — no
        # introspection in the language. Use `normalize` (returns a vector) or
        # similarity on the substrate. `Norm` alias removed with it.
        self._emit("def normalize(self, v):")
        self._indent += 1
        self._emit('"""L2-normalize with an eps-guard so zero-norm input returns zero."""')
        self._emit("n = _torch.linalg.norm(v)")
        self._emit("return v / (n + _torch.finfo(self.dtype).tiny)")
        self._indent -= 1
        self._emit()
        self._emit("def rotation_for(self, role):")
        self._indent += 1
        self._emit('"""Cached Haar-random orthogonal rotation matrix for the role vector."""')
        self._emit("return self._rotation_for(role)")
        self._indent -= 1
        self._emit()
        # PascalCase aliases — the preferred Sutra-side spelling.
        self._emit("MatrixMul = matmul")
        self._emit("TensorProduct = tensor_product")
        self._emit("Outer = outer")
        self._emit("Dot = dot")
        self._emit("Transpose = transpose")
        self._emit("Normalize = normalize")
        self._emit("RotationFor = rotation_for")
        self._emit()
        # Vector component accessors (component/semantic/synthetic) removed
        # 2026-06-07 — host-readout, no introspection in the language. They had
        # zero consumers. `imag`/`truth` accessors removed for the same reason.
        # `real` is retained TEMPORARILY (13 .su + 7 internal consumers) and is
        # the next target of the substrate-purity overhaul (queue.md).
        # `real()` REMOVED from the language (Emma 2026-06-07): no scalar
        # readout — it severs substrate-purity + autograd. This stub exists
        # only so the JS-interop number->string coercion paths fail LOUDLY
        # and CLEARLY (JS host coercion is not substrate-pure, so it is
        # broken by design) instead of a cryptic AttributeError. There is no
        # working scalar readout in the runtime.
        self._emit("def _js_coerce_real(self, v):")
        self._indent += 1
        self._emit("raise RuntimeError(\"JS number<->string coercion needs a host scalar (real()) which was removed: not substrate-pure (Emma 2026-06-07)\")")
        self._indent -= 1
        self._emit()
        # RAM pointers (planning/sutra-spec/ram-pointers.md). `self.ram` is
        # an OPTIONAL external memory device the host attaches (the
        # orchestrator's role) — a list of number-vectors. RAM access is
        # I/O at the boundary, NOT a substrate op: ram_read decodes the
        # pointer-vector to a host address (round(real(ptr)) — the same
        # monitoring readout used elsewhere, here at the I/O wire), reads
        # the host buffer, and returns the stored VRAM vector. The pointer
        # is a substrate-computed `number`; the value comes back as VRAM.
        # Address is discrete round-to-nearest (Emma 2026-06-01: RAM is not
        # differentiable). OOB / no device -> zero vector (no runtime errors
        # by mechanism), per ram-pointers.md open-Q 4.
        self._emit("def ram_read(self, ptr):")
        self._indent += 1
        self._emit("if self.ram is None:")
        self._indent += 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit("_pt = self._st(ptr)")
        self._emit("# Address decode (I/O boundary). ptr may be a full number-")
        self._emit("# vector (read AXIS_REAL) or a bare scalar address (a literal")
        self._emit("# or computed RAM offset, e.g. base+i) — handle both.")
        self._emit("addr = int(round(float((_pt if _pt.ndim == 0 else "
                   "_pt[self.semantic_dim + self.AXIS_REAL]).item())))")
        self._emit("# DIRECT 1D linear memory (a torch tensor, see ram_write): each")
        self._emit("# cell is a real-axis scalar; reconstruct the number-vector by")
        self._emit("# scattering the stored 0-d value onto AXIS_REAL (a tensor op, no")
        self._emit("# host readout). Scales to the 10MB linear memory (1 scalar/cell,")
        self._emit("# no per-cell d-vector). The lazily-allocated Bytes/array case.")
        self._emit("if _torch.is_tensor(self.ram):")
        self._indent += 1
        self._emit("if 0 <= addr < self.ram.shape[0]:")
        self._indent += 1
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_REAL] = self.ram[addr]")
        self._emit("return out")
        self._indent -= 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit("# External-attached LIST device (orchestrator contract: iso5 /")
        self._emit("# ntm_ram attach + index self.ram as a list of vectors).")
        self._emit("if 0 <= addr < len(self.ram):")
        self._indent += 1
        self._emit("return self.ram[addr]")
        self._indent -= 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit()
        self._emit("def ram_write(self, ptr, value):")
        self._indent += 1
        self._emit("_pt = self._st(ptr)")
        self._emit("# Address decode (I/O boundary). ptr may be a full number-")
        self._emit("# vector (read AXIS_REAL) or a bare scalar address (a literal")
        self._emit("# or computed RAM offset, e.g. base+i) — handle both.")
        self._emit("addr = int(round(float((_pt if _pt.ndim == 0 else "
                   "_pt[self.semantic_dim + self.AXIS_REAL]).item())))")
        self._emit("# Store a number-vector so ramRead(...) round-trips: a")
        self._emit("# scalar value (literal / computed) is lifted to make_real at")
        self._emit("# the I/O boundary; a number-vector is stored as-is.")
        self._emit("_vt = self._st(value)")
        self._emit("val_vec = value if (hasattr(value, 'ndim') and "
                   "_vt.ndim != 0) else self.make_real(float(_vt.item()))")
        self._emit("if addr < 0:")
        self._indent += 1
        self._emit("return val_vec")
        self._indent -= 1
        self._emit("# An EXTERNAL orchestrator-attached device stays a list of vectors")
        self._emit("# (unchanged contract: iso5 / ntm_ram attach + index self.ram as a")
        self._emit("# list, including genuine multi-axis VRAM vectors).")
        self._emit("if isinstance(self.ram, list):")
        self._indent += 1
        self._emit("while len(self.ram) <= addr:")
        self._indent += 1
        self._emit("self.ram.append(self.zero_vector())")
        self._indent -= 1
        self._emit("self.ram[addr] = val_vec")
        self._emit("return val_vec")
        self._indent -= 1
        self._emit("# No external device: a DIRECT 1D linear-memory tensor, NOT a")
        self._emit("# Python list (Emma 2026-06-19). Each cell is the real-axis scalar")
        self._emit("# of the value (the byte/number a Bytes.make / array linear memory")
        self._emit("# holds; the OCaml attn tape stores dot/sum NUMBERS too). Grown by")
        self._emit("# doubling. Scales to 10MB: 1 scalar/cell, no pre-grown d-vectors.")
        self._emit("cell = _vt if _vt.ndim == 0 else _torch.dot(val_vec, self._e_real())")
        self._emit("if self.ram is None:")
        self._indent += 1
        self._emit("self.ram = _torch.zeros(max(addr + 1, 16), dtype=self.dtype, "
                   "device=self.device)")
        self._indent -= 1
        self._emit("if addr >= self.ram.shape[0]:")
        self._indent += 1
        self._emit("grown = _torch.zeros(max(addr + 1, 2 * self.ram.shape[0]), "
                   "dtype=self.dtype, device=self.device)")
        self._emit("grown[:self.ram.shape[0]] = self.ram")
        self._emit("self.ram = grown")
        self._indent -= 1
        self._emit("self.ram[addr] = cell")
        self._emit("return val_vec")
        self._indent -= 1
        self._emit()
        # NOTE (2026-06-07): the `ram_gather`/`ram_scatter` "RAM-as-a-VRAM-tensor"
        # ops were REMOVED. They embodied a wrong architecture — treating VRAM as
        # RAM and fusing memory into the step graph — which contradicts the NTM
        # design (planning/sutra-spec/ram-pointers.md: RAM is EXTERNAL host memory
        # accessed through an orchestrator + VRAM mailbox; ramRead/ramWrite are the
        # I/O boundary, NOT substrate ops). Fusing the RNN recurrence (loops) is
        # correct; fusing RAM is not. Keep RAM external.
        self._emit("def make_real(self, x):")
        self._indent += 1
        self._emit('"""Lift a number onto the real axis. Idempotent on an already-')
        self._emit("d-dim number-vector (queue §C \"all numbers on the substrate\":")
        self._emit('`x + 1.0` now yields a number-vector, so `make_real(x + 1.0)`')
        self._emit('receives one and must pass it through — projecting its AXIS_REAL')
        self._emit('cleanly via the real projector, a substrate matmul, NOT a host')
        self._emit('float-readout that would detach autograd and crash on')
        self._emit('a multi-element tensor). A 0-d tensor / host literal takes the')
        self._emit('scaled-one-hot entry boundary."""')
        self._emit("if _torch.is_tensor(x) and x.ndim >= 1 and x.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return self._real_projector() @ x")
        self._indent -= 1
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(x)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        # ---- Number-axis arithmetic (queue §C "all numbers on the
        # substrate") ----
        # int / number / scalar arithmetic runs on the canonical number
        # axis (AXIS_REAL of the synthetic subspace), NOT on host Python
        # floats. `+ - * /` on number-typed operands dispatch here (see
        # _translate_expr in codegen_base.py). Each method coerces both
        # operands to the d-dim number-vector via `_cnum` (the
        # host->substrate entry boundary — a host literal becomes a
        # scaled one-hot on AXIS_REAL; an already-number-vector passes
        # through), so the result is a clean number-vector with the value
        # on AXIS_REAL and zeros elsewhere. Substrate-pure: matmul-class
        # ops only, NO `.item()` / host readout mid-computation. The value
        # stays a tensor end-to-end; host extraction happens only at the
        # terminal display boundary (_decode_terminal_result).
        self._emit("def _num_e_real(self, ref):")
        self._indent += 1
        self._emit('"""Real-axis one-hot DERIVED from `ref` (a live operand tensor)')
        self._emit('so it tracks the operand device. The cached `_e_real()` lives on')
        self._emit('`self.device`; under `torch.jit.trace` a freshly-constructed')
        self._emit('`zeros(..., device=ref.device)` bakes the traced device as a')
        self._emit('CONSTANT, so a CUDA-traced graph replayed on a CPU input device-')
        self._emit('mismatches in the orchestrator subprocess. `zeros_like(ref)`')
        self._emit('derives the one-hot from the input, so the device follows the')
        self._emit('live input through the trace. For a d-dim ref we scatter 1.0 onto')
        self._emit('AXIS_REAL; the cached one-hot is the fallback when ref is not a')
        self._emit('d-dim tensor. Pure tensor, device-portable."""')
        self._emit("if _torch.is_tensor(ref) and ref.ndim >= 1 and ref.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("e = _torch.zeros_like(ref)")
        self._emit("e[self.semantic_dim + self.AXIS_REAL] = 1.0")
        self._emit("return e")
        self._indent -= 1
        self._emit("return self._e_real()")
        self._indent -= 1
        self._emit()
        self._emit("def _num(self, x, ref):")
        self._indent += 1
        self._emit('"""Coerce `x` to a d-dim number-vector, device-tracking `ref`. An')
        self._emit('already-d-dim number-vector passes through; a 0-d tensor scales')
        self._emit('the ref-derived real-axis one-hot; a host scalar multiplies that')
        self._emit('one-hot as a Python number (device-agnostic in a trace — it')
        self._emit('broadcasts to the ref device, so a CUDA-traced graph replays on')
        self._emit('a CPU input without baking a device constant)."""')
        self._emit("if _torch.is_tensor(x) and x.ndim >= 1 and x.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if _torch.is_tensor(x):")
        self._indent += 1
        self._emit("return x * self._num_e_real(ref)")
        self._indent -= 1
        self._emit("return float(x) * self._num_e_real(ref)")
        self._indent -= 1
        self._emit()
        self._emit("def _num_re(self, z):")
        self._indent += 1
        self._emit('"""Real-axis component of a number value as a 0-d tensor, device-')
        self._emit('tracking the operand (cf. `_re`, which uses the cached one-hot).')
        self._emit('A host scalar is returned as a Python float (device-agnostic in')
        self._emit('a trace: it broadcasts to the other operand device instead of')
        self._emit('baking `self.device`, keeping num_mul / num_div device-portable')
        self._emit('when a CUDA-traced graph is replayed on a CPU input)."""')
        self._emit("if _torch.is_tensor(z) and z.ndim >= 1 and z.shape[-1] == self.dim:")
        self._indent += 1
        self._emit("return _torch.dot(z, self._num_e_real(z))")
        self._indent -= 1
        self._emit("if _torch.is_tensor(z):")
        self._indent += 1
        self._emit("return z")
        self._indent -= 1
        self._emit("return float(z)")
        self._indent -= 1
        self._emit()
        self._emit("def num_add(self, a, b):")
        self._indent += 1
        self._emit('"""a + b on the number axis. Element-wise add of two')
        self._emit('real-axis number-vectors keeps the value on AXIS_REAL')
        self._emit('(imag/other axes stay 0). Operands are lifted on a shared')
        self._emit('device so a host literal + a live tensor stay device-aligned."""')
        self._emit("ref = a if _torch.is_tensor(a) else b")
        self._emit("return self._num(a, ref) + self._num(b, ref)")
        self._indent -= 1
        self._emit()
        self._emit("def num_sub(self, a, b):")
        self._indent += 1
        self._emit('"""a - b on the number axis."""')
        self._emit("ref = a if _torch.is_tensor(a) else b")
        self._emit("return self._num(a, ref) - self._num(b, ref)")
        self._indent -= 1
        self._emit()
        self._emit("def num_mul(self, a, b):")
        self._indent += 1
        self._emit('"""a * b on the number axis. Multiply the real-axis')
        self._emit('components and scatter back onto AXIS_REAL — element-wise')
        self._emit('product of the full vectors would also work for two reals')
        self._emit('but the real-axis form is robust to crosstalk on other')
        self._emit('axes. Pure tensor (dot + scalar mul + scaled one-hot)."""')
        self._emit("ref = a if _torch.is_tensor(a) else b")
        self._emit("r = self._num_re(a) * self._num_re(b)")
        self._emit("return r * self._num_e_real(ref)")
        self._indent -= 1
        self._emit()
        self._emit("def num_div(self, a, b):")
        self._indent += 1
        self._emit('"""a / b on the number axis. Element-wise division would')
        self._emit('compute 0/0 = nan on every zero axis and poison the vector;')
        self._emit('divide the real-axis components and scatter the quotient')
        self._emit('back onto AXIS_REAL. Pure tensor, NO host readout."""')
        self._emit("ref = a if _torch.is_tensor(a) else b")
        self._emit("r = self._num_re(a) / self._num_re(b)")
        self._emit("return r * self._num_e_real(ref)")
        self._indent -= 1
        self._emit()
        self._emit("def num_neg(self, a):")
        self._indent += 1
        self._emit('"""Unary minus on the number axis."""')
        self._emit("return -self._num(a, a)")
        self._indent -= 1
        self._emit()
        self._emit("def realvec(self, v):")
        self._indent += 1
        self._emit('"""Project a vector to a CLEAN real-axis number-vector (keep the')
        self._emit('real axis, zero the rest) via the real-axis projector matmul.')
        self._emit('Substrate-pure: stays a tensor, NO host readout (the in-language')
        self._emit("replacement for the removed real() accessor). Decodes an axon")
        self._emit('field filler — which carries crosstalk in non-real dims — to the')
        self._emit('clean number it stores, so == / arithmetic see only the number."""')
        self._emit("return self._real_projector() @ self._st(v)")
        self._indent -= 1
        self._emit()
        self._emit("def make_complex(self, re, im):")
        self._indent += 1
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(re)")
        self._emit("v[self.semantic_dim + self.AXIS_IMAG] = float(im)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def _swap_ri_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_swap_ri_cache') or self._swap_ri_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[r, i] = 1.0; M[i, r] = 1.0")
        self._emit("self._swap_ri_cache = M")
        self._indent -= 1
        self._emit("return self._swap_ri_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _cm_real_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_cm_real_cache') or self._cm_real_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[r, r] = 1.0; M[r, i] = -1.0")
        self._emit("self._cm_real_cache = M")
        self._indent -= 1
        self._emit("return self._cm_real_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _cm_imag_matrix(self):")
        self._indent += 1
        self._emit("if not hasattr(self, '_cm_imag_cache') or self._cm_imag_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[i, r] = 1.0; M[i, i] = 1.0")
        self._emit("self._cm_imag_cache = M")
        self._indent -= 1
        self._emit("return self._cm_imag_cache")
        self._indent -= 1
        self._emit()
        self._emit("def complex_mul(self, a, b):")
        self._indent += 1
        self._emit('"""Complex product: matrix form, no scalar extraction.')
        self._emit('')
        self._emit("c = _cm_real @ (a * b) + _cm_imag @ ((_swap_ri @ a) * b)")
        self._emit('"""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("ab = av * bv")
        self._emit("swapped_ab = (self._swap_ri_matrix() @ av) * bv")
        self._emit("return self._cm_real_matrix() @ ab + self._cm_imag_matrix() @ swapped_ab")
        self._indent -= 1
        self._emit()
        self._emit("def complex_add(self, a, b):")
        self._indent += 1
        self._emit('"""Complex addition. Coerces both operands to complex vectors')
        self._emit('first so `complex + scalar` adds to the real axis only')
        self._emit('rather than broadcasting across imag too."""')
        self._emit("return self._as_complex_vector(a) + self._as_complex_vector(b)")
        self._indent -= 1
        self._emit()
        self._emit("def complex_sub(self, a, b):")
        self._indent += 1
        self._emit('"""Complex subtraction. Same coercion pattern as complex_add."""')
        self._emit("return self._as_complex_vector(a) - self._as_complex_vector(b)")
        self._indent -= 1
        self._emit()
        self._emit("def _conj_matrix(self):")
        self._indent += 1
        self._emit('"""Cached d×d matrix that conjugates a complex vector: identity')
        self._emit('on every axis except imag, where it negates. Built lazily on')
        self._emit('first call, then reused; same pattern as _cm_real_matrix."""')
        self._emit("if not hasattr(self, '_conj_cache') or self._conj_cache is None:")
        self._indent += 1
        self._emit("M = _torch.eye(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("i = self.semantic_dim + self.AXIS_IMAG")
        self._emit("M[i, i] = -1.0")
        self._emit("self._conj_cache = M")
        self._indent -= 1
        self._emit("return self._conj_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _broadcast_real_matrix(self):")
        self._indent += 1
        self._emit('"""Cached d×d matrix that broadcasts the real-axis value of a')
        self._emit('vector to every axis: column real_axis is all-ones, everything')
        self._emit('else is zero. `M @ v` returns a vector whose every element is')
        self._emit('v[real_axis]. Used by complex_div to turn the scalar |b|² on')
        self._emit('the real axis into a vector-wide divisor without scalar')
        self._emit('extraction."""')
        self._emit("if not hasattr(self, '_br_real_cache') or self._br_real_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("r = self.semantic_dim + self.AXIS_REAL")
        self._emit("M[:, r] = 1.0")
        self._emit("self._br_real_cache = M")
        self._indent -= 1
        self._emit("return self._br_real_cache")
        self._indent -= 1
        self._emit()
        self._emit("def complex_div(self, a, b):")
        self._indent += 1
        self._emit('"""Complex division: (a+bi)/(c+di) = ((ac+bd) + (bc-ad)i)/(c²+d²).')
        self._emit('Substrate-pure throughout — no scalar extraction from the')
        self._emit('vector. Three substrate steps:')
        self._emit('  1. conj_b = _conj_matrix @ bv          (negate imag axis)')
        self._emit('  2. num    = complex_mul(av, conj_b)    (numerator complex)')
        self._emit('  3. denom_v = _broadcast_real @ complex_mul(bv, conj_b)')
        self._emit('               (broadcast c²+d² to every axis)')
        self._emit('  return num / denom_v                   (element-wise div)')
        self._emit('Division by a zero divisor produces inf/NaN on the real and')
        self._emit('imag axes, matching Python complex division semantics."""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("conj_b = self._conj_matrix() @ bv")
        self._emit("num = self.complex_mul(av, conj_b)")
        self._emit("denom_complex = self.complex_mul(bv, conj_b)")
        self._emit("denom_vec = self._broadcast_real_matrix() @ denom_complex")
        self._emit("return num / denom_vec")
        self._indent -= 1
        self._emit()
        self._emit("def _as_complex_vector(self, x):")
        self._indent += 1
        self._emit('"""Coerce Python scalar / tensor to complex-plane form."""')
        self._emit("if isinstance(x, _torch.Tensor):")
        self._indent += 1
        self._emit("if x.dim() == 0:")
        self._indent += 1
        self._emit("# 0-d scalar tensor (e.g. a slot-loaded int or a loop")
        self._emit("# state var): lift its value onto the real axis of a")
        self._emit("# number-vector, on-device, so number ops (gt / lt /")
        self._emit("# add / ...) receive a proper complex-plane vector")
        self._emit("# rather than a bare scalar (which breaks the matmul).")
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = x")
        self._emit("return v")
        self._indent -= 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_real(1.0 if x else 0.0)")
        self._indent -= 1
        self._emit("return self.make_real(float(x))")
        self._indent -= 1
        self._emit()
        self._emit("def make_truth(self, t):")
        self._indent += 1
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_TRUTH] = float(t)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def make_char(self, codepoint):")
        self._indent += 1
        self._emit('"""Character literal: a 1-character String. Equivalent to')
        self._emit('make_string(chr(codepoint)). The `char` type is now a')
        self._emit('1-character String; AXIS_CHAR_FLAG is an alias for')
        self._emit('AXIS_STRING_FLAG."""')
        self._emit("return self.make_string(chr(int(codepoint)))")
        self._indent -= 1
        self._emit()
        # `is_char` (a pure alias of is_string) retired 2026-07-08 —
        # zero call sites; CLAUDE.md § "Deprecate aliases aggressively".
        self._emit("# ---- String runtime methods ----")
        self._emit("# Encoding: AXIS_STRING_FLAG marks the vector as a String.")
        self._emit("# Characters pack into the synthetic axes — char[0] at")
        self._emit("# AXIS_REAL (=synthetic[0]), char[1] at AXIS_IMAG")
        self._emit("# (=synthetic[1]), char[k] for k>=2 at synthetic[k+3]")
        self._emit("# (skipping AXIS_TRUTH/STRING_FLAG/LOOP_DONE at synthetic")
        self._emit("# [2..4]). Length is recovered by walking from the highest")
        self._emit("# possible char position down to the first non-zero. See")
        self._emit("# planning/sutra-spec/strings.md.")
        self._emit("def _string_axis(self, char_index):")
        self._indent += 1
        self._emit('"""Map a character index k into the absolute axis offset')
        self._emit('inside the synthetic block (relative to semantic_dim)."""')
        self._emit("return char_index if char_index < 2 else char_index + 3")
        self._indent -= 1
        self._emit()
        self._emit("def string_max_length(self):")
        self._indent += 1
        self._emit('"""Maximum string length that fits in the current')
        self._emit('synthetic_dim. char positions occupy synthetic[0,1] plus')
        self._emit('synthetic[5..synthetic_dim-1]."""')
        self._emit("if self.synthetic_dim < 5:")
        self._indent += 1
        self._emit("return min(self.synthetic_dim, 2)")
        self._indent -= 1
        self._emit("return 2 + (self.synthetic_dim - 5)")
        self._indent -= 1
        self._emit()
        self._emit("def _str_axes(self):")
        self._indent += 1
        self._emit('"""Cached constant LongTensor of the absolute vector offsets')
        self._emit('that hold the String codepoints, in char order: offset k =')
        self._emit('semantic_dim + (k if k<2 else k+3), for k in 0..max_len-1.')
        self._emit('Built once at first use (a compile-time-shaped constant, the')
        self._emit('same class as the exp/trig lookup tables) so string_length /')
        self._emit('char_at / concat are pure tensor gather/scatter over the')
        self._emit('codepoint block instead of host codepoint loops."""')
        self._emit("if not hasattr(self, '_str_axes_cache') or self._str_axes_cache is None:")
        self._indent += 1
        self._emit("ml = self.string_max_length()")
        self._emit("offs = [self.semantic_dim + (k if k < 2 else k + 3) for k in range(ml)]")
        self._emit("self._str_axes_cache = _torch.tensor(offs, dtype=_torch.long, device=self.device)")
        self._indent -= 1
        self._emit("return self._str_axes_cache")
        self._indent -= 1
        self._emit()
        self._emit("def make_string(self, s):")
        self._indent += 1
        self._emit('"""Construct a String value from a Python str. IDEMPOTENT on an')
        self._emit('already-String vector: the type-coercion pass can wrap a String-typed')
        self._emit("initializer in make_string even when it is already a String (e.g.")
        self._emit('`String g = make_string(\"hi\")`), so a double make_string must return')
        self._emit('the value unchanged, not `str(tensor)`-encode its repr as text."""')
        self._emit("if _torch.is_tensor(s) and s.ndim >= 1 and "
                   "s.shape[-1] == self.dim and bool(self.is_string(s)):")
        self._indent += 1
        self._emit("return s")
        self._indent -= 1
        self._emit("if not isinstance(s, str):")
        self._indent += 1
        self._emit("s = str(s)")
        self._indent -= 1
        self._emit("max_len = self.string_max_length()")
        self._emit("# Saturate, do not raise (no-runtime-errors-by-mechanism):")
        self._emit("# a literal longer than the synthetic budget truncates at")
        self._emit("# the cap rather than throwing. This enumerate is the")
        self._emit("# host-literal -> substrate ENTRY boundary (the make_real /")
        self._emit("# _st analogue), not an op-internal substrate read.")
        self._emit("s = s[:max_len]")
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_STRING_FLAG] = 1.0")
        self._emit("for k, ch in enumerate(s):")
        self._indent += 1
        self._emit("axis = self._string_axis(k)")
        self._emit("v[self.semantic_dim + axis] = float(ord(ch))")
        self._indent -= 1
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def is_string(self, v):")
        self._indent += 1
        self._emit('"""True iff v has the AXIS_STRING_FLAG set."""')
        self._emit("return bool(v[self.semantic_dim + self.AXIS_STRING_FLAG].item() >= 0.5)")
        self._indent -= 1
        self._emit()
        # Substrate-pure tag type-tests (Elixir/Erlang is_binary / is_number guards;
        # planning/findings/2026-06-18-substrate-type-tests.md). Each reads the
        # AXIS_STRING_FLAG and scatters `2*ind - 1` onto AXIS_TRUTH (a tensor op, NO host
        # readout, unlike `is_string` which collapses to a host bool for dispatch), so the
        # result is a fuzzy truth value that composes in the `defuzzy` guard blend. SCOPE:
        # only the String flag is a clean runtime tag, so only is_string (is_binary) and
        # is_number (= NOT-a-String) lower. is_list/is_map/is_tuple are NOT supported: they
        # need an axon tag, and the 2026-06-19 attempt to set AXIS_AXON_POPULATED in
        # axon_add was REVERTED — it corrupted nested-axon field reads (the tuple_in_ctor /
        # nested_ctor crosstalk) and a String stored as an axon value (echo). See the
        # finding's "Negative result" section.
        self._emit("def is_string_truth(self, v):")
        self._indent += 1
        self._emit('"""Type-test as a fuzzy truth: +1 on AXIS_TRUTH if v carries the')
        self._emit('AXIS_STRING_FLAG (a String), else -1. Substrate-pure scatter."""')
        self._emit("vt = self._as_any_vector(v)")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = "
                   "2.0 * vt[self.semantic_dim + self.AXIS_STRING_FLAG] - 1.0")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def is_number_truth(self, v):")
        self._indent += 1
        self._emit('"""+1 on AXIS_TRUTH if v is NOT a String (a plain number), else -1:')
        self._emit('1 - 2*sflag. Substrate-pure scatter. NOTE: this does NOT distinguish')
        self._emit('a number from an axon (axons carry no clean runtime tag), so it')
        self._emit('classifies an axon as a number; callers must not rely on is_number to')
        self._emit('reject an axon (see planning/findings/2026-06-18-substrate-type-tests.md)."""')
        self._emit("vt = self._as_any_vector(v)")
        self._emit("sflag = vt[self.semantic_dim + self.AXIS_STRING_FLAG]")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = 1.0 - 2.0 * sflag")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def string_length(self, v):")
        self._indent += 1
        self._emit('"""Length of String v, substrate-pure (Audit REAL LEAK #5;')
        self._emit('was a host `for k in range`, `.item()`, host `if`, host')
        self._emit('`return k+1`). Gather the codepoint block, mark non-zero')
        self._emit('positions, take the highest 1-based position that is')
        self._emit('non-zero: length = max((k+1) where cps[k] >= 0.5). All tensor')
        self._emit('ops; 0-d tensor out. Trailing-zero-as-sentinel preserved')
        self._emit('(a 0 codepoint in the tail reads shorter, same as before).')
        self._emit('The 0.5 threshold (was `!= 0`) makes decode robust to')
        self._emit('superposition residue: a String coming out of select() carries')
        self._emit('~1e-9 leakage from losing branches on higher codepoint axes,')
        self._emit('which the exact-nonzero walk counted as characters (phantom')
        self._emit('NULs). Real codepoints are >= 32; residue is << 1."""')
        self._emit("ax = self._str_axes()")
        self._emit("cps = v.index_select(0, ax)")
        self._emit("nz = (cps.abs() >= 0.5).to(self.dtype)")
        self._emit("pos = _torch.arange(1, ax.shape[0] + 1, dtype=self.dtype, device=self.device)")
        self._emit("return (pos * nz).max()")
        self._indent -= 1
        self._emit()
        self._emit("def string_char_at(self, v, i):")
        self._indent += 1
        self._emit('"""Codepoint at position i, substrate-pure (Audit REAL LEAK')
        self._emit('#5; was `int(i)`, host `if i<0 or i>=...`, `int(.item())`).')
        self._emit('Gather the codepoint block, mask out-of-range to 0 (saturate,')
        self._emit('no host branch/raise). 0-d tensor out.')
        self._emit('')
        self._emit('Index boundary (2026-07-13 reach-audit fix): `i` may arrive as')
        self._emit('a d-dim NUMBER-VECTOR (a loop-threaded state param, e.g.')
        self._emit('`string_char_at(s, i - 1)` inside a loop body — num_sub yields')
        self._emit('a number-vector). `_scalar` projects that to its real-axis 0-d')
        self._emit('value (a dot, substrate-pure); a 0-d/host index passes through.')
        self._emit('The previous `_st(i)` passed a d-dim index through UNPROJECTED,')
        self._emit('making `cps[ci]` a d-wide gather — a d-dim garbage "codepoint"')
        self._emit('that poisoned every downstream string op (measured: the')
        self._emit('reverse-string repro decoded as c + 98 fill chars)."""')
        self._emit("ax = self._str_axes()")
        self._emit("n = ax.shape[0]")
        self._emit("it = self._scalar(i)")
        self._emit("valid = ((it >= 0) & (it < n)).to(self.dtype)")
        self._emit("ci = it.clamp(0, n - 1).long()")
        self._emit("cps = v.index_select(0, ax)")
        self._emit("return cps[ci] * valid")
        self._indent -= 1
        self._emit()
        self._emit("def bigint_from_string(self, s, max_digits, radix=10):")
        self._indent += 1
        self._emit('"""Parse a decimal String into a little-endian base-10 digit')
        self._emit("array of width max_digits — the BigInt construction surface")
        self._emit("(Emma 2026-05-28). Substrate-pure: gather the codepoint block,")
        self._emit("map each digit char to its value (codepoint - 48, masked so")
        self._emit("padding -> 0), and reverse-align big-endian string order into")
        self._emit("little-endian digit order by a computed-index gather:")
        self._emit("digit[j] = dig[L-1-j] for j < L (L = string_length), else 0.")
        self._emit("No host loop/branch/.item() on a digit value; max_digits is a")
        self._emit("structural width literal (the output-array shape). High digits")
        self._emit('beyond max_digits saturate (drop). "12345",md=8 -> [5,4,3,2,1,0,0,0]."""')
        self._emit("ax = self._str_axes()")
        self._emit("m = ax.shape[0]")
        self._emit("cps = s.index_select(0, ax)")
        self._emit("length = self.string_length(s)")
        self._emit("dig = (cps - 48.0) * (cps != 0).to(self.dtype)")
        self._emit("md = int(max_digits)")
        self._emit("j = _torch.arange(md, dtype=self.dtype, device=self.device)")
        self._emit("idx = length - 1.0 - j")
        self._emit("valid = ((idx >= 0) & (idx < m)).to(self.dtype)")
        self._emit("gi = idx.clamp(0, m - 1).long()")
        self._emit("return dig.index_select(0, gi) * valid")
        self._indent -= 1
        self._emit()
        self._emit("def wrap(self, value):")
        self._indent += 1
        self._emit('"""JavaScriptObject.wrap(x) — lift a primitive (int /')
        self._emit('float / string / bool) into a JavaScriptObject. Just')
        self._emit('routes through `_as_any_vector` which already handles')
        self._emit('the primitive-to-vector coercion."""')
        self._emit("return self._as_any_vector(value)")
        self._indent -= 1
        self._emit()
        self._emit("def js_add(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_add(a, b) — JavaScript-coercive `+`.')
        self._emit('If either operand has AXIS_STRING_FLAG set, dispatches to')
        self._emit('string_concat. Otherwise element-wise vector add (numeric')
        self._emit('path). Per Emma 2026-05-10: this is how the JSO override')
        self._emit('absorbs JS\\\'s coercive + semantics.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("# String coercion: if either side carries the string flag,")
        self._emit("# concatenate them as strings. Promote a numeric operand to")
        self._emit("# a string by reading its real-axis value and calling str().")
        self._emit("if self.is_string(av) or self.is_string(bv):")
        self._indent += 1
        self._emit("a_str = av if self.is_string(av) else self.make_string(str(int(self._js_coerce_real(av))) if float(self._js_coerce_real(av)).is_integer() else str(self._js_coerce_real(av)))")
        self._emit("b_str = bv if self.is_string(bv) else self.make_string(str(int(self._js_coerce_real(bv))) if float(self._js_coerce_real(bv)).is_integer() else str(self._js_coerce_real(bv)))")
        self._emit("return self.string_concat(a_str, b_str)")
        self._indent -= 1
        self._emit("return av + bv")
        self._indent -= 1
        self._emit()
        self._emit("def js_strict_eq(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_strict_eq(a, b) — Sutra interpretation')
        self._emit('of `===` per Emma 2026-05-10:')
        self._emit('    bool operator ===(var a, var b) {')
        self._emit('        return defuzzify(a == b);')
        self._emit('    }')
        self._emit('More strictness than the substrate `==` (which is cosine-')
        self._emit('fuzzy similarity) — the defuzzify polarizes the fuzzy')
        self._emit('result along the truth axis. NOT JavaScript reference-')
        self._emit('equality; explicitly redefined for the Sutra surface.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("# Strict equality via element-wise difference norm.")
        self._emit("# Cosine + defuzzify_trit polarizes 'similar but not")
        self._emit("# identical' to the neutral 0, which is wrong for JS")
        self._emit("# `===` (wants binary true/false). Using the diff norm")
        self._emit("# instead: ||a - b|| ≈ 0 iff a and b are component-wise")
        self._emit("# equal. tanh(c - k*||a-b||) maps to +1 at zero diff and")
        self._emit("# saturates to -1 quickly for any non-zero diff.")
        self._emit("# Substrate-pure (substrate audit 2026-06-19): keep diff_norm")
        self._emit("# and tanh as 0-d TENSORS and scatter the truth into AXIS_TRUTH")
        self._emit("# directly, not float()/make_truth, so `===` stays on-graph like")
        self._emit("# eq/eq_synthetic (the float(.item()) form severed autograd).")
        self._emit("diff_norm = _torch.linalg.norm(av - bv)")
        self._emit("truth = _torch.tanh(5.0 - 100.0 * diff_norm)")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = truth")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def js_strict_neq(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_strict_neq(a, b) — `!==` (negation')
        self._emit('of `===`). Computes js_strict_eq, then flips the truth')
        self._emit('axis: a +1 result becomes -1 and vice versa."""')
        self._emit("eq = self.js_strict_eq(a, b)")
        self._emit("# Flip the truth-axis component. Vector clone so we don't")
        self._emit("# mutate the input.")
        self._emit("out = eq.clone()")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = -eq[self.semantic_dim + self.AXIS_TRUTH]")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def js_loose_eq(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_loose_eq(a, b) — JavaScript `==`')
        self._emit('with type coercion. If one side is a string and the')
        self._emit('other is a number, coerce the number to a string and')
        self._emit('compare. If one side is a bool, coerce the bool to a')
        self._emit('number (true=1, false=0) and compare. Otherwise falls')
        self._emit('through to strict equality.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("a_is_str = self.is_string(av)")
        self._emit("b_is_str = self.is_string(bv)")
        self._emit("# String-vs-number coercion: promote the non-string to a")
        self._emit("# string and compare codepoints.")
        self._emit("if a_is_str and not b_is_str:")
        self._indent += 1
        self._emit("r = self._js_coerce_real(bv)")
        self._emit("b_promoted = self.make_string(str(int(r)) if float(r).is_integer() else str(r))")
        self._emit("return self.js_strict_eq(av, b_promoted)")
        self._indent -= 1
        self._emit("if b_is_str and not a_is_str:")
        self._indent += 1
        self._emit("r = self._js_coerce_real(av)")
        self._emit("a_promoted = self.make_string(str(int(r)) if float(r).is_integer() else str(r))")
        self._emit("return self.js_strict_eq(a_promoted, bv)")
        self._indent -= 1
        self._emit("# Same kind (both strings or both numbers): defer to strict.")
        self._emit("return self.js_strict_eq(av, bv)")
        self._indent -= 1
        self._emit()
        self._emit("def js_loose_neq(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_loose_neq(a, b) — `!=` (negation')
        self._emit('of loose `==`)."""')
        self._emit("eq = self.js_loose_eq(a, b)")
        self._emit("out = eq.clone()")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = -eq[self.semantic_dim + self.AXIS_TRUTH]")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        # ---- Ordered comparisons (js_lt / js_gt / js_le / js_ge) ----
        # ECMAScript Abstract Relational Comparison: if BOTH operands
        # are strings → lexicographic by codepoint; otherwise coerce
        # to numbers and compare numerically. NaN on either side makes
        # all four operators return false. Per the JS-interop carve-out
        # (CLAUDE.md "Vibe-coded projects" §"intentional compatibility
        # code"): host-scalar coercion in these methods is the
        # documented compat boundary, parallel to how js_strict_eq /
        # js_loose_eq already cross host for the comparison itself.
        self._emit("def _js_str_cmp(self, av, bv):")
        self._indent += 1
        self._emit('"""Lexicographic compare of two String values. Returns')
        self._emit('-1, 0, +1 (memcmp-style). First differing codepoint')
        self._emit('decides; shorter-with-matching-prefix is less. Host')
        self._emit('int arithmetic over codepoint axes (JS-interop')
        self._emit('compat boundary)."""')
        self._emit("ax = self._str_axes()")
        self._emit("a_cps = av.index_select(0, ax)")
        self._emit("b_cps = bv.index_select(0, ax)")
        self._emit("la = int(self.string_length(av).item())")
        self._emit("lb = int(self.string_length(bv).item())")
        self._emit("n = min(la, lb)")
        self._emit("for i in range(n):")
        self._indent += 1
        self._emit("ai = int(a_cps[i].item())")
        self._emit("bi = int(b_cps[i].item())")
        self._emit("if ai != bi:")
        self._indent += 1
        self._emit("return -1 if ai < bi else 1")
        self._indent -= 1
        self._indent -= 1
        self._emit("if la == lb:")
        self._indent += 1
        self._emit("return 0")
        self._indent -= 1
        self._emit("return -1 if la < lb else 1")
        self._indent -= 1
        self._emit()
        self._emit("def _js_relational(self, a, b, op):")
        self._indent += 1
        self._emit('"""ECMAScript Abstract Relational Comparison core. `op`')
        self._emit('is one of "<", ">", "<=", ">=". Both-string → lex compare;')
        self._emit('otherwise numeric on AXIS_REAL. NaN on either side → false')
        self._emit('(returns make_truth(-1.0))."""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("if self.is_string(av) and self.is_string(bv):")
        self._indent += 1
        self._emit("c = self._js_str_cmp(av, bv)")
        self._emit('if op == "<":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if c < 0 else -1.0)")
        self._indent -= 1
        self._emit('if op == ">":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if c > 0 else -1.0)")
        self._indent -= 1
        self._emit('if op == "<=":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if c <= 0 else -1.0)")
        self._indent -= 1
        self._emit("return self.make_truth(1.0 if c >= 0 else -1.0)")
        self._indent -= 1
        self._emit("# Numeric path: coerce to real-axis scalars and compare.")
        self._emit("# NaN on either side → false for all four operators")
        self._emit("# (ECMAScript IsLessThan returns undefined → false).")
        self._emit("ra = self._js_coerce_real(av)")
        self._emit("rb = self._js_coerce_real(bv)")
        self._emit("if ra != ra or rb != rb:")
        self._indent += 1
        self._emit("return self.make_truth(-1.0)")
        self._indent -= 1
        self._emit('if op == "<":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if ra < rb else -1.0)")
        self._indent -= 1
        self._emit('if op == ">":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if ra > rb else -1.0)")
        self._indent -= 1
        self._emit('if op == "<=":')
        self._indent += 1
        self._emit("return self.make_truth(1.0 if ra <= rb else -1.0)")
        self._indent -= 1
        self._emit("return self.make_truth(1.0 if ra >= rb else -1.0)")
        self._indent -= 1
        self._emit()
        self._emit("def js_lt(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_lt(a, b) — JS `<` with type')
        self._emit('coercion. Both-string → lex compare; otherwise numeric')
        self._emit('compare on AXIS_REAL. NaN on either side → false."""')
        self._emit('return self._js_relational(a, b, "<")')
        self._indent -= 1
        self._emit()
        self._emit("def js_gt(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_gt(a, b) — JS `>` with type')
        self._emit('coercion (symmetric to js_lt with operands swapped)."""')
        self._emit('return self._js_relational(a, b, ">")')
        self._indent -= 1
        self._emit()
        self._emit("def js_le(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_le(a, b) — JS `<=`. NOT defined as')
        self._emit('!(a > b) because of NaN: under JS semantics both `a > b`')
        self._emit('and `a <= b` are false when either side is NaN, so the')
        self._emit('negation identity fails. Explicit comparison instead."""')
        self._emit('return self._js_relational(a, b, "<=")')
        self._indent -= 1
        self._emit()
        self._emit("def js_ge(self, a, b):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_ge(a, b) — JS `>=`. Same NaN-safety')
        self._emit('reasoning as js_le."""')
        self._emit('return self._js_relational(a, b, ">=")')
        self._indent -= 1
        self._emit()
        self._emit("def js_truthy(self, a):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_truthy(a) — JS truthy/falsy table.')
        self._emit('Falsy: 0, "", null, undefined, NaN, false. Everything else')
        self._emit('truthy. Returns a polarized fuzzy on the truth axis (+1')
        self._emit('truthy, -1 falsy).')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("# Strings: falsy iff length zero.")
        self._emit("if self.is_string(av):")
        self._indent += 1
        self._emit("truthy = 1.0 if self.string_length(av) > 0 else -1.0")
        self._emit("return self.make_truth(truthy)")
        self._indent -= 1
        self._emit("# Numbers (real-axis scalars): falsy iff exactly zero. NaN")
        self._emit("# is also falsy in JS — torch.isnan handles it.")
        self._emit("r = self._js_coerce_real(av)")
        self._emit("import math as _math")
        self._emit("if r != r or r == 0.0:")  # NaN check + zero check
        self._indent += 1
        self._emit("return self.make_truth(-1.0)")
        self._indent -= 1
        self._emit("return self.make_truth(1.0)")
        self._indent -= 1
        self._emit()
        self._emit("def js_typeof(self, a):")
        self._indent += 1
        self._emit('"""JavaScriptObject.js_typeof(a) — returns a substrate')
        self._emit('String carrying one of: "number", "string", "boolean",')
        self._emit('"object", "undefined". Detected by reading the value\\\'s')
        self._emit('flag axes; defaults to "number" when no specific flag is')
        self._emit('set (the most common case for transpiled TS values).')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("if self.is_string(av):")
        self._indent += 1
        self._emit('return self.make_string("string")')
        self._indent -= 1
        self._emit("# All other detection paths fall back to number — Sutra")
        self._emit("# doesn't have a runtime distinction between numbers and")
        self._emit("# bare vectors today. Object / boolean / undefined")
        self._emit("# discrimination needs prototype-chain support and the")
        self._emit("# AXIS_AXON_POPULATED sentinel, both partial today.")
        self._emit('return self.make_string("number")')
        self._indent -= 1
        self._emit()
        self._emit("def string_concat(self, a, b):")
        self._indent += 1
        self._emit('"""Concatenate two String values. Reads codepoints from a')
        self._emit('then b into a fresh String vector. Overflow (a-len + b-len')
        self._emit('exceeds string_max_length) raises — the synthetic budget is')
        self._emit('a hard cap. 2026-05-08 addition for TS string + string."""')
        self._emit('# Substrate-pure (Audit REAL LEAK #5; was string_length host')
        self._emit('# ints + `if la+lb>max: raise` + two host `for` copy loops).')
        self._emit('# Concat = shift b right by len(a) and add: a permutation')
        self._emit('# (gather by a shifted index) of the codepoint block, the')
        self._emit('# VSA-native operation Emma specified. Overflow positions')
        self._emit('# fall off the gather mask = saturate, no raise (no-runtime-')
        self._emit('# errors-by-mechanism). All tensor ops.')
        self._emit("ax = self._str_axes()")
        self._emit("n = ax.shape[0]")
        self._emit("la = self.string_length(a)")
        self._emit("a_cps = a.index_select(0, ax)")
        self._emit("b_cps = b.index_select(0, ax)")
        self._emit("src = _torch.arange(n, dtype=self.dtype, device=self.device) - la")
        self._emit("sv = ((src >= 0) & (src < n)).to(self.dtype)")
        self._emit("b_shift = b_cps[src.clamp(0, n - 1).long()] * sv")
        self._emit("out_cps = a_cps + b_shift")
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_STRING_FLAG] = 1.0")
        self._emit("v = v.index_copy(0, ax, out_cps)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def _i2s_pows(self):")
        self._indent += 1
        self._emit('"""Cached power-of-10 table for int_to_string digit')
        self._emit('extraction. Length = the dtype exactness bound (7 digits')
        self._emit('float32, 15 float64) — beyond it the input integer is')
        self._emit('already inexact in the dtype."""')
        self._emit("if not hasattr(self, '_i2s_pows_cache') or self._i2s_pows_cache is None:")
        self._indent += 1
        self._emit("D = 15 if self.dtype == _torch.float64 else 7")
        self._emit("self._i2s_pows_cache = 10.0 ** _torch.arange("
                   "D, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit("return self._i2s_pows_cache")
        self._indent -= 1
        self._emit()
        self._emit("def int_to_string(self, x):")
        self._indent += 1
        self._emit('"""Render an integer NUMBER as a substrate String — the')
        self._emit("number->string formatter (strings.md § Integer formatting).")
        self._emit("Digit extraction is MOD-FREE (Math.mod is banned; measured")
        self._emit("vector-collapse): digit_k = floor(a/10^k) - 10*floor(a/10^(k+1)).")
        self._emit("Leading zeros gate on the quotient-significance mask (0 renders")
        self._emit("'0'); negatives gate codepoint 45 into slot 0 and shift digits")
        self._emit("right by one — a gather by shifted index, the same VSA-native")
        self._emit("permutation string_concat uses. round() first: the INT contract.")
        self._emit("Exact within the dtype bound (7 digits float32 / 15 float64);")
        self._emit('beyond it output is valid-but-unspecified (input already inexact)."""')
        self._emit("a0 = self._scalar(x)")
        self._emit("neg = (a0 < 0).to(self.dtype)")
        self._emit("a = _torch.round(_torch.abs(a0))")
        self._emit("pows = self._i2s_pows()")
        self._emit("D = pows.shape[0]")
        self._emit("q = _torch.floor(a / pows)")
        self._emit("qn = _torch.floor(a / (pows * 10.0))")
        self._emit("digits = q - 10.0 * qn")
        self._emit("nd = _torch.clamp((q > 0).to(self.dtype).sum(), min=1.0)")
        self._emit("ax = self._str_axes()")
        self._emit("n = ax.shape[0]")
        self._emit("idx = _torch.arange(n, dtype=self.dtype, device=self.device)")
        self._emit("place = nd - 1.0 - (idx - neg)")
        self._emit("valid = ((place >= 0) & (place < D) & (idx - neg >= 0))"
                   ".to(self.dtype)")
        self._emit("gath = digits[place.clamp(0, D - 1).long()]")
        self._emit("out_cps = valid * (48.0 + gath) + "
                   "(idx == 0).to(self.dtype) * neg * 45.0")
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_STRING_FLAG] = 1.0")
        self._emit("v = v.index_copy(0, ax, out_cps)")
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def num_to_string(self, x):")
        self._indent += 1
        self._emit('"""Decimal display formatter (strings.md § Decimal formatting):')
        self._emit("shortest decimal, <= 6 fractional digits (round-half-away at the")
        self._emit("6th), trailing fractional zeros trimmed; integral values render")
        self._emit("with no point ('3.0' -> '3', a documented divergence from Python")
        self._emit("str). Pure composition of shipped machinery: gated sign scatter +")
        self._emit("int_to_string(ip) + a fixed-width right-trimmed fraction String,")
        self._emit('joined by string_concat. Exactness rides the dtype mantissa."""')
        self._emit("s = self._scalar(x)")
        self._emit("neg = (s < 0).to(self.dtype)")
        self._emit("a = _torch.abs(s)")
        self._emit("ip = _torch.floor(a)")
        self._emit("f6 = _torch.round((a - ip) * 1000000.0)")
        self._emit("# carry: rounding the fraction to exactly 10^6 bumps the")
        self._emit("# integer part (1.9999995 -> 2). Exact indicator, no branch.")
        self._emit("carry = _torch.clamp(1.0 - _torch.abs(f6 - 1000000.0), min=0.0)")
        self._emit("ip = ip + carry")
        self._emit("f6 = f6 - carry * 1000000.0")
        self._emit("ip_str = self.int_to_string(ip)")
        self._emit("ax = self._str_axes()")
        self._emit("n = ax.shape[0]")
        self._emit("# sign: string_concat reads lengths from the codepoint block,")
        self._emit("# so a zeroed vector concatenates as the empty string.")
        self._emit("sign_v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("sign_v = sign_v.index_copy(0, ax[:1], (45.0 * neg).reshape(1))")
        self._emit("# fraction digits, MSD first, KEEPING leading zeros (3.05 ->")
        self._emit("# '05'): d_k = floor(f6/10^(5-k)) - 10*floor(f6/10^(6-k)).")
        self._emit("fpows = self._i2s_pows()[:6]  # 1..1e5")
        self._emit("fq = _torch.floor(f6 / fpows)")
        self._emit("fqn = _torch.floor(f6 / (fpows * 10.0))")
        self._emit("fdig = (fq - 10.0 * fqn).flip(0)  # MSD first")
        self._emit("# right-trim: length = max(k+1 where fdig[k] != 0), 0 if all zero")
        self._emit("fpos = _torch.arange(1, 7, dtype=self.dtype, device=self.device)")
        self._emit("flen = (fpos * (fdig >= 0.5).to(self.dtype)).max()")
        self._emit("# pack '.' + digits into a fresh String, gated empty when flen==0")
        self._emit("idx = _torch.arange(n, dtype=self.dtype, device=self.device)")
        self._emit("has_frac = (flen >= 0.5).to(self.dtype)")
        self._emit("is_dot = (idx == 0).to(self.dtype)")
        self._emit("dig_pos = idx - 1.0")
        self._emit("dig_valid = ((dig_pos >= 0) & (dig_pos < flen)).to(self.dtype)")
        self._emit("dig_gath = fdig[dig_pos.clamp(0, 5).long()]")
        self._emit("frac_cps = has_frac * (is_dot * 46.0 + dig_valid * (48.0 + dig_gath))")
        self._emit("frac_v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("frac_v = frac_v.index_copy(0, ax, frac_cps)")
        self._emit("return self.string_concat("
                   "self.string_concat(sign_v, ip_str), frac_v)")
        self._indent -= 1
        self._emit()
        self._emit("def string_to_python(self, v):")
        self._indent += 1
        self._emit('"""Decode a String value back to a Python str. This is the')
        self._emit('substrate -> host MONITORING / decode boundary (CLAUDE.md')
        self._emit('explicitly allows decoding substrate output for reporting),')
        self._emit('the analogue of argmax_cosine returning a host index at the')
        self._emit('terminal commit. The int()/.item() here are AT that boundary,')
        self._emit('not inside a substrate op definition. string_length is now a')
        self._emit('0-d tensor, so coerce once here for the host range."""')
        self._emit("n = int(self.string_length(v).item())")
        self._emit("chars = []")
        self._emit("for i in range(n):")
        self._indent += 1
        self._emit("axis = self._string_axis(i)")
        self._emit("# round(), not int(): a select() superposition leaves the")
        self._emit("# winner's codepoints at ~(1-eps)*cp — int() truncated 101.9997")
        self._emit("# to 101 and garbled every decoded character by one.")
        self._emit("chars.append(chr(round(v[self.semantic_dim + axis].item())))")
        self._indent -= 1
        self._emit('return "".join(chars)')
        self._indent -= 1
        self._emit()
        self._emit("def make_trit(self, t):")
        self._indent += 1
        self._emit('"""Three-valued primitive class — aliases make_truth."""')
        self._emit("return self.make_truth(t)")
        self._indent -= 1
        self._emit()
        self._emit("def defuzzify_trit(self, v, iters=10, beta=2.0):")
        self._indent += 1
        self._emit('"""Three-way polarizer toward {-1, 0, +1}. Substrate-pure')
        self._emit('(Audit REAL LEAK #2). Reads the truth axis as a 0-d tensor')
        self._emit('view (no .item()/float()), runs `iters` beta-sharpening steps')
        self._emit('via a runtime for-range over a structural-parameter loop')
        self._emit('count (per Audit #4 reclassification: range() over a')
        self._emit('structural index, with no host scalar branch on data, is')
        self._emit('substrate-pure). Each step: three substrate-pure self.exp')
        self._emit('readouts + tensor arithmetic; then a 0-d-tensor scatter back')
        self._emit('onto the truth axis.')
        self._emit('')
        self._emit('The iters parameter is now runtime-variable per Emma 2026-')
        self._emit('05-28: with iters=1 or 2, β-changes do not get compound-')
        self._emit('doubled across the unroll, keeping the gradient surface')
        self._emit('trainable. Spec semantics: iters defaults to 10 (matches the')
        self._emit('prior codegen-unroll behavior); callers can override.')
        self._emit('"""')
        self._emit("idx = self.semantic_dim + self.AXIS_TRUTH")
        self._emit("x = v[idx]")
        self._emit("b = self._st(beta)")
        self._emit("# Runtime for-range over the structural iters count")
        self._emit("# (Audit #4-style structural-index loop, NOT a data branch).")
        self._emit("# `int(iters)` handles both Python-int literals and 0-d")
        self._emit("# tensor structural indices; iters is a loop count, not data.")
        self._emit("for _t in range(int(iters)):")
        self._indent += 1
        self._emit("w_neg = self._exp_s(-b * (x + 1.0) ** 2)")
        self._emit("w_zero = self._exp_s(-b * x ** 2)")
        self._emit("w_pos = self._exp_s(-b * (x - 1.0) ** 2)")
        self._emit("s = w_neg + w_zero + w_pos")
        self._emit("x = (-w_neg + w_pos) / s")
        self._emit("b = b * 2.0")
        self._indent -= 1
        self._emit("out = v.clone()")
        self._emit("out[idx] = x")
        self._emit("return out")
        self._indent -= 1
        self._emit()

        self._emit("# ---- Integer-axis arithmetic (BigInt building blocks) ----")
        self._emit("#")
        self._emit("# Per planning/sutra-spec/arbitrary-precision.md sub-decision 4")
        self._emit("# (locked Emma 2026-05-28): integer-division primitive.")
        self._emit("# `int_div(x, m)` is floor division; `int_mod(x, m)` is")
        self._emit("# modulo. Both substrate-pure: take and return 0-d tensors,")
        self._emit("# no .item() / float() extraction. Building block for the")
        self._emit("# arbitrary-precision _digit_array_add scan (carry =")
        self._emit("# int_div(sum, radix), digit = int_mod(sum, radix)).")
        self._emit()
        self._emit("def int_div(self, x, m):")
        self._indent += 1
        self._emit('"""Floor division on 0-d tensors. Substrate-pure (no extraction).')
        self._emit('Wraps _torch.div with floor rounding mode; preserves grad.')
        self._emit('"""')
        self._emit("x = self._st(x)")
        self._emit("m = self._st(m)")
        self._emit("return _torch.div(x, m, rounding_mode='floor')")
        self._indent -= 1
        self._emit()
        self._emit("def int_mod(self, x, m):")
        self._indent += 1
        self._emit('"""Integer modulo on 0-d tensors. Substrate-pure (no extraction).')
        self._emit('For positive x and m: x - int_div(x, m) * m, computed as the')
        self._emit('tensor remainder op (`%`) which matches Python `%` semantics')
        self._emit('on non-negative integer-valued tensors.')
        self._emit('"""')
        self._emit("x = self._st(x)")
        self._emit("m = self._st(m)")
        self._emit("return x - _torch.div(x, m, rounding_mode='floor') * m")
        self._indent -= 1
        self._emit()
        self._emit("def digit_array_add(self, digits_a, digits_b, radix=10):")
        self._indent += 1
        self._emit('"""Parallel carry-propagation add over digit arrays.')
        self._emit('')
        self._emit('Per planning/sutra-spec/arbitrary-precision.md (Option A,')
        self._emit("locked Emma 2026-05-28). Inputs: 1-d tensors `digits_a` and")
        self._emit("`digits_b` of equal length N, each value in [0, radix). Returns")
        self._emit("a 1-d tensor of length N with the carry-propagated sum digits;")
        self._emit("overflow saturates (top-digit carry-out is dropped). Substrate-")
        self._emit("pure: every step is a tensor op, no .item() / float() extraction,")
        self._emit("no host scalar branch on data.")
        self._emit('')
        self._emit("Algorithm (v1): per-position pairwise sum; extract initial digit")
        self._emit("+ carry; then N stride-1 propagation steps where each step")
        self._emit("shifts the carry up by 1 position and re-extracts digit + carry.")
        self._emit("Each step is a parallel tensor op (cat + add + div + mul); N")
        self._emit("steps are needed to handle the worst-case all-nines carry chain.")
        self._emit("Loop count N is a structural index (digit-array width), per")
        self._emit("Audit #4 reclassification, so host range() over it is substrate-")
        self._emit("pure. (A true Hillis-Steele log2(N)-step version using generate/")
        self._emit("propagate signals is a possible v2 optimization; v1 ships the")
        self._emit("simpler O(N)-step form that's correct and substrate-pure.)")
        self._emit('"""')
        self._emit("a = self._st(digits_a)")
        self._emit("b = self._st(digits_b)")
        self._emit("r = self._st(radix)")
        self._emit("# Per-position sum, then split into initial digit + carry.")
        self._emit("s = a + b")
        self._emit("c = _torch.div(s, r, rounding_mode='floor')")
        self._emit("d = s - c * r")
        self._emit("# N stride-1 propagation steps. Each step: shift the carry up")
        self._emit("# by 1 position, add it to the digit array, re-extract carry.")
        self._emit("# After N steps every carry has propagated to its terminal")
        self._emit("# position (or fallen off the top — overflow saturates).")
        self._emit("n = d.shape[0] if d.dim() == 1 else d.numel()")
        self._emit("for _step in range(n):")
        self._indent += 1
        self._emit("# Carry from position i feeds position i+1.")
        self._emit("zero = _torch.zeros(1, dtype=c.dtype, device=c.device)")
        self._emit("c_shifted = _torch.cat([zero, c[:n - 1]])")
        self._emit("d = d + c_shifted")
        self._emit("new_c = _torch.div(d, r, rounding_mode='floor')")
        self._emit("d = d - new_c * r")
        self._emit("c = new_c")
        self._indent -= 1
        self._emit("# Top-digit carry-out is silently dropped (overflow saturates).")
        self._emit("return d")
        self._indent -= 1
        self._emit()

        self._emit("# ---- Logical operators — smooth polynomial form ----")
        self._emit("#")
        self._emit("# Same Lagrange-derived polynomials as the numpy backend:")
        self._emit("#   min(a, b) = (a + b + ab - a² - b² + a²b²) / 2")
        self._emit("#   max(a, b) = (a + b - ab + a² + b² - a²b²) / 2")
        self._emit("# Exact on {-1, 0, +1}², C^∞ everywhere, CUDA via torch ops.")
        self._emit()
        self._emit("def _as_truth_vector(self, x):")
        self._indent += 1
        self._emit('"""Return x as a tensor. Scalar / bool → make_truth."""')
        self._emit("if isinstance(x, _torch.Tensor):")
        self._indent += 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_truth(1.0 if x else -1.0)")
        self._indent -= 1
        self._emit("return self.make_truth(float(x))")
        self._indent -= 1
        self._emit()
        # logical_and / logical_or / logical_not runtime methods
        # deleted in v0.3 step 4 — operator lowering + stdlib inline
        # replaces every caller with the inline polynomial form.

        self._emit("# ---- Ordered comparison — pure tensor ops, no branches ----")
        self._emit()
        self._emit("def _real_projector(self):")
        self._indent += 1
        self._emit('"""Diagonal real-axis projector. Cached tensor on device."""')
        self._emit("if not hasattr(self, '_real_proj_cache') or self._real_proj_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("idx = self.semantic_dim + self.AXIS_REAL")
        self._emit("M[idx, idx] = 1.0")
        self._emit("self._real_proj_cache = M")
        self._indent -= 1
        self._emit("return self._real_proj_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _truth_from_real(self):")
        self._indent += 1
        self._emit('"""Matrix moving the real-axis entry to the truth axis."""')
        self._emit("if not hasattr(self, '_t_from_r_cache') or self._t_from_r_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("M[self.semantic_dim + self.AXIS_TRUTH,")
        self._indent += 1
        self._emit("self.semantic_dim + self.AXIS_REAL] = 1.0")
        self._indent -= 1
        self._emit("self._t_from_r_cache = M")
        self._indent -= 1
        self._emit("return self._t_from_r_cache")
        self._indent -= 1
        self._emit()
        self._emit("def _real_from_truth(self):")
        self._indent += 1
        self._emit('"""Matrix moving the truth-axis entry to the real axis')
        self._emit('(cached; the inverse-direction mate of _truth_from_real)."""')
        self._emit("if not hasattr(self, '_r_from_t_cache') or self._r_from_t_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("M[self.semantic_dim + self.AXIS_REAL,")
        self._indent += 1
        self._emit("self.semantic_dim + self.AXIS_TRUTH] = 1.0")
        self._indent -= 1
        self._emit("self._r_from_t_cache = M")
        self._indent -= 1
        self._emit("return self._r_from_t_cache")
        self._indent -= 1
        self._emit()
        self._emit("def cast_number_to_truth(self, x):")
        self._indent += 1
        self._emit('"""`(fuzzy|bool|trit) NUMBER` — the numeric→truth cast')
        self._emit("(types.md § Casting): the one cast pair that genuinely")
        self._emit("moves an axis. _cnum lifts a 0-d/host number onto AXIS_REAL")
        self._emit("(entry boundary), then a cached permutation-style matmul")
        self._emit('moves that entry to AXIS_TRUTH. Pure tensor ops throughout."""')
        self._emit("return self._truth_from_real() @ self._cnum(x)")
        self._indent -= 1
        self._emit()
        self._emit("def cast_truth_to_number(self, x):")
        self._indent += 1
        self._emit('"""`(number|int) TRUTH` — the truth→numeric cast: moves the')
        self._emit("AXIS_TRUTH entry to AXIS_REAL by the cached inverse-direction")
        self._emit('matmul. Truth values are canonical d-dim vectors (make_truth),')
        self._emit('which _cnum passes through unchanged."""')
        self._emit("return self._real_from_truth() @ self._cnum(x)")
        self._indent -= 1
        self._emit()
        self._emit("CMP_SLOPE = 100.0")
        self._emit()
        self._emit("def gt(self, a, b):")
        self._indent += 1
        self._emit('"""a > b — differentiable tanh on real-axis difference."""')
        self._emit("av = self._as_complex_vector(a)")
        self._emit("bv = self._as_complex_vector(b)")
        self._emit("diff_r = self._real_projector() @ (av - bv)")
        self._emit("signed = _torch.tanh(self.CMP_SLOPE * diff_r)")
        self._emit("return self._truth_from_real() @ signed")
        self._indent -= 1
        self._emit()
        # lt / ge / le runtime methods deleted in v0.3 step 4.

        self._emit("# ---- Equality — cosine similarity on tensors ----")
        self._emit()
        self._emit("def eq(self, a, b):")
        self._indent += 1
        self._emit('"""a == b — cosine similarity, eps-guarded divide, no branch.')
        self._emit('')
        self._emit('Substrate-pure: returns a fresh vector with cos scattered into')
        self._emit('the truth axis as a 0-d tensor (NOT float()). This keeps the')
        self._emit('value on-graph when `==` is composed inside trainable surfaces')
        self._emit('(defuzz β harness; the gradient chain that float(cos.item())')
        self._emit('previously detached). The numerics are identical to the prior')
        self._emit('make_truth(float(cos.item())) form.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("na = _torch.sqrt((av * av).sum())")
        self._emit("nb = _torch.sqrt((bv * bv).sum())")
        self._emit("cos = (av * bv).sum() / (na * nb + _torch.finfo(self.dtype).tiny)")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = cos")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        # Number-family equality — the exact relu indicator (Emma
        # 2026-07-08). Cosine eq is DEGENERATE at the zero vector
        # (cos(0,v) is 0/0 → a runtime zero can never equal anything,
        # including zero), which made zero-testing unreachable — see
        # planning/findings/2026-07-08-zero-equality-reads-neutral-
        # cosine-degenerate.md.
        self._emit("def num_eq(self, a, b):")
        self._indent += 1
        self._emit('"""Number == number via the exact indicator:')
        self._emit('truth = 2*relu(1 - |x - y|) - 1 — +1 at equal, -1 at')
        self._emit('|diff| >= 1 (exact gap 2.0 at integer spacing, no residual;')
        self._emit('the neural-Unix keystone on the truth convention). Fractional')
        self._emit('nearness interpolates linearly (|d|=0.5 -> 0, neutral). The')
        self._emit('unit width is a trainable-surface candidate (a gain k on |d|),')
        self._emit('fixed at 1 today. All tensor ops; differentiable a.e."""')
        self._emit("d = _torch.abs(self._scalar(a) - self._scalar(b))")
        self._emit("truth = 2.0 * _torch.clamp(1.0 - d, min=0.0) - 1.0")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = truth")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def num_neq(self, a, b):")
        self._indent += 1
        self._emit('"""!= for number-family values — truth-axis negation of num_eq."""')
        self._emit("return -self.num_eq(a, b)")
        self._indent -= 1
        self._emit()
        # Synthetic-axis equality — Euclidean distance + tanh
        # (2026-05-08 directive). For int / float / complex / char /
        # string operands; cosine doesn't distinguish well between
        # values that share direction but differ in magnitude.
        self._emit("def eq_synthetic(self, a, b):")
        self._indent += 1
        self._emit('"""Synthetic-axis equality — 1 - 2*tanh(||a - b||).')
        self._emit('')
        self._emit('Substrate-pure scatter (same shape as eq): truth is a 0-d tensor')
        self._emit('written into the truth axis; no float()/.item() boundary inside')
        self._emit('the operation.')
        self._emit('"""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("diff = av - bv")
        self._emit("dist = _torch.sqrt((diff * diff).sum())")
        self._emit("truth = 1.0 - 2.0 * _torch.tanh(dist)")
        self._emit("out = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = truth")
        self._emit("return out")
        self._indent -= 1
        self._emit()
        self._emit("def neq_synthetic(self, a, b):")
        self._indent += 1
        self._emit('"""!= for synthetic-axis values — negation of eq_synthetic."""')
        self._emit("return -self.eq_synthetic(a, b)")
        self._indent -= 1
        self._emit()
        # neq runtime method deleted in v0.3 step 4.

        self._emit("def _as_any_vector(self, x):")
        self._indent += 1
        self._emit('"""Coerce any runtime value to a d-dim tensor for comparison.')
        self._emit('')
        self._emit('Python str → make_string (NOT embed): all callers')
        self._emit('(js_add, js_strict_eq, js_loose_eq, js_typeof, js_truthy,')
        self._emit('js_lt/gt/le/ge, eq_synthetic, neq_synthetic) inspect the')
        self._emit('AXIS_STRING_FLAG via is_string() to dispatch — embedding')
        self._emit('the string would clear the flag and break all of them.')
        self._emit('Fixed 2026-05-20 when the JSO ordered-comparison work')
        self._emit('exposed the pre-existing js_add/loose_eq/typeof/truthy')
        self._emit('latent bug. JS-interop carve-out (CLAUDE.md "Vibe-coded')
        self._emit('projects" §"intentional compatibility code")."""')
        self._emit("if isinstance(x, _torch.Tensor):")
        self._indent += 1
        self._emit("if x.dim() == 0:")
        self._indent += 1
        self._emit("# 0-d scalar tensor (e.g. a loop counter after the soft-")
        self._emit("# mux freeze turns it into a 0-d tensor, or a slot-loaded")
        self._emit("# int): a NUMBER, so lift it onto the real axis like")
        self._emit("# make_real does for a Python scalar — but on-device, no")
        self._emit("# float() readout. Mirrors _as_complex_vector. Without this")
        self._emit("# `diff = scalar - number_vector` broadcasts the scalar")
        self._emit("# across every axis, so eq_synthetic(loop_counter, k) never")
        self._emit("# reads 0 distance even when equal — equality halts in")
        self._emit("# loops then never fire (finding 2026-06-17-while-loop-")
        self._emit("# halt-is-single-condition-only.md, equality-halt root cause).")
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = x")
        self._emit("return v")
        self._indent -= 1
        self._emit("return x")
        self._indent -= 1
        self._emit("if isinstance(x, bool):")
        self._indent += 1
        self._emit("return self.make_truth(1.0 if x else -1.0)")
        self._indent -= 1
        self._emit("if isinstance(x, (int, float)):")
        self._indent += 1
        self._emit("return self.make_real(float(x))")
        self._indent -= 1
        self._emit("if isinstance(x, str):")
        self._indent += 1
        self._emit("return self.make_string(x)")
        self._indent -= 1
        self._emit("raise TypeError(f'cannot coerce {type(x).__name__} to a tensor for comparison')")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Defuzzification — torch version ----")
        self._emit()
        self._emit("def _truth_projector(self):")
        self._indent += 1
        self._emit('"""Diagonal dim×dim projector onto truth axis. Cached tensor."""')
        self._emit("if not hasattr(self, '_truth_proj_cache') or self._truth_proj_cache is None:")
        self._indent += 1
        self._emit("M = _torch.zeros((self.dim, self.dim), dtype=self.dtype, device=self.device)")
        self._emit("idx = self.semantic_dim + self.AXIS_TRUTH")
        self._emit("M[idx, idx] = 1.0")
        self._emit("self._truth_proj_cache = M")
        self._indent -= 1
        self._emit("return self._truth_proj_cache")
        self._indent -= 1
        self._emit()
        # defuzzify runtime method deleted in v0.3 step 4. The
        # `defuzzy(x)` source form is expanded inline by codegen.py's
        # `_defuzzy_expr_src` into ten nested eq calls (inherited
        # unchanged here).
        self._emit()
        self._emit("def make_random_rotation(self, angle, n_planes=1, seed=None):")
        self._indent += 1
        self._emit('"""Block-diagonal Haar rotation, scaled by fractional power.')
        self._emit('')
        self._emit("Seeded by numpy's RandomState for deterministic Haar-uniformity;")
        self._emit("the result is converted to a torch tensor on self.device. Used")
        self._emit("by eigenrotation loops.")
        self._emit('"""')
        self._emit("import numpy as _np_bridge")
        self._emit("rng = _np_bridge.random.RandomState(seed if seed is not None else self.seed)")
        self._emit("A = rng.randn(self.semantic_dim, self.semantic_dim)")
        self._emit("Q_sem_np, _ = _np_bridge.linalg.qr(A)")
        self._emit("w, V = _np_bridge.linalg.eig(Q_sem_np)")
        self._emit("phases = _np_bridge.angle(w) * (angle / _np_bridge.pi)")
        self._emit("R_sem_np = _np_bridge.real((V * _np_bridge.exp(1j * phases)) @ _np_bridge.linalg.inv(V))")
        self._emit("R_sem = _torch.as_tensor(R_sem_np, dtype=self.dtype, device=self.device)")
        self._emit("R = _torch.eye(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("R[:self.semantic_dim, :self.semantic_dim] = R_sem")
        self._emit("return R")
        self._indent -= 1
        self._emit()
        self._emit("def compile_prototypes(self, prototype_vectors, frame_seed=None):")
        self._indent += 1
        self._emit("return dict(prototype_vectors)")
        self._indent -= 1
        self._emit()
        self._emit("def _step(self, state, R, target, halted, k, threshold, eps=1e-12):")
        self._indent += 1
        self._emit('"""RNN cell: one branchless tail-recursive loop step (torch tensor ops)."""')
        self._emit("cand = R @ state")
        self._emit("cand = cand / (_torch.linalg.norm(cand) + eps)")
        self._emit("sim = _torch.dot(cand, target) / (_torch.linalg.norm(target) + eps)")
        self._emit("halt = 1.0 / (1.0 + _torch.exp(-k * (sim - threshold)))")
        self._emit("one = _torch.tensor(1.0, dtype=self.dtype, device=self.device)")
        self._emit("halted = _torch.minimum(halted + halt, one)")
        self._emit("state = (1.0 - halted) * cand + halted * state")
        self._emit("return state, halted")
        self._indent -= 1
        self._emit()
        self._emit("def loop(self, initial_state, rotation, compiled_prototypes,")
        self._indent += 1
        self._emit("target_name=None, threshold=0.5, max_iters=50, k=20.0, frame_seed=None):")
        self._emit('"""Branchless RNN-style tail-recursive loop cell (torch backend).')
        self._emit('')
        self._emit("Same semantics as the numpy backend. T-step unroll, soft halt via")
        self._emit("sigmoid, output gating via AXIS_LOOP_DONE. Autograd-friendly:")
        self._emit("every op is differentiable with respect to state, target, threshold.")
        self._emit('"""')
        self._emit("state = initial_state.clone()")
        self._emit("halted = _torch.tensor(0.0, dtype=self.dtype, device=self.device)")
        self._emit("iters_active = _torch.tensor(0.0, dtype=self.dtype, device=self.device)")
        self._emit("if target_name is not None:")
        self._indent += 1
        self._emit("target = compiled_prototypes[target_name]")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("target = next(iter(compiled_prototypes.values()))")
        self._indent -= 1
        self._emit("for _t in range(max_iters):")
        self._indent += 1
        self._emit("iters_active = iters_active + (1.0 - halted)")
        self._emit("state, halted = self._step(state, rotation, target, halted, k, threshold)")
        self._indent -= 1
        self._emit("# Output gating: scale value axes by halted; mark AXIS_LOOP_DONE.")
        self._emit("gated = state * halted")
        self._emit("gated[self.semantic_dim + self.AXIS_LOOP_DONE] = halted")
        self._emit("return target_name, gated, iters_active")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit(
            f"_VSA = _TorchVSA("
            f"semantic_dim={self._semantic_dim}, "
            f"synthetic_dim={self._synthetic_dim}, "
            f"seed={self.runtime_seed}, "
            f"llm_model={self._llm_model!r})"
        )
        if self._prefetch_strings:
            self._emit(f"_VSA.embed_batch({self._prefetch_strings!r})")
            # Compile-time SutraDB population (queue item 2). Every embedded
            # string in the program is now in the SutraDB codebook and
            # decodable via _VSA.nearest_string. Strings declared but not
            # used in expressions are still in the prefetch list and so
            # still get inserted; they're available for decode even though
            # no expression in the program references them.
            self._emit("_VSA.populate_sutradb()")
            # Compile-time rotation pre-warm (queue item 3). Conservatively
            # pre-warms a rotation matrix for every codebook entry so the
            # runtime never pays the QR cost on the hot path. Over-warms
            # for fillers that aren't ever used as roles, but the cost is
            # one-time and proportional to the codebook size which is
            # small for typical programs. A targeted "scan for bind() role
            # args only" pass would be a future optimization.
            self._emit("_VSA.prewarm_rotation_cache()")
        # Module-level constants exposing the static axon-key analysis
        # results. Downstream tooling (Yantra's kernel router for lazy
        # axon evaluation; future per-receiver projection) reads these
        # instead of re-parsing the .su source. Always emit even when
        # empty so consumers can rely on the symbol being present.
        # See sutra_compiler.axon_keys.
        bound = getattr(self, "_axon_keys_bound", frozenset())
        read = getattr(self, "_axon_keys_read", frozenset())
        self._emit(f"AXON_KEYS_BOUND = frozenset({sorted(bound)!r})")
        self._emit(f"AXON_KEYS_READ = frozenset({sorted(read)!r})")
        self._emit()
        self._emit()
        self._emit("def _argmax_cosine(query, candidates):")
        self._indent += 1
        self._emit('"""Vectorized cosine argmax on torch tensors.')
        self._emit('')
        self._emit("Stacks candidates into (N, d), computes all N cosines as one")
        self._emit("matmul against the query, returns the candidate at the argmax.")
        self._emit("This is the GPU-shaped form: O(1) big kernel, not O(N) small ones.")
        self._emit("")
        self._emit("Note: SutraDB integration (queue item 2) does NOT route through")
        self._emit("here — see _VSA.nearest_string for the embedded-DB decode path.")
        self._emit("argmax_cosine takes a runtime candidate-vector list; SutraDB is")
        self._emit("the compile-time-populated string-to-embedding store.")
        self._emit('"""')
        self._emit("if not candidates:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("M = _torch.stack([")
        self._indent += 1
        self._emit("_torch.as_tensor(c, dtype=_DTYPE, device=_DEVICE)")
        self._emit("for c in candidates")
        self._indent -= 1
        self._emit("])")
        self._emit("q = _torch.as_tensor(query, dtype=_DTYPE, device=_DEVICE)")
        self._emit("row_norms = _torch.linalg.norm(M, dim=1)")
        self._emit("q_norm = _torch.linalg.norm(q)")
        self._emit("# eps-guard q_norm the same way row_norms is guarded below")
        self._emit("# (Audit REAL LEAK #7 — was `if float(q_norm) == 0: return")
        self._emit("# candidates[0]`, a data-dependent host branch). Zero query")
        self._emit("# norm → M@q is the zero vector → all scores equal → argmax")
        self._emit("# picks index 0, exactly the old behaviour, no host branch.")
        self._emit("safe_qn = _torch.where(q_norm > 0, q_norm, _torch.ones_like(q_norm))")
        self._emit("safe_rn = _torch.where(row_norms > 0, row_norms, _torch.ones_like(row_norms))")
        self._emit("scores = (M @ q) / (safe_rn * safe_qn)")
        self._emit("neg_inf = _torch.full_like(scores, float('-inf'))")
        self._emit("scores = _torch.where(row_norms > 0, scores, neg_inf)")
        self._emit("return candidates[int(_torch.argmax(scores).item())]")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit_select_helper()
        self._emit()
        self._emit("def _vector_map_lookup(pairs, key):")
        self._indent += 1
        self._emit('"""Cosine-argmax lookup for vector-keyed maps.')
        self._emit("")
        self._emit("Stacks the codebook keys into a single substrate matrix at")
        self._emit("call time, runs one matmul + argmax against the query, and")
        self._emit("returns the value at the matching index. No host control")
        self._emit("flow on the runtime path.")
        self._emit('"""')
        self._emit("if not pairs:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("keys = _torch.stack([")
        self._indent += 1
        self._emit("_torch.as_tensor(k, dtype=_DTYPE, device=_DEVICE)")
        self._emit("for k, _ in pairs")
        self._indent -= 1
        self._emit("])")
        self._emit("q = _torch.as_tensor(key, dtype=_DTYPE, device=_DEVICE)")
        self._emit("row_norms = _torch.linalg.norm(keys, dim=1)")
        self._emit("q_norm = _torch.linalg.norm(q)")
        self._emit("safe_rn = _torch.where(row_norms > 0, row_norms, _torch.ones_like(row_norms))")
        self._emit("safe_qn = _torch.where(q_norm > 0, q_norm, _torch.ones_like(q_norm))")
        self._emit("scores = (keys @ q) / (safe_rn * safe_qn)")
        self._emit("neg_inf = _torch.full_like(scores, float('-inf'))")
        self._emit("scores = _torch.where(row_norms > 0, scores, neg_inf)")
        self._emit("return pairs[int(_torch.argmax(scores).item())][1]")
        self._indent -= 1


def translate_module(module: ast.Module, **kwargs) -> str:
    """Translate a parsed Sutra module to self-contained torch Python.

    Same simplify + prefetch-collection pass as the numpy backend, so
    the torch backend benefits from every algebraic rewrite and the
    batched Ollama pre-fetch without duplicating that infrastructure.
    """
    from .simplify import simplify_module, collect_embedded_strings
    from .inliner import inline_stdlib_calls
    from .promise_desugar import desugar_promises
    from .loop_desugar import desugar_implicit_loops
    from .axon_keys import collect_axon_keys
    # Axon-keys static analysis runs BEFORE simplify/inline so that
    # the keys pulled out match the user-visible source pattern (the
    # simplifier may rewrite things in ways that obscure the bind/
    # item shape — e.g. inlined helpers fusing across function
    # boundaries — even though the runtime semantics are unchanged).
    bound_keys, read_keys = collect_axon_keys(module)
    # Stage-1 promise desugar runs first — same pass as the CPU codegen.
    desugar_promises(module)
    # Implicit tail-recursive loop desugar: loop(expr){body} ->
    # synthesized iterative_loop LoopFunctionDecl + LoopCallStmt
    # (queue.md item 0). Before inlining so the synthesized loop
    # function bodies get the same stdlib inlining as hand-written ones.
    desugar_implicit_loops(module)
    # Inline stdlib calls — same pass as the CPU codegen uses.
    inline_stdlib_calls(module)
    simplify_module(module)
    strings = collect_embedded_strings(module)
    cg = PyTorchCodegen(**kwargs)
    cg._prefetch_strings = strings
    cg._axon_keys_bound = bound_keys
    cg._axon_keys_read = read_keys
    # Dimension-audit diagnostic (CLAUDE.md "Subtler substrate breaches" #1,
    # substrate audit 2026-06-19): a program that embeds no codebook strings
    # (no basis_vector / embed) and binds no axon string-keys does not use the
    # LLM semantic subspace at all, so an LLM-sized semantic_dim is paid for
    # nothing (matrices scale with dim^2). collect_embedded_strings covers
    # basis_vector + embed; bound_keys/read_keys cover axon string-keys, so
    # all-three-empty is a reliable "codebook unused" signal. Warn loudly but
    # still compile (Sutra is opinionated, not authoritarian).
    if (not strings and not bound_keys and not read_keys
            and cg._semantic_dim >= 256):
        import warnings as _warnings
        _warnings.warn(
            f"semantic_dim={cg._semantic_dim} but this program uses no codebook "
            "(no basis_vector / embed, no axon string-keys); the LLM semantic "
            "subspace is unused, so the large dimension is pure cost. Consider a "
            "much smaller runtime_dim (the synthetic axes need only a handful).",
            stacklevel=2,
        )
    return cg.translate(module)
