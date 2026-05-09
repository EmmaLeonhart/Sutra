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
        self._emit("identity across runs gives the same rotation. Matches the")
        self._emit("numpy backend's hash scheme exactly when the semantic content")
        self._emit("is bit-for-bit equal.")
        self._emit('"""')
        self._emit("import hashlib")
        self._emit("b = role_vec.detach().cpu().contiguous().numpy().tobytes()")
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
        self._emit("return Q @ filler")
        self._indent -= 1
        self._emit()
        self._emit("def unbind(self, role, record):")
        self._indent += 1
        self._emit("# Q is orthogonal so unbind(role, record) = Q_role^T @ record.")
        self._emit("# Round-trip: unbind(r, bind(r, v)) = Q^T @ Q @ v = v exactly.")
        self._emit("Q = self._rotation_for(role)")
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
        # ---- Axon runtime methods ----
        # Axons share the substrate operations of the rotation hashmap
        # (an axon is a bundle of bind(role, value) terms over a
        # codebook of role-by-string-name) but are a distinct
        # user-facing class — see planning/sutra-spec/axons.md. The
        # methods below implement the substrate operations the
        # `Axon` stdlib class declares as `static intrinsic method`.
        self._emit("# ---- Axon runtime methods ----")
        self._emit("def axon_new(self):")
        self._indent += 1
        self._emit("return _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._indent -= 1
        self._emit()
        self._emit("def axon_add(self, axon, key, value):")
        self._indent += 1
        self._emit("# Key may arrive as a Python string (compile-time")
        self._emit("# identifier) or as an already-embedded vector.")
        self._emit("# Strings are auto-embedded into a basis vector.")
        self._emit("key_vec = self.embed(key) if isinstance(key, str) else key")
        self._emit("# Scalar fillers (Python int / float) are promoted to")
        self._emit("# a real-axis vector via make_real so the bind matmul")
        self._emit("# works. Per the axon spec, axons can carry values of")
        self._emit("# any kind; on the substrate they all become vectors.")
        self._emit("if isinstance(value, (int, float)):")
        self._indent += 1
        self._emit("value = self.make_real(float(value))")
        self._indent -= 1
        self._emit("return axon + self.bind(key_vec, value)")
        self._indent -= 1
        self._emit()
        self._emit("def axon_item(self, axon, key):")
        self._indent += 1
        self._emit("key_vec = self.embed(key) if isinstance(key, str) else key")
        self._emit("return self.unbind(key_vec, axon)")
        self._indent -= 1
        self._emit()
        # ---- 2D-Givens-per-slot rotation binding (synthetic subspace) ----
        # Mirrors the numpy backend's slot block. See codegen.py for the
        # block; this is the pytorch realization, with `_torch.zeros`
        # and `tensor.clone()` instead of `_np.copy()`.
        self._emit("# ---- 2D-Givens-per-slot rotation binding (synthetic subspace) ----")
        self._emit("# Mirrors the numpy backend slot block; see codegen.py.")
        self._emit("# SLOT_BASE = 5 to leave room for AXIS_LOOP_DONE at synthetic[4].")
        self._emit("SLOT_BASE = 5")
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
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("new = state.clone() if hasattr(state, 'clone') else state.copy()")
        self._emit("new[i] = float(scalar)")
        self._emit("new[j] = 0.0")
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
        self._emit("import math as _math")
        self._emit("i, j = self._slot_plane(slot_idx)")
        self._emit("c, s = _math.cos(float(angle)), _math.sin(float(angle))")
        self._emit("new = state.clone() if hasattr(state, 'clone') else state.copy()")
        self._emit("xi, xj = float(state[i]), float(state[j])")
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
        self._emit("return float(_torch.dot(a, b) / (na * nb + _torch.finfo(self.dtype).tiny))")
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
        self._emit('"""Inner / dot product → scalar."""')
        self._emit("return float(_torch.dot(a, b))")
        self._indent -= 1
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
        self._emit("def make_string(self, s):")
        self._indent += 1
        self._emit('"""Construct a String value from a Python str."""')
        self._emit("if not isinstance(s, str):")
        self._indent += 1
        self._emit("s = str(s)")
        self._indent -= 1
        self._emit("max_len = self.string_max_length()")
        self._emit("if len(s) > max_len:")
        self._indent += 1
        self._emit("raise ValueError(")
        self._emit('"string %r length %d exceeds synthetic-axis budget %d; '
                   'increase synthetic_dim" % (s, len(s), max_len))')
        self._indent -= 1
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
        self._emit('"""Return the length of String v by scanning from the')
        self._emit('highest possible char position down to the first non-zero')
        self._emit('codepoint. Trailing-zero-as-sentinel: a string with')
        self._emit('codepoint 0 in its tail will read shorter than written."""')
        self._emit("max_k = self.string_max_length()")
        self._emit("for k in range(max_k - 1, -1, -1):")
        self._indent += 1
        self._emit("axis = self._string_axis(k)")
        self._emit("if v[self.semantic_dim + axis].item() != 0.0:")
        self._indent += 1
        self._emit("return k + 1")
        self._indent -= 1
        self._indent -= 1
        self._emit("return 0")
        self._indent -= 1
        self._emit()
        self._emit("def string_char_at(self, v, i):")
        self._indent += 1
        self._emit('"""Return the codepoint at position i (as an int). Out-of-')
        self._emit('range positions return 0."""')
        self._emit("i = int(i) if not isinstance(i, int) else i")
        self._emit("if i < 0 or i >= self.string_max_length():")
        self._indent += 1
        self._emit("return 0")
        self._indent -= 1
        self._emit("axis = self._string_axis(i)")
        self._emit("return int(v[self.semantic_dim + axis].item())")
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
        self._emit('Element-wise vector add; numeric add for number-axis')
        self._emit('operands. String concatenation under `+` is deferred —')
        self._emit('strings should be wrapped explicitly today."""')
        self._emit("av = self._as_any_vector(a)")
        self._emit("bv = self._as_any_vector(b)")
        self._emit("return av + bv")
        self._indent -= 1
        self._emit()
        self._emit("def string_concat(self, a, b):")
        self._indent += 1
        self._emit('"""Concatenate two String values. Reads codepoints from a')
        self._emit('then b into a fresh String vector. Overflow (a-len + b-len')
        self._emit('exceeds string_max_length) raises — the synthetic budget is')
        self._emit('a hard cap. 2026-05-08 addition for TS string + string."""')
        self._emit("la = self.string_length(a)")
        self._emit("lb = self.string_length(b)")
        self._emit("max_len = self.string_max_length()")
        self._emit("if la + lb > max_len:")
        self._indent += 1
        self._emit("raise ValueError(")
        self._emit('"concat result length %d exceeds synthetic-axis budget %d; '
                   'increase synthetic_dim" % (la + lb, max_len))')
        self._indent -= 1
        self._emit("v = _torch.zeros(self.dim, dtype=self.dtype, device=self.device)")
        self._emit("v[self.semantic_dim + self.AXIS_STRING_FLAG] = 1.0")
        self._emit("for k in range(la):")
        self._indent += 1
        self._emit("axis = self._string_axis(k)")
        self._emit("v[self.semantic_dim + axis] = a[self.semantic_dim + axis]")
        self._indent -= 1
        self._emit("for k in range(lb):")
        self._indent += 1
        self._emit("src_axis = self._string_axis(k)")
        self._emit("dst_axis = self._string_axis(la + k)")
        self._emit("v[self.semantic_dim + dst_axis] = b[self.semantic_dim + src_axis]")
        self._indent -= 1
        self._emit("return v")
        self._indent -= 1
        self._emit()
        self._emit("def string_to_python(self, v):")
        self._indent += 1
        self._emit('"""Decode a String value back to a Python str. Useful for')
        self._emit('returning string-valued results to the host."""')
        self._emit("n = self.string_length(v)")
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
        self._emit('"""Three-way polarizer toward {-1, 0, +1} — torch version."""')
        self._emit("x = float(v[self.semantic_dim + self.AXIS_TRUTH].item())")
        self._emit("b = float(beta)")
        self._emit("for _ in range(int(iters)):")
        self._indent += 1
        self._emit("import math as _math")
        self._emit("w_neg = _math.exp(-b * (x + 1.0) ** 2)")
        self._emit("w_zero = _math.exp(-b * x ** 2)")
        self._emit("w_pos = _math.exp(-b * (x - 1.0) ** 2)")
        self._emit("s = w_neg + w_zero + w_pos")
        self._emit("x = (-w_neg + w_pos) / s")
        self._emit("b *= 2.0")
        self._indent -= 1
        self._emit("out = v.clone()")
        self._emit("out[self.semantic_dim + self.AXIS_TRUTH] = float(x)")
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
        self._emit('"""Coerce any runtime value to a d-dim tensor for comparison."""')
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
        self._emit("return self.embed(x)")
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
        self._emit('"""RNN cell: one branchless eigenrotation step (torch tensor ops)."""')
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
        self._emit('"""Branchless RNN-style eigenrotation loop (torch backend).')
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
        self._emit("if float(q_norm) == 0:")
        self._indent += 1
        self._emit("return candidates[0]")
        self._indent -= 1
        self._emit("safe_rn = _torch.where(row_norms > 0, row_norms, _torch.ones_like(row_norms))")
        self._emit("scores = (M @ q) / (safe_rn * q_norm)")
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
        self._emit('"""Identity-first lookup for vector-keyed maps, cosine fallback."""')
        self._emit("for k, v in pairs:")
        self._indent += 1
        self._emit("if k is key:")
        self._indent += 1
        self._emit("return v")
        self._indent -= 1
        self._indent -= 1
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
        self._emit("if float(q_norm) == 0:")
        self._indent += 1
        self._emit("return pairs[0][1]")
        self._indent -= 1
        self._emit("safe_rn = _torch.where(row_norms > 0, row_norms, _torch.ones_like(row_norms))")
        self._emit("scores = (keys @ q) / (safe_rn * q_norm)")
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
    # Inline stdlib calls first — same pass as the CPU codegen uses.
    inline_stdlib_calls(module)
    simplify_module(module)
    strings = collect_basis_vector_strings(module)
    cg = PyTorchCodegen(**kwargs)
    cg._prefetch_strings = strings
    return cg.translate(module)
