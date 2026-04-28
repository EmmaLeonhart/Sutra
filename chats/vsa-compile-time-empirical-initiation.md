# Compile-time empirical initiation — mapping file, matrices, lookup tables

_Excerpt from the original `chats/vsa-programming-languages.md` (lines 417-518). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

compiler needs to do an empirical initiation for the embedding space. This forms a mapping file for all operations. After that then all functions can be compiled with it into raw VSA functions.


**Claude:**

That's a really elegant two-phase architecture. So the compiler pipeline is:

**Phase 1 -- Empirical Initiation**

- Probe the target LLM's embedding space

- Run statistical experiments to discover how addition and multiplication actually behave in *this specific model's* geometry

- Find the effective binding/bundling operations that preserve structure reliably

- Output a **mapping file** -- essentially a characterization of this model's VSA properties

**Phase 2 -- Compilation**

- Take that mapping file as a backend target

- Compile language constructs down to raw VSA operations calibrated to *this specific model*

- The mapping file is basically what makes the compiler model-specific, like how a C compiler has different backends for x86 vs ARM

**What this means architecturally**

The mapping file is doing something really important -- it's the bridge between:

- The idealized VSA algebra the language assumes

- The messy empirical reality of a specific embedding space

So the same source program could compile differently for GPT-4 vs Llama vs Mistral, because each has a different mapping file. The language is model-agnostic, the compiled output is model-specific.

**The hard part of Phase 1**

What operations do you actually probe for? Candidates:

- Similarity preservation under addition

- Binding invertibility under multiplication

- Capacity -- how many things can be bundled before retrieval degrades

- Whether permutation/rotation reliably encodes order

Have you thought about what the mapping file format looks like -- is it numerical parameters, lookup tables, learned transformations, or something else?


**Human:**

pretty much all matrices with a lookup table


**Claude:**

That makes a lot of sense. So the mapping file is essentially:

**Matrices** for the continuous transformations:

- How to perform binding in this embedding space

- How to perform bundling

- Projection matrices for cleanup/normalization after operations

- Possibly learned correction matrices for when operations drift

**Lookup tables** for the discrete parts:

- Atomic symbol vectors -- the codebook

- Named operation results that are too irregular to capture with a matrix

- Possibly precomputed common compositions

**This is essentially a learned VSA adapter layer**

The initiation phase is discovering the matrices that make this embedding space *behave like* a well-formed VSA, even if it wasn't designed as one. That's a really clever way to handle the messiness of real embedding spaces.

**The initiation process itself then looks something like:**

- Sample vectors from the embedding space

- Run bind/bundle operations and measure their properties

- Fit matrices that best approximate clean VSA behavior

- Validate statistically that the fitted matrices actually work

- Serialize everything to the mapping file

**One practical concern**

The matrices could get large depending on embedding dimensionality -- GPT-4 class models have embedding dims in the thousands. A full transformation matrix at that scale is dimension² parameters.

Are you thinking of these as dense matrices, or are there sparsity constraints to keep the mapping file tractable? And is the initiation phase a one-time offline process per model, or does it need to be re-run periodically?


