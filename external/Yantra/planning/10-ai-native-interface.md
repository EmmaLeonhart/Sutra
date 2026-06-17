# AI-native interface

## The interface that doesn't exist

On a conventional system, AI integration goes through a translation
layer:

```
model thought → text → parse → execute → output → re-embed → model thought
```

Tool use, MCP, function calling, agent scaffolding — these are all
plumbing around the same fact: the model thinks in vectors but the OS
speaks in bytes. Every loop iteration through that plumbing is an
opportunity to drop information, mistranslate intent, hallucinate a
response, or stall.

Yantra removes the loop:

```
model activation → Sutra program → tensor output → directly consumable
```

There is no API surface called "the AI API". There is just the OS,
where every process already takes an axon and returns an axon. A model
that wants to operate the system does not call `read_file("foo")`; it
reads the same syscall axon any other process reads, because the
syscall result is already the same shape as the model's activations.

## What this means in practice

Three concrete consequences:

### Perception is a process

A JEPA-style joint-embedding predictive model running on Yantra emits
its predicted latents as axons. The application that consumes those
latents is *not* "the AI" — it is just a process whose input role is a
JEPA latent. The application can be a Sutra program written by hand, a
transpiled JS dashboard, or another model. They all see the same shape.

This is the part that makes Yantra closer to "embodied cognition" than
to "AI with computer access". Perception, memory, reasoning, and action
are all first-class operations on the same representation. There is no
hard boundary between "sensing" and "thinking" — there is no place to
draw one.

### Local AI is everywhere by default

Every process can read and emit axons, so every process can integrate a
local model trivially:

- A file manager that wants to do semantic search asks the FS bridge
  for files in `semantic` mode and runs cosine similarity.
- A terminal that wants to suggest commands runs a small local model
  over the shell history axons.
- A monitoring dashboard that wants to flag anomalies runs an
  embedding-distance check against a baseline.

None of these need a special "AI API". They just consume axons.

### The model is not "using" a computer

A model running on Yantra is not bolted on top of a computer issuing
string commands. The model's outputs *are* axons that can be routed
directly to the input role of any process that accepts that role. The
model's inputs *are* axons coming from other processes. There is no
text serialization layer between the model and the rest of the system.

This is what was meant by "should have been called an agent". The word
"agent" got claimed by something narrow — a model with tool-use
scaffolding around it. What Yantra makes possible is the broader thing
agents were originally trying to be: a mind whose cognition and action
happen in the same operation.

## The alignment pacemaker

A specific application of the AI-native interface that drives some of
the design.

The idea: misalignment in a model is rarely a values problem. More often
it is a representational misfiring — a circuit that does something
useful in most contexts firing inappropriately in another context. The
right intervention is not to delete the circuit (it is load-bearing)
but to insert a corrective structure that catches the misfire and
steers around it. Like a cardiac pacemaker for the model's
representations.

On Yantra, the pacemaker is just another Sutra program:

- Sparse-autoencoder-derived neurons identify the misfiring circuit.
- A Sutra program is compiled that monitors the circuit's activations
  in axon space and applies a corrective rotation when the misfiring
  signature appears.
- The pacemaker process runs as a normal Yantra process, with normal
  capability discipline, in the same tensor space the model itself
  runs in.

This is not vapourware — it is one of the active research threads
feeding into the OS design. The OS has to make this pattern
*ordinary*: launching a pacemaker should look like any other process
launch, the pacemaker should be capable of inspecting the model's
axons via well-defined capabilities, and the corrective action should
flow through standard IPC.

The same template applies to non-AI systems. The pattern "find the
misfiring circuit, insert a corrective structure, preserve the
underlying function" works whether the substrate is a transformer, a
fly connectome, or a hardware spiking neural network. Yantra's job is
to make the template a first-class citizen of the OS.

## What is "the AI" on a Yantra box?

There is no single thing that is "the AI". There is:

- An embedding model the FS bridge uses for semantic-mode reads.
- One or more local LLMs that long-running processes invoke as needed.
- Application-specific perception models (JEPA-style world models for
  autonomous systems, vision models for camera input, etc.).
- Optionally an alignment pacemaker watching whichever of the above is
  most prone to misfiring.

All of them are processes. They all have manifests, capabilities, and
fixed allocations. The OS treats them like every other process.

## Why this matters for the broader pitch

Two angles people keep asking about:

**"Yantra is the OS for AI workloads."** Yes, in the sense that local
AI integrates seamlessly. Also yes, in the sense that an AI agent
running on Yantra has continuity between thought and action that no
agent running on Linux can have. The translation layer is gone; what
remains is closer to a cognitive substrate.

**"Yantra is the OS that AI runs."** Eventually, yes. A model that can
emit Sutra programs (or compile them from its outputs) can author new
processes on its own behalf. Capability discipline still applies —
processes the model creates inherit only the capabilities the user
granted to the model — so this is not an unbounded new attack surface,
just the natural extension of the substrate.

## Open questions

- **Embedding-model versioning.** When the system embedding model
  changes, every cached `semantic` representation in the FS rots. We
  need a defensible "regenerate on demand" plus "hold old caches until
  fully migrated" story.
- **Cross-process activation steering.** The pacemaker needs to read
  another process's internal activations. That is a delegated
  capability with privacy and isolation implications even within a
  single user's box. The right default is conservative.
- **Non-AI processes as AI input.** Sometimes the model wants to
  consume the output of an arbitrary process (a sensor reading, a file
  metadata query). The axon model handles this trivially — but there
  may be a usability layer where the model can *introspect* the
  available axon channels to decide which to subscribe to. That
  borders on reflective programming and needs a careful design.
