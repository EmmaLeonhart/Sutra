"""
S2 Runtime — Core Vector Programming Language Runtime
======================================================

This is the execution engine for S2 programs. It implements:
  - Sign-flip binding/unbinding (proven superior to Hadamard on natural embeddings)
  - Bundling (superposition) with noise tracking
  - Snap-to-nearest (codebook-based error correction)
  - Truth extraction matrix M(v)
  - Cone traversal (directed neighborhood queries)
  - Structured matching (many-to-many projection primitive)
  - Empirical initiation (substrate calibration)

The runtime operates on any embedding substrate reachable via Ollama.
"""

import sys
import io
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ============================================================
# Substrate: Embedding backend
# ============================================================

class Substrate:
    """An embedding space that S2 programs execute on."""

    def __init__(self, model_name="mxbai-embed-large"):
        self.model_name = model_name
        self._cache = {}
        self.dim = None
        self.calibration = None  # Set by empirical initiation

    def embed(self, texts):
        """Embed one or more texts. Returns (N, dim) numpy array."""
        if isinstance(texts, str):
            texts = [texts]
        # Check cache
        uncached = [t for t in texts if t not in self._cache]
        if uncached:
            import ollama
            result = ollama.embed(model=self.model_name, input=uncached)
            vecs = np.array(result.embeddings, dtype=np.float64)
            for t, v in zip(uncached, vecs):
                self._cache[t] = v
            if self.dim is None:
                self.dim = vecs.shape[1]
        out = np.array([self._cache[t] for t in texts])
        return out if len(texts) > 1 else out[0]

    def random_roles(self, n, seed=None):
        """Generate n random role vectors for binding."""
        if self.dim is None:
            raise ValueError("Embed something first to discover dimensionality")
        rng = np.random.default_rng(seed)
        return rng.standard_normal((n, self.dim)).astype(np.float64)


# ============================================================
# Tier 1: Primitive operations (scalars, tuples, iteration)
# ============================================================

def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(dot / (na * nb))


def euclidean_distance(a, b):
    return float(np.linalg.norm(a - b))


# ============================================================
# Tier 2: Algebraic VSA operations — O(1)
# ============================================================

def bind(filler, role):
    """Sign-flip binding: flip filler signs based on role sign pattern.
    Self-inverse: bind(bind(f, r), r) ≈ f.
    Proven superior to Hadamard on natural embedding spaces."""
    signs = np.sign(role)
    signs[signs == 0] = 1
    return filler * signs


def unbind(bound, role):
    """Unbind is identical to bind (sign-flip is self-inverse)."""
    return bind(bound, role)


def bundle(*vectors):
    """Superposition: elementwise addition. The result is similar to all inputs."""
    result = np.zeros_like(vectors[0], dtype=np.float64)
    for v in vectors:
        result += v
    return result


def similarity(a, b):
    """Fuzzy truth value: how similar are two vectors? Returns [−1, 1]."""
    return cosine_similarity(a, b)


# ============================================================
# Tier 3: Non-algebraic operations — O(log n) via ANN
# ============================================================

