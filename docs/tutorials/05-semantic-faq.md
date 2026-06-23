# 05 — Build a semantic FAQ matcher

This is the first tutorial where Sutra does something a newcomer would call *useful*. We build a tiny support bot: it knows five canned answers, and when a user asks a question **in their own words** it returns the right one. The trick is that the match is by **meaning**, not keywords — "I forgot my login and need to change it" finds "how do I reset my password" even though the two sentences barely share a word.

## What you'll learn

- How `embed(...)` turns a sentence into a point in semantic space
- How `argmax_cosine` picks the nearest known point — the whole matching engine, in one line
- Why this is *semantic* matching and not string matching
- How to run a program whose embeddings come from a real model, with no separate server

## Prerequisites

```bash
pip install "sutra-dev[runtime,embed]"
```

The `[embed]` extra loads the frozen `nomic-embed-text` model **in-process** — you do not need an Ollama daemon. The first run downloads the model once (a few hundred MB; it prints a one-line notice and caches it).

## The program

`examples/semantic_faq.su`:

```c
// @embedding: nomic-embed-text

// The knowledge base: five questions, each embedded by meaning.
vector q_reset  = embed("how do I reset my password");
vector q_refund = embed("how do I get a refund");
vector q_hours  = embed("what are your business hours");
vector q_track  = embed("where is my order");
vector q_cancel = embed("how do I cancel my subscription");

// Each question vector maps to its canned answer.
map<vector, string> ANSWER = {
    q_reset:  "Go to Settings > Security > Reset Password.",
    q_refund: "Refunds are issued within 5 business days from your Orders page.",
    q_hours:  "We are open 9am to 6pm, Monday through Friday.",
    q_track:  "Track your order under Orders > Track Shipment.",
    q_cancel: "Cancel anytime under Settings > Subscription > Cancel."
};

// Take an embedded query, return the answer of the nearest question.
function string answer(vector query) {
    vector winner = argmax_cosine(query,
        [q_reset, q_refund, q_hours, q_track, q_cancel]);
    return ANSWER[winner];
}

// A user asks in their own words — a paraphrase of one canned question.
function string ask_password() { return answer(embed("I forgot my login and need to change it")); }

function string main() {
    return ask_password();
}
```

## Run it

```bash
sutrac --run examples/semantic_faq.su
```

You get back:

```
Go to Settings > Security > Reset Password.
```

The query string `"I forgot my login and need to change it"` never appears in the knowledge base. Yet it routed to the password answer, because in `nomic-embed-text`'s embedding space the *meaning* of that sentence sits closest to the *meaning* of "how do I reset my password."

## How it works, line by line

1. **`embed("...")`** sends each string through the frozen embedding model and returns its coordinate — a `vector` — in semantic space. Sentences that mean similar things land near each other; sentences that mean different things land far apart. This is the one place a model runs; everything after is geometry.

2. **`map<vector, string> ANSWER`** is a codebook: it pairs each *question vector* with the *answer string* you want to return when that question wins. Sutra's `map<vector, K>` is a content-addressed table — you look it up with the winning vector, not with an index.

3. **`argmax_cosine(query, [...])`** is the entire matching engine. It compares the query vector against every question vector by cosine similarity and returns the closest one. No `if`, no keyword list, no rules — one geometric argmax. (Under the hood it compiles to a single stacked matrix-multiply plus an argmax; see [Snap-to-nearest](03-snap-to-nearest.md) for why that is the cleanup primitive.)

4. **`ANSWER[winner]`** maps the winning question vector back to its answer.

## Why this is the interesting case

Compare it to the earlier tutorials. Tutorials 01–03 use `basis_vector("name")` — *random* atoms that are deterministic per name but carry no meaning, so `basis_vector("cat")` is no closer to `basis_vector("kitten")` than to `basis_vector("airplane")`. That is perfect for demonstrating bind/unbind mechanics without depending on a model.

Here we use `embed(...)` instead, and that changes everything: the geometry now *encodes meaning*, so nearness means semantic similarity. That is what lets a paraphrase match. Swapping `basis_vector` for `embed` is the step from "symbolic plumbing" to "understands what the user meant."

## Extend it

- Add a sixth FAQ and a paraphrased query for it. Does it route correctly?
- Try a deliberately ambiguous query ("I have a problem with my account") and see which answer wins — the failure modes here are the same *Voronoi-cell* boundaries from [Snap-to-nearest](03-snap-to-nearest.md): when a query sits near the boundary between two questions, the match can flip.
- Add a confidence floor: if even the best match is weak, you would want to fall back to "let me connect you to a human." That needs a *threshold* on the top cosine — a natural next step once you have read the [operators reference](../operators.md).

## What to read next

- The [Operations and operators reference](../operators.md) — the formal definition of `argmax_cosine`, `embed`, and the rest.
- [What is Sutra](../what-is-sutra.md) — the bigger picture of why a language built on embedding geometry is a different kind of tool.
