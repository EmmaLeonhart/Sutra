"""
Spike-VSA Bridge: encode/decode between hypervectors and spike patterns.

Encoding: centered rate coding (preserves sign information)
Decoding: pseudoinverse reconstruction from KC spike rates
"""

import numpy as np
from mushroom_body_model import build_model, run_stimulus, get_spike_rates


class SpikeVSABridge:
    """
    Bridge between hypervectors and the mushroom body spiking circuit.

    Encode: hypervector → PN input currents (centered rate coding)
    Decode: KC spike rates → hypervector (pseudoinverse of connectivity matrix)
    """

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

        # Precompute pseudoinverse of PN→KC connectivity for decoding
        # This inverts the random projection: KC rates → estimated PN currents
        self.pn_kc_pinv = np.linalg.pinv(self.pn_kc_matrix)  # shape (n_pn, n_kc)

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

    def decode_kc(self, duration_ms=None):
        """
        Decode from KC spike rates using pseudoinverse of connectivity matrix.

        The PN→KC connectivity is a random projection. The pseudoinverse
        reconstructs the PN-space input from KC population activity.
        This is compressed sensing: ~5% of 2000 KCs active = 100 measurements
        reconstructing 50 PN dimensions.

        Returns:
            array of shape (dim,) — decoded hypervector
        """
        if duration_ms is None:
            duration_ms = self._last_duration_ms

        # Get KC firing rates
        kc_rates = get_spike_rates(self.model['kc_spikes'], self.n_kc, duration_ms)

        # Pseudoinverse reconstruction: KC rates → estimated PN currents
        pn_estimate = self.pn_kc_pinv @ kc_rates

        # Convert currents back to hypervector (inverse of encode)
        # Remove baseline and undo gain scaling
        # We don't know the exact baseline/gain used, so just normalize
        mean = pn_estimate.mean()
        std = pn_estimate.std()
        if std > 1e-10:
            decoded = (pn_estimate - mean) / std
        else:
            decoded = pn_estimate - mean

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

    def round_trip(self, hypervector, duration_ms=200):
        """
        Full encode → run → decode pipeline.

        Returns:
            (decoded_vector, cosine_fidelity)
        """
        currents = self.encode(hypervector)
        self.run(currents, duration_ms=duration_ms)
        decoded = self.decode_kc(duration_ms)
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
