# Embedding training, knowledge-graph loss function, Wikidata pollution

_Excerpt from the original `chats/kolmogorov-arnold-networks-for-tensor-operations.md` (lines 687-814). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

## User

This would be very nice because I hate only having nomic text

## Claude

Yeah, nomic-embed is great for what it is but it's a general purpose text embedding model — it was built for retrieval, not for computation. It has no idea that someone might want to address presidential dimensions of a person vector, or do arithmetic in currency space, or have clean separable dimensions for ontological categories.

A Sutra-native embedding space would be built with completely different goals:

Ontological categories should be geometrically separable

Class hierarchies should have corresponding geometric structure — Human and President should have a clean subspace relationship

Arithmetic properties should be preserved — the currency dimensions should behave like numbers

Synthetic dimensions should be explicitly reserved and documented so the compiler knows where to look

The space should be versioned and stable so compiled programs don't break when the model updates

Right now you're essentially doing archaeology — trying to find structure in a space that wasn't built for you. Sometimes you find clean structure like the gender vector or the age vector you discovered empirically. But that's accidental. A Sutra-native space would make all of that intentional and guaranteed.

And it would be a significant research contribution in its own right. Nobody has built an embedding space explicitly designed to serve as a computational substrate for a programming language. That's a new thing. The paper basically writes itself — "we present an embedding space co-designed with a programming language, and show that programs compiled against it have properties X, Y, Z that are impossible with general purpose embeddings."

That's an Anthropic-relevant research direction too, which doesn't hurt.

## User

Yes and we do have a many to many traversal method that might become part of a loss function

## Claude

Oh that's a really natural connection.

Your directed vector search — treating embedding space as a navigable graph and traversing it — could become a loss function that trains the embedding space to be more traversable in the ways Sutra needs. Essentially you're saying "here are the paths that Sutra programs want to walk, train the space so those paths are clean and well-structured."

Which is a completely novel way to define a loss function for an embedding model. Current embedding models are trained on:

Contrastive losses — similar things should be close, dissimilar things far

Retrieval losses — the right document should rank higher than wrong documents

Reconstruction losses — encode and decode faithfully

Nobody is training on "the many-to-many traversal paths that a programming language needs to walk should be geometrically coherent." But that's a perfectly well-defined loss — you could measure how clean the traversal is, how consistent the path structure is across similar entity types, how well ontological relationships are preserved along traversal paths.

And the many-to-many aspect is important because it's not just "Human to President is a clean vector offset" — it's that the same offset works consistently across many humans and many presidents, and composes correctly with other offsets. That compositionality is exactly what word2vec arithmetic demonstrated and what nobody has deliberately trained for since.

Sutra's traversal method gives you a concrete way to measure that compositionality, which gives you a loss function, which gives you a training objective for a Sutra-native embedding space.

That's a complete research pipeline right there.

## User

I have heard about a couple of logically operation-based, specially trained betting systems. I've heard of this, but I don't know how serious they were, and I think they may really have not actually been. It's honestly possible that those things even existed and there were people who tried to make loss functions like this. Geometric heresy of class relations is geometrically consistent with, like, I don't know, wiki data stuff or whatever knowledge graph you're using. Geometric consistency of representing a knowledge graph in your embedding space would be an interesting loss function.

## Claude

Yeah, knowledge graph embedding is actually a pretty well developed research area — TransE, RotatE, ComplEx and a bunch of others are all explicitly trying to embed knowledge graph relations as geometric operations. TransE is the classic one where a relation is just a translation vector — `head + relation = tail`, so `Paris + capital_of_inverse = France`. That's exactly the word2vec arithmetic idea but applied deliberately to structured knowledge.

So the loss function you're describing isn't completely novel in that sense — people have trained on Wikidata-style triples before. But what those systems were doing was essentially:

Take a knowledge graph

Embed it so the graph structure is geometrically preserved

Use the embedding for link prediction — guessing missing edges in the graph

What they weren't doing is:

Using geometric consistency of the knowledge graph as a component of a more general embedding space loss

Co-designing the loss with a programming language's computational needs

Combining knowledge graph consistency with traversal compositionality as a joint objective

So there's prior art on the knowledge graph side, but the specific combination you're pointing at — geometric consistency of ontological class relations as part of a loss function that also optimizes for Sutra's traversal properties — that particular synthesis probably hasn't been done.

The Wikidata angle is interesting because Wikidata is already structured around an ontology with class hierarchies, properties, and typed relations. It's almost a ready-made training signal for exactly the kind of geometric structure Sutra needs.

## User

Yeah, I would. Wikidata is what I used for the thing, but I'd definitely question the usage of Wikidata for this because I think Wikidata is kind of polluted.

## Claude

Yeah, Wikidata has real quality issues that would matter a lot for this use case.

The problem is Wikidata is crowdsourced and its ontology is notoriously inconsistent. The class hierarchy is a mess — things are categorized differently depending on who edited them, there are circular relationships, redundant classes, conflicting type assignments. Donald Trump might be simultaneously instance-of `human`, `politician`, `businessperson`, and `television personality` with no clear geometric interpretation of how those relate.

For general knowledge retrieval that's fine — you just want coverage. But for training an embedding space where you need geometrically consistent class hierarchies, Wikidata's inconsistency would pollute the loss signal. You'd be training the space to be consistent with an inconsistent ontology, which is worse than not training on it at all.

Better candidates might be:

WordNet — much cleaner hierarchy, carefully curated, but limited to language concepts

CYC — extremely carefully curated logical ontology, but proprietary and old

Schema.org — cleaner than Wikidata, designed for structured data, reasonable class hierarchy

BioPortal ontologies — if you want a domain where ontologies are taken very seriously, biology has extremely rigorous ones

A purpose-built ontology — honestly given your Pramana work you might be better positioned than most to define the ontology you actually want and train against that

The last option is interesting because it closes the loop — Sutra's type hierarchy is the ontology, and you train the embedding space to be geometrically consistent with Sutra's own class structure. The language defines its own ground truth.

## User

Yeah, I would definitely be interested in training my own, like, in building my own ontologies or something like this, but I don't know if that's necessarily the best thing to do. I don't know how much compute they'll be giving me and how much compute I'd be needing to train my own embedding space like this.

## Claude

Yeah, compute is the real constraint here and it's worth being realistic about.

Training a competitive general purpose embedding model from scratch is extremely expensive — we're talking about the kind of compute that only well-funded labs can do. nomic-embed, which is one of the smaller competitive models, still required significant resources and a large team.

But there's a spectrum of options that require much less compute:

Fine-tuning an existing model — take something like nomic-embed or a sentence transformer and fine-tune it with your knowledge graph consistency loss. You're not training from scratch, you're nudging an already good embedding space toward better geometric structure for Sutra's needs. This is much more feasible compute-wise.

Adapter layers — even cheaper, you add a small learned transformation on top of an existing embedding model that remaps the space to be more geometrically consistent. The base model is frozen, you only train the adapter.

Synthetic data generation — you could use an LLM to generate clean ontological triples based on your Sutra type hierarchy, which sidesteps the Wikidata pollution problem without needing a massive knowledge graph. Generate exactly the relationships you care about.

The fine-tuning approach is probably the most realistic near-term path. You'd define your loss function — traversal compositionality plus ontological geometric consistency — and fine-tune an existing model against it with a relatively modest amount of compute.

And honestly that's also a more publishable result in some ways — "we show that fine-tuning with this novel loss function produces embedding spaces with these computational properties" is a cleaner contribution than "we trained a new embedding model from scratch."

