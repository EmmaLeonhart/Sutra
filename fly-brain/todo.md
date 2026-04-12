# Fly-Brain TODO

## Real Connectome Integration

### Phase 1: Hemibrain (current target)
- [ ] Get neuPrint API token from neuprint.janelia.org
- [ ] Build `hemibrain_loader.py` — pull real PN→KC connectivity from hemibrain v1.2.1
- [ ] Replace random projection in `mushroom_body_model.py` with real hemibrain wiring
- [ ] Validate: KC sparsity still lands in 2-10% range with real connectivity
- [ ] Re-run `test_codegen_e2e.py` — all 16/16 decisions still correct
- [ ] Re-run `permutation_conditional.py` — prototype discrimination still clean
- [ ] Update paper to say "connectome-derived" honestly (currently a facsimile)
- [ ] Commit hemibrain connectivity matrix as cached .npz so CI doesn't need API access

### Phase 2: FlyWire (after hemibrain works)
- [ ] Pull full adult Drosophila PN→KC connectivity from FlyWire/codex
- [ ] Scale model to FlyWire dimensions (~140k neurons)
- [ ] Benchmark: prototype capacity at FlyWire scale (~10k-15k items)
- [ ] Run Doom on FlyWire-scale substrate (see DOOM.md milestone ladder)

### Phase 3: Doom on FlyWire
- [ ] Loop compilation (recurrent KC→KC connections)
- [ ] 1D integer arithmetic on substrate
- [ ] Pong demo (minimum viable game on fly brain)
- [ ] General boolean composition (`&&`, `||`)
- [ ] Fixed-point arithmetic compilation
- [ ] Doom logic-only with host rendering
