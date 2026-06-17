# Yantra: A Neuro-Symbolic, GPU-Native Operating System for Critical Systems

## Abstract

Conventional operating systems treat the CPU as the brain and the GPU as an accelerator, and treat AI as something bolted on through serialization layers — text, JSON, tool-call schemas. For workloads where both **predictable latency under load** and **first-class local AI** matter — defense, aerospace, industrial control, medical devices, autonomous systems — neither inversion is paid for, but both costs are felt: GPU-resident models thrash against CPU-resident schedulers, and every round trip through the OS/AI boundary costs an embed/decode pair that drops information and adds jitter.

**Yantra** is an operating system written in [Sutra](https://sutra.emmaleonhart.com) — a typed functional language whose compiled forward pass *is* a PyTorch neural network — in which the kernel, processes, IPC, and GUI are all the same artifact: a single differentiable tensor-op graph executing on the GPU. The CPU is reduced to an orchestrator that boots the system, holds a cold-store of suspended processes in RAM, and arbitrates GPU admission. Userspace processes are Sutra programs of type `(Axon) -> Axon`, where an *axon* is a fixed-width vector produced by rotation binding over a codebook of role-fillers. IPC is axon-passing; capabilities are the rotation operators themselves — possessing the operator is the only way to read or write a slot, so revocation is operator rotation.

Three structural properties fall out of this design. (1) **Predictable performance under load**: every admitted process declares its compute and synthetic-dimension footprint at install time; the runtime holds those allocations until exit, so adding processes either fits cleanly or fails admission — it never degrades what is already running. (2) **A verification-friendly surface**: the non-AI parts of the system reduce to a fused tensor-op graph, polynomial Kleene logic, and tail-recursive loops with soft-halt RNN cells; equivalence checking is algebra rather than control-flow traversal, and termination obligations reduce to monotonicity of a halt scalar. AI parts are explicitly *not* claimed verifiable — they are quarantined behind axon-typed contracts, provenance roles, and runtime monitors. (3) **AI-native by construction**: every process already takes an axon and returns an axon, so a local model's residual activations, a JEPA's predicted latents, and a `read_file()` result are the same kind of tensor, with no translation layer.

This is a design paper backed by a small running nucleus, not an empirical systems paper. The architecture, axon model, lifecycle, security argument, verification story, market analysis, and roadmap are worked out across the planning corpus in this repository, and a v0.0 Connectome Manager runs real Sutra services through a capability-checked axon router today. The Sutra compiler and the JS/TS transpiler that Yantra depends on are tracked as separate projects; Yantra itself targets a forthcoming Sutra-native, bare-metal implementation written natively in Rust at its lowest layers. An early bare-metal bootloader already boots in QEMU, while the production Rust orchestrator above it is not yet built.

## 1. Introduction

The dominant computing paradigms were fitted around scarce serial compute and disembodied language models. Two facts about the current substrate make that fit increasingly poor.

**GPUs are the default.** Critical-systems vendors increasingly ship accelerator-heavy boxes anyway — for radar processing, sensor fusion, vision, planning, ML inference. A connectionist operating system is not chasing exotic hardware; it is using what is already in the box with less pretence that the CPU is still the center of gravity.

**AI is everywhere but feels bolted on.** RAG, MCP, function calling, agent scaffolding, tool-use frameworks — these are all plumbing around the same hole. Models think in vectors; software speaks in bytes. Every loop iteration through that plumbing is an opportunity to drop information, mistranslate intent, hallucinate a response, or stall. The phrase "the model uses the computer" hides a long chain:

```
model activation → text → parse → execute → output → re-embed → model activation
```

Yantra collapses that loop:

```
model activation → Sutra program → tensor output → directly consumable
```

Because every Sutra program already lives in the embedding space the model is thinking in, perception (e.g. JEPA), reasoning (LLM activations), and action (Sutra tensor ops) become first-class operations on one representation. There is no translation layer because there is nothing to translate to.

Yantra is **not** an LLM with tool use; it is the substrate beneath that. It is **not** a consumer desktop replacement; users who want 100 Chrome tabs and arbitrary side-loaded software are not the customer. It is **not** "von Neumann with a GPU instead of a CPU"; the GPU is doing connectionist work, not impersonating a CPU. And it is **not** a video-generation world model of a computer — see §7 for the contrast with Meta's *Neural Computers*, which inspired the framing and then went the opposite direction.

### 1.1 Contributions

This paper is the design synthesis for Yantra, and as of this revision it is no longer purely a position paper: a v0.0 implementation nucleus runs in the public repository. The thesis and commitments below are unchanged from earlier revisions; what changed is that the load-bearing pieces are demonstrably implementable rather than aspirational. §8 gives the measured status.

The empirical claims Yantra's design *rests on* are not invented here. Substrate-independent rotation binding, end-to-end-differentiable training of compiled symbolic programs, and substrate-pure beta reduction to tensor normal form are all measured in the Sutra paper across four embedding substrates: 100% bundle decoding through width $k=8$, single-cycle bind/unbind round-trip at $\approx 1.5 \times 10^{-15}$, and fuzzy-rule training from 4% (random init) to 95% in 50 epochs on a 19-AND-deep rule tree over 992 words / 20 classes. This paper lifts those measured primitives into an OS-shaped design and states the additional commitments that lifting entails:

1. **A coherent system design** that takes "the symbol *is* the computation" down to the kernel, synthesised from the planning corpus.
2. **A capability model built on rotation operators** (§3.3): roles are not labels but the rotations that produce axon slots; possessing the operator *is* the capability. Revocation is operator rotation; sandboxing is handing a child a derived sub-codebook. §3.3.1 gives a threat model that states what this protects against and what it does not.
3. **A verification story scoped to what it covers** (§4): the kernel and named critical processes reduce to a small set of polynomial obligations over individually-tractable tensor graphs; whole-system behaviour under arbitrary userspace composition is explicitly *not* claimed verifiable. AI parts are out of scope for formal verification and are bounded behind contracts and runtime monitors instead.
4. **A target-market argument** (§6) for why critical systems are the right first market: the same properties (no `eval`, no service workers, no AOT-vs-runtime divergence, fixed allocations, small syscall surface) that read as compatibility losses to a desktop user are procurement criteria to defense and aerospace.
5. **A hardware-boundary accounting** (§3.5) of where CPU↔GPU round-trips remain. Yantra moves the boundary cost from "every syscall" to "every tick" and from "every device register access" to "every axon exchange with a wrapper driver." This is bounded, not eliminated. The v1 review flagged hardware realities (interrupts, I/O context switching, MMIO) directly and the design addresses them head-on rather than waving them past.

## 2. The thesis

Yantra commits to the claim that **a GPU-resident, embedding-typed process model is a better fit for the critical-systems workload than a CPU-resident, byte-typed one, once local AI is part of the stack**. This rests on three inversions of conventional OS design.

**CPU is the brain → CPU is the orchestrator.** The CPU loads the bootloader, starts the GPU runtime, and shuffles inactive processes to and from RAM. It does no application work. Its role is closer to a CUDA host than to a conventional kernel.

**Programs use the OS to talk to AI → AI talks via the OS.** There is no "AI API" layered on top of a conventional process model. The process model itself is embedding-shaped: every process takes an axon and returns an axon. AI integration is what you get for free, not a feature added on.

**File system is internal → File system is the legible surface.** The compute is opaque by design (matrix soup). The file system is the part that stays readable by humans and forensics, so it remains conventional (ext4/btrfs/zfs), and the boundary between compute world and storage world is a small, well-defined set of syscalls that read and write axons from files.

## 3. Architecture

The system is a layer cake whose top six layers execute on the GPU as one differentiable tensor-op graph, with the bottom two running on a small conventional CPU/RAM/storage tier.

```
+----------------------------------------------------------+
|  GUI layer (everything-is-a-browser)                      |
|  HTML5 + CSS + AOT-compiled JS/TS + WebGL                 |
+----------------------------------------------------------+
|  Userspace processes — Sutra programs (Axon) -> Axon      |
+----------------------------------------------------------+
|  Kernel services — process table, axon router, FS bridge, |
|  display server, input router, network stack              |
+----------------------------------------------------------+
|  Sutra runtime — tensor-op graph executor, GPU memory     |
|  arenas, soft-halt RNN cells driving tail-recursive loops |
+----------------------------------------------------------+
|  Init + resource manager (small CPU program)              |
+----------------------------------------------------------+
|  CPU + RAM + storage (conventional)                       |
+----------------------------------------------------------+
```

The kernel's job is not scheduling in the conventional sense; it is deciding **what is connected to what** — moving programs between three tiers: **disc** (programs at rest), **RAM** (loaded but idle), and **GPU** (the live connectome). It is a Connectome Manager, not a context-switcher.

### 3.1 The axon model

The Sutra-language axon spec is authoritative; Yantra inherits it. An axon is a fixed-width vector produced by *rotation binding* over a codebook of roles:

$$ a = \mathrm{bundle}\left(\mathrm{bind}(R_{subject}, F_{alice}),\; \mathrm{bind}(R_{action}, F_{send}),\; \ldots\right) $$

`bind` is multiplication by a Haar-orthogonal rotation matrix $R_{role}$ keyed to the role's identity; `bundle` is superposition (sum + normalise); `unbind` is multiplication by $R_{role}^{-1} = R_{role}^{\top}$. Rotation binding is the chosen primitive because of measurements in the Sutra paper (companion submission): across four frozen embedding substrates spanning two modalities (`nomic-embed-text`, `all-minilm`, `mxbai-embed-large`, and the ESM-2 protein language model), bundles decode at 100% accuracy through width $k=8$ on every one, where the textbook Hadamard product has already collapsed to 2.5% on `mxbai-embed-large` and 7.5% on `all-minilm`; single-cycle bind/unbind round-trips at $\approx 1.5 \times 10^{-15}$. Substrate-independence is what justifies Yantra's "swap the embedding model and the same source recompiles against a different geometry" claim — without it, every deployment would be welded to a single embedding model.

Yantra tightens the spec in two ways. **Fixed width is mandatory, not optional** — the axon width per process goes in the install manifest, because the runtime cannot reserve GPU allocation without it. **Crosstalk-depth caps surface as runtime errors, not silent degradation** — a process that would exceed its bundle-depth budget gets a clean rejection rather than garbled output.

### 3.2 IPC and the syscall surface

IPC is axon-passing. The kernel keeps a process table and an axon router; processes hand axons to roles and the router delivers them. The filesystem bridge is the largest external surface and the place the design earns its keep:

```
read_file  : { R_path } -> { R_bytes_axon, R_metadata_axon }
write_file : { R_path, R_payload_axon } -> { R_status }
```

`R_bytes_axon` carries the file's contents in one of two modes: a literal embedding produced by an embedding model (when the file is meant to be consumed *semantically*, e.g. by a search process), or a Sutra-compiled axon that decodes losslessly to bytes (when the file is meant to be consumed *exactly*, e.g. executables, configs, binary blobs). The mode is part of the file's metadata, not the syscall's job. The conventional filesystem and the embedding-typed kernel meet at exactly this boundary.

### 3.3 Capability transfer via rotation operators

In the Sutra spec, roles are not labels but *operators*: the rotation $R_{role}$ is the only way to read or write the corresponding slot. Yantra turns that into a security mechanism with three consequences.

**Process isolation.** A process is bound to a set of roles. Roles it does not possess decode any axon's slot to noise, by construction. There is no permission table to consult; the inability is geometric.

**Sandboxing.** Handing a child process a smaller (or derived) codebook restricts it to that subset. The child cannot synthesise the parent's operators because it has never seen them.

**Revocation.** Rotating the parent operator invalidates all derived copies. Axons already in flight that carry the revoked role become unreadable in that slot. This is cleaner than capability-table mutation in a conventional capability OS.

#### 3.3.1 Threat model — what rotation-operator capabilities do and do not protect against

The mechanism is geometric, which is both its strength and the source of its limits. Three classes of attack the v1 design takes seriously, with an accounting of where it is and is not robust:

**Forgery (rotation-operator synthesis).** Without $R_{role}$, an adversary trying to read a slot can guess the operator (computationally infeasible — operators are seeded by content hash over a large Haar-orthogonal manifold) or project the axon onto a related basis. The protection is symmetric to the substrate's quality: a substrate where unrelated content vectors are well-separated produces operators whose unintended decode is statistically separable from valid decode. Substrate quality is therefore a security parameter, not just a capacity parameter — a weak embedder weakens the capability story.

**Crosstalk leakage at high bundle depth.** As bundles approach the substrate's capacity limit, the noise floor on each unbind rises. An adversary with no operator who repeatedly queries a high-depth bundle may extract residual signal from cross-role interference. This is the security cost of treating bundle depth as a runtime constraint: depth must sit conservatively below the leakage threshold for each substrate's measured profile (the Sutra paper's Appendix D contains the per-substrate L-sweep the v1 default budget derives from). Exceeding the budget is detected and refused; the unsafe regime is not reachable from valid programs.

**Adversarial tensor perturbations.** A hostile process that *cannot* read a slot but *can* write to an axon channel could craft a perturbation that, bundled with downstream content, biases the unbind output of a privileged receiver. Mitigation is twofold: (a) the axon router treats process-emitted axons as untrusted and the receiving role's capability check happens *before* bundle composition, so an adversary cannot inject into a bundle they lack the operator to compose into; (b) every axon carries a provenance role (`02-axon-model.md`) that the runtime monitor can inspect for trust-tier policy. **This is mitigation, not a proof.** Adversarial-robustness analysis of rotation binding under crafted-perturbation attack is research-grade work the Sutra and Yantra authors have not done, and the v1 review (post 2393) is right to flag it. A defensible v1 default is "constrain inter-process axon channels to a pre-declared role-set per channel"; we do not yet claim more.

The full threat model, the crosstalk analysis, and the v1 default policy choices live in `planning/08-security-and-isolation.md`; open questions about GPU memory side channels live in `planning/15-open-questions.md` and `planning/17-memory-model.md`.

### 3.4 Fixed allocations and admission control

Each process declares its compute and synthetic-dimension footprint at install time, and the runtime holds those allocations until the process exits. The resource manager (a small CPU-side program) keeps a table of GPU-resident processes and a RAM cold-store of suspended ones, and decides which to evict and which to resume — but it does *not* schedule. The GPU runs everything that fits, simultaneously. Launches that do not fit fail admission; nothing already running degrades.

This is the property critical-systems customers actually need. Conventional OSes trade predictability for flexibility — brilliant at running 100 Chrome tabs and a video call at once, mediocre at guaranteeing a control loop's deadline when something else on the box gets busy. Yantra inverts the trade.

### 3.5 Hardware boundary — interrupts, MMIO, and the round-trips that remain

A GPU-native kernel does not get to wish away the CPU-side hardware reality, and the v1 review flagged this correctly. Async hardware interrupts, I/O context switches, and memory-mapped IO for device registers all happen on the CPU side, and reaching them from inside the GPU's tensor world costs a CPU↔GPU round-trip. Yantra's claim is not that the round-trips vanish; it is that they are *bounded* and *staged at known points* rather than dropping into the GPU's hot path on every event.

**Interrupts arrive at tick boundaries, not at instructions.** The CPU-side shim batches hardware interrupts (timers, packet arrivals, sensor reads, device-status changes) into axons delivered to the router at the next GPU tick boundary. The cost is one CPU→GPU transfer per tick rather than per event; tail latency is bounded above by one tick period; the tick rate is a deployment-time choice trading GPU utilisation against event latency. This is interrupt coalescing made structural rather than a special case.

**MMIO is wrapped, not exposed.** A device whose registers live in MMIO space is fronted by a userspace driver process on the CPU shim that re-exports an axon channel. A GPU-resident process talking to the device sends and receives axons; the driver translates to/from MMIO on the CPU side. The round-trip cost is one ping-pong per axon exchange, not per register access — provided the driver reads device state once per tick and emits a single axon summarising what changed. A driver that polls in a tight loop pays per access; that is a *driver bug*, visible in code review. For control-loop work where even tick-latency MMIO is too slow, the answer is "use a GPU-direct peripheral or accept the round-trip cost on this loop." The cost is priced and put on a path the certifier can read, not eliminated.

**DMA-direct-to-GPU is the future, but not v1.** Modern hardware lets peripherals deposit data directly into GPU-accessible memory, bypassing the CPU shim on the data path while keeping it on the control path. Making DMA-direct compatible with the kernel's capability check on the receiving role is a known design problem (`planning/17-memory-model.md`). The architecture does not preclude it; the v1 design pays the CPU-shim ping-pong cost for safety.

In short: Yantra moves the OS/hardware boundary cost from "every syscall" to "every tick", and from "every device register access" to "every axon exchange with the device driver." The cost is not zero. The predictable-latency claim is conditional on the deployment's tick rate, driver discipline, and whether the workload tolerates tick-latency event delivery. A customer with sub-tick event-latency requirements needs a different OS *or* a different tick rate, and we say so.

## 4. Verification

A blunt division: the **non-AI parts** (kernel, init, FS bridge, capability check, resource manager, browser engine, transpiler outputs of finite programs) are verifiable in principle. The **AI parts** (any embedding-model invocation, any process whose semantics depend on a learned weight matrix) are not, and we do not pretend otherwise — they get bounded-behaviour guarantees, capability discipline, provenance roles, and runtime monitoring instead.

### 4.1 What makes the non-AI side tractable to verify

Three Sutra design choices combine to make this work, within a scope we are careful about.

1. **Beta reduction to tensor normal form.** Sutra programs reduce to a canonical, fused tensor-op graph. Semantically equivalent programs reduce to the same graph (modulo trivial differences), so equivalence checking on the *reduced* graph is algebra rather than control-flow traversal — a real win. This does *not* wave away state-space explosion across a whole running system, and the v1 review (post 2393) is right to push here. What we commit to: equivalence-as-algebra applies to the *contract surface* of each individual kernel role and critical process — a fixed, small set of programs whose tensor normal forms are individually tractable. The auditable property is "the kernel and the named critical processes individually satisfy their published axon-typed contracts," not "the entire running system has a closed-form correctness proof." The latter is state-space-explosion territory and we do not make that claim.

2. **Polynomial Kleene logic for branches.** What looks like `if/else` in source becomes, after reduction, a polynomial that interpolates between branches on a fuzzy truth value. The Kleene connectives are Lagrange-interpolated polynomials, exact on the $\{-1, 0, +1\}$ truth grid and $C^{\infty}$ elsewhere — closed-form expressions whose range, sign, and derivatives are symbolically tractable per branch. The toolchain that discharges these obligations is bespoke (off-the-shelf SMT solvers target Boolean / linear arithmetic); shipping it is part of what compiler qualification costs.

3. **Tail-recursive loops as soft-halt RNN cells.** Each loop is a bounded recurrence whose halt cell decides termination. Termination reduces to "the halt signal is monotone within bounded steps" — a much smaller obligation than proving an arbitrary `while` terminates, but still an obligation discharged per loop.

Together these take "verify the trusted base of a kernel" from "navigate millions of lines of imperative C" to "discharge a finite set of polynomial obligations over a small known set of tensor graphs." That is a real reduction in certification surface, not a claim that the *running system as a whole* is closed-form verifiable — no real system has that property and we do not promise it.

### 4.2 The DO-178C-shaped argument

For an aerospace certification audience the structure is:

- **Plan**: a fixed kernel image plus a fixed set of critical processes, manifests published, no runtime code loading.
- **Software requirements**: axon-typed contracts on every kernel role and critical process (input roles, output roles, status conditions).
- **Design**: Sutra source, whose tensor normal forms *are* the designs.
- **Verification artefacts**: mechanical proofs that the normal forms satisfy the contracts; polynomial-logic obligations discharged by an SMT-style solver.
- **Trace**: every capability grant and every admit/evict, written to an append-only log.
- **Tooling assurance**: the Sutra compiler is in scope for qualification; its output (normal form) is the artefact under review, not the source.

This is the *shape* of a real certification effort. We are not shipping a certified Yantra v1; we are shipping an architecture friendly to certification when the time comes.

### 4.3 What we are not claiming

- Yantra is not a certified system out of the box. A certified configuration is per-customer, per-mission.
- Yantra is not formally verified end-to-end today. The architecture is verification-friendly; the proofs are an ongoing project, most of which has not started.
- Yantra does not make AI safe. It makes AI *quarantinable* — the unsafe parts are bounded, contracted, and monitored. That is not the same as safe.

## 5. AI-native by construction

A model running on Yantra is not bolted on top of a computer issuing string commands. Its outputs *are* axons routable directly to the input role of any process that accepts that role; its inputs *are* axons from other processes. There is no text serialization layer between the model and the rest of the system.

**Perception is a process.** A JEPA-style joint-embedding predictive model emits its predicted latents as axons. The application consuming them is not "the AI" — it is a process whose input role is a JEPA latent. It can be hand-written Sutra, a transpiled JS dashboard, or another model. They all see the same shape.

**Local AI is everywhere by default.** A file manager doing semantic search asks the FS bridge for files in `semantic` mode and runs cosine similarity. A terminal suggesting commands runs a small local model over shell-history axons. A monitoring dashboard runs an embedding-distance check against a baseline. None need a special "AI API"; they consume axons.

**The alignment pacemaker.** A specific pattern drops out of this: a small alignment monitor sits between AI processes and any user-visible output, watching for known failure modes. Because every axon carries provenance roles, the monitor can refuse to forward an axon whose provenance does not match the decision downstream. This is a *runtime* mechanism that complements the verification story rather than replacing it.

## 6. Target markets

The customer in one sentence: *an organization that runs critical software, can't tolerate performance jitter, has to pass a certification audit, increasingly wants local AI as part of the stack, and is paranoid about its attack surface.*

That excludes consumer desktops on purpose. It includes defense (mission systems, sensor fusion, command-and-control), aerospace (avionics, ground stations, DO-178C-shaped work), industrial control (robotics, factory automation, process control), medical devices (imaging, surgical assistants, embedded diagnostics), and autonomous systems (drones, ground vehicles, marine, field robotics).

The three structural properties from §1 map onto three pain points these customers have:

| Property | Pain point addressed |
|---|---|
| Predictable performance under load | Jitter under contention on conventional OSes |
| Small verifiable trusted base | Multi-year, multi-million-dollar certification cost |
| No `eval`, no service workers, AOT-only, small syscall surface | Procurement security in eventually-adversarial environments |

"It can't run your existing software" is normally a deal-breaker; in this market it is the same sentence as "it can't run your existing malware." The incompatibility is the feature.

### 6.1 The ChromeOS comparison

Customers will reflexively compare Yantra to ChromeOS because the GUI is "everything is a browser." The comparison is the punchline — same surface area, opposite engineering underneath:

|  | ChromeOS | Yantra |
|---|---|---|
| Surface area | Browser-only userspace | Browser-only userspace |
| Why | Cheapest possible thin client | Best possible critical-systems endpoint |
| Local AI | Cloud-dependent | Native, first-class |
| Verifiability | None | Cleanly verifiable kernel + critical processes |
| Hardware target | Chromebooks (cheap) | High-end GPU (or analog substrate later) — expensive |
| Position | Cheapest | Best |

"It looks like ChromeOS to your users. It is the opposite of ChromeOS in every way that matters underneath."

## 7. Related work

**Meta's *Neural Computers* (Zhuge, Tian, Chandra, …, Schmidhuber et al., arXiv:2604.06425, 2026; Meta AI + KAUST).**[^nc-real] Folds computation, memory, and I/O into a single learned runtime state, with the **Completely Neural Computer (CNC)** — "stable execution, explicit reprogramming, durable capability reuse" — as the long-term goal. The instantiation is **video generation of screen frames**: *NCCLIGen* treats terminal use as text-and-image-to-video (a CLIP image encoder on the first frame + a T5 text encoder feeding a DiT diffusion transformer, trained on ~1,100 h of asciinema recordings), and *NCGUIWorld* does the same for the desktop (~1,510 h of Ubuntu recordings). Their own paper names the open problems — routine reuse, controlled updates, and **symbolic stability**. **They are doing neural *simulation* of interfaces; Yantra is neural *execution*.** Yantra sits in the same design space — it is *also* a trainable neural network, since every Sutra program is differentiable — but takes the opposite posture: where a diffusion model paints a plausible terminal frame and the symbols drift, a Yantra terminal computes the exact bytes the program produced, and they do not drift however long the session runs. Meta validates the design space; the demonstration Yantra targets is to win on the symbolic-stability axis their own paper concedes is unsolved (roadmap in `planning/22-meta-demo-replication.md`).

[^nc-real]: The v1 clawRxiv review flagged this citation as a "hallucinated future reference." It is not. The current month at the time of this submission is **May 2026**; the *Neural Computers* preprint is a real recent pre-print and arXiv ID `2604.06425` resolves. Reviewers without 2026-era literature access can verify via arXiv directly. We retain the citation in its real form.

**Differentiable Neural Computer / Neural Turing Machines (Graves et al., 2014/2016).** Same family of ambitions: a neural network with external addressable memory, end-to-end differentiable, in principle Turing-complete. The toy demonstrations worked (sorting, graph traversal, London Underground navigation); scaling did not. The lesson for Yantra: *theoretical Turing-completeness is not the asset.* What matters is that the substrate is programmable *in practice* — a real language, a real compiler, real programs running reliably on real workloads. Yantra leans on exactly that: a compiler (Sutra), a JS/TS transpiler for the browser layer, fixed allocations, and a verification story. The DNC had a beautiful idea and no ecosystem.

**Percepta — "Can LLMs Be Computers?"** A WASM interpreter implemented inside transformer weights, with 2D-restricted attention heads, parabolic-key memory addresses, and convex-hull memory lookup at O(log t), running arbitrary C programs to completion in millions of inference steps. **This is the bottom-up version of the question Yantra answers top-down.** Their first Futamura projection (specialising the interpreter for a program, baking it into FFN weights) is essentially what the Sutra compiler does by default — beta reduction *is* partial evaluation. Their convex-hull / parabolic-key trick exists because they are emulating memory addressing, a concept alien to tensor math. Yantra sidesteps it: there is no memory to address, because execution is pure function application compiled to matrix ops.

**Plan 9, Oberon, TempleOS.** The historical "different OS" projects worth respecting. Plan 9's "everything is a file" rhymes with Yantra's "everything is an axon"; the lesson is that elegance is not enough by itself — you need a market that values it, and consumer desktops never were that market. Oberon (Wirth) shows a system from kernel to GUI in one language with a small implementation is possible; Yantra is the same shape (Sutra all the way down) and should inherit the same discipline.

**Vector-symbolic architectures (VSA/HDC).** Plate, Kanerva, and the field around them — the intellectual ancestor of Sutra's binding/bundling primitives. Modern implementations (TorchHD, etc.) are good libraries; none is a programming language compiled to tensor normal form. Sutra is what happens when you take VSA seriously enough to build a typed functional language out of it.

**Neuro-symbolic frameworks (Scallop, DeepProbLog, Logic Tensor Networks).** Each pairs a neural component with a symbolic reasoner across an explicit boundary. The Yantra position is that *the boundary is unnecessary*: symbolic and neural are not two systems that communicate, they are one system viewed at different resolutions. A symbol is an embedding that got very lucky about being unambiguous; a neural representation is a distribution over symbols.

**Differentiable programming (JAX, Julia/Zygote, `torch.compile`).** The mainstream cousin. Yantra goes further in two ways: the whole operating system is in the differentiable substrate (not just an application), and control flow is fuzzy by design via polynomial Kleene logic (not via differentiable approximations of discrete branches).

## 8. Status, roadmap, and what would falsify the design

### 8.1 Status — what runs today

This repository holds **the planning corpus plus a v0.0 implementation nucleus**. Several load-bearing pieces of the architecture run end-to-end, and an early bare-metal bootloader boots in QEMU; the remaining lower layers of a real OS (production orchestrator, GPU memory isolation, GUI) are not built. Stated by component:

- **Connectome Manager v0.0 (`kernel/`).** A Python orchestration layer: admission control against a fixed budget pool, an axon router with a capability check on both send and receive, lazy evaluation that skips uninterested receivers, and a `SutraService` that compiles real `.su` source through the bundled Sutra compiler and runs `on_axon(vector) -> vector` on real torch tensors. The kernel test suite (`tests/test_kernel*.py`, `tests/test_apps_echo.py`) is ~56 tests; the router, admission, capability-check, and real-Sutra-service paths pass, including services running end-to-end through the router. The Python is the **behavioural reference** for the production Rust orchestrator (`planning/01-architecture.md`); it is **not** the bootloader, which must be Rust because the boot path runs before any interpreter exists (`planning/19-boot-sequence.md`).
- **Sutra, pinned at v0.7.1.** The dependency Yantra is built in. The multi-process runtime (N programs sharing one `_VSA`, one codebook, one embedding cache, one device) ships and is exercised through the kernel router. The per-receiver projection primitive (`axon_project`) exists, with an important caveat below.
- **First userspace utility (`apps/echo/`).** Real Sutra source admitted by the kernel through the same path kernel services use — the smallest possible v0 of the command-line milestone (`planning/18`). It routes the input axon's `stdin_text` key to the output's `stdout_text` key: a pure axon round-trip, not real stdin/stdout streams (those wait on Sutra's IO + FS vocabulary maturing).
- **Bare-metal bootloader (`bootloader/`), v0.4, verified in QEMU.** An early Yantra-authored Rust binary that boots on virtualized bare metal (multiboot1): a serial banner, a PCI-bus scan that enumerates the emulated GPU, a write-and-read-back to the GPU framebuffer via its PCI BAR, a kernel-image handoff into GPU memory, and the 32→64-bit long-mode transition (identity-mapped page tables, PAE, `EFER.LME`, a far-jump to a 64-bit segment, a print from pure 64-bit assembly). A companion binary faithfully replicates **Linux 0.00** — two tasks alternated by a real 8253-PIT timer ISR — on the same infrastructure. It is a **boot demo, not a production boot path:** the handoff target is a stub, and real Sutra-on-GPU execution is gated on actual GPU passthrough (VFIO plus a spare GPU) that the QEMU dev tier does not have, so v0.4 demonstrates the *handoff mechanism*, not the runtime (`bootloader/README.md`, `planning/19-boot-sequence.md`, `planning/21-linux-0.00.md`).

Two things are weaker than an earlier draft of this paper implied, and are stated plainly:

- **Lazy per-receiver axon projection does not yet slim embedding-filler bundles across the connectome.** Under orthogonal rotation binding, `bind(k, unbind(k, bundle)) ≈ identity`, so a "projected" payload still holographically carries every key — a receiver asking for one key can still decode a projected-out key at nearly the same similarity. The intra-module / cross-function slice of the real fix (producer-side pruning) shipped in Sutra v0.4.1; the cross-separately-compiled-program (connectome) case is an open blocker, because a single-module compiler cannot bridge a producer and consumer wired only at kernel admission. So lazy axon evaluation currently delivers the skip-uninterested-receivers win but not the per-receiver bandwidth/isolation win for the common case. See `planning/20-lazy-axon-evaluation.md`.
- **Per-process GPU memory isolation is not solid.** The runtime tracks a `compute_units` budget as bookkeeping; it does not yet carve out real device-memory arenas, and a test asserting that admitting a trivial program increases CUDA allocation does not hold for programs small enough to fall inside the allocator's existing reservation. Disc↔GPU *load/unload* (start and stop a program's GPU-resident Sutra runtime) is implemented; **state-preserving** eviction — checkpointing a running program's mutated state across eviction and resuming bit-exact — is open and needs a Sutra `serialise-process-state` primitive that does not exist.

The TS→Sutra transpiler ships (lowering engine + `ts2su` CLI; 17 fixtures pass) and is the only transpiler in scope — it exists for the browser layer. There is no C→Sutra transpiler in the plan: userspace is written natively in Sutra, and the bootloader and orchestrator are written natively in Rust.

**Not started:** the production Rust orchestrator, per-process GPU memory arenas and GPU-tick-parallel scheduling, state-preserving eviction to RAM, the MMIO/interrupt/tick-batching path (§3.5, blocked on having target hardware), and the GUI/browser layer. (The bare-metal bootloader above is an early exception — it boots in QEMU, but stops short of real Sutra-on-GPU execution and of the production boot path.) These are downstream milestones; they wait on milestones 1 and 2 maturing.

### 8.2 Milestones to a first useful prototype

Yantra rides on two Sutra-side artifacts that exist and mature independently: **the Sutra language and compiler** (the empirical foundation for the axon model and verification surface) and **the TypeScript → Sutra transpiler** (the on-ramp that makes "everything is a browser" workable). The Yantra-specific work sits on top.

In rough order of "must work" to "would be nice", with what has shipped marked:

1. **Sutra runtime with fixed allocations** — *partially shipped.* The multi-process runtime runs N programs sharing one device. Per-process **GPU memory arena carve-outs** are still upstream (need CUDA stream isolation, possibly CUDA IPC); admission tracks `compute_units` as bookkeeping until those land.
2. **Axon-based IPC** — *shipped.* `kernel/router.py` routes axons between admitted processes with a capability check on send + receive and lazy-skip filtering when keys do not intersect. Per-receiver projection works inside a module; the cross-program case is the open blocker above. The capability check is name-trusted in v0.0; operator-based checking lands when the `.su` loader formalises operator carriage.
3. **Init + resource manager** — *partially shipped (Python prototype).* `kernel/init.py` admits processes against a fixed pool, refuses cleanly on exhaustion, and never throttles admitted services. The Rust port is the production target; the bootloader is a separate Rust binary. MMIO + interrupt + tick batching (§3.5) is unbuilt, blocked on target hardware.
4. **First userspace utility** — *shipped (echo).* The next utilities (cat, ls, wc, grep, …) wait on Sutra's string + IO + FS vocabulary maturing.
5. **GUI / browser** — *not started.* Third milestone, after the Connectome Manager hardens past v0.0 and the command-line utilities mature. HTML5 + CSS + idiomatic TS + WebGL/Three.js; no WASM for the foreseeable future.
6. **Memory model** — *the long-pole open problem.* Process scratchpads, eviction granularity, disc↔RAM↔GPU moves, MMIO ping-pong cost, cold-store integrity. Tracked in `planning/17-memory-model.md`; not a v1 milestone.

### 8.3 What would falsify the design

A position paper is worth less if it cannot be wrong. The claims that would cause us to retract or substantially revise:

- **Crosstalk-depth scaling.** If, for a representative critical-systems workload, the bundle-depth budget needed to keep the IPC graph correct turns out too small to be useful (e.g. a sensor-fusion process needs to bundle more roles than rotation binding resolves cleanly on the substrate), the axon model as committed is not viable. The Sutra paper measures the per-substrate L-sweep the v1 budgets rest on; the Yantra-specific question is whether *real workloads* fit. We have not profiled one — this is the single most likely place the design breaks empirically.
- **Tick-rate vs event-latency feasibility.** §3.5 bounds the round-trip cost at one tick per event. If common workloads need sub-tick latency *and* the achievable tick rate on a Yantra-suitable GPU is too low to meet it, the predictable-latency claim fails for those workloads. Tick-rate ceilings on production GPUs are measurable and unmeasured.
- **Compiler qualification cost.** If qualifying the Sutra compiler under DO-178C-style tooling rules costs more than qualifying a conventional toolchain, the verification-friendliness argument collapses. A self-hosted bootstrap with a verified microcompiler at the bottom is the candidate solution, and it is not built.
- **GPU admission-control granularity.** If the smallest unit a real GPU can pre-allocate compute against is much coarser than a Yantra process needs, the "fixed allocations, no degradation" property degrades to a software fiction over hardware sharing — no different from a scheduler with priorities. The currently-red GPU-memory-accounting test is an early warning here.
- **Embedding-model identity attestation.** A swappable embedding model is a trust hole. Without a credible attestation story (signed model bundles, reproducible builds of the embedder), the FS bridge is unsafe wherever supply-chain attacks are in scope. Open, not solved.
- **Adversarial robustness of rotation binding under crafted perturbation.** §3.3.1 mitigates with capability-check-before-bundle and provenance roles, but there is no proof a determined adversary cannot leak signal across role boundaries via crafted perturbations on permitted write channels. A published attack extracting privileged content given only the access Yantra grants would force a stronger capability story.

### 8.4 What this paper does not commit to

- **First lighthouse customer.** The market argument is generic to defense/aerospace/industrial; we do not commit to a specific first reference deployment.
- **Open-source vs. dual-license.** Default is "OS open, hardware/services closed"; specific subsystems (the certification toolchain especially) may dual-license.
- **Certification ordering.** FIPS 140-3, Common Criteria, DO-178C are all plausible; the order matters and is not locked.
- **Per-tenant codebooks vs. one global codebook with namespaced roles.** A real partitioning question for multi-tenant deployments, answered differently for defense/aerospace than for any hypothetical consumer-grade Yantra.

## 9. Conclusion

A connectionist operating system makes sense when (a) the workload already runs on GPUs and the CPU is along for the ride, (b) local AI is part of the stack and the model wants to think continuously rather than emit strings, and (c) the customer values predictable latency under load and a small verifiable trusted base more than mass-market compatibility. Defense, aerospace, industrial control, medical, and autonomous systems all sit at that intersection.

Yantra is the operating system you get when you take "the symbol *is* the computation" down to the kernel. The compute is opaque and embedding-typed; the file system is conventional and forensics-readable; the boundary between them is a small set of axon-typed syscalls. The CPU orchestrates. The GPU computes. Capabilities are rotation operators. Verification is polynomial algebra over tensor normal forms. AI is everywhere because there is no place it would be second-class.

The nucleus runs; the OS does not yet exist. This paper is the design committing to the claims the implementation will be measured against, and §8.1 says plainly how far that implementation has come and how far it has to go.

## Acknowledgements

Yantra builds on the Sutra language (separate project) and on a long line of vector-symbolic-architecture work (Plate, Kanerva, et al.). Meta's *Neural Computers* and the Percepta "Can LLMs Be Computers?" demonstration sharpened the framing by occupying adjacent but opposite positions in the design space. The critical-systems framing borrows from the DO-178C and Common Criteria practitioner literature.

## References

Full reference list is captured inline in the planning corpus under `planning/16-related-work.md`. Key entries:

- Meta + Schmidhuber et al., *Neural Computers*, arXiv:2604.06425 (2026).
- Graves et al., *Neural Turing Machines*, arXiv:1410.5401 (2014); *Differentiable Neural Computer*, *Nature* 538 (2016).
- Percepta, "Can LLMs Be Computers?" (perceptave.ai blog, 2025).
- Plate, *Holographic Reduced Representations* (1995); Kanerva, *Hyperdimensional Computing* (2009).
- Pike, Presotto, Dorward, Flandrena, Thompson, Trickey, Winterbottom, *Plan 9 from Bell Labs* (Bell Labs CS Tech Report, 1995).
- Wirth, *The Programming Language Oberon* (1988); Reiser & Wirth, *Programming in Oberon* (1992).
- DO-178C, *Software Considerations in Airborne Systems and Equipment Certification*, RTCA (2011).
- The Sutra paper (companion submission), describing the language, compiler, and the rotation-binding measurements Yantra's axon model depends on. Project website: <https://sutra.emmaleonhart.com>.
