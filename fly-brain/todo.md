# Fly-Brain TODO

## Real Connectome Integration

### Phase 1: Hemibrain — DONE
- [x] Get neuPrint API token from neuprint.janelia.org
- [x] Build `hemibrain_loader.py` — pull real PN→KC connectivity from hemibrain v1.2.1
- [x] Replace random projection in `mushroom_body_model.py` with real hemibrain wiring
- [x] Validate: KC sparsity still lands in 2-10% range (result: 7.8%)
- [x] Re-run `test_codegen_e2e.py` — 16/16 PASS on hemibrain
- [x] Re-run `permutation_conditional.py` — 16/16 PASS, +1.000 cosine winners
- [x] Update paper to say "connectome-derived" (title + all sections updated)
- [x] Commit hemibrain connectivity matrix as cached .npz (0.1 MB)

### Phase 1.5: Geometric Loops — IN PROGRESS
- [x] Brain-native bind (synaptic weight modulation, not numpy sign-flip)
- [x] Brain-native bundle (summed PN currents)
- [x] Brain-native similarity (KC pattern Jaccard overlap)
- [x] Rotation primitive (`make_rotation`, `rotate_on_brain`)
- [x] Basic loop test (`test_loop.py`)
- [ ] Validate geometric loop on hemibrain substrate
- [ ] Compile `while` to rotation + snap + prototype match
- [ ] Codegen backend support for loops
- [ ] Pong demo using geometric loops (minimum viable game)

### Phase 2: FlyWire (after loops work)
- [ ] Pull full adult Drosophila PN→KC connectivity from FlyWire/codex
- [ ] Scale model to FlyWire dimensions (~140k neurons)
- [ ] Benchmark: prototype capacity at FlyWire scale (~10k-15k items)
- [ ] Run Doom on FlyWire-scale substrate (see DOOM.md milestone ladder)

### Phase 3: Doom on FlyWire
- [ ] Loop compilation via geometric rotation (NOT recurrent KC→KC)
- [ ] 1D integer arithmetic on substrate
- [ ] Pong demo (minimum viable game on fly brain)
- [ ] General boolean composition (`&&`, `||`)
- [ ] Fixed-point arithmetic compilation
- [ ] Doom logic-only with host rendering

## Tooling

### IntelliJ Sutra Plugin
- [ ] Diagnose why `!editor.bat` fails (likely JAVA_HOME or Gradle daemon issue)
- [ ] Get `sdk/intellij-sutra` `runIde` task working
- [ ] Test .su file syntax highlighting in sandbox IDE
- [ ] Verify code completion and live templates work
