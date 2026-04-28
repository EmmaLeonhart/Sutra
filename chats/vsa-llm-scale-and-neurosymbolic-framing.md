# LLM scale, OpenAI-as-host, neurosymbolic positioning

_Excerpt from the original `chats/vsa-programming-languages.md` (lines 519-646). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

If you are doing this with GPT-4 you are literally OpenAI with a massive fucking server.


**Claude:**

Ha, fair point. You're not building this for closed frontier models where you can't even access the embedding space directly anyway.

**The realistic targets are:**

- Local open-weight models -- Llama, Mistral, Phi, Gemma etc.

- Where you have full access to the embedding space

- Where you can actually run the initiation probes

- Where the matrix sizes are manageable -- smaller models have embedding dims in the hundreds to low thousands

**Which actually works better for your use case anyway**

- You control the whole stack

- Initiation can run on the same hardware as inference

- The mapping file is a reasonable size

- You can iterate fast without API costs or rate limits

**The matrix size becomes very tractable**

Something like Llama 3 8B has embedding dim ~4096. A dense transformation matrix is 4096² which is ~67M floats -- about 256MB at float32. Not trivial but totally manageable locally. Smaller models like Phi-3 mini at 3072 dim are even more reasonable.

**This also clarifies the target user**

Someone running local models, probably for research or experimental AI work, who understands VSA conceptually and wants to use this as a genuine inference substrate rather than prompt engineering. That's a pretty well defined audience.

What's your target model size range -- are we talking 3B-13B class, or are you open to larger local models like 70B?


**Human:**

If OpenAI wants to hire me, go for it and I will implement this on their embeddings.


**Claude:**

Lmao fair enough. Leave the door open.

But practically speaking, starting with local models is actually the **better research story** anyway:

- You can publish the initiation methodology openly

- Anyone can reproduce it on their own hardware

- The mapping file approach means if OpenAI *does* come knocking, the architecture already scales -- you just need their compute and embedding access to run initiation

**The way this plays out realistically:**

- Build and validate on small-to-mid local models (7B-13B range)

- Show it works statistically -- programs produce coherent outputs

- That's your proof of concept and your paper/portfolio

- Scaling to larger models or proprietary embeddings is just an engineering problem at that point, the hard intellectual work is already done

**The thing that makes this publishable and hireable**

Nobody has done the empirical initiation approach -- characterizing an arbitrary embedding space as a VSA via fitted matrices and building a compiler on top of that mapping. That's the novel contribution. The language itself is interesting but that pipeline is the thing that's genuinely new.

**Honest question though** -- where are you at right now in terms of:

- Is this still in the design/ideation phase

- Have you started prototyping anything

- What's your background, are you coming at this from the PL side, the ML side, or both?


**Human:**

I mean this is intended as probabilistic symbol manipulation within a neurosymbolic system


**Claude:**

Oh that clarifies the entire purpose beautifully. So this isn't trying to replace conventional computation -- it's filling a very specific gap in neurosymbolic systems:

**The gap it fills**

Neurosymbolic systems currently have an awkward interface between:

- The neural side -- continuous, distributed, probabilistic

- The symbolic side -- discrete, local, deterministic

Your language lives **at that interface** -- it's symbolic enough to express structured reasoning, but probabilistic and distributed enough to stay in the neural substrate. No lossy conversion between the two worlds.

**"Probabilistic symbol manipulation" is the key phrase**

This means:

- Symbols aren't crisp -- they're vectors with similarity neighborhoods

- Manipulation isn't deterministic -- it's statistically reliable within bounds

- The output of a "program" isn't a value -- it's a distribution over the embedding space

- Correctness is always approximate, which is fine and expected

**This reframes what the language actually is**

It's not really a programming language in the Turing-complete general sense as the primary goal -- it's a **structured reasoning layer** for neurosymbolic systems that:

- Takes symbolic structure as input

- Manipulates it probabilistically in embedding space

- Returns symbols or structures the neural system can consume directly

**Which means the compiler's real job is**

Translating structured symbolic expressions into sequences of embedding space operations that a neural system can execute without ever leaving vector space.

Is the intended runtime a standalone inference pass, or is this meant to run interleaved with normal neural network forward passes?