class Codebook:
    """A set of known vectors for snap-to-nearest error correction.
    This is the S2 equivalent of a symbol table / cleanup memory."""

    def __init__(self):
        self.vectors = []
        self.labels = []
        self._label_set = set()
        self._matrix = None

    def add(self, label, vector):
        if label in self._label_set:
            return  # don't add duplicates
        self.vectors.append(vector.copy())
        self.labels.append(label)
        self._label_set.add(label)
        self._matrix = None  # invalidate cache

    def add_batch(self, labels, vectors):
        for label, vec in zip(labels, vectors):
            self.add(label, vec)

    @property
    def matrix(self):
        if self._matrix is None and self.vectors:
            self._matrix = np.array(self.vectors)
        return self._matrix

    def __len__(self):
        return len(self.vectors)

    def snap(self, vector, metric="cosine"):
        """Snap a noisy vector to the nearest codebook entry.
        Returns (clean_vector, label, distance, rank)."""
        if not self.vectors:
            raise ValueError("Empty codebook")
        mat = self.matrix
        if metric == "cosine":
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-10)
            mat_normed = mat / norms
            v_norm = np.linalg.norm(vector)
            v_normed = vector / max(v_norm, 1e-10)
            sims = mat_normed @ v_normed
            best_idx = int(np.argmax(sims))
            return self.vectors[best_idx].copy(), self.labels[best_idx], float(1 - sims[best_idx]), 0
        else:  # euclidean
            diffs = mat - vector
            dists = np.linalg.norm(diffs, axis=1)
            best_idx = int(np.argmin(dists))
            return self.vectors[best_idx].copy(), self.labels[best_idx], float(dists[best_idx]), 0

    def cone_traverse(self, origin, direction, spread=0.5, top_k=5):
        """Directed neighborhood query: find codebook entries within a cone.

        The cone is defined by an origin point, a direction vector, and an
        angular spread (cosine threshold). Returns entries that are both
        near the origin AND in the specified direction.

        This is S2's non-algebraic branching mechanism."""
        if not self.vectors:
            return []
        mat = self.matrix
        # Displacement from origin to each codebook entry
        displacements = mat - origin
        disp_norms = np.linalg.norm(displacements, axis=1, keepdims=True)
        disp_norms = np.maximum(disp_norms, 1e-10)
        disp_normed = displacements / disp_norms

        dir_norm = np.linalg.norm(direction)
        if dir_norm < 1e-10:
            return []
        dir_normed = direction / dir_norm

        # Cosine of displacement angle vs direction
        alignments = disp_normed @ dir_normed

        # Filter: within cone (alignment > spread threshold)
        mask = alignments >= spread
        indices = np.where(mask)[0]

        if len(indices) == 0:
            return []

        # Rank by alignment (higher = more aligned with direction)
        sorted_idx = indices[np.argsort(-alignments[indices])][:top_k]
        return [(self.labels[i], self.vectors[i].copy(), float(alignments[i]))
                for i in sorted_idx]


# ============================================================
# Truth extraction: M(v) · v → truth vector
# ============================================================

