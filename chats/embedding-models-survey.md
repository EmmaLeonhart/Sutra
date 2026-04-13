# Embedding models for vector databases


**Human:**

Most common embedding model for vector databases


**Claude:**

**text-embedding-ada-002** was the dominant standard for a long time, but as of 2025 - 2026 the landscape has shifted:

**Most widely used today:**

- **OpenAI text-embedding-3-small / 3-large** -- replaced ada-002 as OpenAI's default; 3-small is extremely popular for cost/performance ratio

- **Cohere embed-v3** -- strong choice for multilingual and retrieval-specific tasks

**Popular open/self-hosted options:**

- **nomic-embed-text** -- very common in local/OSS stacks (Ollama, etc.)

- **BGE models** (BAAI/bge-large-en-v1.5, bge-m3) -- frequent default in LangChain/LlamaIndex examples

- **all-MiniLM-L6-v2** -- lightweight, ubiquitous in sentence-transformers tutorials

**For production RAG pipelines**, text-embedding-3-small or a BGE model tends to be the pragmatic default right now. The 3-small model hits a sweet spot of ~1536 dimensions, low cost, and solid MTEB scores.

**Dimension note:** Most production deployments cluster around 768 - 1536 dimensions -- enough expressiveness without bloating storage/HNSW graph size.

Is there a specific use case or database (SutraDB, Pinecone, Weka, etc.) you're choosing for?


**Human:**

mxbai is that one used


**Claude:**

Yes! **mxbai-embed-large-v1** (by MixedBread AI) is genuinely popular, especially in the local/OSS stack. It punches well above its weight on MTEB benchmarks -- it was beating text-embedding-3-large on some retrieval tasks when it dropped, which caused a lot of buzz.

Common places you'll see it:

- **Ollama** -- it's one of the featured embedding models, so it gets a lot of default usage

- **AnythingLLM, Open WebUI** -- popular picks in those UIs

- **Self-hosted RAG pipelines** where people want a strong open model without API costs

1024 dimensions, Apache 2.0 license, good retrieval performance. It's a solid choice. Not as universally dominant as BGE or MiniLM in terms of raw usage share, but well-regarded in the local-first AI community.

Were you considering it for SutraDB's default embedding recommendation, or just curious?


**Human:**

No, i found a major error with mxbai large. And im not sure how many people it affects. Extreme collision with diacritics


**Claude:**

That's a significant find. What's the collision behavior -- are diacritic variants hashing to nearly identical vectors (cosine similarity ~1.0), or collapsing to the exact same embedding?


**Human:**

Entire extremely different words are colliding. This is like a SolidGoldMagikarp situation


**Claude:**

That's serious. SolidGoldMagikarp-level means it's likely a tokenizer artifact -- words with diacritics probably hitting an OOV or underrepresented token that maps to some degenerate region of the embedding space, causing unrelated words to cluster there.

A few questions to scope the blast radius:

- Is it specific diacritics (e.g. ą, ę, ñ, ü) or broad across any non-ASCII?

- Are the colliding words semantically unrelated but diacritic-bearing, or is it mixing diacritic and non-diacritic forms?

- What's the similarity score -- are we talking 0.97+ or literally identical vectors?

This would disproportionately affect **multilingual content** -- Romance languages, Slavic languages, Vietnamese, anything with heavy diacritic use. If mxbai-embed-large is someone's default in a multilingual RAG pipeline, their retrieval is silently broken for a whole class of queries and they'd never know without specifically testing it.

Have you reported it upstream to MixedBread? This seems like something worth a GitHub issue or even a public write-up -- the embedding community would want to know.


**Human:**

mxbai embed large seemingly has ō and a variety of other diacritics not only not show up properly, but it appears they completely consume the attention of the model so even long strings are eaten up. I’m guessing it has a really weird value in its key too


**Claude:**

Yeah that tracks perfectly. The pathological token pattern from SolidGoldMagikarp -- the token has a bizarre key/query value that dominates the attention computation, so everything else in the sequence gets drowned out. The residual stream after that attention head is essentially just "ō-token" regardless of what surrounds it.

The mechanism is probably:

- ō (and similar) got very few training examples, so its embedding is poorly initialized and never corrected

- Its key vector happens to land in a high-magnitude region that scores anomalously high attention weights

- Everything else in the sequence attends to it and gets overwritten, OR it absorbs all attention to itself and the other tokens can't communicate

The result being that `"The quick brown fox"` and `"Completely unrelated sentence"` produce nearly identical embeddings if both contain ō -- because the output is dominated by that one token's pathological representation.

**Practical blast radius for mxbai specifically:**

- Japanese romanization (Tōkyō, Ōsaka)

- Maori, Polynesian languages (heavy macron use)

- Academic/linguistic text with IPA or long vowel notation

- Medieval/classical text transcriptions

