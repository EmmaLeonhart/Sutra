"""
VSA operations on the fly brain substrate.

Hybrid architecture:
- bind/unbind/bundle: algebraic operations in numpy (sign-flip binding)
- snap: encode → circuit run → decode (APL provides biological cleanup)
- similarity: cosine similarity in numpy
- embed: generate random hypervectors for named concepts

This implements the Akasha language's core operations using the mushroom body
circuit as the computational substrate for cleanup/discretization.
"""

import numpy as np
from spike_vsa_bridge import SpikeVSABridge, cosine_similarity


class FlyBrainVSA:
    """
    Akasha VSA operations backed by a simulated fly brain.

    Usage:
        vsa = FlyBrainVSA(dim=50)
        a = vsa.embed("apple")
        b = vsa.embed("vinegar")
        bound = vsa.bind(a, b)
        cleaned = vsa.snap(bound)
        retrieved = vsa.unbind(a, cleaned)
        score = vsa.similarity(retrieved, b)
    """

    def __init__(self, dim=50, n_kc=2000, seed=42, snap_duration_ms=300):
        self.dim = dim
        self.n_kc = n_kc
        self.seed = seed
        self.snap_duration_ms = snap_duration_ms
        self.codebook = {}  # name → hypervector
        self._snap_count = 0

    def embed(self, name):
        """Get or create a random hypervector for a named concept."""
        if name not in self.codebook:
            # Use deterministic seed based on name for reproducibility
            name_seed = hash(name) % (2**31)
            self.codebook[name] = np.random.RandomState(name_seed).randn(self.dim)
        return self.codebook[name].copy()

    def bind(self, a, b):
        """
        Sign-flip binding (self-inverse).

        Produces a vector dissimilar to both inputs. Encoding key-value
        pairs and role-filler structures. Done in numpy — this is a
        pure algebraic operation.
        """
        signs = np.sign(b)
        signs[signs == 0] = 1
        return a * signs

    def unbind(self, role, bound):
        """
        Unbind = bind (sign-flip is self-inverse).

        Given a role vector, extract the approximate filler from a
        bound structure.
        """
        return self.bind(role, bound)

    def bundle(self, *vectors):
        """
        Superpose vectors by addition (fuzzy OR).

        The result is similar to all inputs. Signal-to-noise degrades
        as more items are superposed.
        """
        result = np.zeros(self.dim)
        for v in vectors:
            result = result + v
        return result

    def snap(self, vector):
        """
        Cleanup/discretization through the mushroom body circuit.

        Encode the vector as PN currents, run through the spiking
        circuit (APL enforces sparse coding via graded feedback
        inhibition), decode from KC population via a learned linear
        readout.

        The decoder is the biologically-plausible learned MBON-style
        readout (`decode_learned`), not the earlier pseudoinverse
        shortcut. The learned readout is cached in
        SpikeVSABridge._learned_readout_cache by
        (seed, dim, n_kc) so the training cost is paid once per
        unique parameter tuple and amortized across every snap that
        follows. See spike_vsa_bridge.py for details on the readout
        fitting procedure (ridge regression on ~20 training
        hypervector/KC-pattern pairs).

        This is where the biological substrate does real computation.
        The sparse random projection + graded APL feedback acts as a
        noise-tolerant cleanup memory, and the learned readout reads
        out the result without peeking at the connectome.
        """
        # Each snap needs a fresh model (Brian2 is stateful)
        bridge = SpikeVSABridge(
            dim=self.dim, seed=self.seed + self._snap_count,
            n_kc=self.n_kc
        )
        self._snap_count += 1

        # Ensure the learned readout is fit (cheap cache hit after
        # the first bridge with this parameter tuple).
        bridge.fit_learned_readout()

        decoded, fidelity = bridge.round_trip(vector, self.snap_duration_ms)
        return decoded

    def similarity(self, a, b):
        """Cosine similarity between two hypervectors."""
        return cosine_similarity(a, b)

    def make_permutation_key(self, name):
        """
        Build an involutory permutation key: a fixed random sign vector.

        In this sign-flip VSA, a permutation is a pointwise sign pattern.
        Applying it twice returns the original, so it acts as an involution
        (s * s = 1). This is the primitive that implements boolean negation
        at the vector-space level: `not(X) = permute(NOT_KEY, X)`.

        Keys are deterministic in the name, so `make_permutation_key("NOT")`
        always returns the same vector for a given VSA instance.
        """
        key_seed = (hash("permkey:" + name) % (2**31)) ^ self.seed
        return np.random.RandomState(key_seed).choice([-1, 1], size=self.dim).astype(float)

    def permute(self, key, vector):
        """
        Apply a permutation key to a vector.

        For sign-flip VSA, permute = pointwise multiply by the sign key.
        This is an involution: permute(k, permute(k, x)) == x.

        Distributes over binding: permute(k, bind(a, b)) == bind(permute(k, a), b)
        == bind(a, permute(k, b)). Used to implement boolean negation on
        conditional queries without Python-side if-statements.
        """
        return vector * key

    def snap_to_codebook(self, vector):
        """
        Snap to nearest named vector in the codebook.

        Returns (vector, name, distance).
        """
        if not self.codebook:
            raise ValueError("Codebook is empty")
        names = list(self.codebook.keys())
        matrix = np.array([self.codebook[n] for n in names])
        diffs = matrix - vector
        dists = np.linalg.norm(diffs, axis=1)
        best_idx = np.argmin(dists)
        return matrix[best_idx], names[best_idx], float(dists[best_idx])
