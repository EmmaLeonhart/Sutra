"""Runtime for the sutra_compiler numpy backend.

This file is not imported by the generated code — it is inlined into
the generated Python verbatim by codegen_numpy.py. It lives as real
Python source (rather than as a stream of `_emit(...)` calls) so it
can be linted, type-checked, tested, and edited with tooling that
understands Python.

Everything below this docstring is copied into the emitted module as
part of the prelude. The codegen appends the `_VSA = _NumpyVSA(...)`
instantiation and an optional `_VSA.embed_batch([...])` prefetch
immediately after.
"""
from __future__ import annotations

import numpy as _np


class _NumpyVSA:
    """Frozen-LLM-backed VSA runtime. Rotation binding, normalized bundle.

    Bind is role-seeded Haar-random orthogonal rotation applied to
    filler: bind(filler, role) = Q_role @ filler, with Q_role cached
    by role-vector hash. Unbind is the transpose. See
    planning/findings/2026-04-22-rotation-binding-prototype-design.md
    for the compromise this prototype takes (rotation in the same
    768-d semantic subspace as sign-flip did, not in a dedicated
    synthetic subspace — so cross-talk stays 1/sqrt(d) statistical).
    """

    def __init__(self, dim, seed, llm_model):
        self.dim = dim
        self.seed = seed
        self.llm_model = llm_model
        self._codebook = {}
        # Rotation matrix cache: role-vector-hash -> orthogonal matrix.
        # Generating a 768x768 Haar rotation is O(d^3); caching makes
        # repeated bind/unbind with the same role O(d^2) lookup + matmul.
        self._rot_cache = {}
        # On-disk embedding cache. Second-and-later runs load every
        # previously-seen basis_vector(...) string from disk instead of
        # hitting Ollama. Cache is keyed by (model, dim) so changing
        # either invalidates cleanly (different cache file).
        import os as _os
        self._cache_dir = _os.path.join(
            _os.environ.get('XDG_CACHE_HOME', _os.path.expanduser('~/.cache')),
            'sutra', 'embeddings')
        _os.makedirs(self._cache_dir, exist_ok=True)
        # Sanitize model name for use as filename.
        _safe_model = llm_model.replace('/', '_').replace(':', '_')
        self._cache_path = _os.path.join(
            self._cache_dir, f'{_safe_model}-d{dim}.npz')
        self._load_disk_cache()

    def _load_disk_cache(self):
        """Populate self._codebook from the on-disk embedding cache.

        Tolerant of a missing or corrupt cache file — a failed load
        leaves self._codebook empty and lets Ollama fetches repopulate
        it. The cache is performance, not correctness.
        """
        import os as _os
        if not _os.path.exists(self._cache_path):
            return
        try:
            with _np.load(self._cache_path, allow_pickle=False) as data:
                for key in data.files:
                    self._codebook[key] = data[key].astype(_np.float64)
        except Exception:
            # Corrupt cache: ignore and let Ollama repopulate.
            self._codebook = {}

    def _write_disk_cache(self):
        """Persist self._codebook atomically to disk.

        Writes to a tempfile then renames, so a partial write (crash,
        SIGKILL) leaves the old cache intact rather than corrupted.
        Called whenever embed / embed_batch fetches new vectors so
        subsequent runs hit the cache on module init.
        """
        import os as _os, tempfile as _tempfile
        if not self._codebook:
            return
        fd, tmp = _tempfile.mkstemp(
            dir=self._cache_dir, prefix='.tmp-', suffix='.npz')
        _os.close(fd)
        try:
            _np.savez(tmp, **self._codebook)
            # _np.savez writes tmp.npz, but tempfile handed us tmp ending
            # in .npz already — reconcile: savez appends .npz only if the
            # path does not already end in .npz. Python tempfile gives us
            # a .npz path, so savez leaves it as-is.
            _os.replace(tmp, self._cache_path)
        except Exception:
            # Cache-write failure is non-fatal. Remove the tmp and continue.
            try:
                _os.unlink(tmp)
            except OSError:
                pass

    def _postprocess_embedding(self, v):
        # Mean-center + unit-normalize + pad/truncate to self.dim + renorm.
        # Shared by embed() and embed_batch(); both need byte-identical
        # post-processing so single vs batched fetches produce the same
        # codebook entries.
        #
        # Mean-center: rotation binding assumes zero-mean vectors.
        # Raw LLM embeddings cluster in a cone (all-positive-ish), which
        # collapses sign-based operations to a near-constant pattern and
        # destroys role-filler separation. Centering restores the algebra.
        v = v - _np.mean(v)
        n = _np.linalg.norm(v)
        if n > 0: v = v / n
        # Truncate or pad to self.dim if the LLM dim differs.
        if v.shape[0] != self.dim:
            if v.shape[0] > self.dim:
                v = v[:self.dim]
            else:
                v = _np.concatenate([v, _np.zeros(self.dim - v.shape[0])])
            n = _np.linalg.norm(v)
            if n > 0: v = v / n
        return v

    def embed(self, name):
        """Frozen-LLM embedding via Ollama. No random fallback.
        If Ollama is unavailable or the model is missing, this raises.
        The numpy backend is defined as running on frozen LLM embeddings;
        a random-vector fallback is not Sutra."""
        if name not in self._codebook:
            import ollama
            r = ollama.embed(model=self.llm_model, input=name)
            v = _np.array(r['embeddings'][0], dtype=_np.float64)
            self._codebook[name] = self._postprocess_embedding(v)
            self._write_disk_cache()
        return self._codebook[name].copy()

    def embed_batch(self, names):
        """Batched Ollama embed: one HTTP round-trip for many names.

        Populates self._codebook for every name in `names` that isn't
        already cached. Subsequent embed(name) calls hit the cache in
        memory with no network round-trip. Replaces N sequential
        embed() calls at module init with one batched call; real
        wall-clock win on programs with many basis_vector strings.
        """
        missing = [n for n in names if n not in self._codebook]
        if not missing:
            return
        import ollama
        r = ollama.embed(model=self.llm_model, input=missing)
        for i, name in enumerate(missing):
            v = _np.array(r['embeddings'][i], dtype=_np.float64)
            self._codebook[name] = self._postprocess_embedding(v)
        # One batched write after all fetches in this call.
        self._write_disk_cache()

    def _role_hash(self, role_vec):
        """Deterministic uint32 seed from a role vector.

        Uses the float64 bytes of the vector, so tiny numerical noise
        produces the same seed as long as the vector is bit-identical.
        Bit-level determinism is what we want here — callers should
        not retrieve via a different-but-similar role; that's what
        hashmap_get's continuous-projection path is for.
        """
        import hashlib
        h = hashlib.blake2b(role_vec.tobytes(), digest_size=8).digest()
        return int.from_bytes(h, 'little') & 0xFFFFFFFF

    def _rotation_for(self, role_vec):
        """Haar-random orthogonal matrix seeded by the role vector.

        Uses QR decomposition of a random matrix (standard Haar draw).
        Cached per role-hash so the same role always produces the same
        rotation — required for bind/unbind round-trip.
        """
        key = self._role_hash(role_vec)
        if key not in self._rot_cache:
            rng = _np.random.RandomState(key)
            A = rng.randn(self.dim, self.dim)
            Q, _R = _np.linalg.qr(A)
            # Flip sign of rows where R's diagonal was negative, so the QR
            # output is Haar-uniform rather than biased by the QR sign.
            d = _np.sign(_np.diag(_R))
            d[d == 0] = 1.0
            Q = Q * d
            self._rot_cache[key] = Q
        return self._rot_cache[key]

    def bind(self, role, filler):
        # Rotation binding. Role-first convention matches the majority
        # of .su demos (analogy, fuzzy_dispatch, knowledge_graph, etc.):
        #   bind(role, filler) = Q_role @ filler
        # Q_role is the Haar-random rotation seeded by the role vector.
        # Replaces sign-flip (retired 2026-04-21). See spec binding.md.
        Q = self._rotation_for(role)
        return Q @ filler

    def unbind(self, role, record):
        # Role-first, matching bind. Q is orthogonal so inverse = transpose:
        #   unbind(role, record) = Q_role^T @ record
        # For the matched-pair term in the bundle,
        #   Q_role^T @ Q_role @ filler = filler exactly.
        # Other bundled terms appear as Q_role^T @ Q_other @ ... which
        # is random-ish noise with ~1/sqrt(d) magnitude per term.
        Q = self._rotation_for(role)
        return Q.T @ record

    def bundle(self, *vectors):
        s = _np.sum(vectors, axis=0)
        n = _np.linalg.norm(s)
        return s / n if n > 0 else s

    def zero_vector(self):
        """Zero vector in the runtime dim.

        Emitted by the simplifier for identities that resolve to zero
        (e.g. displacement(a, a) → zero, bundle(zero_vector()) absorbed).
        Also the starting accumulator for hashmap_new; kept as its own
        method so future substrates can override (e.g. a connectome
        backend's no-spike state instead of numeric zero).
        """
        return _np.zeros(self.dim, dtype=_np.float64)

    def bundle_of_binds(self, *role_filler_pairs):
        """Fused bind+sum+normalize over N role-filler pairs.

        Emitted by the compiler when every arg to bundle() is itself
        a bind() call. The N binds are independent (no shared state),
        so executing them as a batch instead of sequentially is
        correct and ~Nx faster on GPU-class hardware.

        numpy implementation: stack the per-role rotation matrices
        into (N, d, d), stack fillers into (N, d), batched einsum
        for the bind, sum over N, normalize. Same result as sequential
        bind+sum+normalize, in a single einsum + reduce.

        This is the independence-structure case the PyTorch/GPU
        backend was gated on per STATUS.md — the fused form collapses
        N small kernel launches into O(1) big ones.
        """
        if not role_filler_pairs:
            return self.zero_vector()
        roles = [rf[0] for rf in role_filler_pairs]
        fillers = [rf[1] for rf in role_filler_pairs]
        Q_stack = _np.stack([self._rotation_for(r) for r in roles])  # (N, d, d)
        F_stack = _np.stack([_np.asarray(f, dtype=_np.float64) for f in fillers])  # (N, d)
        # Batched bind: element-i is Q_i @ f_i; shape (N, d).
        bound = _np.einsum('nij,nj->ni', Q_stack, F_stack)
        s = bound.sum(axis=0)
        n = _np.linalg.norm(s)
        return s / n if n > 0 else s

    # ---- Rotation-hashmap (library pattern per open question) ----
    #
    # Prototype of the rotation-hashmap described in
    # planning/open-questions/rotation-hashmap-as-language-feature.md.
    # Implemented as runtime methods — accessed by test scripts, not
    # wired into the .su surface syntax yet. If the mechanism works,
    # this is evidence for Candidate A (first-class map<K,V>); if
    # capacity is poor, evidence for Candidate B (library-only).

    def hashmap_new(self):
        """Empty accumulator — a zero vector in the runtime dim."""
        return _np.zeros(self.dim, dtype=_np.float64)

    def hashmap_set(self, acc, key_vec, val_vec):
        """Store val under key: acc + bind(key, val).

        Reuses the same role-seeded Haar rotation as bind itself, so
        the hashmap has identical capacity / cross-talk behavior as a
        bundle of role-filler pairs. The only difference from bind + 
        bundle is the API — the caller doesn't have to construct the
        bundle themselves; set() just accumulates additively.

        Storage is additive WITHOUT normalization. Normalizing after
        every set would destroy the magnitude information downstream
        retrieval depends on. Normalize at retrieval time if needed.

        LIMITATION: key lookup is by bit-identical hash of key_vec, so
        soft lookup (noisy query key -> approximate recovery) does NOT
        work with this prototype. A continuous-hash variant using
        Householder reflections or learned projections would enable
        soft lookup; future work per the open question.
        """
        return acc + self.bind(key_vec, val_vec)

    def hashmap_get(self, acc, key_vec):
        """Retrieve val associated with key: unbind(key, acc).

        Returns the raw recovered vector; caller applies cleanup
        (argmax_cosine against a codebook) or uses it directly.
        Cross-talk from other stored entries appears as noise with
        ~1/sqrt(d) magnitude per other entry. For N stored entries
        and a d-dim substrate, recovered signal-to-noise is ~1/sqrt(N).
        """
        return self.unbind(key_vec, acc)

    def similarity(self, a, b):
        na = _np.linalg.norm(a)
        nb = _np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(_np.dot(a, b) / (na * nb))

    def make_random_rotation(self, angle, n_planes=1, seed=None):
        """Haar-random rotation, scaled so its largest eigenphase ~= angle.

        Uniform-angle Givens composition makes every plane orbit at the
        same frequency, so any trajectory is near-periodic and never
        explores the hypersphere. A Haar-random orthogonal matrix has a
        spectrum of eigenphases and produces quasi-periodic trajectories
        that actually sample the sphere. `angle` and `n_planes` are kept
        in the signature for API compatibility with the fly-brain VSA.
        """
        rng = _np.random.RandomState(seed if seed is not None else self.seed)
        A = rng.randn(self.dim, self.dim)
        Q, _ = _np.linalg.qr(A)
        # Fractional matrix power via eigendecomposition so the caller
        # can still dial rotation magnitude via `angle`. Q^(angle/pi)
        # interpolates between identity (angle=0) and full Q (angle=pi).
        w, V = _np.linalg.eig(Q)
        phases = _np.angle(w) * (angle / _np.pi)
        R = (V * _np.exp(1j * phases)) @ _np.linalg.inv(V)
        return _np.real(R)

    def compile_prototypes(self, prototype_vectors, frame_seed=None):
        """Pass-through on the numpy substrate: no KC sparsification here."""
        return dict(prototype_vectors)

    def loop(self, initial_state, rotation, compiled_prototypes,
        target_name=None, threshold=0.5, max_iters=50, frame_seed=None):
        """Eigenrotation: iterate state <- R @ state until match."""
        state = initial_state.copy()
        for iters in range(1, max_iters + 1):
            state = rotation @ state
            n = _np.linalg.norm(state)
            if n > 0: state = state / n
            best_name, best_score = None, -1.0
            for nm, proto in compiled_prototypes.items():
                s = self.similarity(state, proto)
                if s > best_score:
                    best_score = s; best_name = nm
            if target_name is not None and best_name == target_name and best_score >= threshold:
                return best_name, state, iters
            if target_name is None and best_score >= threshold:
                return best_name, state, iters
        return best_name, state, max_iters



