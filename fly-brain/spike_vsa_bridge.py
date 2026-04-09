"""
Spike-VSA Bridge: encode/decode between hypervectors and spike patterns.

This is the novel component — the interface between S2's VSA operations
and the biological neural circuit.

Encoding: hypervector → input currents (rate coding)
Decoding: spike trains → hypervector (population rate readout)
"""

import numpy as np


def encode(hypervector, n_neurons, min_current=0.5, max_current=2.5):
    """
    Encode a hypervector as input currents for neurons (rate coding).

    Maps each component of the hypervector to a current injection value.
    Higher vector components → higher currents → higher firing rates.

    Args:
        hypervector: array of shape (dim,) — the vector to encode
        n_neurons: number of input neurons (must divide evenly or pad)
        min_current: minimum current (below threshold = no spikes)
        max_current: maximum current (saturating firing rate)

    Returns:
        array of shape (n_neurons,) — current values for each neuron
    """
    dim = len(hypervector)

    if dim == n_neurons:
        # 1:1 mapping
        components = hypervector
    elif dim > n_neurons:
        # Downsample: average groups of dimensions
        group_size = dim // n_neurons
        components = np.array([
            np.mean(hypervector[i * group_size:(i + 1) * group_size])
            for i in range(n_neurons)
        ])
    else:
        # Upsample: repeat dimensions
        components = np.resize(hypervector, n_neurons)

    # Normalize to [0, 1] range
    v_min, v_max = components.min(), components.max()
    if v_max - v_min > 1e-10:
        normalized = (components - v_min) / (v_max - v_min)
    else:
        normalized = np.full(n_neurons, 0.5)

    # Map to current range
    currents = min_current + normalized * (max_current - min_current)
    return currents


def decode(spike_monitor, n_neurons, duration_ms, output_dim):
    """
    Decode spike trains into a hypervector (population rate readout).

    Each neuron's mean firing rate becomes one or more components of
    the output vector.

    Args:
        spike_monitor: Brian2 SpikeMonitor object
        n_neurons: number of neurons being monitored
        duration_ms: simulation duration in milliseconds
        output_dim: desired output vector dimensionality

    Returns:
        array of shape (output_dim,) — decoded hypervector
    """
    # Compute firing rates for each neuron
    rates = np.zeros(n_neurons)
    spike_indices = np.array(spike_monitor.i)
    for idx in range(n_neurons):
        rates[idx] = np.sum(spike_indices == idx) / (duration_ms / 1000.0)

    if n_neurons == output_dim:
        raw = rates
    elif n_neurons > output_dim:
        # Downsample: average groups
        group_size = n_neurons // output_dim
        raw = np.array([
            np.mean(rates[i * group_size:(i + 1) * group_size])
            for i in range(output_dim)
        ])
    else:
        # Upsample: repeat
        raw = np.resize(rates, output_dim)

    # Normalize to zero-mean unit-variance (standard for embedding vectors)
    mean = raw.mean()
    std = raw.std()
    if std > 1e-10:
        normalized = (raw - mean) / std
    else:
        normalized = raw - mean

    return normalized


def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return dot / (norm_a * norm_b)


def round_trip_fidelity(original, decoded):
    """
    Measure how well a vector survives encode → simulate → decode.

    Returns cosine similarity between original and decoded vectors.
    A positive value means the circuit preserves some signal.
    Values > 0.3 are promising. Values > 0.5 are good.
    """
    return cosine_similarity(original, decoded)
