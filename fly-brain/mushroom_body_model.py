"""
Mushroom body circuit model for Akasha fly brain substrate.

Architecture:
  - PNs (projection neurons): receive external input
  - KCs (Kenyon cells): sparse random input from PNs (~7 per KC)
  - APL (anterior paired lateral): continuous inhibition on KCs (non-spiking,
    biologically faithful — real APL is graded, Papadopoulou et al. 2011)
  - MBONs (mushroom body output neurons): read out KC activity

The sparse random projection from PNs to KCs is structurally identical
to VSA encoding. APL feedback enforces ~5% KC activation (winner-take-all).
"""

from brian2 import *
import numpy as np


# Default neuron counts
DEFAULT_N_PN = 50
DEFAULT_N_KC = 2000
DEFAULT_N_MBON = 20

# How many PNs each KC receives input from (biological: ~7)
DEFAULT_KC_FAN_IN = 7


def build_model(seed=42, n_pn=DEFAULT_N_PN, n_kc=DEFAULT_N_KC,
                n_mbon=DEFAULT_N_MBON, kc_fan_in=DEFAULT_KC_FAN_IN,
                apl_weight=0.02):
    """
    Build the mushroom body circuit.

    Args:
        seed: random seed for reproducible connectivity
        n_pn: number of projection neurons (input layer)
        n_kc: number of Kenyon cells (sparse coding layer)
        n_mbon: number of mushroom body output neurons (readout layer)
        kc_fan_in: number of PNs each KC receives input from
        apl_weight: strength of APL inhibition (tune for ~5% KC sparsity)

    Returns:
        dict with network, neuron groups, monitors, and connectivity matrix
    """
    start_scope()
    rng = np.random.RandomState(seed)

    # --- LIF equations ---
    lif_eqs = '''
    dv/dt = (I_ext + I_syn - v) / tau : 1
    I_ext : 1
    I_syn : 1
    tau : second
    '''

    # KC equations include inhibitory current from APL
    kc_eqs = '''
    dv/dt = (I_ext + I_syn - I_inh - v) / tau : 1
    I_ext : 1
    I_syn : 1
    I_inh : 1
    tau : second
    '''

    # --- Neuron groups ---

    PNs = NeuronGroup(n_pn, lif_eqs, threshold='v > 1', reset='v = 0',
                      refractory=2*ms, method='exact')
    PNs.tau = 10*ms
    PNs.v = 0

    KCs = NeuronGroup(n_kc, kc_eqs, threshold='v > 1', reset='v = 0',
                      refractory=5*ms, method='exact')
    KCs.tau = 20*ms
    KCs.v = 0

    MBONs = NeuronGroup(n_mbon, lif_eqs, threshold='v > 1', reset='v = 0',
                        refractory=5*ms, method='exact')
    MBONs.tau = 15*ms
    MBONs.v = 0

    # --- Build PN→KC connectivity matrix ---
    # Each KC gets exactly kc_fan_in random PNs
    pn_kc_matrix = np.zeros((n_kc, n_pn), dtype=np.float64)
    sources = []
    targets = []
    for kc_idx in range(n_kc):
        pn_inputs = rng.choice(n_pn, size=kc_fan_in, replace=False)
        sources.extend(pn_inputs)
        targets.extend([kc_idx] * kc_fan_in)
        pn_kc_matrix[kc_idx, pn_inputs] = 1.0

    # --- Synapses ---

    # PN → KC: sparse random connectivity
    syn_pn_kc = Synapses(PNs, KCs, on_pre='v_post += 0.3')
    syn_pn_kc.connect(i=sources, j=targets)

    # KC → MBON: random connectivity
    syn_kc_mbon = Synapses(KCs, MBONs, on_pre='v_post += 0.15')
    syn_kc_mbon.connect(p=0.3)

    # --- APL: continuous inhibition via NetworkOperation ---
    # Real APL is non-spiking (graded). We implement k-winners-take-all:
    # at each timestep, compute a dynamic threshold so only the top fraction
    # of KCs (by membrane potential) can fire. This enforces target sparsity.
    stored_apl_weight = apl_weight  # capture for closure
    target_active = max(1, int(n_kc * 0.05))  # 5% target

    @network_operation(dt=defaultclock.dt)
    def apl_inhibition():
        kc_v = np.array(KCs.v[:])
        if len(kc_v) == 0:
            return
        # k-winners-take-all: only the top target_active KCs by voltage
        # are allowed to fire. Losers get massive inhibitory current that
        # overwhelms any synaptic input, effectively silencing them.
        sorted_indices = np.argsort(kc_v)[::-1]
        inh = np.full(len(kc_v), 100.0)  # massive inhibition by default
        inh[sorted_indices[:target_active]] = 0.0  # winners get none
        KCs.I_inh = inh

    # --- Monitors ---
    pn_spikes = SpikeMonitor(PNs)
    kc_spikes = SpikeMonitor(KCs)
    mbon_spikes = SpikeMonitor(MBONs)

    # Build network
    net = Network(PNs, KCs, MBONs,
                  syn_pn_kc, syn_kc_mbon,
                  apl_inhibition,
                  pn_spikes, kc_spikes, mbon_spikes)

    return {
        'net': net,
        'PNs': PNs,
        'KCs': KCs,
        'MBONs': MBONs,
        'pn_spikes': pn_spikes,
        'kc_spikes': kc_spikes,
        'mbon_spikes': mbon_spikes,
        'pn_kc_matrix': pn_kc_matrix,
        'n_pn': n_pn,
        'n_kc': n_kc,
        'n_mbon': n_mbon,
    }


