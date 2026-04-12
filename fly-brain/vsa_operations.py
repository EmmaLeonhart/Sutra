"""
VSA operations on the fly brain substrate.

Brain-native architecture:
- bind/unbind: input-space multiplication (a * sign(b)) presented as
  PN currents — antennal lobe preprocessing, no synaptic weight changes
- bundle: superposition via summed PN input currents
  (convergent input — same as a fly smelling multiple odors at once)
- snap: encode → circuit run → decode (APL provides biological cleanup)
- similarity: KC pattern overlap (Jaccard similarity in brain space)
- is_true: cosine similarity to a reserved true vector (defuzzification)
- conditional: fuzzy weighted superposition of both branches
- embed: generate random hypervectors for named concepts

All core VSA operations route through the spiking circuit.  The mushroom
body performs the matrix multiplications that VSA algebra requires:
PN→KC is the random projection, APL enforces sparsity, KC patterns
are the computational representation.  The PN→KC synaptic weights are
the connectome wiring and remain fixed — binding operates in the input
space, analogous to antennal lobe lateral processing (Wilson 2013).
"""

import numpy as np
from spike_vsa_bridge import SpikeVSABridge, cosine_similarity


class FlyBrainVSA:
    """
    Sutra VSA operations backed by a simulated fly brain.

    Usage:
        vsa = FlyBrainVSA(dim=50)
        a = vsa.embed("apple")
        b = vsa.embed("vinegar")
        bound = vsa.bind(a, b)
        cleaned = vsa.snap(bound)
        retrieved = vsa.unbind(a, cleaned)
        score = vsa.similarity(retrieved, b)
    """

    def __init__(self, dim=50, n_kc=2000, seed=42, snap_duration_ms=300,
                 use_hemibrain=False):
        self.use_hemibrain = use_hemibrain
        if use_hemibrain:
            # Auto-detect dimensions from cached hemibrain data
            from hemibrain_loader import load_cache
            data = load_cache()
            if data is None:
                raise RuntimeError(
                    "hemibrain_pn_kc.npz not found. Run hemibrain_loader.py first."
                )
            n_kc_real, n_pn_real = data['binary_matrix'].shape
            self.dim = n_pn_real
            self.n_kc = n_kc_real
        else:
            self.dim = dim
            self.n_kc = n_kc
        self.seed = seed
        self.snap_duration_ms = snap_duration_ms
        self.codebook = {}  # name → hypervector
        self._op_count = 0

    def _make_bridge(self, fixed_seed=None):
        """Create a fresh SpikeVSABridge for a circuit operation.

        Each operation needs a fresh Brian2 model (stateful simulator).
        The learned readout is cached class-level, so the training
        cost is paid only once.

        Args:
            fixed_seed: if set, use this seed instead of incrementing.
                All operations that need to compare KC patterns MUST
                share the same seed (the fixed-frame invariant).
                Prototype compilation and loops use this.
        """
        bridge_kwargs = dict(n_kc=self.n_kc)
        if self.use_hemibrain:
            bridge_kwargs['use_hemibrain'] = True
        if fixed_seed is not None:
            seed = fixed_seed
        else:
            seed = self.seed + self._op_count
            self._op_count += 1
        bridge = SpikeVSABridge(
            dim=self.dim, seed=seed,
            **bridge_kwargs
        )
        n_samples = 80 if self.use_hemibrain else 20
        bridge.fit_learned_readout(n_samples=n_samples)
        return bridge

    def embed(self, name):
        """Get or create a random hypervector for a named concept."""
        if name not in self.codebook:
            # Use deterministic seed based on name for reproducibility
            name_seed = hash(name) % (2**31)
            self.codebook[name] = np.random.RandomState(name_seed).randn(self.dim)
        return self.codebook[name].copy()

    def bind(self, a, b):
        """
        Binding through the spiking circuit via input-space multiplication.

        The binding is computed as a * sign(b) in the PN input space
        (antennal lobe preprocessing), then presented as PN currents.
        The circuit computes:

            KC_pattern = sparsify(W @ encode(a * sign(b)))

        The binding happens in the INPUT to the circuit — the PN→KC
        synaptic weights remain fixed (they are the connectome wiring).
        This is biologically grounded: the antennal lobe transforms
        odor representations before they reach the mushroom body.
        """
        bridge = self._make_bridge()
        return bridge.bind_on_brain(a, b, self.snap_duration_ms)

    def unbind(self, role, bound):
        """
        Unbind through the spiking circuit (sign-flip is self-inverse).

        Given a role vector, extract the approximate filler from a
        bound structure.  Same input-space multiplication as bind.
        """
        return self.bind(role, bound)

    def bundle(self, *vectors):
        """
        Superpose vectors through the spiking circuit (fuzzy OR).

        Sums the encoded PN currents for all input vectors and presents
        the combined pattern.  The circuit computes:

            KC_pattern = sparsify(W @ (encode(a) + encode(b) + ...))

        This is exactly what happens when a fly smells multiple odors
        at once — convergent PN input creates a superposed KC pattern.
        """
        bridge = self._make_bridge()
        return bridge.bundle_on_brain(list(vectors), self.snap_duration_ms)

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
        bridge = self._make_bridge()
        decoded, fidelity = bridge.round_trip(vector, self.snap_duration_ms)
        return decoded

    def similarity(self, a, b):
        """
        Similarity via KC pattern overlap on the spiking circuit.

        Encodes each vector, runs the circuit, and computes Jaccard
        similarity of the binary KC activation patterns.  This measures
        similarity in the brain's native 1882-D KC space rather than
        the 140-D PN input space.
        """
        bridge = self._make_bridge()
        return bridge.similarity_on_brain(a, b, self.snap_duration_ms)

    # ------------------------------------------------------------------
    # Fuzzy logic: is_true and conditional branching
    #
    # The original Sutra design uses reserved true/false vectors in the
    # embedding space.  is_true(v) = cosine similarity to the true
    # vector — a continuous [0, 1] truth value.  Conditional branching
    # is fuzzy weighted superposition:
    #   result = weight * branch_A + (1 - weight) * branch_B
    # Both branches execute simultaneously; the condition determines
    # which dominates.  No discrete branching, no if/else — the
    # geometry handles it.
    # ------------------------------------------------------------------

    def _get_true_vec(self):
        """Get the reserved true vector (deterministic, in unused latent region)."""
        if not hasattr(self, '_true_vec'):
            rng = np.random.RandomState(hash("__RESERVED_TRUE__") % (2**31))
            self._true_vec = rng.randn(self.dim)
            self._true_vec /= np.linalg.norm(self._true_vec)
        return self._true_vec

    def _get_false_vec(self):
        """Get the reserved false vector (deterministic, orthogonal to true)."""
        if not hasattr(self, '_false_vec'):
            rng = np.random.RandomState(hash("__RESERVED_FALSE__") % (2**31))
            self._false_vec = rng.randn(self.dim)
            # Orthogonalize against true
            true_vec = self._get_true_vec()
            self._false_vec -= np.dot(self._false_vec, true_vec) * true_vec
            self._false_vec /= np.linalg.norm(self._false_vec)
        return self._false_vec

    def is_true(self, vector):
        """
        Defuzzification: cosine similarity to the reserved true vector.

        Returns a scalar in [-1, 1] that measures how "true" a vector
        is.  This is the bridge between the fuzzy vector world and
        crisp control decisions.  In the original Sutra design, this
        maps to checking which region of the latent space a result
        lands in — near true or near false.

        The true/false vectors are reserved in a semantically void
        region of the embedding space and are just vectors like
        everything else — no special type needed.
        """
        true_vec = self._get_true_vec()
        norm_v = np.linalg.norm(vector)
        if norm_v < 1e-10:
            return 0.0
        return float(np.dot(vector, true_vec) / norm_v)

    def conditional(self, condition_vec, branch_true_vec, branch_false_vec):
        """
        Fuzzy conditional branching via weighted superposition.

        Both branches execute simultaneously.  The condition vector's
        proximity to the reserved true vector determines the weight:

            weight = is_true(condition)
            result = weight * branch_true + (1 - weight) * branch_false

        This is O(1), purely algebraic, and runs on the spiking
        substrate (the weighted sum is presented as PN currents).
        There is no "wrong branch" — there is a weighted mixture
        where confidence propagates as geometry.

        Returns the blended vector (not snapped — snap separately
        if cleanup is needed).
        """
        weight = (self.is_true(condition_vec) + 1.0) / 2.0  # map [-1,1] -> [0,1]
        return weight * branch_true_vec + (1.0 - weight) * branch_false_vec

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

    # ------------------------------------------------------------------
    # Geometric loops on the brain
    #
    # A loop is a repeated rotation in vector space.  Each iteration
    # applies a rotation matrix R to the state vector, snaps through
    # the mushroom body circuit, and checks whether the resulting KC
    # pattern matches a target prototype.  The rotation traces a
    # geometric trajectory: v, Rv, R²v, R³v, ...  Combined with
    # conditional branching (which we already have via permutation
    # keys), this gives the brain iteration and counting.
    # ------------------------------------------------------------------

    def make_rotation(self, angle, plane_indices=None, seed=None):
        """
        Create a rotation matrix for use in loops.

        Produces a Givens rotation in a 2D plane of the vector space.
        Each application rotates the state by `angle` radians in that
        plane, leaving all other dimensions fixed.

        For richer trajectories, compose multiple rotations:
            R = make_rotation(0.3, (0,1)) @ make_rotation(0.2, (2,3))

        Args:
            angle: rotation angle in radians
            plane_indices: tuple (i, j) — which 2D plane to rotate in.
                If None, picks a random plane deterministically.
            seed: random seed for plane selection (if plane_indices is None)

        Returns:
            orthogonal matrix R of shape (dim, dim)
        """
        R = np.eye(self.dim)
        if plane_indices is None:
            rng = np.random.RandomState(seed or self.seed)
            i, j = rng.choice(self.dim, size=2, replace=False)
        else:
            i, j = plane_indices
        c, s = np.cos(angle), np.sin(angle)
        R[i, i] = c
        R[i, j] = -s
        R[j, i] = s
        R[j, j] = c
        return R

    def make_random_rotation(self, angle, n_planes=1, seed=None):
        """
        Create a rotation that acts across multiple random 2D planes.

        More planes = richer trajectory through the vector space.
        With n_planes=1 the trajectory is a circle; with more planes
        it becomes a higher-dimensional spiral.

        Args:
            angle: rotation angle per plane (radians)
            n_planes: how many independent 2D planes to rotate in
            seed: random seed for reproducible plane selection

        Returns:
            orthogonal matrix R of shape (dim, dim)
        """
        rng = np.random.RandomState(seed or self.seed)
        R = np.eye(self.dim)
        # Pick 2*n_planes distinct dimensions
        dims = rng.choice(self.dim, size=min(2 * n_planes, self.dim),
                          replace=False)
        for p in range(min(n_planes, len(dims) // 2)):
            i, j = dims[2 * p], dims[2 * p + 1]
            c, s = np.cos(angle), np.sin(angle)
            G = np.eye(self.dim)
            G[i, i] = c
            G[i, j] = -s
            G[j, i] = s
            G[j, j] = c
            R = G @ R
        return R

    def compile_prototypes(self, prototype_vectors, frame_seed=None):
        """
        Snap prototype vectors through the circuit and store their
        KC activation patterns.  Used as the target table for loops
        and for conditional branching.

        The KC patterns are the brain's native representation — sparse
        binary codes in the 1882-D KC space.  Matching against these
        patterns is what MBONs do biologically.

        IMPORTANT: all prototypes and the loop that matches against
        them must share the same PN→KC projection (the fixed-frame
        invariant).  Pass the same frame_seed to compile_prototypes()
        and loop().

        Args:
            prototype_vectors: dict of {name: hypervector}
            frame_seed: fixed seed for the PN→KC projection.
                Defaults to self.seed.

        Returns:
            dict of {name: kc_pattern} — binary arrays in KC space
        """
        if frame_seed is None:
            frame_seed = self.seed
        compiled = {}
        for name, vec in prototype_vectors.items():
            bridge = self._make_bridge(fixed_seed=frame_seed)
            pattern = bridge.snap_to_kc_pattern(vec, self.snap_duration_ms)
            compiled[name] = pattern
        return compiled

    def loop(self, initial_state, rotation, compiled_prototypes,
             target_name=None, threshold=0.3, max_iters=20,
             frame_seed=None):
        """
        Execute a geometric loop on the brain.

        Each iteration:
          1. Rotate the state vector by R (geometric step)
          2. Snap through the mushroom body circuit (project + sparsify)
          3. Compare the resulting KC pattern against compiled prototypes
          4. If match found (or target reached), return

        The rotation traces a trajectory: v, Rv, R²v, R³v, ...
        The circuit projects each rotated state into KC space and the
        APL sparsification creates discrete basins of attraction.
        When the trajectory enters a target basin, the loop terminates.

        This is how counting works on the brain: N iterations of
        rotation by angle θ accumulates Nθ total rotation.  Place
        target prototypes at known angles and the loop counts to N.

        IMPORTANT: frame_seed must match the seed used in
        compile_prototypes(), or the KC patterns won't be comparable
        (the fixed-frame invariant).

        Args:
            initial_state: starting hypervector
            rotation: orthogonal matrix R (from make_rotation)
            compiled_prototypes: dict {name: kc_pattern} from
                compile_prototypes()
            target_name: if set, only terminate when this prototype
                matches.  If None, terminate on any match above
                threshold.
            threshold: Jaccard overlap threshold for convergence
            max_iters: safety limit
            frame_seed: fixed seed for PN→KC projection.
                Defaults to self.seed.  Must match compile_prototypes().

        Returns:
            (matched_name, final_state, num_iterations)
            matched_name is None if max_iters reached without convergence.
        """
        if frame_seed is None:
            frame_seed = self.seed

        # The rotation accumulates cleanly on the original vector:
        # iteration i presents R^i @ initial_state to the brain.
        # Each rotated point is projected fresh through the circuit
        # (no accumulated decode noise between iterations).
        #
        # Biological analogue: the rotation is a sensory transformation
        # (lateral antennal-lobe processing) applied to the input
        # before each mushroom-body pass.  The mushroom body sees a
        # different input each iteration and checks whether it matches
        # a stored prototype.
        R_power = np.eye(self.dim)  # R^0 = identity
        for i in range(max_iters):
            # 1. Accumulate rotation: R^(i+1)
            R_power = rotation @ R_power
            state = R_power @ initial_state

            # 2. Snap through circuit with FIXED frame, get KC pattern
            bridge = self._make_bridge(fixed_seed=frame_seed)
            kc_pattern = bridge.snap_to_kc_pattern(state, self.snap_duration_ms)

            # 3. Compare against prototypes (Jaccard overlap in KC space)
            best_name = None
            best_overlap = -1.0
            for name, proto_pattern in compiled_prototypes.items():
                intersection = np.sum(kc_pattern * proto_pattern)
                union = np.sum(np.clip(kc_pattern + proto_pattern, 0, 1))
                overlap = float(intersection / max(union, 1.0))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_name = name

            # 4. Check convergence
            if best_overlap >= threshold:
                if target_name is None or best_name == target_name:
                    decoded = bridge.decode_learned(self.snap_duration_ms)
                    return best_name, decoded, i + 1

        return None, state, max_iters
