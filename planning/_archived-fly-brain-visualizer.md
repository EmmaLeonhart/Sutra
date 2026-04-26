# Fly-Brain Visualizer (archived)

**Status: design doc, no implementation. Archived 2026-04-26
along with the fly-brain backend retirement. Preserved as
historical record; revisit if the fly-brain research line
resumes.**
Companion pane to the embedding-space visualizer described in
[`sutra-spec/20-ide-architecture.md`](sutra-spec/20-ide-architecture.md).
This is Sutra-specific IDE UX for programs that target the fly-brain
substrate.

## Why this exists

The fly-brain work (see [`../fly-brain/STATUS.md`](../fly-brain/STATUS.md))
gave Sutra an end-to-end path from `.su` source through the compiler's
`--emit-flybrain` codegen onto a Brian2-simulated mushroom body model,
with verified correct behavior on the `permutation_conditional.su`
reference program. That pipeline works, but debugging it today means
reading Brian2 spike monitor output and eyeballing NumPy arrays.

The IDE can do much better. The reference compiler already knows which
projection neurons, Kenyon cells, and mushroom body output neurons each
`.su` construct maps to; the visualizer's job is to show the programmer
(or an agent) what the compiled substrate is doing while it runs.

This is genuinely novel IDE territory. No existing IDE has a pane that
says "here is the biological circuit your code compiled to, and here
are the spikes firing through it as this test case runs." The closest
analog is a logic-analyzer trace view in an FPGA toolchain, which
nobody has ever needed to think about in a programming language context
before.

## What the visualizer has to show

- **Cells**: the PNs, KCs, and MBONs as discrete nodes with identity.
- **Connectivity**: which PNs feed which KCs (the sparse ~7-fan-in
  random projection), which KCs feed which MBONs, and the APL
  inhibition loop.
- **Live spike activity**: per-cell spike rasters or flashes during a
  simulation run, scrubbable along the time axis.
- **KC sparsity**: the ~5% active fraction enforced by APL inhibition
  is the key biological invariant — the viz has to make it visible
  at a glance.
- **Source-to-circuit mapping**: hover a KC, highlight the `.su` source
  line that compiled to it. Hover a source line, highlight the cells
  that line controls. This is the debugger affordance that makes the
  whole pane worth building.
- **Compile-time probe results**: if the `--emit-flybrain` codegen's
  fixed-frame invariant (see `fly-brain/STATUS.md` §Technical Insight 2)
  fails, the violation shows up visually as a mismatch in the pane.

## Two interpretations of "fly-brain visualizer"

The label is ambiguous, and the ambiguity matters for the delivery
tiers below.

### (a) Topological view — the abstract Brian2 network

Renders the PN/KC/MBON graph as nodes and edges, not anatomy. Layout is
force-directed or layered (PN layer → KC layer → MBON layer).

**Pros:**
- Matches what the current `fly-brain/mushroom_body_model.py` substrate
  actually is: 50 PNs + 2000 KCs + 20 MBONs with random seeded
  connectivity. No real-neuron mapping required.
- Cheap — a graph renderer is well-trodden UI.
- Directly useful for debugging today's `.su` → Brian2 pipeline without
  any new research prerequisites.
- Wires cleanly into `codegen_flybrain.py`'s existing output: each
  generated program already knows its connectivity matrix and its
  seeded projection.

**Cons:**
- Isn't "biological" — the visual doesn't actually look like a fly
  brain, just like a sparse bipartite graph.
- No story for anyone who wants to see where in the *real* brain their
  code is running, which is most of the bio audience we're pitching
  the fly-brain experiments to.

### (b) Anatomical view — backed by hemibrain/FlyWire

Renders real biological neurons in 3D, inside the actual mushroom body
calyx mesh. Each simulated PN/KC/MBON gets mapped to an identified
hemibrain or FlyWire neuron and drawn at its real position with its
real skeleton.

**Data is available:**
- **Hemibrain** (Janelia) — every traced neuron has an `.swc` skeleton
  and xyz coordinates, plus `.obj` neuropil meshes. Queryable through
  `neuprint-python`. Permissively licensed.
- **FlyWire** (Princeton / Seung lab) — full adult female brain,
  ~140k neurons, meshes + skeletons.
- **`navis`** (Python) is the standard tool for loading/rendering these;
  it emits to plotly/vispy/k3d out of the box.

**Pros:**
- The right visual story for the paper: "Sutra programs running on
  identified neurons in the actual connectome." This is the novelty
  claim the fly-brain chapter of the paper already leans on.
- The bio audience (connectome labs, Janelia, FlyWire community) will
  instantly recognize what they're looking at.
- Gives the language a uniquely compelling debugging experience nothing
  else has.

**Cons:**
- **We have to do the mapping first.** Right now the abstract
  50-PN / 2000-KC / 20-MBON network has *no* correspondence to any
  specific hemibrain neuron IDs. Building that mapping is research, not
  rendering:
  1. Pick a subset of real hemibrain PNs (probably glomerulus-labelled,
     ~50 total) to play the role of "PN 0..49".
  2. Pick a subset of real KCs (probably filtered by subclass and claw
     count matching our random-projection fan-in) to play the role of
     "KC 0..1999".
  3. Pick real MBONs (20 of them — these are mostly 1:1 with biology
     already, which is convenient).
  4. Rewire `codegen_flybrain.py` so the emitted Python carries through
     the hemibrain cell IDs, not just opaque indices.
  5. Verify the simulated KC sparsity under the real biological
     fan-in structure, because the numbers may shift away from the
     abstract ~5% once real claw counts are in play.
