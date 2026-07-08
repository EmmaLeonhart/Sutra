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

(As in tutorial 01, `examples/semantic_faq.su` ships in the
[source repo](https://github.com/EmmaLeonhart/Sutra), not the pip package — save the
program above to a local file if you installed only from PyPI.)

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

Compare it to the earlier retrieval tutorials. There, the query you matched was a stored item itself or a lightly-noised copy of one — `hello_world.su` identifies the greeting against a codebook that *contains* that exact greeting. The match is impressive plumbing, but the query and the answer are nearly the same string.

Here the query shares almost no words with the question it matches — "I forgot my login and need to change it" against "how do I reset my password." It still lands right because nearness in the embedding space is *semantic* distance: the model places paraphrases close together even when their words differ. The earlier tutorials matched a stored string to a near-copy of itself; here you match a genuinely different wording. That generalization to unseen phrasings is the step from "retrieve what I stored" to "understand what the user meant."

## Extend it

- Add a sixth FAQ and a paraphrased query for it. Does it route correctly?
- Try a deliberately ambiguous query ("I have a problem with my account") and see which answer wins — the failure modes here are the same *Voronoi-cell* boundaries from [Snap-to-nearest](03-snap-to-nearest.md): when a query sits near the boundary between two questions, the match can flip.
- Add a confidence floor: if even the best match is weak, you would want to fall back to "let me connect you to a human." That needs a *threshold* on the top cosine — a natural next step once you have read the [operators reference](../operators.md).
- Notice the query is **hardcoded** — `embed("I forgot my login and need to change it")` is written into the source, not read from a live user. That is not an oversight: core Sutra has no `read`/stdin/file-read, so input enters a program at the source (via `embed`) or as a loaded matrix, and you rerun per question. Why that is, and the small set of places data *does* cross the host boundary, is the subject of [The host bridge — Sutra's I/O model](../host-bridge.md).

## What to read next

- The [Operations and operators reference](../operators.md) — the formal definition of `argmax_cosine`, `embed`, and the rest.
- [What is Sutra](../what-is-sutra.md) — the bigger picture of why a language built on embedding geometry is a different kind of tool.

---

**Next: [06 — Strings & formatting](06-strings-and-formatting.md)**