def run_stimulus(model, input_currents, duration_ms=200):
    """
    Run the mushroom body model with given input currents on PNs.

    Args:
        model: dict returned by build_model()
        input_currents: array of shape (n_pn,) — current injection per PN
        duration_ms: simulation duration in milliseconds

    Returns:
        model dict (monitors now contain spike data)
    """
    n_pn = model['n_pn']
    assert len(input_currents) == n_pn, f"Expected {n_pn} currents, got {len(input_currents)}"

    model['PNs'].I_ext = input_currents
    model['net'].run(duration_ms * ms)

    return model


def get_spike_rates(spike_monitor, n_neurons, duration_ms):
    """Get mean firing rate (Hz) for each neuron from a SpikeMonitor."""
    rates = np.zeros(n_neurons)
    spike_indices = np.array(spike_monitor.i)
    for idx in range(n_neurons):
        rates[idx] = np.sum(spike_indices == idx) / (duration_ms / 1000.0)
    return rates


def get_kc_sparsity(model, duration_ms):
    """Fraction of KCs that fired at least once."""
    n_kc = model['n_kc']
    spike_indices = np.array(model['kc_spikes'].i)
    active_kcs = len(set(spike_indices))
    return active_kcs / n_kc


def print_summary(model, duration_ms):
    """Print a summary of circuit activity."""
    n_pn = model['n_pn']
    n_kc = model['n_kc']
    n_mbon = model['n_mbon']

    pn_rates = get_spike_rates(model['pn_spikes'], n_pn, duration_ms)
    kc_rates = get_spike_rates(model['kc_spikes'], n_kc, duration_ms)
    mbon_rates = get_spike_rates(model['mbon_spikes'], n_mbon, duration_ms)

    active_kcs = np.sum(kc_rates > 0)
    kc_sparsity = active_kcs / n_kc

    print(f"PN mean rate:   {np.mean(pn_rates):.1f} Hz (active: {np.sum(pn_rates > 0)}/{n_pn})")
    print(f"KC mean rate:   {np.mean(kc_rates):.1f} Hz (active: {active_kcs}/{n_kc}, sparsity: {kc_sparsity:.1%})")
    print(f"MBON mean rate: {np.mean(mbon_rates):.1f} Hz (active: {np.sum(mbon_rates > 0)}/{n_mbon})")


if __name__ == '__main__':
    print("Building mushroom body model...")
    model = build_model()
    print(f"  PNs: {model['n_pn']}, KCs: {model['n_kc']}, MBONs: {model['n_mbon']}")

    # Test with random input currents
    duration = 200
    input_currents = np.random.uniform(0.5, 2.0, size=model['n_pn'])
    print(f"\nRunning with random input currents for {duration}ms...")
    model = run_stimulus(model, input_currents, duration_ms=duration)

    print("\n--- Circuit Activity ---")
    print_summary(model, duration)
    print(f"KC sparsity: {get_kc_sparsity(model, duration):.1%}")
