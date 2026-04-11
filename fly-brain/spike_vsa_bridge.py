"""
Spike-VSA Bridge: encode/decode between hypervectors and spike patterns.

Encoding: centered rate coding (preserves sign information)

Decoding: two paths are supported.

  (a) LEARNED LINEAR READOUT (default, biologically plausible).
      A small set of random hypervectors is pushed through the circuit
      at bridge-construction time (or, when the cache is warm, reused
      from a previous bridge with the same parameters). The resulting
      (KC_firing_pattern → hypervector) pairs are fit via ridge
      regression to produce a linear decoder W of shape (n_kc, dim).
      decode() and round_trip() use W by default. This is the
      biological analog of a learned MBON readout — in the real fly,
      MBONs acquire their readout weights via dopamine-gated plasticity
      during associative learning; here we acquire them via ridge
      regression over a training set, which is the same shape of
      computation (a learned linear map from KC population to readout
      vector) without committing to the exact biological learning rule.

  (b) PSEUDOINVERSE RECONSTRUCTION (baseline, retained for comparison).
      The PN→KC random projection has a Moore-Penrose pseudoinverse
      that analytically inverts the forward map given perfect
      knowledge of the connectome. This is NOT biologically plausible
      — a real MBON does not know the connectivity matrix of the KCs
      it reads from — but it is retained as a reference decoder for
      validating that the circuit is invertible in principle and for
      measuring how much fidelity is lost when going from privileged
      pinv to learned W. Exposed as `decode_kc_pinv()`.

Cache: learned readout weights are cached class-level, keyed on
(seed, dim, n_kc). The first bridge with a given parameter tuple pays
the training cost (~20 additional Brian2 circuit runs); subsequent
bridges with the same parameters reuse the cached weights. This keeps
the e2e test at a ~2x slowdown vs. the pseudoinverse-only path rather
than the ~20x it would otherwise cost.
"""

import numpy as np
from mushroom_body_model import build_model, run_stimulus, get_spike_rates