This is actually *worse* than a simple OOV collapse because it's not silent -- the model still produces a confident-looking embedding with normal magnitude, so nothing in your pipeline signals that retrieval is broken.

Worth documenting carefully before you publish. Do you have reproducible test vectors?


**Human:**

Yes I have reproducible test vectors. I was trying to find the glitch tokens in order to I was trying to find glitch tokens in order to was trying to find glitch tokens in order to support a model that in order to support a theory that I have a why glitch tokens worked the way they did? Again, I was writing a scientific paper Glitch tokens when I found this, and I just realized that it was utterly massive and I thought it was a I thought that it was a glitch in my software, that I had, like, thousands of collisions I thought there was a glitch in my software because I would have thought that the only glitch token of Would have thought that even if I found a glitch token, the glitch token would have only maybe been, like, one thing. Not something that consumes the attention,


**Claude:**

Right -- your prior was reasonable: a glitch token should produce *one* weird degenerate embedding, maybe cause *one* collision. What you're seeing is categorically different because ō and its family aren't just degenerate -- they're **attention sinks**. The pathology isn't "this token has a bad embedding," it's "this token hijacks the entire forward pass," which means the blast radius scales with *how common the character is in your corpus* rather than being a localized anomaly.

So instead of finding one SolidGoldMagikarp, you found a whole class of tokens that share the same failure mode -- which is actually the more interesting theoretical result. The original SGM paper was essentially "look at this weird thing," but what you're describing points toward a *mechanism*: something about how underrepresented diacritic tokens get initialized or trained produces systematically high-magnitude key vectors, and that might be a general property of this class rather than a one-off.

That's a stronger paper than what you started writing.

The reproducible test vectors are critical -- you can probably show:

- Cosine similarity matrix across your colliding strings (visually damning)

- Similarity degrades as a function of ō-token presence/density

- Non-mxbai models don't exhibit this on the same strings

Do you have a theory yet on *why* this specific character class produces the high-magnitude keys? Tokenizer boundary artifacts, pre-training data distribution, or something in the architecture itself?


**Human:**

Yeah. No. No. I already I already did it. I already again, I was I I ran my my search for glitch tokens, search for I I ran my my vector, my vector mapping software. On Okay. And only MXB AI models actually do any of this. So I'm guessing that it is some kind of something it is something fundamental to them. I think it's because it's it's, it's something fundamental to them. I'm worried it's like it gets turned into an unrolled or something like that. But it's even then, like, even if it can't process the characters, it doesn't just, like, do a it it doesn't just, like, silent, like, fail. Like, completely destroys whatever query that you're using. I don't know why is I so I think it's related to the I think it's related to the architecture itself. You know, with the width. I guess, related to the architecture itself, but I'm not really entirely sure.


**Claude:**

Yeah, the fact that it's **mxbai-specific** and not reproducible on other models is the key signal -- this isn't a general embedding model problem, it's something in their training pipeline or architecture specifically.

The "unrolled token" hypothesis is interesting. If ō gets split or handled in a way that produces an anomalous byte-fallback token, and that token's key vector is high-magnitude due to poor training signal, that would explain why it doesn't silently fail -- it *actively corrupts* rather than just producing noise. Silent failure would be "I don't know this token, here's a zero vector." What you're describing is more like the token has a *confident but wrong* representation that bullies everything else.

The architecture width angle is worth pursuing too -- wider models sometimes have more capacity for these pathological attractors to form and persist because there's less gradient pressure to correct them. A narrow model might accidentally regularize them out.

What other models did you test against? Just curious what your baseline comparison set looks like -- if it's clean across OpenAI, nomic, BGE etc. then you can make a strong "mxbai-specific" claim with confidence.

And practically -- you now have two papers or one paper with two parts: the glitch token theory you were originally writing, and this as a concrete real-world instantiation of the mechanism in a widely-deployed production model. The mxbai finding *is* your empirical evidence for the theory.


**Human:**

Yeah. I tested against I tested against all those ones. It's just MXB AI.


**Claude:**

That's a clean result then. Isolated to mxbai, reproducible, with test vectors -- that's publishable as-is.

The structure basically writes itself:

- **Theory** -- why glitch tokens work the way they do, attention sink mechanism, high-magnitude key hypothesis

- **Predicted consequence** -- if the theory is correct, you'd expect to find models where this manifests as corpus-wide retrieval corruption, not just isolated weird outputs

- **mxbai as the empirical case** -- here's exactly that, at scale, isolated to one model family, with vectors

The mxbai finding upgrades your paper from "here's an interesting theory about a known phenomenon" to "here's a theory with predictive power, and here's the prediction coming true in production."

You should probably disclose to MixedBread before you publish though. Both for ethics and because their response (or non-response) is itself informative -- if they confirm it's architectural that strengthens your mechanism claim.

Do you have a venue in mind? This feels like it could get traction beyond just an academic paper -- the embedding community would pick this up fast given how many people are running mxbai in production right now via Ollama.