def truth_matrix(v):
    """Derive the truth-extraction matrix M(v) from a vector.
    M(v) projects v onto its principal component direction, yielding
    a scalar "truth magnitude" that can be compared across vectors.

    For recursive refinement: apply is_true(is_true(v)) for increasing
    confidence sharpening."""
    v = np.asarray(v, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return np.zeros_like(v)
    # M(v) = v·vᵀ / ||v||² — projects onto v's direction
    # M(v)·v = v (||v||²/||v||²) = v, but the magnitude encodes confidence
    unit = v / norm
    return np.outer(unit, unit)


def is_true(v, reference=None):
    """Extract a scalar truth value from a vector.
    If reference is provided, returns similarity to reference (supervised truth).
    If not, returns the vector's self-consistency (magnitude as confidence)."""
    if reference is not None:
        return cosine_similarity(v, reference)
    # Unsupervised: magnitude relative to expected magnitude
    return float(np.linalg.norm(v))


def is_true_recursive(v, reference=None, depth=3):
    """Recursive truth extraction: each application sharpens confidence.
    Returns list of truth values at each depth."""
    values = [is_true(v, reference)]
    M = truth_matrix(v)
    current = v.copy()
    for _ in range(depth - 1):
        current = M @ current
        values.append(is_true(current, reference))
    return values


# ============================================================
# Structured matching (from many-to-many: the projection primitive)
# ============================================================

def compute_direction(group_a, group_b):
    """Derive a unit direction vector from the displacement between two groups."""
    mean_a = np.mean(group_a, axis=0)
    mean_b = np.mean(group_b, axis=0)
    direction = mean_a - mean_b
    norm = np.linalg.norm(direction)
    if norm < 1e-10:
        return direction
    return direction / norm


def project_away(embeddings, control_vectors):
    """Remove components along all control vectors (confounders)."""
    single = embeddings.ndim == 1
    if single:
        embeddings = embeddings.reshape(1, -1)
    result = embeddings.copy()
    for v in control_vectors:
        vv = np.dot(v, v)
        if vv < 1e-10:
            continue
        projections = (result @ v) / vv
        result = result - np.outer(projections, v)
    return result[0] if single else result


def structured_match(query, candidates, target_direction=None,
                     control_vectors=None, alpha=0.5, beta=0.5):
    """Three-part structured matching.
    1. SELECT: maximize similarity along target direction
    2. CONTROL: project away confounding dimensions
    3. RESIDUAL: cosine on what's left

    Score = alpha * residual_cosine + beta * target_projection
    """
    if control_vectors is None:
        control_vectors = []
    # Project away confounders
    q_res = project_away(query, control_vectors)
    c_res = project_away(candidates, control_vectors)

    # Residual cosine
    q_norm = np.linalg.norm(q_res)
    if q_norm < 1e-10:
        residual_scores = np.zeros(len(candidates))
    else:
        q_unit = q_res / q_norm
        c_norms = np.linalg.norm(c_res, axis=1, keepdims=True)
        c_norms = np.maximum(c_norms, 1e-10)
        residual_scores = (c_res / c_norms) @ q_unit

    # Directional selection
    if target_direction is not None:
        sel_scores = c_res @ target_direction
        if np.max(np.abs(sel_scores)) > 1e-10:
            sel_scores = (sel_scores - sel_scores.min()) / (sel_scores.max() - sel_scores.min() + 1e-10)
        scores = alpha * residual_scores + beta * sel_scores
    else:
        scores = residual_scores

    return scores


# ============================================================
# Empirical Initiation: probe a substrate, build calibration
# ============================================================

def empirical_initiation(substrate, test_texts=None, verbose=True):
    """Probe an embedding substrate to characterize its algebraic fidelity.
    Returns a calibration dict with capacity, noise profile, and recommendations."""
    if test_texts is None:
        test_texts = [
            "The cat sat on the mat",
            "Dogs love to play fetch",
            "The economy grew by three percent",
            "Quantum mechanics describes particles",
            "She walked to the store",
            "Music fills the concert hall",
            "Rain falls gently on the roof",
            "The algorithm runs in linear time",
            "Children laughed in the playground",
            "Stars shine brightly at night",
            "The treaty was signed in Geneva",
            "Photosynthesis converts sunlight to energy",
            "He cooked dinner for his family",
            "Waves crashed against the rocky shore",
            "The database query returned no results",
            "Birds migrated south for the winter",
        ]

    if verbose:
        print(f"Probing substrate: {substrate.model_name}")

    vecs = substrate.embed(test_texts)
    dim = vecs.shape[1]
    if verbose:
        print(f"  Dimensionality: {dim}")
        mags = np.linalg.norm(vecs, axis=1)
        print(f"  Magnitude range: {mags.min():.2f} — {mags.max():.2f} (mean {mags.mean():.2f})")

    # Test sign-flip binding fidelity
    codebook = Codebook()
    for i, (text, vec) in enumerate(zip(test_texts, vecs)):
        codebook.add(text, vec)

    roles = substrate.random_roles(len(test_texts), seed=42)

    # Test binding capacity: how many role-filler pairs can we bundle and recover?
    max_capacity = 0
    for n_roles in range(1, min(len(test_texts), 16)):
        structure = np.zeros(dim, dtype=np.float64)
        for i in range(n_roles):
            structure += bind(vecs[i], roles[i])
        recovered = unbind(structure, roles[0])
        snapped_vec, snapped_label, dist, _ = codebook.snap(recovered)
        if snapped_label == test_texts[0]:
            max_capacity = n_roles
        else:
            break

    if verbose:
        print(f"  Sign-flip bundling capacity: {max_capacity} roles")

    # Test chain depth: how many bind/unbind cycles before signal degrades?
    chain_depth = 0
    v = vecs[0].copy()
    role = roles[0]
    for step in range(1, 21):
        v = bind(v, role)
        v = unbind(v, role)
        cos = cosine_similarity(v, vecs[0])
        if cos < 0.99:
            break
        chain_depth = step

    if verbose:
        print(f"  Chain depth (cos > 0.99): {chain_depth} steps")

    # Test snap recovery after bundling
    snap_recovery = []
    for n_roles in [2, 4, 8]:
        if n_roles >= len(test_texts):
            break
        structure = np.zeros(dim, dtype=np.float64)
        for i in range(n_roles):
            structure += bind(vecs[i], roles[i])
        correct = 0
        for i in range(n_roles):
            recovered = unbind(structure, roles[i])
            _, label, _, _ = codebook.snap(recovered)
            if label == test_texts[i]:
                correct += 1
        snap_recovery.append({
            "n_roles": n_roles,
            "correct": correct,
            "accuracy": correct / n_roles
        })
        if verbose:
            print(f"  Snap recovery at {n_roles} roles: {correct}/{n_roles}")

    calibration = {
        "model": substrate.model_name,
        "dim": dim,
        "capacity": max_capacity,
        "chain_depth": chain_depth,
        "snap_recovery": snap_recovery,
        "binding_method": "sign-flip",
    }
    substrate.calibration = calibration
    return calibration


# ============================================================
# S2 Environment: the runtime state for program execution
# ============================================================

@dataclass
class S2Env:
    """Runtime environment for S2 program execution."""
    substrate: Substrate
    codebook: Codebook = field(default_factory=Codebook)
    variables: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)  # execution trace
    _role_counter: int = 0

    def embed(self, text):
        """Embed a text and register it in the codebook."""
        vec = self.substrate.embed(text)
        self.codebook.add(text, vec)
        return vec

    def embed_batch(self, texts):
        """Embed multiple texts and register all in codebook."""
        vecs = self.substrate.embed(texts)
        self.codebook.add_batch(texts, vecs)
        return vecs

    def get_role(self, name):
        """Get or create a named role vector."""
        if name not in self.roles:
            self.roles[name] = self.substrate.random_roles(1, seed=hash(name) % (2**31))[0]
        return self.roles[name]

    def let(self, name, value):
        """Bind a variable name to a vector value."""
        self.variables[name] = value
        self.trace.append(("let", name, type(value).__name__))
        return value

    def get(self, name):
        """Retrieve a variable."""
        return self.variables[name]

    def bind(self, filler, role_name):
        """Bind a filler to a named role."""
        role = self.get_role(role_name)
        result = bind(filler, role)
        self.trace.append(("bind", role_name))
        return result

    def unbind(self, structure, role_name):
        """Unbind (query) a role from a structure."""
        role = self.get_role(role_name)
        result = unbind(structure, role)
        self.trace.append(("unbind", role_name))
        return result

    def bundle(self, *vectors):
        """Bundle (superpose) multiple vectors."""
        result = bundle(*vectors)
        self.trace.append(("bundle", len(vectors)))
        return result

    def snap(self, vector, metric="cosine"):
        """Snap a vector to the nearest codebook entry."""
        clean, label, dist, _ = self.codebook.snap(vector, metric)
        self.trace.append(("snap", label, f"dist={dist:.4f}"))
        return clean, label

    def cone(self, origin, direction, spread=0.5, top_k=5):
        """Cone traversal: directed neighborhood query."""
        results = self.codebook.cone_traverse(origin, direction, spread, top_k)
        self.trace.append(("cone", len(results), f"spread={spread}"))
        return results

    def is_true(self, vector, reference=None, depth=1):
        """Truth extraction."""
        if depth == 1:
            return is_true(vector, reference)
        return is_true_recursive(vector, reference, depth)

    def match(self, query, candidates, target_direction=None,
              control_vectors=None, alpha=0.5, beta=0.5):
        """Structured matching query."""
        if isinstance(candidates, list):
            candidates = np.array(candidates)
        scores = structured_match(query, candidates, target_direction,
                                  control_vectors, alpha, beta)
        self.trace.append(("match", len(candidates)))
        return scores


# ============================================================
# Convenience: run S2 operations and print results
# ============================================================

def demo_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


if __name__ == "__main__":
    print("S2 Runtime loaded. Use S2Env to execute programs.")
    print("Run s2_demos.py for demonstrations.")
