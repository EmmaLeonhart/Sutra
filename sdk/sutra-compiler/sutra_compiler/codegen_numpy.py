"""AST -> pure-numpy Python source translator.

This is the demo-path backend. It emits self-contained Python modules
that depend only on numpy — no fly-brain imports, no spiking simulator,
no learned MBON readouts. VSA ops run as plain matrix operations on CPU.

The fly-brain backend (`codegen_flybrain.py`) stays for fly-brain-only
work. The demo path (what the paper points at, what fresh clones run)
goes through this file.

Design is a thin subclass of `FlyBrainCodegen`: the translator logic for
expressions, statements, loops, declarations is identical — only the
prelude changes. `snap` is not supported here (the demo substrate has no
cleanup circuit; programs that need `snap` should target the fly-brain
backend).
"""

from __future__ import annotations

from typing import List

from . import ast_nodes as ast
from .codegen_flybrain import FlyBrainCodegen, CodegenNotSupported


class NumpyCodegen(FlyBrainCodegen):
    """Emits a self-contained numpy-only module.

    Overrides the prelude and rejects `snap()` at codegen time. Everything
    else (function bodies, bind/bundle/unbind/similarity/argmax_cosine,
    map lookup, loop unrolling) is inherited unchanged.
    """

    # Frozen-LLM substrate. The numpy backend runs on frozen LLM
    # embeddings via Ollama — no random-vector fallback. If Ollama is
    # unavailable or the model is missing, compiled programs raise.
    # Default model: nomic-embed-text (768-dim). Avoid mxbai-embed-large
    # per CLAUDE.md — it has a documented attention-sink defect on
    # diacritics and is treated as a known-broken baseline.
    DEFAULT_LLM_MODEL = "nomic-embed-text"
    DEFAULT_LLM_DIM = 768

    def __init__(self, *, runtime_dim: int | None = None,
                 runtime_seed: int = 42,
                 llm_model: str | None = None) -> None:
        self._llm_model = llm_model if llm_model is not None else self.DEFAULT_LLM_MODEL
        # If using LLM default, dim is the LLM's; otherwise allow override.
        if runtime_dim is None:
            runtime_dim = self.DEFAULT_LLM_DIM
        # List of strings that appear in `basis_vector("...")` calls,
        # populated by translate_module() between simplify and codegen.
        # The codegen emits a batched Ollama pre-fetch at module init
        # to replace N sequential HTTP round-trips with one call.
        self._prefetch_strings: list[str] = []
        super().__init__(
            runtime_dim=runtime_dim,
            runtime_seed=runtime_seed,
            runtime_n_kc=0,
            runtime_use_hemibrain=False,
        )

    # Ops not supported by the pure-numpy substrate. `snap` requires a
    # cleanup circuit (MB spiking model or equivalent); rotation-based
    # loop primitives need the same. Programs that use these should
    # target `codegen_flybrain` instead.
    _UNSUPPORTED_BUILTINS = frozenset({
        "snap",
        "make_rotation",
        "compile_prototypes",
        "geometric_loop",
    })

    def _translate_eigenrotation_loop(self, stmt):
        """Eigenrotation on the numpy substrate.

        Differences from fly-brain:
        - Haar-random orthogonal matrix (fly-brain's uniform-angle
          Givens gives a tight periodic orbit that never explores).
        - Threshold is parsed from the condition (the numeric literal
          side of `similarity(state, target) < T`). Fly-brain uses a
          fixed 0.3 because matching is KC-pattern Jaccard; numpy
          matches on raw cosine, which has a very different scale.
        """
        from . import ast_nodes as ast
        lid = self._next_loop_id()
        state_var = self._extract_loop_state_var(stmt.body)
        target_expr = self._extract_loop_target(stmt.condition)

        threshold = 0.9
        cond = stmt.condition
        if isinstance(cond, ast.BinaryOp):
            for side in (cond.left, cond.right):
                if isinstance(side, ast.FloatLiteral):
                    threshold = side.value
                elif isinstance(side, ast.IntLiteral):
                    threshold = float(side.value)

        self._emit(f"{lid}_R = _VSA.make_random_rotation("
                   f"angle=1.0, n_planes=_VSA.dim // 2, seed=_VSA.seed)")
        self._emit(f"{lid}_target = {target_expr}")
        self._emit(f"{lid}_protos = _VSA.compile_prototypes("
                   f"{{\"target\": {lid}_target}})")
        self._emit(f"{lid}_name, {state_var}, {lid}_iters = _VSA.loop(")
        self._indent += 1
        self._emit(f"{state_var}, {lid}_R, {lid}_protos,")
        self._emit(f"target_name=\"target\", threshold={threshold}, max_iters=500)")
        self._indent -= 1

    def _translate_call(self, call: ast.Call) -> str:
        callee = call.callee
        if isinstance(callee, ast.Identifier):
            if callee.name in self._UNSUPPORTED_BUILTINS:
                raise CodegenNotSupported(
                    call,
                    f"`{callee.name}` is not supported on the pure-numpy "
                    f"substrate; use the fly-brain backend if you need it",
                )
        return super()._translate_call(call)

    def _emit_prelude(self) -> None:
        self._emit('"""Generated by sutra_compiler.codegen_numpy. Do not edit by hand."""')
        self._emit("from __future__ import annotations")
        self._emit()
        self._emit("import numpy as _np")
        self._emit()
        self._emit()
        self._emit("class _NumpyVSA:")
        self._indent += 1
        self._emit('"""Frozen-LLM-backed VSA runtime. Rotation binding, normalized bundle.')
        self._emit('')
        self._emit('Bind is role-seeded Haar-random orthogonal rotation applied to')
        self._emit('filler: bind(filler, role) = Q_role @ filler, with Q_role cached')
        self._emit('by role-vector hash. Unbind is the transpose. See')
        self._emit('planning/findings/2026-04-22-rotation-binding-prototype-design.md')
        self._emit('for the compromise this prototype takes (rotation in the same')
        self._emit('768-d semantic subspace as sign-flip did, not in a dedicated')
        self._emit('synthetic subspace — so cross-talk stays 1/sqrt(d) statistical).')
        self._emit('"""')
        self._emit()
        self._emit("def __init__(self, dim, seed, llm_model):")
        self._indent += 1
        self._emit("self.dim = dim")
        self._emit("self.seed = seed")
        self._emit("self.llm_model = llm_model")
        self._emit("self._codebook = {}")
        self._emit("# Rotation matrix cache: role-vector-hash -> orthogonal matrix.")
        self._emit("# Generating a 768x768 Haar rotation is O(d^3); caching makes")
        self._emit("# repeated bind/unbind with the same role O(d^2) lookup + matmul.")
        self._emit("self._rot_cache = {}")
        self._emit("# On-disk embedding cache. Second-and-later runs load every")
        self._emit("# previously-seen basis_vector(...) string from disk instead of")
        self._emit("# hitting Ollama. Cache is keyed by (model, dim) so changing")
        self._emit("# either invalidates cleanly (different cache file).")
        self._emit("import os as _os")
        self._emit("self._cache_dir = _os.path.join(")
        self._indent += 1
        self._emit("_os.environ.get('XDG_CACHE_HOME', _os.path.expanduser('~/.cache')),")
        self._emit("'sutra', 'embeddings')")
        self._indent -= 1
        self._emit("_os.makedirs(self._cache_dir, exist_ok=True)")
        self._emit("# Sanitize model name for use as filename.")
        self._emit("_safe_model = llm_model.replace('/', '_').replace(':', '_')")
        self._emit("self._cache_path = _os.path.join(")
        self._indent += 1
        self._emit("self._cache_dir, f'{_safe_model}-d{dim}.npz')")
        self._indent -= 1
        self._emit("self._load_disk_cache()")
        self._indent -= 1
        self._emit()
        self._emit("def _load_disk_cache(self):")
        self._indent += 1
        self._emit('"""Populate self._codebook from the on-disk embedding cache.')
        self._emit('')
        self._emit("Tolerant of a missing or corrupt cache file — a failed load")
        self._emit("leaves self._codebook empty and lets Ollama fetches repopulate")
        self._emit("it. The cache is performance, not correctness.")
        self._emit('"""')
        self._emit("import os as _os")
        self._emit("if not _os.path.exists(self._cache_path):")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("try:")
        self._indent += 1
        self._emit("with _np.load(self._cache_path, allow_pickle=False) as data:")
        self._indent += 1
        self._emit("for key in data.files:")
        self._indent += 1
        self._emit("self._codebook[key] = data[key].astype(_np.float64)")
        self._indent -= 1
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
        self._emit('"""Persist self._codebook atomically to disk.')
        self._emit('')
        self._emit("Writes to a tempfile then renames, so a partial write (crash,")
        self._emit("SIGKILL) leaves the old cache intact rather than corrupted.")
        self._emit("Called whenever embed / embed_batch fetches new vectors so")
        self._emit("subsequent runs hit the cache on module init.")
        self._emit('"""')
        self._emit("import os as _os, tempfile as _tempfile")
        self._emit("if not self._codebook:")
        self._indent += 1
        self._emit("return")
        self._indent -= 1
        self._emit("fd, tmp = _tempfile.mkstemp(")
        self._indent += 1
        self._emit("dir=self._cache_dir, prefix='.tmp-', suffix='.npz')")
        self._indent -= 1
        self._emit("_os.close(fd)")
        self._emit("try:")
        self._indent += 1
        self._emit("_np.savez(tmp, **self._codebook)")
        self._emit("# _np.savez writes tmp.npz, but tempfile handed us tmp ending")
        self._emit("# in .npz already — reconcile: savez appends .npz only if the")
        self._emit("# path does not already end in .npz. Python tempfile gives us")
        self._emit("# a .npz path, so savez leaves it as-is.")
        self._emit("_os.replace(tmp, self._cache_path)")
        self._indent -= 1
        self._emit("except Exception:")
        self._indent += 1
        self._emit("# Cache-write failure is non-fatal. Remove the tmp and continue.")
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
        self._emit('"""Frozen-LLM embedding via Ollama. No random fallback.')
        self._emit("If Ollama is unavailable or the model is missing, this raises.")
        self._emit("The numpy backend is defined as running on frozen LLM embeddings;")
        self._emit('a random-vector fallback is not Sutra."""')
        self._emit("if name not in self._codebook:")
        self._indent += 1
        self._emit("import ollama")
        self._emit("r = ollama.embed(model=self.llm_model, input=name)")
        self._emit("v = _np.array(r['embeddings'][0], dtype=_np.float64)")
        self._emit("# Mean-center: sign-flip binding assumes zero-mean vectors.")
        self._emit("# Raw LLM embeddings cluster in a cone (all-positive-ish), which")
        self._emit("# collapses sign(role) to a near-constant pattern and destroys")
        self._emit("# role-filler separation. Centering restores the algebra.")
        self._emit("v = v - _np.mean(v)")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("# Truncate or pad to self.dim if the LLM dim differs.")
        self._emit("if v.shape[0] != self.dim:")
        self._indent += 1
        self._emit("if v.shape[0] > self.dim:")
        self._indent += 1
        self._emit("v = v[:self.dim]")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("v = _np.concatenate([v, _np.zeros(self.dim - v.shape[0])])")
        self._indent -= 1
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._indent -= 1
        self._emit("self._codebook[name] = v")
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit("return self._codebook[name].copy()")
        self._indent -= 1
        self._emit()
        self._emit("def embed_batch(self, names):")
        self._indent += 1
        self._emit('"""Batched Ollama embed: one HTTP round-trip for many names.')
        self._emit('')
        self._emit("Populates self._codebook for every name in `names` that isn't")
        self._emit("already cached. Subsequent embed(name) calls hit the cache in")
        self._emit("memory with no network round-trip. Replaces N sequential")
        self._emit("embed() calls at module init with one batched call; real")
        self._emit("wall-clock win on programs with many basis_vector strings.")
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
        self._emit("v = _np.array(r['embeddings'][i], dtype=_np.float64)")
        self._emit("v = v - _np.mean(v)")
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._emit("if v.shape[0] != self.dim:")
        self._indent += 1
        self._emit("if v.shape[0] > self.dim:")
        self._indent += 1
        self._emit("v = v[:self.dim]")
        self._indent -= 1
        self._emit("else:")
        self._indent += 1
        self._emit("v = _np.concatenate([v, _np.zeros(self.dim - v.shape[0])])")
        self._indent -= 1
        self._emit("n = _np.linalg.norm(v)")
        self._emit("if n > 0: v = v / n")
        self._indent -= 1
        self._emit("self._codebook[name] = v")
        self._indent -= 1
        self._emit("# One batched write after all fetches in this call.")
        self._emit("self._write_disk_cache()")
        self._indent -= 1
        self._emit()
        self._emit("def _role_hash(self, role_vec):")
        self._indent += 1
        self._emit('"""Deterministic uint32 seed from a role vector.')
        self._emit('')
        self._emit("Uses the float64 bytes of the vector, so tiny numerical noise")
        self._emit("produces the same seed as long as the vector is bit-identical.")
        self._emit("Bit-level determinism is what we want here — callers should")
        self._emit("not retrieve via a different-but-similar role; that's what")
        self._emit("hashmap_get's continuous-projection path is for.")
        self._emit('"""')
        self._emit("import hashlib")
        self._emit("h = hashlib.blake2b(role_vec.tobytes(), digest_size=8).digest()")
        self._emit("return int.from_bytes(h, 'little') & 0xFFFFFFFF")
        self._indent -= 1
        self._emit()
        self._emit("def _rotation_for(self, role_vec):")
        self._indent += 1
        self._emit('"""Haar-random orthogonal matrix seeded by the role vector.')
        self._emit('')
        self._emit("Uses QR decomposition of a random matrix (standard Haar draw).")
        self._emit("Cached per role-hash so the same role always produces the same")
        self._emit("rotation — required for bind/unbind round-trip.")
        self._emit('"""')
        self._emit("key = self._role_hash(role_vec)")
        self._emit("if key not in self._rot_cache:")
        self._indent += 1
        self._emit("rng = _np.random.RandomState(key)")
        self._emit("A = rng.randn(self.dim, self.dim)")
        self._emit("Q, _R = _np.linalg.qr(A)")
        self._emit("# Flip sign of rows where R's diagonal was negative, so the QR")
        self._emit("# output is Haar-uniform rather than biased by the QR sign.")
        self._emit("d = _np.sign(_np.diag(_R))")
        self._emit("d[d == 0] = 1.0")
        self._emit("Q = Q * d")
        self._emit("self._rot_cache[key] = Q")
        self._indent -= 1
        self._emit("return self._rot_cache[key]")
        self._indent -= 1
        self._emit()
        self._emit("def bind(self, role, filler):")
        self._indent += 1
        self._emit("# Rotation binding. Role-first convention matches the majority")
        self._emit("# of .su demos (analogy, fuzzy_dispatch, knowledge_graph, etc.):")
        self._emit("#   bind(role, filler) = Q_role @ filler")
        self._emit("# Q_role is the Haar-random rotation seeded by the role vector.")
        self._emit("# Replaces sign-flip (retired 2026-04-21). See spec binding.md.")
        self._emit("Q = self._rotation_for(role)")
        self._emit("return Q @ filler")
        self._indent -= 1
        self._emit()
        self._emit("def unbind(self, role, record):")
        self._indent += 1
        self._emit("# Role-first, matching bind. Q is orthogonal so inverse = transpose:")
        self._emit("#   unbind(role, record) = Q_role^T @ record")
        self._emit("# For the matched-pair term in the bundle,")
        self._emit("#   Q_role^T @ Q_role @ filler = filler exactly.")
        self._emit("# Other bundled terms appear as Q_role^T @ Q_other @ ... which")
        self._emit("# is random-ish noise with ~1/sqrt(d) magnitude per term.")
        self._emit("Q = self._rotation_for(role)")
        self._emit("return Q.T @ record")
        self._indent -= 1
        self._emit()
        self._emit("def bundle(self, *vectors):")
        self._indent += 1
        self._emit("s = _np.sum(vectors, axis=0)")
        self._emit("n = _np.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("def zero_vector(self):")
        self._indent += 1
        self._emit('"""Zero vector in the runtime dim.')
        self._emit('')
        self._emit("Emitted by the simplifier for identities that resolve to zero")
        self._emit("(e.g. displacement(a, a) → zero, bundle(zero_vector()) absorbed).")
        self._emit("Also the starting accumulator for hashmap_new; kept as its own")
        self._emit("method so future substrates can override (e.g. a connectome")
        self._emit("backend's no-spike state instead of numeric zero).")
        self._emit('"""')
        self._emit("return _np.zeros(self.dim, dtype=_np.float64)")
        self._indent -= 1
        self._emit()
        self._emit("def bundle_of_binds(self, *role_filler_pairs):")
        self._indent += 1
        self._emit('"""Fused bind+sum+normalize over N role-filler pairs.')
        self._emit('')
        self._emit("Emitted by the compiler when every arg to bundle() is itself")
        self._emit("a bind() call. The N binds are independent (no shared state),")
        self._emit("so executing them as a batch instead of sequentially is")
        self._emit("correct and ~Nx faster on GPU-class hardware.")
        self._emit("")
        self._emit("numpy implementation: stack the per-role rotation matrices")
        self._emit("into (N, d, d), stack fillers into (N, d), batched einsum")
        self._emit("for the bind, sum over N, normalize. Same result as sequential")
        self._emit("bind+sum+normalize, in a single einsum + reduce.")
        self._emit("")
        self._emit("This is the independence-structure case the PyTorch/GPU")
        self._emit("backend was gated on per STATUS.md — the fused form collapses")
        self._emit("N small kernel launches into O(1) big ones.")
        self._emit('"""')
        self._emit("if not role_filler_pairs:")
        self._indent += 1
        self._emit("return self.zero_vector()")
        self._indent -= 1
        self._emit("roles = [rf[0] for rf in role_filler_pairs]")
        self._emit("fillers = [rf[1] for rf in role_filler_pairs]")
        self._emit("Q_stack = _np.stack([self._rotation_for(r) for r in roles])  # (N, d, d)")
        self._emit("F_stack = _np.stack([_np.asarray(f, dtype=_np.float64) for f in fillers])  # (N, d)")
        self._emit("# Batched bind: element-i is Q_i @ f_i; shape (N, d).")
        self._emit("bound = _np.einsum('nij,nj->ni', Q_stack, F_stack)")
        self._emit("s = bound.sum(axis=0)")
        self._emit("n = _np.linalg.norm(s)")
        self._emit("return s / n if n > 0 else s")
        self._indent -= 1
        self._emit()
        self._emit("# ---- Rotation-hashmap (library pattern per open question) ----")
        self._emit("#")
        self._emit("# Prototype of the rotation-hashmap described in")
        self._emit("# planning/open-questions/rotation-hashmap-as-language-feature.md.")
        self._emit("# Implemented as runtime methods — accessed by test scripts, not")
        self._emit("# wired into the .su surface syntax yet. If the mechanism works,")
        self._emit("# this is evidence for Candidate A (first-class map<K,V>); if")
        self._emit("# capacity is poor, evidence for Candidate B (library-only).")
        self._emit()
        self._emit("def hashmap_new(self):")
        self._indent += 1
        self._emit('"""Empty accumulator — a zero vector in the runtime dim."""')
        self._emit("return _np.zeros(self.dim, dtype=_np.float64)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_set(self, acc, key_vec, val_vec):")
        self._indent += 1
        self._emit('"""Store val under key: acc + bind(key, val).')
        self._emit('')
        self._emit("Reuses the same role-seeded Haar rotation as bind itself, so")
        self._emit("the hashmap has identical capacity / cross-talk behavior as a")
        self._emit("bundle of role-filler pairs. The only difference from bind + ")
        self._emit("bundle is the API — the caller doesn't have to construct the")
        self._emit("bundle themselves; set() just accumulates additively.")
        self._emit("")
        self._emit("Storage is additive WITHOUT normalization. Normalizing after")
        self._emit("every set would destroy the magnitude information downstream")
        self._emit("retrieval depends on. Normalize at retrieval time if needed.")
        self._emit("")
        self._emit("LIMITATION: key lookup is by bit-identical hash of key_vec, so")
        self._emit("soft lookup (noisy query key -> approximate recovery) does NOT")
        self._emit("work with this prototype. A continuous-hash variant using")
        self._emit("Householder reflections or learned projections would enable")
        self._emit("soft lookup; future work per the open question.")
        self._emit('"""')
        self._emit("return acc + self.bind(key_vec, val_vec)")
        self._indent -= 1
        self._emit()
        self._emit("def hashmap_get(self, acc, key_vec):")
        self._indent += 1
        self._emit('"""Retrieve val associated with key: unbind(key, acc).')
        self._emit('')
        self._emit("Returns the raw recovered vector; caller applies cleanup")
        self._emit("(argmax_cosine against a codebook) or uses it directly.")
        self._emit("Cross-talk from other stored entries appears as noise with")
        self._emit("~1/sqrt(d) magnitude per other entry. For N stored entries")
        self._emit("and a d-dim substrate, recovered signal-to-noise is ~1/sqrt(N).")
        self._emit('"""')
        self._emit("return self.unbind(key_vec, acc)")
        self._indent -= 1
        self._emit()
        self._emit("def similarity(self, a, b):")
        self._indent += 1
        self._emit("na = _np.linalg.norm(a)")
        self._emit("nb = _np.linalg.norm(b)")
        self._emit("if na == 0 or nb == 0:")
        self._indent += 1
        self._emit("return 0.0")
        self._indent -= 1
        self._emit("return float(_np.dot(a, b) / (na * nb))")
        self._indent -= 1
        self._emit()
        self._emit("def make_random_rotation(self, angle, n_planes=1, seed=None):")
        self._indent += 1
        self._emit('"""Haar-random rotation, scaled so its largest eigenphase ~= angle.')
        self._emit('')
        self._emit('Uniform-angle Givens composition makes every plane orbit at the')
        self._emit('same frequency, so any trajectory is near-periodic and never')
        self._emit('explores the hypersphere. A Haar-random orthogonal matrix has a')
        self._emit('spectrum of eigenphases and produces quasi-periodic trajectories')
        self._emit('that actually sample the sphere. `angle` and `n_planes` are kept')
        self._emit('in the signature for API compatibility with the fly-brain VSA.')
        self._emit('"""')
        self._emit("rng = _np.random.RandomState(seed if seed is not None else self.seed)")
        self._emit("A = rng.randn(self.dim, self.dim)")
        self._emit("Q, _ = _np.linalg.qr(A)")
        self._emit("# Fractional matrix power via eigendecomposition so the caller")
        self._emit("# can still dial rotation magnitude via `angle`. Q^(angle/pi)")
        self._emit("# interpolates between identity (angle=0) and full Q (angle=pi).")
        self._emit("w, V = _np.linalg.eig(Q)")
        self._emit("phases = _np.angle(w) * (angle / _np.pi)")
        self._emit("R = (V * _np.exp(1j * phases)) @ _np.linalg.inv(V)")
        self._emit("return _np.real(R)")
        self._indent -= 1
        self._emit()
        self._emit("def compile_prototypes(self, prototype_vectors, frame_seed=None):")
        self._indent += 1
        self._emit('"""Pass-through on the numpy substrate: no KC sparsification here."""')
        self._emit("return dict(prototype_vectors)")
        self._indent -= 1
        self._emit()
        self._emit("def loop(self, initial_state, rotation, compiled_prototypes,")
        self._indent += 1
        self._emit("target_name=None, threshold=0.5, max_iters=50, frame_seed=None):")
        self._emit('"""Eigenrotation: iterate state <- R @ state until match."""')
        self._emit("state = initial_state.copy()")
        self._emit("for iters in range(1, max_iters + 1):")
        self._indent += 1
        self._emit("state = rotation @ state")
        self._emit("n = _np.linalg.norm(state)")
        self._emit("if n > 0: state = state / n")
        self._emit("best_name, best_score = None, -1.0")
        self._emit("for nm, proto in compiled_prototypes.items():")
        self._indent += 1
        self._emit("s = self.similarity(state, proto)")
        self._emit("if s > best_score:")
        self._indent += 1
        self._emit("best_score = s; best_name = nm")
        self._indent -= 1
        self._indent -= 1
        self._emit("if target_name is not None and best_name == target_name and best_score >= threshold:")
        self._indent += 1
        self._emit("return best_name, state, iters")
        self._indent -= 1
        self._emit("if target_name is None and best_score >= threshold:")
        self._indent += 1
        self._emit("return best_name, state, iters")
        self._indent -= 1
        self._indent -= 1
        self._emit("return best_name, state, max_iters")
        self._indent -= 1
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit(
            f"_VSA = _NumpyVSA(dim={self.runtime_dim}, seed={self.runtime_seed}, "
            f"llm_model={self._llm_model!r})"
        )
        # Batched pre-fetch of every basis_vector("...") string argument
        # the program uses. One Ollama round-trip instead of N sequential
        # ones. Collected by the simplify pass (see translate_module).
        if self._prefetch_strings:
            self._emit(f"_VSA.embed_batch({self._prefetch_strings!r})")
        self._emit()
        self._emit()
        self._emit("def _argmax_cosine(query, candidates):")
        self._indent += 1
        self._emit('"""Candidate with the largest cosine similarity to query.')
        self._emit('')
        self._emit("Vectorized: stacks `candidates` into a (N, d) matrix and")
        self._emit("computes all N cosines in a single matmul. Equivalent to the")
        self._emit("old Python for-loop over _VSA.similarity, but ~Nx faster on")
        self._emit("CPU and the shape the PyTorch/GPU backend will reuse without")
        self._emit("any further rewriting. N small-kernel launches becomes 1 big one.")
        self._emit('"""')
        self._emit("if not candidates:")
        self._indent += 1
        self._emit("return None")
        self._indent -= 1
        self._emit("M = _np.stack([_np.asarray(c, dtype=_np.float64) for c in candidates])")
        self._emit("q = _np.asarray(query, dtype=_np.float64)")
        self._emit("row_norms = _np.linalg.norm(M, axis=1)")
        self._emit("q_norm = _np.linalg.norm(q)")
        self._emit("if q_norm == 0:")
        self._indent += 1
        self._emit("return candidates[0]")
        self._indent -= 1
        self._emit("safe_rn = _np.where(row_norms > 0, row_norms, 1.0)")
        self._emit("scores = (M @ q) / (safe_rn * q_norm)")
        self._emit("scores = _np.where(row_norms > 0, scores, -_np.inf)")
        self._emit("return candidates[int(_np.argmax(scores))]")
        self._indent -= 1
        self._emit()
        self._emit()
        self._emit_select_helper()
        self._emit()
        self._emit("def _vector_map_lookup(pairs, key):")
        self._indent += 1
        self._emit('"""Identity-first lookup for vector-keyed maps, cosine fallback.')
        self._emit('')
        self._emit("Identity-hit short-circuits before any matmul (the common case")
        self._emit("for literal vector keys). The cosine fallback stacks and matmuls.")
        self._emit('"""')
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
        self._emit("keys = _np.stack([_np.asarray(k, dtype=_np.float64) for k, _ in pairs])")
        self._emit("q = _np.asarray(key, dtype=_np.float64)")
        self._emit("row_norms = _np.linalg.norm(keys, axis=1)")
        self._emit("q_norm = _np.linalg.norm(q)")
        self._emit("if q_norm == 0:")
        self._indent += 1
        self._emit("return pairs[0][1]")
        self._indent -= 1
        self._emit("safe_rn = _np.where(row_norms > 0, row_norms, 1.0)")
        self._emit("scores = (keys @ q) / (safe_rn * q_norm)")
        self._emit("scores = _np.where(row_norms > 0, scores, -_np.inf)")
        self._emit("return pairs[int(_np.argmax(scores))][1]")
        self._indent -= 1


def translate_module(module: ast.Module, **kwargs) -> str:
    """Translate a parsed Sutra module to self-contained numpy Python.

    Runs the simplification pass over the AST before handing to the
    codegen so identity rewrites (bundle(v) -> v, bundle flattening)
    happen in source-to-source form rather than in the emitted
    Python. Also collects every `basis_vector("...")` string literal
    so the codegen can emit a batched Ollama pre-fetch at module init
    (N HTTP round-trips collapse into one batched embed call).
    These are prerequisites for the PyTorch/GPU backend port.
    """
    from .simplify import simplify_module, collect_basis_vector_strings
    simplify_module(module)
    strings = collect_basis_vector_strings(module)
    cg = NumpyCodegen(**kwargs)
    cg._prefetch_strings = strings
    return cg.translate(module)