- **Weeks of work.** This is a meaningful research step, not a
  rendering step.
- **Data licensing**: hemibrain is clean; FlyWire has some publication
  embargoes worth checking before redistribution.

## Delivery tiers

The IDE architecture doc already splits the whole IDE into tiers. The
fly-brain visualizer slots into them like this:

### v0.1 — no visualizer (already shipped)

The IntelliJ plugin scaffold under `sdk/intellij-sutra/` does not
include any visualizer pane. The goal is just to get `.su` files
highlighted and the compiler wired into the diagnostics path.

### v0.2 — embedding-space visualizer

First visualizer, covering the general Sutra case. 3D hyperplane with
user-chosen composite basis vectors, as specified in
[`sutra-spec/20-ide-architecture.md`](sutra-spec/20-ide-architecture.md).

### v0.3 — fly-brain topological view (option a)

Second visualizer pane, tuned specifically to fly-brain compilation.
Ships as:

- A tool window registered by the IntelliJ plugin.
- A graph renderer over the Brian2 network topology from
  `codegen_flybrain.py`.
- Live spike activity feed from a running Brian2 simulation, scrubbable
  along the time axis.
- KC sparsity heatmap overlay.
- Source-to-circuit mapping driven by span information carried through
  the compiler — hover an `.su` line, highlight the generated cells;
  hover a cell, highlight the line.
- Driven by the same MCP surface used for the embedding-space pane,
  so agents can query "which KCs are active right now" and "which
  source line produced KC 412" without a human in the loop.

This is the pragmatic version. It doesn't require any new research,
it unblocks everyone who wants to debug a `.su` → brain compilation
today, and it's a direct upgrade over reading Brian2 arrays.

### v0.4+ — fly-brain anatomical view (option b)

Research-blocked on the "Sutra units ↔ hemibrain neuron IDs" mapping.
Gets its own planning sub-doc once the mapping work starts. Builds on
v0.3 by swapping the graph renderer for a 3D anatomical renderer
without changing any of the source-to-circuit mapping, MCP surfaces,
or spike-feed infrastructure.

Likely implementation path: JCEF tool window loading a three.js scene
that consumes mesh + skeleton data precomputed from hemibrain exports.

## Design rules carried over from the main IDE doc

Every feature listed here must be **agent-accessible** over MCP. The
parity rule from `20-ide-architecture.md` §"Why This Matters" applies
verbatim: if a human can hover a KC in the anatomical view and see the
source line, an agent must be able to ask for the same mapping without
going through the UI.

Concretely, the fly-brain pane's MCP surface has to include at least:

- `flybrain.topology(project) -> { pns, kcs, mbons, edges }`
- `flybrain.spikes(run, start_time, end_time) -> [spike_events]`
- `flybrain.kc_sparsity(run) -> [fractions]`
- `flybrain.source_for_cell(cell_id) -> { file, span }`
- `flybrain.cells_for_source(file, line) -> [cell_ids]`
- (v0.4) `flybrain.anatomy(cell_id) -> { skeleton, neuropil, xyz }`

## Open questions

- **Live-sim plumbing.** How does the visualizer get spike data while a
  Brian2 run is in progress — a file watcher, a sub-process pipe, an
  embedded runtime that owns the Brian2 process lifecycle directly?
  Probably the last of those, for agent control, but it couples the
  IDE tightly to the fly-brain runtime.
- **Rendering stack for v0.3.** JCEF + d3/plotly, JCEF + three.js, or
  native Swing batched renderer? The same question the main visualizer
  pane faces, so the answer should be shared across both panes.
- **Scrubbing semantics.** Time scrubbing inside a single simulation
  run is obvious; does scrubbing extend to stepping between `.su`
  statements mapped onto the biological time axis?
- **The mapping as a versioned artifact.** Once the
  "Sutra units ↔ hemibrain IDs" correspondence exists, is it shipped
  inside the compiler, inside the plugin, as a data package, or in a
  new `fly-brain-mapping/` repo subtree? The VSA-paper authors will
  have opinions here.
- **FlyWire vs hemibrain.** Hemibrain is smaller, cleaner, and has the
  mushroom body complete. FlyWire is bigger and has the full brain but
  some embargoes. v0.4 should target hemibrain first and extend to
  FlyWire later.

## Related

- [`sutra-spec/20-ide-architecture.md`](sutra-spec/20-ide-architecture.md) — parent IDE architecture doc
- [`../fly-brain/STATUS.md`](../fly-brain/STATUS.md) — current state of the fly-brain substrate
- [`../fly-brain/DEMO.md`](../fly-brain/DEMO.md) — what the compile-to-brain pipeline actually does today
- [`../sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`](../sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py) — the AST → FlyBrainVSA translator whose output the visualizer renders
- [`../sdk/intellij-sutra/`](../sdk/intellij-sutra/) — the IntelliJ plugin scaffold this visualizer slots into
