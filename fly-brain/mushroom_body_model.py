"""
Simplified mushroom body circuit model for S2 fly brain substrate.

Architecture (scaled down for fast iteration):
  - PNs (projection neurons): 50 neurons, receive external input
  - KCs (Kenyon cells): 200 neurons, sparse random input from PNs (~7 per KC)
  - APL (anterior paired lateral): 1 inhibitory neuron, feedback on KCs
  - MBONs (mushroom body output neurons): 10 neurons, read out KC activity

The real fly has ~2000 KCs and ~34 MBON types. This is a prototype.
"""

from brian2 import *
import numpy as np


# LIF equations shared across neuron types
LIF_EQS = '''
dv/dt = (I_ext + I_syn - v) / tau : 1
I_ext : 1
I_syn : 1
tau : second
'''

# Neuron counts
N_PN = 50
N_KC = 200
N_APL = 1
N_MBON = 10

# How many PNs each KC receives input from (biological: ~7)
KC_FAN_IN = 7


def build_model(seed=42):
    """Build the mushroom body circuit. Returns (network, monitors) dict."""
    start_scope()
    np.random.seed(seed)

    # --- Neuron groups ---

    PNs = NeuronGroup(N_PN, LIF_EQS, threshold='v > 1', reset='v = 0',
                      refractory=2*ms, method='exact')
    PNs.tau = 10*ms
    PNs.v = 0

    KCs = NeuronGroup(N_KC, LIF_EQS, threshold='v > 1', reset='v = 0',
                      refractory=5*ms, method='exact')
    KCs.tau = 20*ms
    KCs.v = 0

    APL = NeuronGroup(N_APL, LIF_EQS, threshold='v > 1', reset='v = 0',
                      refractory=10*ms, method='exact')
    APL.tau = 15*ms
    APL.v = 0

    MBONs = NeuronGroup(N_MBON, LIF_EQS, threshold='v > 1', reset='v = 0',
                        refractory=5*ms, method='exact')
    MBONs.tau = 15*ms
    MBONs.v = 0

    # --- Synapses ---

    # PN → KC: sparse random connectivity (~7 PNs per KC)
    syn_pn_kc = Synapses(PNs, KCs, on_pre='v_post += 0.3')
    # Build sparse random connectivity: each KC gets exactly KC_FAN_IN PNs
    sources = []
    targets = []
    for kc_idx in range(N_KC):
        pn_inputs = np.random.choice(N_PN, size=KC_FAN_IN, replace=False)
        sources.extend(pn_inputs)
        targets.extend([kc_idx] * KC_FAN_IN)
    syn_pn_kc.connect(i=sources, j=targets)

    # KC → APL: all KCs excite the APL (drives feedback inhibition)
    syn_kc_apl = Synapses(KCs, APL, on_pre='v_post += 0.05')
    syn_kc_apl.connect()  # all-to-one

    # APL → KC: global inhibition (winner-take-all sparsity)
    # Strong inhibition to enforce ~5-10% KC activation (biological target)
    syn_apl_kc = Synapses(APL, KCs, on_pre='v_post -= 2.0')
    syn_apl_kc.connect()  # one-to-all

    # KC → MBON: each MBON reads from a random subset of KCs
    syn_kc_mbon = Synapses(KCs, MBONs, on_pre='v_post += 0.15')
    syn_kc_mbon.connect(p=0.3)  # 30% connectivity

    # --- Monitors ---
    pn_spikes = SpikeMonitor(PNs)
    kc_spikes = SpikeMonitor(KCs)
    apl_spikes = SpikeMonitor(APL)
    mbon_spikes = SpikeMonitor(MBONs)

    # Build network
    net = Network(PNs, KCs, APL, MBONs,
                  syn_pn_kc, syn_kc_apl, syn_apl_kc, syn_kc_mbon,
                  pn_spikes, kc_spikes, apl_spikes, mbon_spikes)

    return {
        'net': net,
        'PNs': PNs,
        'KCs': KCs,
        'APL': APL,
        'MBONs': MBONs,
        'pn_spikes': pn_spikes,
        'kc_spikes': kc_spikes,
        'apl_spikes': apl_spikes,
        'mbon_spikes': mbon_spikes,
    }


def run_stimulus(model, input_currents, duration_ms=200):
    """
    Run the mushroom body model with given input currents on PNs.

    Args:
        model: dict returned by build_model()
        input_currents: array of shape (N_PN,) — current injection per PN
        duration_ms: simulation duration in milliseconds

    Returns:
        model dict (monitors now contain spike data)
    """
    assert len(input_currents) == N_PN, f"Expected {N_PN} currents, got {len(input_currents)}"

    model['PNs'].I_ext = input_currents
    model['net'].run(duration_ms * ms)

    return model


def get_spike_rates(spike_monitor, n_neurons, duration_ms):
    """Get mean firing rate (Hz) for each neuron from a SpikeMonitor."""
    rates = np.zeros(n_neurons)
    for idx in range(n_neurons):
        spike_count = np.sum(np.array(spike_monitor.i) == idx)
        rates[idx] = spike_count / (duration_ms / 1000.0)
    return rates


def print_summary(model, duration_ms):
    """Print a summary of circuit activity."""
    pn_rates = get_spike_rates(model['pn_spikes'], N_PN, duration_ms)
    kc_rates = get_spike_rates(model['kc_spikes'], N_KC, duration_ms)
    mbon_rates = get_spike_rates(model['mbon_spikes'], N_MBON, duration_ms)
    apl_count = model['apl_spikes'].num_spikes

    active_kcs = np.sum(kc_rates > 0)
    kc_sparsity = active_kcs / N_KC

    print(f"PN mean rate:  {np.mean(pn_rates):.1f} Hz (active: {np.sum(pn_rates > 0)}/{N_PN})")
    print(f"KC mean rate:  {np.mean(kc_rates):.1f} Hz (active: {active_kcs}/{N_KC}, sparsity: {kc_sparsity:.1%})")
    print(f"APL spikes:    {apl_count}")
    print(f"MBON mean rate: {np.mean(mbon_rates):.1f} Hz (active: {np.sum(mbon_rates > 0)}/{N_MBON})")


if __name__ == '__main__':
    print("Building mushroom body model...")
    model = build_model()
    print(f"  PNs: {N_PN}, KCs: {N_KC}, APL: {N_APL}, MBONs: {N_MBON}")
    print(f"  KC fan-in: {KC_FAN_IN} PNs per KC")

    # Test with random input currents
    duration = 200
    input_currents = np.random.uniform(0.5, 2.0, size=N_PN)
    print(f"\nRunning with random input currents for {duration}ms...")
    model = run_stimulus(model, input_currents, duration_ms=duration)

    print("\n--- Circuit Activity ---")
    print_summary(model, duration)
