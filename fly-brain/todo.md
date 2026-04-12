# Fly-Brain TODO

## Real Connectome Integration

### Phase 1: Hemibrain — DONE
- [x] Get neuPrint API token from neuprint.janelia.org
- [x] Build `hemibrain_loader.py` — pull real PN→KC connectivity from hemibrain v1.2.1
- [x] Replace random projection in `mushroom_body_model.py` with real hemibrain wiring
- [x] Validate: KC sparsity still lands in 2-10% range (result: 7.8%)
- [x] Re-run `test_codegen_e2e.py` — 12/16 on hemibrain (input-space binding, biologically plausible)
- [x] Re-run `permutation_conditional.py` — 4/4 distinct program permutations
- [x] Update paper to say "connectome-derived" (title + all sections updated)
- [x] Commit hemibrain connectivity matrix as cached .npz (0.1 MB)

### Phase 1.5: Geometric Loops — DONE
- [x] Brain-native bind (input-space multiplication, not synaptic weight flipping)
- [x] Brain-native bundle (summed PN currents)
- [x] Brain-native similarity (KC pattern Jaccard overlap)
- [x] Rotation primitive (`make_rotation`, `rotate_on_brain`)
- [x] Basic loop test (`test_loop.py`)
- [x] Validate geometric loop on hemibrain substrate (3/3 PASS)
- [x] Codegen backend support for loops (while, for, do-while emit eigenrotation)
- [x] Geometric loop builtins (make_rotation, compile_prototypes, geometric_loop)
- [x] is_true (cosine to reserved true vector) and fuzzy conditional branching
- [ ] Compile `while` to rotation + snap + prototype match (automatic pattern recognition)

### Phase 1.6: Strengthen & Explore — TODO
Try each of these sequentially. If one doesn't pan out quickly, move on to the next.

#### 1. Strengthen binding signal (12/16 → higher)
The move from synaptic weight flipping to input-space binding (`a * sign(b)` as PN
currents) is biologically correct but produces a weaker decorrelation signal. The old
approach created true inhibition (negative synapse weights); the new approach only
reduces excitation (lower PN current). Ideas to try:
- **Silence negative PNs entirely**: set currents to 0 for PNs where `a * sign(b) < 0`
  instead of encoding them as below-baseline. This creates a sparser, more contrastive
  input pattern — closer to what the fly does when some glomeruli are actively suppressed.
- **Two-pass binding**: present `a` and `sign(b)` in sequential circuit passes, let the
  circuit's temporal dynamics compute the conjunction. Biologically grounded in the
  fly's ability to process sequential odor presentations.
- **Increase encoding gain**: raise the gain parameter from 0.6 to something higher so
  the sign-flip component dominates the baseline. Simple parameter tuning, no
  architectural change.
- **Learned binding matrix**: train a matrix that maps `(a, b) → bound` using the
  circuit's own KC patterns as training signal. This is the `is_converter` approach
  from the original Sutra design — everything reduces to learned matrix multiplication.

#### 2. Implement is_converter matrices (original Sutra conditional design)
The current `is_true` and `conditional` are minimal implementations. The original
vision from the design chats was deeper:
- **is_converter**: a single learned matrix that transforms any concept vector into a
  test operator (matrix). `is_dog = is_converter * dog` produces a matrix that, when
  applied to an input, maps it toward the reserved true/false region.
- **Universal test operator**: one `is_converter` works for ALL concepts — it extracts
  the "is this similar to X?" computation from any X. This is a strong empirical claim
  that needs validation on the fly brain substrate.
- **Everything is multiplication**: `is_dog * input → near true or near false`. The
  test, the conditional, the transformation — all matrix multiplication. The compiler
  can fold and fuse these aggressively.
- **How to train it**: collect (concept, input, true/false) triples by running pairs
  through the circuit and measuring KC pattern overlap. The is_converter is the matrix
  that best predicts whether two inputs activate overlapping KC populations.

#### 3. Pong demo on hemibrain
Minimum viable game running entirely on the spiking substrate. This is the proof that
geometric loops + fuzzy conditionals + the hemibrain circuit can do something interactive.
- **Game state**: ball position (x, y) and paddle position as vectors in the 140-D
  PN input space. Encode as role-filler bindings: `state = bind(x_role, x_val) + bind(y_role, y_val) + bind(paddle_role, paddle_val)`.
- **Game logic**: one geometric loop per frame. Each iteration: unbind positions,
  compute next position (rotation = ball velocity), check boundary conditions via
  `is_true`, compute paddle action via `conditional`.
- **I/O**: external input (player paddle movement) modifies the state vector between
  loop iterations. This is the I/O-driven termination from the original design —
  the loop runs on the brain, external signals modify the termination landscape.
- **Rendering**: host-side only. The brain computes game logic; a Python wrapper reads
  the decoded state vector and draws pixels. The biological substrate handles the
  computation, not the display.
- **Success criterion**: ball bounces off walls and paddle, score increments. Doesn't
  need to be fast or pretty — needs to be *computed by the fly brain*.

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
