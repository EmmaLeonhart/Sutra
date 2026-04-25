# SutraDev — Claude Code session

*Raw text dump from a Claude Code (CLI) session HTML export. The standard
extractor in scripts/extract_chat.py only handles claude.ai web chats; this
is a one-off salvage to preserve the content before deleting the HTML.*

---

So for the "sutra paper" what were the findings in different versions of it?
Ran 12 commands, read a file
The sutra paper has gone through ~14 reviewed versions. Here's the arc of findings as the scope shrank and the empirical claims got more honest.
v1 (51a997b, "S2 language design paper")
Framing: A programming language paper. Headline "novel contributions": three-tier operation model (primitive / algebraic-O(1) / non-algebraic-O(log n)), truth-extraction matrix M(v)·v = t, empirical initiation (compile-time substrate calibration), cone traversal as control flow. Empirical grounding leaned entirely on the prior cartography paper (86 predicates, r=0.861). No new VSA experiments. Turing-completeness claimed via VSA + ANN + external graph memory.
fe7731d / 533a6d4 — first real binding experiments
Added actual measurements: Hadamard binding fails on bundled role-filler structures over LLM embeddings (2/7 snap correct at 7 roles). Sign-flip binding works (7/7 at 7 roles, then later extended to 14/14 on 15-item codebook on GTE-large, BGE-large, Jina-v2). 10/10 chained bind-unbind-snap. This is the empirical core that survives to today.
aa9ccac — §6.6 "compile to brain"
Added a Brian2 mushroom-body run as a "biological substrate" result. Subsequent revisions (d515ff9, 46b03e2) tightened this to "two-pipeline parity with fly-brain paper" and pointed to the Shiu whole-brain LIF model.
29f6662 / 4c7df5b — reviewer-driven fixes
v1 got Reject. Surgical fixes added: learned MBON readout, dimensionality defense, etc.
7b41532 — is_true honesty
The original "truth-extraction matrix" was a trivial identity-style construction that didn't actually do anything. Replaced with cosine-based is_true.
c2b643c — tier framing stripped
"Tier 1/2/3" prose removed (the framing the user explicitly rejects).
33872e + e30678b — the pivot
Paper renamed from a language paper to an embedding-operations paper. Language claims dropped. Scope trimmed to: which VSA ops work on frozen LLM embeddings, at what capacity, on which substrates.
fedb12b (current, v14)
Replaces the "10/10 chained" headline (which reviewers flagged as a tiny curated codebook) with a Wikidata-scale eval: 200 instances/role × 5 classes × {2,3,5} roles × {10,50,200} codebooks. Accuracy lands 14–22× above chance across all 9 configs; 5-role/200-codebook is 6.3% on 1000 trials (chance 0.5%, p < 10⁻²⁵). This is the honest capacity number — much lower than 14/14 once fillers are within-class clustered.
Net trajectory
Started as an ambitious language-design paper with mostly speculative contributions. Ended as a narrow empirical paper: Hadamard fails, sign-flip works at modest capacity on three frozen LLM embedding models, snap is not the bottleneck, mxbai has a documented pathology. Everything language-related moved to a separate paper.
Hadamard is a non-normalized embedding model?
No — Hadamard is a binding operation (elementwise vector multiplication, a ⊙ b), not an embedding model. It's the textbook VSA binding choice.
The four embedding models tested are: GTE-large, BGE-large-en-v1.5, Jina-v2-base-en, mxbai-embed-large. All four happen to be non-normalized (output magnitudes 17–26 instead of 1.0) when accessed via raw transformers without the post-processing normalization layer.
The §3.3 table is probably what's confusing — it has a column "Hadamard Capacity" next to the model names. That column means "how many roles you can bundle before Hadamard binding stops recovering the right filler on that embedding model." So:
Rows = embedding models (the substrates)
Columns = which binding operation is being measured on that substrate
The paper's headline finding is the comparison between those columns: Hadamard binding caps out at ~3–5 roles on every model tested; sign-flip binding gets to 14 on the same models. Non-normalization is a separate property of the embedding models that matters because magnitude carries information for VSA-style ops, but it's orthogonal to the Hadamard-vs-sign-flip question.
So it was never what I wanted it seems
Right. Looking at it against what's in memory (project_sutra_paper_real_scope.md, feedback_no_sign_flip.md): the paper was supposed to be displacements → consolidate → learned matrices, a three-step arc where semantic binding (learned matrices) is the headline and sign-flip is at most a side note about non-semantic binding.
What actually shipped across all 14 versions is the opposite:
v1 — a language paper with speculative contributions (three-tier model, truth-extraction matrix) and no binding experiments at all. Missed the scope from a different direction.
v3 onward — sign-flip became the empirical core because it was the thing that produced clean 14/14 numbers. The reviewer loop then hardened that choice.
current (fedb12b) — the title is literally "Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces." Sign-flip is the headline. Learned matrices don't appear. The three-step arc (displacements → consolidate → learned matrices) is not the structure of the paper.
The thing that probably happened: each reviewer round pushed toward "what's the cleanest empirical claim you can defend?" and sign-flip had the best table. Learned-matrix binding is a harder experiment — you have to actually learn the matrices on displacement data, show they beat sign-flip, show they encode something semantic that sign-flip can't. That work was never done, so the paper drifted toward what had been measured.
If you want the paper to match the vision, the real move is: rewrite §3 around learned matrices as semantic binding, demote sign-flip to a paragraph in §3.2 as "the non-semantic baseline," and actually run the learned-matrix experiment on the cartography displacements. The rest of the current paper (mxbai pathology, cost analysis, cross-substrate validation) can stay as supporting material but it's not the spine.
Want me to sketch what that rewrite would look like as a STATUS.md item?
I want to rewrite it to try to find learned matrices
Before sketching the rewrite, let me check what's already been tried — git log mentions a recent finding that naive lstsq on nomic didn't produce a clean object-of matrix.
Ran 2 commands, read a file
Good — there's already a 2026-04-15 finding (planning/findings/2026-04-15-nomic-object-matrix-identity-wins.md) that tried exactly this and is worth reading before we touch the paper. Short version: naive lstsq on 30 SVO sentences gave 0% top-1, identity won, and the matrix was severely underdetermined (590k params from 24 training examples). Two confounds killed it: (a) objects were lexically present in the sentences so identity trivially wins, (b) not enough data for a full d×d fit. The finding itself lists the follow-up experiments to run.
Before any paper rewrite, I think we need to run the real experiment first — the paper has to follow the measurements, not lead them. Here's what I'd propose:
Experiment (before paper):
Data: Wikidata triples, 5–10 well-populated predicates (capital of, country of citizenship, author of, located in, instance of, …), 500+ pairs each. Objects are not lexically derivable from subjects in these cases, which kills the identity confound.
Embeddings: nomic-embed-text, mean-centered + L2-normalized (same as codegen_numpy.py's embed()).
For each predicate p, fit four M_p variants:
Displacement (rank-0): d_p = mean(v_o - v_s) — the cartography baseline
Orthogonal Procrustes: restrict to rotation — the RotatE-style story
Low-rank: M = UV^T with rank ∈ {10, 30, 50}
Ridge regression: full d×d with λ > 0
Evaluate: held-out top-1 retrieval against per-predicate object codebook, mean rank, mean cosine. Baselines: identity, constant mean-object, random Gaussian.
Three possible outcomes and what each means for the paper:
Learned M beats displacement on most predicates → paper's headline is "roles are learned matrices; displacement is the rank-0 approximation."
Learned M ≈ displacement → paper says "for these predicates, the affine approximation is already tight; bind degenerates to translation."
Neither beats identity → we'd need a different predicate set or a different substrate, and the paper would say so honestly.
Paper rewrite (after experiment): §1 frames as "prior work found displacements; can we learn richer linear operators?" §3 becomes the learned-matrix results; sign-flip gets demoted to a paragraph as "what non-semantic binding looks like for comparison." The mxbai pathology and cost analysis survive as supporting material.
Want me to start with the experiment script — pulling the Wikidata triples and running the four-way comparison on one or two predicates as a pilot before expanding? That's the fastest path to knowing whether outcome (1), (2), or (3) is what we're looking at, and it'll determine the paper's spine.
Remote Control connecting…
Can we try to make the language paper just on all the stuff we did on it? Also yeah the wikidata triples
Let me check the current state and understand the full scope of what's been done.
Read 6 files, ran 3 commands
OK — so the language paper already exists at language-paper/paper.md and is structurally solid (explains the language, compiler, three demos 23/23, fly-brain negative findings). The latest review was Reject (v8) mainly on "trivial evaluation" and "sign-flip binding."
The key fix: it still frames bind as sign-flip, which contradicts the actual vision (roles are learned matrices). Let me do targeted edits to align the paper with the real design, then commit and push.
Two parallel tracks:
Fix the language paper now
Start the Wikidata triples experiment (separate script)
Let me start with the paper edits.
Edited a file
Now fix the abstract — it currently mentions sign-flip as the binding choice. Let me update it to reflect the learned-matrix vision.
Edited a file
Now update the intro's contribution statement to mention learned matrices as the binding design:
Edited a file
Now update the Related Work section — it still cites the sign-flip companion paper as grounding for bind:
Edited a file
Now update the conclusion to match:
Edited a file
Now let me also fix the reference to the sign-flip companion paper — it shouldn't be listed as a key reference anymore:
Edited a file
Now commit and push the language paper, then start the Wikidata triples experiment.
Ran 5 commands
Language paper pushed. Now let me check the existing Wikidata experiment infrastructure and start the learned-matrix experiment.
Read 2 files, ran a command
Good — I can see the existing infrastructure. Now let me build the learned-matrix experiment. The key difference from the existing probe: use Wikidata triples (not SVO sentences), multiple predicates, and try several matrix fitting methods.
Created a file
Let me check that Ollama is running and nomic-embed-text is available, then do a pilot run on one predicate:
Check Ollama and nomic-embed-text availability
Good — 768-dim nomic embeddings are available. Let me run a pilot on just one predicate (capital-of) with a small N to verify the script works before the full run:
Pilot run on capital-of predicate with 100 pairs
Interesting — initial results show the problem clearly: nomic embeddings for short entity names are all extremely correlated (0.95+ cosine between everything), so no method can discriminate at retrieval. Mean rank is worse than chance because the methods learn the cluster centroid. This is important data.
Let me run the full experiment across all predicates to see if any behave differently:
Full learned-matrix experiment across all predicates
Results are in and they're informative but negative. Here's the honest picture:
Key findings across predicates:
PredicatePairsCodebookBest MethodTop-1Identity Top-1Chance
capital-of167157mean-object/ridge83%60%0.6%
country-of-citizenship2001(degenerate)100%100%100%
located-in-country19615mean-object3.1%0.5%6.7%
author-of198147procrustes26.2%24.1%0.7%
instance-of——(timeout)———
What happened:
country-of-citizenship was degenerate — SPARQL returned 200 people all with 1 unique country
capital-of looks good (83% top-1) but the methods converge to the mean-object baseline — they're learning the cluster centroid, not a relational operator
located-in-country and author-of: no method meaningfully beats identity. Procrustes edges identity by 2pp on author-of — marginal
All learned methods (ridge, low-rank, Procrustes) collapse to near-mean-object because nomic embeddings for short entity names cluster at cos > 0.95
This is the same finding as the 30-sentence probe at larger scale: nomic's embedding space is too isotropic for bare entity names to support learned role matrices. The signal-to-noise ratio for "France → Paris" is drowned by the fact that every country and every capital has cos > 0.95 with every other.
Let me commit the experiment and write a finding.
Commit experiment script and results
Now write the finding:
Created a file, ran a command
OK, here's where we are:
Language paper: Pushed with learned-matrix framing replacing sign-flip. It now describes the language, what it seeks to solve, the three demos (23/23), the fly-brain negative findings, and the design vision of roles as learned matrices.
Learned-matrix experiment: Null result on nomic with bare entity names. This is consistent with the earlier 30-sentence probe — nomic clusters short names too tightly for role matrices to learn from.
What's worth trying next (from the finding):
Richer texts — embed "France is a country in Europe" instead of bare "France". The cartography paper used Wikidata labels with more context and found signal there. This is the most promising follow-up because it matches what actually worked before.
Different substrate — GTE-large (1024-dim) might have less anisotropy
Predicate templates — "The capital of France is ___" gives the model a structural cue about what role to extract
The null result is honest and real. The question is whether it's a problem with the setup (bare names are too short) or a deeper problem with the approach. The cartography paper did find 86 consistent displacements — so the structure exists somewhere in these spaces. The experiment just hasn't found the right way to access it yet.
Want me to try the richer-text variant next, or focus on something else?
I want a 3d visualizer for the IDE for programming stuff
Explore VS Code extension structure
Got it — when you run a .su program, it should both print the result AND open a Three.js 3D visualization showing the vectors and operations. Let me check what the existing visualizer HTML looks like, then build this.
Read 3 files
Now let me check the smoke test to understand how programs get run:
Read a file
Now I have a clear picture. The plan:
Add tracing to the _NumpyVSA class so it records every vector + operation
After execution, PCA-project to 3D and emit a self-contained HTML file with Three.js
Wire it into the VS Code extension as a webview panel that opens on run
Let me build this. I'll start with the Three.js visualizer template + a trace-emitting wrapper, then wire it into the extension.
Read a file
I'll build this in three pieces: (1) a trace-recording wrapper for the runtime, (2) a Three.js visualizer HTML template, (3) VS Code wiring. Let me start.
Created a file
Now create the trace-emitting wrapper that the codegen can inject:
Created a file
Now add --trace support to the compiler CLI and modify the codegen to emit tracing code:
Found files, read a file
Now add the --run-viz command to the compiler CLI:
Edited a file
That tracing approach is too messy. Let me rewrite it with a cleaner strategy — inject tracing code directly into the generated Python source before exec:
Edited a file
Now add the --run-viz flag to the argument parser and dispatch:
Edited 2 files
Now let's test it on the role_filler_record example:
Ran 2 commands
It works. Let me check the generated HTML:
Ran a command, read a file
Trace is working. 9 basis vectors, 3 bind operations, 1 bundle, 1 unbind — exactly right for the role_filler_record program. PCA projects them to 3D with basis vectors clustered together and bind outputs spread apart.
Let me also test on fuzzy_branching:
Test run-viz on fuzzy_branching
Now add the sutra.runVisualize command to the VS Code extension:
Read a file, edited a file
Now add the command implementation to extension.ts:
Edited a file
Let me also test the hello_world program:
Test run-viz on hello_world
All three examples work. Let me clean up the generated viz files (they shouldn't be committed), then commit and push:
Read 2 files, ran a command, searched code
Now commit and push everything:
Ran 6 commands
Everything is pushed. Here's what you now have:
3D Visualizer — how to use it:
# From sdk/sutra-compiler/:
python -m sutra_compiler --run-viz ../../examples/role_filler_record.su
This does two things:
Prints the program result to stdout (e.g. red)
Generates role_filler_record_viz.html — open it in any browser to see the 3D scene
What the visualization shows:
Each vector as a colored sphere (PCA-projected from 768D to 3D)
Purple = basis vectors (embed), Pink = bind outputs, Green = bundle outputs, Orange = unbind outputs, Cyan = results
Lines connecting operation inputs to outputs
Animated step-by-step reveal (Play/Pause/Reset)
Orbit controls (drag to rotate, scroll to zoom)
Hover tooltips showing vector name, type, and step number
In VS Code: The extension now has a "Sutra: Run & Visualize 3D" command that compiles the active .su file, runs it with tracing, and opens the Three.js visualizer in a webview panel next to your code.
The generated .html and .json trace files are gitignored so they won't pollute the repo.
Okay, here's actually something I'd be interested in. I would like to have it so that there are two different run buttons in the IDE:
One of them is a run without visualisation.
One is a run with visualisation.
Also, it's not supposed to be fucking Visual Studio Code; it's supposed to be like the IntelliJ IDE we've been building for it.
Read 6 files
Now let me check the existing viz tool window to see how it loads HTML:
Read a file
Good. Now I have the full picture. The plan:
Add a visualize flag to SutraRunConfiguration
Create a second SutraRunConfigurationType — "Sutra Visualize" — or better, add a checkbox to the existing run config + a second gutter action
When running with visualization, pass --run-viz instead of --run, then load the trace JSON into the JCEF embedding tool window
The cleanest IntelliJ approach: use a custom Executor (like how Debug is a separate executor from Run). That gives you two gutter icons and two toolbar buttons automatically.
Read a file
Now I'll build this properly. The approach:
SutraVisualizeExecutor — a custom Executor (like Debug) that shows a second gutter icon
SutraVisualizeRunner — a ProgramRunner that handles the visualize executor, runs --run-viz, and loads the trace into the JCEF tool window
Update the run config to support both modes
Copy the Three.js HTML template into IntelliJ resources
Created 2 files
Now update the gutter line marker to show both Run and Visualize actions:
Created a file
Now register the executor and runner in plugin.xml:
Edited a file
Now copy the Three.js visualizer HTML into the IntelliJ resources:
Copy Three.js visualizer to IntelliJ resources
Let me verify the build compiles. Check the Gradle setup:
Ran 2 commands
Allow Claude to Run cd "C:\Users\Immanuelle\Documents\Github\Sutra\sdk\intellij-sutra" && ./gradlew.bat compileKotlin 2>&1 | tail -30?
Test compile the IntelliJ plugin
cd "C:\Users\Immanuelle\Documents\Github\Sutra\sdk\intellij-sutra" && ./gradlew.bat compileKotlin 2>&1 | tail -30
Deny
Esc
Always allow for project (local)
CtrlEnter
Allow once
Enter
