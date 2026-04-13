# Entity resolution in LLM embeddings for RAG

**Human:**

I think that LLMs really should basically have entity resolution points built into their embedding models, or at least made public, because RAG pipelines always have to rely on worse embedding models and it is crazy, and you can have different coordinates from the value of a token so (river)bank and (financial )bank would often end up in different coordinates.

**Claude:**

This is a genuinely interesting point, and you're touching on a real tension in how LLMs and RAG systems are currently architected. Let me push back a little and also extend your idea.

**Where you're right**

The core observation is solid: frontier LLMs develop rich, context-sensitive representations internally — the classic polysemy example you give (river bank vs. financial bank) is well-documented. Models like BERT famously demonstrated that contextual embeddings resolve this: the same token gets different vector coordinates depending on surrounding context. Frontier LLMs do this far better than dedicated embedding models, which are typically smaller, older, or trained on less data.

The mismatch is real: you retrieve documents using a weaker model, then process them with a stronger one that would have represented the query differently. The retrieval step is the bottleneck, and you're encoding at a lower fidelity than you're reasoning at.

**Where it gets complicated**

A few wrinkles worth considering:

- **Dimensionality and exposure**: Frontier LLM internal representations are often thousands of dimensions, spread across layers, and not obviously a single "embedding" — it's more like a trajectory through representation space across layers. Which layer's activations do you expose? The last? Middle? A learned aggregate?
- **Training objective mismatch**: LLMs are trained to predict next tokens, not to produce retrieval-friendly embeddings. The geometry of their internal space isn't necessarily optimized for nearest-neighbor search the way contrastive/bi-encoder models are. You'd likely need fine-tuning anyway.
- **Computational cost**: Using a frontier model as your encoder means running it at retrieval time over your entire corpus. Dedicated embedding models are cheap precisely because they're small.
- **Entity resolution specifically**: What you're describing for entities is essentially asking for the model's internal coreference/disambiguation signal to be surfaced. That's a really interesting ask — it's less "give me an embedding" and more "give me a canonical entity ID or cluster coordinate." That's closer to what knowledge graphs try to do, and combining LLM representations with KG-style entity linking is an active research area.

**The more radical version of your idea**

You could argue that the right architecture is something like: frontier models should expose a **canonicalization endpoint** — given a span of text in context, return a stable identifier or coordinate for the resolved entity, not just a raw embedding. That would be more useful than raw internals for exactly the bank/bank disambiguation problem you describe. It would also be more auditable.

The practical reason this hasn't happened is partly commercial (embeddings-as-a-service is a product line) and partly that the research on what "canonical" means inside these models is still unsettled.

It's a legitimate architectural critique of the current RAG stack.

**Human:**

I think a big thing is that you need to  have this actually operating actively as a part of the process. Not repeating anything and doing the RAG in one swoop basically

**Claude:**

Yes — you're describing something more like a **unified inference-time process** rather than the current two-stage pipeline (retrieve, then read). The distinction matters a lot.

The current RAG architecture is fundamentally a hand-off: a dumb retrieval step throws documents over the wall to a smart reasoning step, and those two never talk to each other. The retrieval is frozen at query time — it doesn't know what the model is going to do with the results, and the model can't influence what gets retrieved mid-reasoning.

What you're pointing at is more like **active retrieval as part of the forward pass** — where the model's evolving internal state at inference time is itself the query signal. So as the model is building its representation of what you're asking, that representation is simultaneously driving what gets pulled in, which updates the representation, and so on. The retrieval and reasoning are the same process, not sequential stages.

This connects to a few threads:

- **Memorizing vs. retrieving**: Right now the line between what's in weights vs. what's in a retrieval corpus is hard and architectural. A more fluid system would blur that — the model's parametric knowledge and external knowledge would be accessed through the same mechanism.
- **Iterative/chain retrieval** approaches (like FLARE or some agentic RAG setups) gesture at this but still discretize it into steps. What you're describing is more continuous.
- **Attention over a dynamic context** is sort of already this, but the corpus has to be pre-loaded. The missing piece is making the corpus itself dynamic and responsive to the model's internal state in real time.

The entity resolution point from before fits here too — if the model is actively resolving "bank (financial)" mid-reasoning, that resolved representation should be what's querying the index, not the raw token. The disambiguation happens before retrieval, inside the same process.

The hard engineering problem is that nearest-neighbor search over a large corpus isn't differentiable in a way that's easy to integrate into a forward pass. There's been work on this (REALM, RAG-token model, some memory-augmented transformer architectures) but it's genuinely difficult to make efficient. The two-stage pipeline exists partly because it's the tractable approximation.

But you're right that it's an approximation of the wrong thing.
