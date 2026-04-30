# Karpathy "LLM wiki" — exploratory research

**Status:** parked pending research. Not scheduled. The user has flagged this as interesting in the context-management sense but does not yet know the details well enough to scope work against it.

## What we think it is (from the user's description, 2026-04-13)

Andrej Karpathy has floated (on Twitter / blog / talk — unclear which, needs verification) a concept along the lines of an **"LLM wiki"** — a context-management artifact that persistently holds the context an LLM needs across interactions, rather than reconstructing it per conversation or per session. The user describes the core idea as **"a context management tool thing,"** and is specifically interested in it because Sutra already treats context management as a first-class language concern (see `CLAUDE.md`: *"The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional."*).

We do not yet have a verified source. Before committing any work, we need to:

1. Find the actual Karpathy artifact — is it a tweet, a blog post, a talk, a repo, all of the above?
2. Identify whether anything concrete exists (a repo, a protocol, a spec) or whether it is still at the "concept floated" stage.
3. Read whatever is there and summarize the primitives — what does an "LLM wiki" store, how does it get updated, how does an LLM query it.

## Why the user thinks this might matter for Sutra

Sutra's existing design commits to context-management-as-infrastructure:

- **MCP server is a core part of the language runtime, not an add-on** (`CLAUDE.md`). The tooling becomes part of the runtime because long-range dependencies in the fuzzy-vector semantics cannot be captured in a single file.
- **S1/Sutra dual runtime.** S1 is the fast cached layer; Sutra is the deliberate semantic layer. This is already the shape of a "persistent context store + deliberate execution over it."
- **`queue.md` protocol.** The `Queued work` section + "read queue.md every session" rule is a lo-fi version of the same idea — the session's context persists in a file that the next session is required to read before acting.

If Karpathy's framing has a clean formalization of what an "LLM wiki" stores and how it's queried, it could either (a) give Sutra's MCP layer a better protocol to speak, (b) suggest that queue.md should be structured as something more wiki-shaped and less narrative-shaped, or (c) turn out to be orthogonal and we learn nothing. All three are fine outcomes of the research step.

## Research questions (to be answered before any implementation)

1. **Where is the actual artifact?** Twitter URL, blog post URL, talk recording, repo — whichever exists. Needs web search.
2. **What is the storage model?** Plaintext, structured (JSON / YAML), graph, vectors? Append-only or editable? Versioned?
3. **What is the query model?** Full-text, embedding similarity, structured query, LLM-generated query-on-query? Does the wiki index itself?
4. **What is the update model?** Human-curated, LLM-curated, hybrid? Is there a review step, a trust model, a conflict resolution story?
5. **How does it compose with tool use?** Is the wiki accessed via a tool the LLM calls, via injection into the system prompt, via RAG, via something else?
6. **Has anyone built on it?** Are there implementations, blog posts from users, repos attempting the concept?
7. **What does it *not* do?** The most useful summary often comes from the things Karpathy explicitly calls out of scope.

## Relevance-to-Sutra questions (only meaningful after the above)

1. Does Sutra's MCP-as-runtime design fit any of the storage or query models? Mapping MCP to the Karpathy framing would tell us whether we already have this or not.
2. Does `queue.md`-as-persistent-context count as a degenerate LLM wiki? If yes, is there a cheap upgrade path that gets the benefits without building something new?
3. Is the "LLM wiki" concept substrate-agnostic (works with any LLM) or does it assume a specific LLM architecture? Sutra assumes embedding-space-as-substrate, which is a stronger claim — does the wiki concept conflict or compose?
4. Is there anything in the wiki concept that would change Sutra's language-level design (new operations, new types, new syntactic form), or is it purely at the tooling / runtime layer? If purely runtime, it does not touch `planning/sutra-spec/` — that's useful to know early.

## What "doing this work" would look like

Not scheduled. When it comes back:

1. Web research step: find the artifact, read it, write a one-page summary of what it is and isn't. Commit the summary to this directory. This is the whole first milestone — do not skip to implementation.
2. Delta analysis: compare the wiki concept to Sutra's MCP-as-runtime, `queue.md`, and the S1/Sutra dual runtime. Commit the delta analysis.
3. Decision point: with the analysis in hand, the user decides whether to (a) do nothing (the concept is interesting but Sutra is different enough that it doesn't map), (b) adjust the MCP/queue.md protocol to borrow a specific idea, or (c) build something bigger.

No language spec changes, no code changes, no dependency adds until after the decision point.

## What this is NOT

- Not a commitment to build an LLM wiki.
- Not a commitment to change Sutra's language surface.
- Not a priority over the Claw4S paper cycle.
- Not something to start implementing before the research step is done.
