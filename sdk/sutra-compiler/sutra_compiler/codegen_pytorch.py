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

    def _is_pytorch_backend(self) -> bool:
        """Override: this backend emits torch tensor ops, so try/catch
        uses _torch.tanh for the polarizer."""
        return True

    def _emit_select_helper(self) -> None:
        """Torch-based softmax for the Sutra `select` primitive.

        Same numerical shape as the numpy version (subtract max for
        stability, exp, normalize, weighted sum), all on tensors so the
        whole path stays on the chosen device.
        """
        self._emit("def _select_softmax(scores, options):")
        self._indent += 1
        self._emit('"""Softmax-weighted superposition of option vectors (torch)."""')
        self._emit("s = _torch.as_tensor(scores, dtype=_DTYPE, device=_DEVICE)")
        self._emit("s = s - _torch.amax(s)")
        self._emit("w = _torch.exp(s)")
        self._emit("w = w / _torch.sum(w)")
        self._emit("opts = _torch.stack([")
        self._indent += 1
        self._emit("_torch.as_tensor(o, dtype=_DTYPE, device=_DEVICE)")
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
        self._emit("_DTYPE = _torch.float32")
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
        self._emit("# Rotation matrix cache: role-hash -> tensor on self.device.")
        self._emit("# Generating a 768x768 Haar rotation is O(d^3) on CPU (seeded")
        self._emit("# via numpy for Haar-uniformity). Cached on the GPU after the")
        self._emit("# first draw so repeated bind/unbind with the same role is a")
        self._emit("# lookup + one matmul, no transfer.")
        self._emit("self._rot_cache = {}")
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
        self._emit("self._cache_path = _os.path.join(")
        self._indent += 1
        self._emit("self._cache_dir, f'{_safe_model}-d{self.dim}.pt')")
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
        self._emit("import ollama")
        self._emit("r = ollama.embed(model=self.llm_model, input=name)")
        self._emit("v = _torch.tensor(r['embeddings'][0], dtype=self.dtype, device=self.device)")
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
        self._emit("import ollama")
        self._emit("r = ollama.embed(model=self.llm_model, input=missing)")
        self._emit("for i, name in enumerate(missing):")
        self._indent += 1
        self._emit("v = _torch.tensor(r['embeddings'][i], dtype=self.dtype, device=self.device)")
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
        self._emit("def _role_hash(self, role_vec):")
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
        self._emit('"""')
        self._emit("import hashlib")
        self._emit("# View as uint8 reinterprets the underlying bytes without")
        self._emit("# copying. bytes() then materializes them into a Python")
        self._emit("# bytes object suitable for hashlib. Same bytes as the")
        self._emit("# previous .numpy().tobytes() call (verified).")
        self._emit("b = bytes(role_vec.detach().cpu().contiguous().view(_torch.uint8))")
        self._emit("h = hashlib.blake2b(b, digest_size=8).digest()")
        self._emit("return int.from_bytes(h, 'little') & 0xFFFFFFFF")
        self._indent -= 1
        self._emit()
        self._emit("def _rotation_for(self, role_vec):")
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
        self._emit("key = self._role_hash(role_vec)")
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
        self._indent -= 1
        self._emit("return self._rot_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def bind(self, role, filler):")
        self._indent += 1
        self._emit("# Rotation binding. bind(role, filler) = Q_role @ filler. Role-")
        self._emit("# first convention (matches numpy backend and the .su demos).")
        self._emit("Q = self._rotation_for(role)")
        self._emit("# Defensively coerce filler to runtime device + dtype so a")
        self._emit("# host-side caller passing a CPU tensor doesn't device-mismatch")
        self._emit("# Q (which lives on self.device). No-op when filler is already")
        self._emit("# on the right device — matches the pattern bundle() uses.")
        self._emit("filler = _torch.as_tensor(filler, dtype=self.dtype, device=self.device)")
        self._emit("return Q @ filler")
        self._indent -= 1
        self._emit()
        self._emit("def unbind(self, role, record):")
        self._indent += 1
        self._emit("# Q is orthogonal so unbind(role, record) = Q_role^T @ record.")
        self._emit("# Round-trip: unbind(r, bind(r, v)) = Q^T @ Q @ v = v exactly.")
        self._emit("Q = self._rotation_for(role)")
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
        self._emit("def _axon_permutation_for(self, role_vec):")
        self._indent += 1
        self._emit('"""Per-key deterministic permutation of the synthetic block.')
        self._emit('Cached per role-hash, just like _rotation_for. Returns a')
        self._emit('long tensor of synthetic_dim indices on the device.')
        self._emit('"""')
        self._emit("key = self._role_hash(role_vec)")
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
        self._emit("rotated = self.bind(key_vec, value)")
        self._emit("perm = self._axon_permutation_for(key_vec)")
        self._emit("return axon + self._axon_permute_synthetic(rotated, perm)")
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
        self._emit("perm = self._axon_permutation_for(key_vec)")
        self._emit("unpermuted = self._axon_unpermute_synthetic(axon, perm)")
        self._emit("return self.unbind(key_vec, unpermuted)")
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
        self._emit("def slot_store(self, state, slot_idx, scalar):")
        self._indent += 1
        self._emit('"""Write `scalar` into the (i, j) slot plane. Substrate-pure')
        self._emit('(Audit REAL LEAK #8 slot_store part; was `new[i] =')
        self._emit('float(scalar)` — a substrate->host extraction when `scalar`')
        self._emit('is a 0-d tensor). `self._st(scalar)` keeps an already-tensor')
        self._emit('value on the substrate (no-op view) and is the literal entry')
        self._emit('boundary for a host literal — the same _st() boundary used')
        self._emit('everywhere else. i, j are structural slot indices, not data;')
        self._emit('the scatter writes are tensor ops."""')
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("new = state.clone() if hasattr(state, 'clone') else state.copy()")
        self._emit("new[i] = self._st(scalar)")
        self._emit("new[j] = self._st(0.0)")
        self._emit("return new")
        self._indent -= 1
        self._emit()
        self._emit("def slot_load(self, state, slot_idx):")
        self._indent += 1
        self._emit('"""Read the slot scalar. Returns a torch 0-dim tensor.')
        self._emit('')
        self._emit("Substrate-pure: downstream arithmetic stays in tensor land. See")
        self._emit("planning/findings/2026-04-30-substrate-purity-leak-enumeration.md.")
        self._emit('"""')
        self._emit("i, _j = self._slot_plane(slot_idx)")
        self._emit("return state[i]")
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
        self._emit("# ---- Substrate scalar primitives (boundary-leak reductions) ----")
        self._emit()
        self._emit("def truth_axis(self, vec_or_scalar):")
        self._indent += 1
        self._emit('"""Read AXIS_TRUTH from a fuzzy-vector result, or pass scalars through.')
        self._emit('')
        self._emit("Returns a torch 0-dim tensor; substrate-pure loop halt checks consume")
        self._emit("the result without crossing the Python boundary.")
        self._emit('"""')
        self._emit("if hasattr(vec_or_scalar, '__len__') and len(vec_or_scalar) > 1:")
        self._indent += 1
        self._emit("return vec_or_scalar[self.semantic_dim + self.AXIS_TRUTH]")
        self._indent -= 1
        self._emit("if _torch.is_tensor(vec_or_scalar):")
        self._indent += 1
        self._emit("return vec_or_scalar")
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
        self._emit("c = self.cos(angle)")
        self._emit("s = self.sin(angle)")
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
        self._emit("xt = self._st(x).clamp(self._EXP_LO, self._EXP_HI)")
        self._emit("return self._lerp(xt, self._EXP_XS, self._EXP_VALUES, self._EXP_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def _ln_table(self, x):")
        self._indent += 1
        self._emit('"""Natural-log lookup leaf: ln(x) for a 0-d tensor x.')
        self._emit('Non-positive / out-of-range saturates at the table edge')
        self._emit('(ln near LN_LO = a large negative - the valid limit)."""')
        self._emit("xt = self._st(x).clamp(self._LN_LO, self._LN_HI)")
        self._emit("return self._lerp(xt, self._LN_XS, self._LN_VALUES, self._LN_DX)")
        self._indent -= 1
        self._emit()
        self._emit("def _trig_reduce(self, x):")
        self._indent += 1
        self._emit('"""Reduce a 0-d angle to (-pi, pi] via x - 2pi*round(x/2pi).')
        self._emit('rotation is periodic so this is the angle it actually turns')
        self._emit('Periodic, so mod 2pi comes for free. Pure tensor."""')
        self._emit("xt = self._st(x)")
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
        self._emit("def exp(self, x):")
        self._indent += 1
        self._emit('"""exp at a scalar-typed boundary = real(cexp(x)). For real x')
        self._emit('(imag 0): realExp=[e^x,0], imaginaryExp=[1,0], product=[e^x,0],')
        self._emit('real part = e^x. This IS the documented real(exp(i*theta))')
        self._emit('projection, not a deviation. 0-d tensor out (back-compat with')
        self._emit('scalar call sites; the full complex op is cexp)."""')
        self._emit("return self._re(self.cexp(self._cnum(x)))")
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
        self._emit("def cos(self, x):")
        self._indent += 1
        self._emit('"""cos(theta) = real(exp(i*theta)) - the documented')
        self._emit('definitional reduction. exp(i*theta) = cexp of the PURE-')
        self._emit('IMAGINARY number theta*i (theta on the imag axis), so the')
        self._emit('eigenrotation turns through theta. Real part = cos."""')
        self._emit("itheta = self._mk(0.0, self._st(x))")
        self._emit("return self._re(self.imaginaryExp(itheta))")
        self._indent -= 1
        self._emit()
        self._emit("def sin(self, x):")
        self._indent += 1
        self._emit('"""sin(theta) = imag(exp(i*theta)) - imag part of the same')
        self._emit('pure-imaginary eigenrotation (theta on the imag axis)."""')
        self._emit("itheta = self._mk(0.0, self._st(x))")
        self._emit("return self._im(self.imaginaryExp(itheta))")
        self._indent -= 1
        self._emit()
        self._emit("def pow(self, x, y):")
        self._indent += 1
        self._emit('"""x^y = exp(y*ln x) - change-of-base identity. 0-d tensor."""')
        self._emit("return self.exp(self._st(y) * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def sqrt(self, x):")
        self._indent += 1
        self._emit('"""sqrt(x) = exp(0.5*ln x) - the y=1/2 case of pow."""')
        self._emit("return self.exp(0.5 * self.log(x))")
        self._indent -= 1
        self._emit()
        self._emit("def tan(self, x):")
        self._indent += 1
        self._emit('"""tan = sin/cos. cos->0 gives +/-inf (valid limit; no host if)."""')
        self._emit("return self.sin(x) / self.cos(x)")
        self._indent -= 1
        self._emit()
        self._emit("def sinh(self, x):")
        self._indent += 1
        self._emit('"""(e^x - e^-x)/2."""')
        self._emit("xt = self._st(x)")
        self._emit("return (self.exp(xt) - self.exp(-xt)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def cosh(self, x):")
        self._indent += 1
        self._emit('"""(e^x + e^-x)/2."""')
        self._emit("xt = self._st(x)")
        self._emit("return (self.exp(xt) + self.exp(-xt)) * 0.5")
        self._indent -= 1
        self._emit()
        self._emit("def tanh(self, x):")
        self._indent += 1
        self._emit('"""(e^2x - 1)/(e^2x + 1) [stable]; large |x| => exp saturates')
        self._emit('so tanh -> +/-1, the correct limit, no host range check."""')
        self._emit("e2x = self.exp(2.0 * self._st(x))")
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
        self._emit("return _torch.floor(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def ceil(self, x):")
        self._indent += 1
        self._emit('"""Round toward +∞. Substrate: torch.ceil."""')
        self._emit("return _torch.ceil(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def round(self, x):")
        self._indent += 1
        self._emit('"""Nearest integer, ties-to-even (torch default). JS Math.round')
        self._emit('is half-up — mismatch tracked in the substrate-purity audit."""')
        self._emit("return _torch.round(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def trunc(self, x):")
        self._indent += 1
        self._emit('"""Truncate toward zero. Substrate: torch.trunc."""')
        self._emit("return _torch.trunc(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def abs(self, x):")
        self._indent += 1
        self._emit('"""|x|. Substrate: torch.abs."""')
        self._emit("return _torch.abs(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def sign(self, x):")
        self._indent += 1
        self._emit('"""-1 / 0 / +1. Substrate: torch.sign."""')
        self._emit("return _torch.sign(self._st(x))")
        self._indent -= 1
        self._emit()
        self._emit("def fmod(self, x, m):")
        self._indent += 1
        self._emit('"""Truncation modulus (JS / C / C# / Rust / TS `%`): result')
        self._emit('has the sign of x. x - m·trunc(x/m). Divisor 0 yields a NaN')
        self._emit('tensor — the mathematically-valid degenerate result, not a')
        self._emit('host ZeroDivisionError (no scalar control flow)."""')
        self._emit("xt = self._st(x)")
        self._emit("mt = self._st(m)")
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
        self._emit("xt = self._st(x)")
        self._emit("mt = self._st(m)")
        self._emit("theta = self._TWO_PI * xt / mt")
        self._emit("phi = _torch.atan2(self.sin(theta), self.cos(theta))")
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
        self._emit("xt = self._st(x)")
        self._emit("mt = self._st(m)")
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
        self._emit("def norm(self, v):")
        self._indent += 1
        self._emit('"""L2 norm. Scalar result."""')
        self._emit("return float(_torch.linalg.norm(v))")
        self._indent -= 1
        self._emit()
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
        self._emit("Norm = norm")
        self._emit("Normalize = normalize")
        self._emit("RotationFor = rotation_for")
        self._emit()
        self._emit("# ---- Vector component accessors (debugging / teaching) ----")
        self._emit()
        self._emit("def component(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i of v over the full extended state vector."""')
        self._emit("return float(v[int(i)].item())")
        self._indent -= 1
        self._emit()
        self._emit("def semantic(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i within the semantic block."""')
        self._emit("idx = int(i)")
        self._emit("if idx < 0 or idx >= self.semantic_dim:")
        self._indent += 1
        self._emit("raise IndexError(")
        self._indent += 1
        self._emit('f"semantic index {idx} out of range [0, {self.semantic_dim})")')
        self._indent -= 1
        self._indent -= 1
        self._emit("return float(v[idx].item())")
        self._indent -= 1
        self._emit()
        self._emit("def synthetic(self, v, i):")
        self._indent += 1
        self._emit('"""Return element i within the synthetic block."""')
        self._emit("idx = int(i)")
        self._emit("if idx < 0 or idx >= self.synthetic_dim:")
        self._indent += 1
        self._emit("raise IndexError(")
        self._indent += 1
        self._emit('f"synthetic index {idx} out of range [0, {self.synthetic_dim})")')
        self._indent -= 1
        self._indent -= 1
        self._emit("return float(v[self.semantic_dim + idx].item())")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Canonical-axis accessors (real/imag/truth) ----")
        self._emit()
        self._emit("def real(self, v):")
        self._indent += 1
        self._emit("return float(v[self.semantic_dim + self.AXIS_REAL].item())")
        self._indent -= 1
        self._emit()
        self._emit("def imag(self, v):")
        self._indent += 1
        self._emit("return float(v[self.semantic_dim + self.AXIS_IMAG].item())")
        self._indent -= 1
        self._emit()
        self._emit("def truth(self, v):")
        self._indent += 1
        self._emit("return float(v[self.semantic_dim + self.AXIS_TRUTH].item())")
        self._indent -= 1
        self._emit()
        self._emit("def make_real(self, x):")
        self._indent += 1
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_REAL] = float(x)")
        self._emit("return v")
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
        self._emit("def is_char(self, v):")
        self._indent += 1
        self._emit('"""True iff v is a String value (kept as `is_char` for')
        self._emit('backward-compat with code that pre-dated the rename to')
        self._emit('AXIS_STRING_FLAG; new code should use is_string)."""')
        self._emit("return bool(v[self.semantic_dim + self.AXIS_STRING_FLAG].item() >= 0.5)")
        self._indent -= 1
        self._emit()
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
        self._emit('"""Construct a String value from a Python str."""')
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
        self._emit("def string_length(self, v):")
        self._indent += 1
        self._emit('"""Length of String v, substrate-pure (Audit REAL LEAK #5;')
        self._emit('was a host `for k in range`, `.item()`, host `if`, host')
        self._emit('`return k+1`). Gather the codepoint block, mark non-zero')
        self._emit('positions, take the highest 1-based position that is')
        self._emit('non-zero: length = max((k+1) where cps[k] != 0). All tensor')
        self._emit('ops; 0-d tensor out. Trailing-zero-as-sentinel preserved')
        self._emit('(a 0 codepoint in the tail reads shorter, same as before)."""')
        self._emit("ax = self._str_axes()")
        self._emit("cps = v.index_select(0, ax)")
        self._emit("nz = (cps != 0).to(self.dtype)")
        self._emit("pos = _torch.arange(1, ax.shape[0] + 1, dtype=self.dtype, device=self.device)")
        self._emit("return (pos * nz).max()")
        self._indent -= 1
        self._emit()
        self._emit("def string_char_at(self, v, i):")
        self._indent += 1
        self._emit('"""Codepoint at position i, substrate-pure (Audit REAL LEAK')
        self._emit('#5; was `int(i)`, host `if i<0 or i>=...`, `int(.item())`).')
        self._emit('Gather the codepoint block, mask out-of-range to 0 (saturate,')
        self._emit('no host branch/raise). 0-d tensor out."""')
        self._emit("ax = self._str_axes()")
        self._emit("n = ax.shape[0]")
        self._emit("it = self._st(i)")
        self._emit("valid = ((it >= 0) & (it < n)).to(self.dtype)")
        self._emit("ci = it.clamp(0, n - 1).long()")
        self._emit("cps = v.index_select(0, ax)")
        self._emit("return cps[ci] * valid")
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
        self._emit("a_str = av if self.is_string(av) else self.make_string(str(int(self.real(av))) if float(self.real(av)).is_integer() else str(self.real(av)))")
        self._emit("b_str = bv if self.is_string(bv) else self.make_string(str(int(self.real(bv))) if float(self.real(bv)).is_integer() else str(self.real(bv)))")
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
        self._emit("import math as _math")
        self._emit("diff_norm = float(_torch.linalg.norm(av - bv))")
        self._emit("truth = _math.tanh(5.0 - 100.0 * diff_norm)")
        self._emit("return self.make_truth(truth)")
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
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = -float(eq[self.semantic_dim + self.AXIS_TRUTH].item())")
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
        self._emit("r = self.real(bv)")
        self._emit("b_promoted = self.make_string(str(int(r)) if float(r).is_integer() else str(r))")
        self._emit("return self.js_strict_eq(av, b_promoted)")
        self._indent -= 1
        self._emit("if b_is_str and not a_is_str:")
        self._indent += 1
        self._emit("r = self.real(av)")
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
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = -float(eq[self.semantic_dim + self.AXIS_TRUTH].item())")
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
        self._emit("ra = self.real(av)")
        self._emit("rb = self.real(bv)")
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
        self._emit("r = self.real(av)")
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
        self._emit("chars.append(chr(int(v[self.semantic_dim + axis].item())))")
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
        self._emit('(Audit REAL LEAK #2; was float(v[..].item()) + host for-range')
        self._emit('+ _math.exp + float(x) writeback). Reads the truth axis as a')
        self._emit('0-d tensor view (no .item()/float()), runs the spec-fixed')
        self._emit('10-step beta-sharpening as a straight-line tensor-op chain')
        self._emit('unrolled at codegen time (like the defuzzy loop(10): the')
        self._emit('unrolled form is what the fusion pass targets), each step')
        self._emit('three substrate-pure self.exp readouts, then a 0-d-tensor')
        self._emit('scatter back onto the truth axis. The iters arg is kept for')
        self._emit('signature compat; the spec definition is 10, like defuzzy."""')
        self._emit("idx = self.semantic_dim + self.AXIS_TRUTH")
        self._emit("x = v[idx]")
        self._emit("b = self._st(beta)")
        # Emit-time unroll: the spec-level definition is 10 iterations
        # (defuzzy is loop(10)). Unrolling here means the EMITTED code
        # is a straight-line tensor-op chain — no runtime host `for`.
        for _ in range(10):
            self._emit("w_neg = self.exp(-b * (x + 1.0) ** 2)")
            self._emit("w_zero = self.exp(-b * x ** 2)")
            self._emit("w_pos = self.exp(-b * (x - 1.0) ** 2)")
            self._emit("s = w_neg + w_zero + w_pos")
            self._emit("x = (-w_neg + w_pos) / s")
            self._emit("b = b * 2.0")
        self._emit("out = v.clone()")
        self._emit("out[idx] = x")
        self._emit("return out")
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
        self._emit('"""a == b — cosine similarity, eps-guarded divide, no branch."""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("na = _torch.sqrt((av * av).sum())")
        self._emit("nb = _torch.sqrt((bv * bv).sum())")
        self._emit("cos = (av * bv).sum() / (na * nb + _torch.finfo(self.dtype).tiny)")
        self._emit("return self.make_truth(float(cos.item()))")
        self._indent -= 1
        self._emit()
        # Synthetic-axis equality — Euclidean distance + tanh
        # (2026-05-08 directive). For int / float / complex / char /
        # string operands; cosine doesn't distinguish well between
        # values that share direction but differ in magnitude.
        self._emit("def eq_synthetic(self, a, b):")
        self._indent += 1
        self._emit('"""Synthetic-axis equality — 1 - 2*tanh(||a - b||)."""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("diff = av - bv")
        self._emit("dist = _torch.sqrt((diff * diff).sum())")
        self._emit("truth = 1.0 - 2.0 * _torch.tanh(dist)")
        self._emit("return self.make_truth(float(truth.item()))")
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
    from .simplify import simplify_module, collect_basis_vector_strings
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
    strings = collect_basis_vector_strings(module)
    cg = PyTorchCodegen(**kwargs)
    cg._prefetch_strings = strings
    cg._axon_keys_bound = bound_keys
    cg._axon_keys_read = read_keys
    return cg.translate(module)
