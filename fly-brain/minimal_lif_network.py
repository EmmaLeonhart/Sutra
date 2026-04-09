"""
Minimal Brian2 smoke test: 100 LIF neurons with random sparse connectivity.
Validates that Brian2 is installed and working correctly.
"""

from brian2 import *
import numpy as np

def main():
    # Reset Brian2 state (important for reruns)
    start_scope()

    # Parameters
    N = 100          # number of neurons
    duration = 500   # simulation duration in ms
    p_connect = 0.1  # connection probability

    # LIF neuron model
    eqs = '''
    dv/dt = (I - v) / (10*ms) : 1
    I : 1
    '''

    # Create neuron group
    neurons = NeuronGroup(N, eqs, threshold='v > 1', reset='v = 0',
                          refractory=5*ms, method='exact')
    neurons.v = 'rand() * 0.5'

    # Inject current into first 20 neurons (input layer)
    neurons.I[:20] = 1.5

    # Random sparse connectivity
    synapses = Synapses(neurons, neurons, on_pre='v_post += 0.1')
    synapses.connect(p=p_connect)

    # Monitor spikes
    spike_mon = SpikeMonitor(neurons)
    rate_mon = PopulationRateMonitor(neurons)

    # Run simulation
    print(f"Running {N}-neuron LIF network for {duration}ms...")
    run(duration * ms)

    # Report results
    total_spikes = spike_mon.num_spikes
    active_neurons = len(set(spike_mon.i))
    mean_rate = total_spikes / (N * duration / 1000)

    print(f"Total spikes: {total_spikes}")
    print(f"Active neurons: {active_neurons}/{N}")
    print(f"Mean firing rate: {mean_rate:.1f} Hz")
    print(f"Synapses created: {len(synapses)}")
    print("Brian2 smoke test PASSED")


if __name__ == '__main__':
    main()