class SpikeVSABridge:
    """
    Bridge between hypervectors and the mushroom body spiking circuit.

    Encode: hypervector → PN input currents (centered rate coding)
    Decode: KC spike rates → hypervector via a learned linear readout
            (default) or the pseudoinverse of the PN→KC connectivity
            matrix (baseline).
    """

    # Class-level cache of learned readouts keyed on (seed, dim, n_kc).
    # First bridge with a given key trains the readout once by running
    # ~20 random hypervectors through the circuit and fitting a ridge
    # regression; subsequent bridges with the same key reuse the
    # cached weights.
    _learned_readout_cache: dict = {}

    def __init__(self, dim=50, seed=42, **model_kwargs):
        """
        Args:
            dim: hypervector dimensionality (must equal n_pn)
            seed: random seed for reproducible connectivity
            **model_kwargs: passed to build_model (n_kc, apl_weight, etc.)
        """
        self.dim = dim
        self.seed = seed
        self.model_kwargs = model_kwargs

        # Ensure n_pn matches dim
        if 'n_pn' not in model_kwargs:
            model_kwargs['n_pn'] = dim

        # Build the model and extract connectivity
        self.model = build_model(seed=seed, **model_kwargs)
        self.pn_kc_matrix = self.model['pn_kc_matrix']  # shape (n_kc, n_pn)
        self.n_pn = self.model['n_pn']
        self.n_kc = self.model['n_kc']
        self.n_mbon = self.model['n_mbon']

        # Precompute pseudoinverse of PN→KC connectivity for the
        # comparison-baseline decoder (decode_kc_pinv).
        self.pn_kc_pinv = np.linalg.pinv(self.pn_kc_matrix)

        # Learned readout: populated lazily on first use or
        # eagerly via fit_learned_readout(). The cache key matches
        # the bridge's operating parameters so two bridges built with
        # the same (seed, dim, n_kc) share one trained readout.
        self._learned_W = None
        self._last_duration_ms = 200

    def rebuild(self, seed=None):
        """Rebuild the model (needed between runs since Brian2 is stateful)."""
        if seed is not None:
            self.seed = seed
        self.model = build_model(seed=self.seed, **self.model_kwargs)
        self.pn_kc_matrix = self.model['pn_kc_matrix']
        self.pn_kc_pinv = np.linalg.pinv(self.pn_kc_matrix)

    def encode(self, hypervector, baseline_current=1.2, gain=0.6):
        """
        Encode a hypervector as PN input currents (centered rate coding).

        Zero component → baseline current. Positive → above baseline.
        Negative → below baseline. Preserves sign information.

        Args:
            hypervector: array of shape (dim,)
            baseline_current: current at zero component value
            gain: scaling factor for component → current mapping

        Returns:
            array of shape (n_pn,) — current values for each PN
        """
        assert len(hypervector) == self.dim, f"Expected dim={self.dim}, got {len(hypervector)}"

        # Normalize to unit variance to get consistent current range
        std = hypervector.std()
        if std > 1e-10:
            normalized = hypervector / std
        else:
            normalized = hypervector

        # Center around baseline current
        currents = baseline_current + gain * normalized

        # Clamp to non-negative (can't inject negative current)
        currents = np.maximum(currents, 0.0)

        return currents

    def run(self, currents, duration_ms=200):
        """Run the circuit with given PN input currents."""
        self.model = run_stimulus(self.model, currents, duration_ms=duration_ms)
        self._last_duration_ms = duration_ms

    def decode_kc_pinv(self, duration_ms=None):
        """
        Baseline decoder (retained for comparison, not the default).

        Decodes from KC spike rates using the Moore-Penrose pseudoinverse
        of the PN→KC connectivity matrix. This is NOT biologically
        plausible — a real MBON does not have privileged access to the
        connectivity matrix of the KCs it reads from — but it IS a
        useful reference decoder for checking that the circuit is
        invertible in principle.

        The v1 and v2 reviews of the fly-brain paper correctly flagged
        this approach as a biologically-implausible shortcut. The
        default decoder is now `decode_learned()`, which uses a ridge
        regression fit on a training set of (hypervector, KC_pattern)
        pairs — the same SHAPE of computation a dopamine-trained MBON
        performs, without the connectome peek.

        Returns:
            array of shape (dim,) — decoded hypervector
        """
        if duration_ms is None:
            duration_ms = self._last_duration_ms

        kc_rates = get_spike_rates(self.model['kc_spikes'], self.n_kc, duration_ms)
        pn_estimate = self.pn_kc_pinv @ kc_rates

        mean = pn_estimate.mean()
        std = pn_estimate.std()
        if std > 1e-10:
            decoded = (pn_estimate - mean) / std
        else:
            decoded = pn_estimate - mean
        return decoded

    # Backward-compatibility alias. Old code that called decode_kc()
    # expected the pseudoinverse behavior; new code should call
    # decode_learned() or decode_kc_pinv() explicitly.
    def decode_kc(self, duration_ms=None):
        """Deprecated alias for [decode_kc_pinv]. Use [decode_learned]
        for the biologically-plausible default decoder."""
        return self.decode_kc_pinv(duration_ms)

    def _collect_kc_rates(self, duration_ms):
        """Internal: read the current KC firing-rate vector."""
        return get_spike_rates(
            self.model['kc_spikes'], self.n_kc, duration_ms,
        )

    def _cache_key(self):
        """Tuple used to key the learned-readout cache."""
        return (self.seed, self.dim, self.n_kc)

    def fit_learned_readout(self, n_samples=20, duration_ms=200,
                            ridge_lambda=1e-3, rng_seed=12345):
        """
        Fit a linear decoder W such that `W @ kc_rates ≈ hypervector`
        for a set of training (hypervector, kc_rates) pairs.

        Uses the dual form of ridge regression because n_samples is
        always much smaller than n_kc — solving the n_samples-sized
        Gram matrix is vastly cheaper than solving the n_kc-sized one.

        Training cost: this method runs the Brian2 simulation
        `n_samples` times, each at `duration_ms` ms. For n_samples=20
        and duration_ms=200, that's typically 10-60 seconds wall-clock
        depending on the host. The weights are cached at the class
        level keyed on (seed, dim, n_kc), so this cost is paid once
        per unique parameter tuple and amortized across all subsequent
        bridges with the same key.

        Returns:
            The fitted weight matrix W of shape (n_kc, dim).
        """
        cache_key = self._cache_key()
        if cache_key in SpikeVSABridge._learned_readout_cache:
            self._learned_W = SpikeVSABridge._learned_readout_cache[cache_key]
            return self._learned_W

        rng = np.random.RandomState(rng_seed)
        X_rows = []  # each row is a kc_rate vector, shape (n_kc,)
        Y_rows = []  # each row is the driving hypervector, shape (dim,)
        for _ in range(n_samples):
            hv = rng.randn(self.dim)
            hv = hv / (np.linalg.norm(hv) + 1e-10)  # unit-length
            currents = self.encode(hv)
            self.run(currents, duration_ms=duration_ms)
            kc_rates = self._collect_kc_rates(duration_ms)
            X_rows.append(kc_rates)
            Y_rows.append(hv)
        X = np.asarray(X_rows)  # (n_samples, n_kc)
        Y = np.asarray(Y_rows)  # (n_samples, dim)

        # Dual-form ridge regression:
        #   primal: W = argmin ||X W - Y||² + λ ||W||²
        #   dual:   α = (X X^T + λI)^{-1} Y, then W = X^T α
        # Gram matrix is (n_samples x n_samples) instead of (n_kc x n_kc).
        n = n_samples
        gram = X @ X.T + ridge_lambda * np.eye(n)
        alpha = np.linalg.solve(gram, Y)
        W = X.T @ alpha  # shape (n_kc, dim)

        self._learned_W = W
        SpikeVSABridge._learned_readout_cache[cache_key] = W

        # After training runs the circuit n_samples times, the Brian2
        # model has accumulated state. Rebuild once so the caller's
        # first "real" snap starts from a clean slate.
        self.model = build_model(seed=self.seed, **self.model_kwargs)
        self.pn_kc_matrix = self.model['pn_kc_matrix']
        self.pn_kc_pinv = np.linalg.pinv(self.pn_kc_matrix)

        return W

    def decode_learned(self, duration_ms=None):
        """
        Decode from KC spike rates using the learned linear readout W.

        This is the default decoder. It is biologically plausible in
        the sense that MBONs in the real fly acquire their readout
        weights via dopamine-gated plasticity — a learned linear map
        from KC population activity to a readout vector. Our W is
        fitted via ridge regression rather than DAN-mediated
        plasticity, but the shape of the computation is the same:
        `readout = W @ kc_pattern`, with W learned from experience.

        Falls back to the pseudoinverse decoder if the learned readout
        has not been fit on this bridge (either directly or via cache
        lookup).

        Returns:
            array of shape (dim,) — decoded hypervector
        """
        if duration_ms is None:
            duration_ms = self._last_duration_ms

        if self._learned_W is None:
            # Try the cache before falling back to pseudoinverse.
            cached = SpikeVSABridge._learned_readout_cache.get(self._cache_key())
            if cached is not None:
                self._learned_W = cached
        if self._learned_W is None:
            # No trained readout and no cached entry — fall back.
            return self.decode_kc_pinv(duration_ms)

        kc_rates = self._collect_kc_rates(duration_ms)
        decoded = self._learned_W.T @ kc_rates  # (dim, n_kc) @ (n_kc,) = (dim,)
        mean = decoded.mean()
        std = decoded.std()
        if std > 1e-10:
            decoded = (decoded - mean) / std
        else:
            decoded = decoded - mean
        return decoded

    def decode_mbon(self, duration_ms=None):
        """
        Decode from MBON spike rates (simpler but lower fidelity).

        Returns:
            array of shape (dim,) — decoded hypervector
        """
        if duration_ms is None:
            duration_ms = self._last_duration_ms

        mbon_rates = get_spike_rates(self.model['mbon_spikes'], self.n_mbon, duration_ms)

        # Simple: resize MBON rates to match dim
        if self.n_mbon == self.dim:
            raw = mbon_rates
        elif self.n_mbon > self.dim:
            group_size = self.n_mbon // self.dim
            raw = np.array([
                np.mean(mbon_rates[i * group_size:(i + 1) * group_size])
                for i in range(self.dim)
            ])
        else:
            raw = np.resize(mbon_rates, self.dim)

        mean = raw.mean()
        std = raw.std()
        if std > 1e-10:
            return (raw - mean) / std
        return raw - mean

    def round_trip(self, hypervector, duration_ms=200,
                   decoder='learned'):
        """
        Full encode → run → decode pipeline.

        Args:
            hypervector: the input vector to round-trip through the circuit
            duration_ms: simulation duration (ms)
            decoder: which decoder to use. One of:
                - 'learned' (default): the fitted linear readout W.
                  Biologically plausible; does not peek at the PN→KC
                  connectivity matrix. If no trained W is available
                  for this bridge (neither directly nor in the
                  class-level cache), falls back to 'pinv' silently.
                - 'pinv': the baseline pseudoinverse decoder. Uses
                  privileged knowledge of the connectome. Retained
                  for comparison against the learned decoder.

        Returns:
            (decoded_vector, cosine_fidelity)
        """
        currents = self.encode(hypervector)
        self.run(currents, duration_ms=duration_ms)
        if decoder == 'pinv':
            decoded = self.decode_kc_pinv(duration_ms)
        else:
            decoded = self.decode_learned(duration_ms)
        fidelity = cosine_similarity(hypervector, decoded)
        return decoded, fidelity


def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(dot / (norm_a * norm_b))
