# Entity Resolution and Active Retrieval

## The Fidelity Mismatch Problem

Current RAG (Retrieval-Augmented Generation) pipelines have a fundamental architectural flaw: frontier LLMs have rich contextual embeddings that resolve polysemy (river bank vs. financial bank), but the retrieval step uses a separate, weaker embedding model. The retrieval model doesn't have the context that the generation model has. This is a **fidelity mismatch** — the dumb retriever fetches documents for the smart generator, but the retriever doesn't understand the query the way the generator does.

Example: The LLM, mid-reasoning about financial regulations, has internally resolved "bank" to mean "financial institution." But the retrieval embedding model, seeing "bank" in isolation, returns documents about river banks, blood banks, and actual banks with roughly equal relevance. The LLM then has to re-disambiguate from the retrieved context, wasting capacity and risking confusion.

## The Canonicalization Endpoint

Proposed solution: LLMs should expose a **canonicalization endpoint**. Given a span of text in context, return a stable identifier or coordinate for the resolved entity — not just a raw embedding.

```
canonicalize("bank", context="The Federal Reserve regulates banks...")
-> Q22687 (Wikidata: "bank" as financial institution)
   or: a stable vector in a canonical entity space
```

This would be more useful than raw internal embeddings because:
- It's **auditable** — you can check what the model thinks "bank" means
- It's **stable** — the same entity in different phrasings maps to the same ID
- It's **interoperable** — different models can agree on entity identity via shared identifiers

## Active Retrieval During Inference

The deeper proposal: retrieval shouldn't be a separate preprocessing step. The model's **evolving internal state during inference** should drive retrieval in real time.

Instead of: `embed query -> retrieve docs -> feed to LLM -> generate`

It should be: `LLM starts reasoning -> internal state drives retrieval -> retrieved context updates internal state -> reasoning continues with new context -> more retrieval if needed -> ...`

The disambiguation happens **before retrieval, inside the same process**. The model's mid-reasoning representation of "bank" (already resolved to financial institution by context) is what queries the index. The retrieval system sees the resolved representation, not the ambiguous surface form.

This is architecturally hard because nearest-neighbor search over a large corpus isn't differentiable in a way that's easy to integrate into a forward pass. Existing work (REALM, RAG-token model, memory-augmented transformers) tackles this but it's genuinely difficult to make efficient. The two-stage pipeline exists partly because it's the tractable approximation.

## How This Maps to Sutra

Entity resolution is a **core Sutra operation**, not a library function. In embedding space, the same surface form maps to different vectors depending on context. Sutra must handle this natively.

The MCP server architecture is Sutra's version of active retrieval during inference:
- The MCP server holds **semantic context** that the Sutra runtime uses to resolve ambiguous references
- Resolution happens in real time during computation, not as a preprocessing step
- The server maintains a **running model of what entities are in scope** and what they resolve to in the current context
- This is why the MCP server is part of the runtime, not an add-on — without it, entity resolution would require leaving vector space to do symbolic lookup

The canonicalization endpoint concept maps to a potential Sutra built-in:

```
resolved = canonicalize(ambiguous_vector, context_vector)
```

This would be a vector-graph operation (it requires ANN lookup against an entity codebook, informed by context) but a very commonly needed one — more common than cone traversal or graph hop.