def _argmax_cosine_idx(M, q):
    """Index in M of the row most cosine-similar to q.

    Returns None if q is the zero vector (caller decides the
    fallback — first candidate for _argmax_cosine, first pair's
    value for _vector_map_lookup).

    This is the shape the PyTorch/GPU backend reuses without any
    further rewriting: N small-kernel launches becomes 1 big one.
    """
    row_norms = _np.linalg.norm(M, axis=1)
    q_norm = _np.linalg.norm(q)
    if q_norm == 0:
        return None
    safe_rn = _np.where(row_norms > 0, row_norms, 1.0)
    scores = (M @ q) / (safe_rn * q_norm)
    scores = _np.where(row_norms > 0, scores, -_np.inf)
    return int(_np.argmax(scores))


def _argmax_cosine(query, candidates):
    """Candidate with the largest cosine similarity to query."""
    if not candidates:
        return None
    M = _np.stack([_np.asarray(c, dtype=_np.float64) for c in candidates])
    q = _np.asarray(query, dtype=_np.float64)
    idx = _argmax_cosine_idx(M, q)
    return candidates[0] if idx is None else candidates[idx]


def _select_softmax(scores, options):
    """Softmax-weighted superposition of option vectors."""
    s = _np.asarray(scores, dtype=float)
    s = s - _np.max(s)
    w = _np.exp(s)
    w = w / _np.sum(w)
    opts = _np.asarray(options, dtype=float)
    return (w[:, None] * opts).sum(axis=0)


def _vector_map_lookup(pairs, key):
    """Identity-first lookup for vector-keyed maps, cosine fallback.

    Identity-hit short-circuits before any matmul (the common case
    for literal vector keys). The cosine fallback stacks and matmuls
    through the shared _argmax_cosine_idx helper.
    """
    for k, v in pairs:
        if k is key:
            return v
    if not pairs:
        return None
    M = _np.stack([_np.asarray(k, dtype=_np.float64) for k, _ in pairs])
    q = _np.asarray(key, dtype=_np.float64)
    idx = _argmax_cosine_idx(M, q)
    return pairs[0][1] if idx is None else pairs[idx][1]
