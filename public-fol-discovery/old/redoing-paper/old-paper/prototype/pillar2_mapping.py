"""Pillar 2 — Embedding Space + Virtual Knowledge Graph Construction.

This is the core innovation: entity-bridged VKG expansion that pulls in
causally-relevant propositions even when they have low direct query similarity.

Dual representation:
  - NetworkX DiGraph  → algorithmic path-finding (Pillar 3)
  - RDFLib Graph      → formal semantics and SPARQL queries
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import ollama
import rdflib
from rdflib import Literal, Namespace, URIRef

from prototype.pillar1_extraction import Proposition

EMBED_MODEL = "mxbai-embed-large"
NS = Namespace("http://neurosymbolic.example.org/")


# ── Embedding helpers ─────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts using mxbai-embed-large (1024-dim)."""
    vectors = []
    for text in texts:
        resp = ollama.embed(model=EMBED_MODEL, input=text)
        vectors.append(resp["embeddings"][0])
    return np.array(vectors, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between vector *a* (1-D) and matrix *b* (N x D)."""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norm @ a_norm


# ── Similarity-based retrieval (used by both standard and neurosymbolic) ──────

@dataclass
class ScoredItem:
    index: int
    text: str
    score: float


def retrieve_by_similarity(
    query: str,
    corpus: list[str],
    top_k: int = 5,
    corpus_embeddings: np.ndarray | None = None,
) -> tuple[list[ScoredItem], np.ndarray]:
    """Return top-k corpus items by cosine similarity to *query*.

    Also returns the corpus embeddings matrix for reuse.
    """
    if corpus_embeddings is None:
        print("  [pillar2] Embedding corpus...")
        corpus_embeddings = embed_texts(corpus)

    query_vec = embed_texts([query])[0]
    scores = cosine_similarity(query_vec, corpus_embeddings)
    ranked = np.argsort(scores)[::-1][:top_k]

    results = [
        ScoredItem(index=int(idx), text=corpus[idx], score=float(scores[idx]))
        for idx in ranked
    ]
    return results, corpus_embeddings


# ── Entity matching ───────────────────────────────────────────────────────────

def _entity_overlap(entities_a: list[str], entities_b: list[str]) -> bool:
    """Check if two entity lists share any entity (lowercase)."""
    set_a = {e.lower().strip() for e in entities_a}
    set_b = {e.lower().strip() for e in entities_b}
    return bool(set_a & set_b)


def _embedding_entity_match(
    ent_a: str, ent_b: str, threshold: float = 0.85
) -> bool:
    """Soft entity matching via embedding cosine similarity."""
    vecs = embed_texts([ent_a, ent_b])
    sim = float(cosine_similarity(vecs[0], vecs[1:]))
    return sim >= threshold


# ── VKG Construction (the secret sauce) ───────────────────────────────────────

@dataclass
class VKG:
    """Virtual Knowledge Graph — runtime semantic workspace."""
    nx_graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    rdf_graph: rdflib.Graph = field(default_factory=rdflib.Graph)
    propositions: list[Proposition] = field(default_factory=list)
    seed_indices: list[int] = field(default_factory=list)
    bridged_indices: list[int] = field(default_factory=list)


def _safe_uri(text: str) -> str:
    """Make a string safe for use as a URI fragment."""
    return text.lower().replace(" ", "_").replace(",", "").replace(".", "")


def build_vkg(
    query: str,
    propositions: list[Proposition],
    corpus: list[str],
    top_k_seed: int = 4,
    bridge_threshold_ratio: float = 0.6,
) -> VKG:
    """Build a Virtual Knowledge Graph via seed + entity bridging.

    Algorithm:
      1. Embed all propositions, rank by query similarity
      2. Seed: take top-k propositions
      3. Collect entities from seed propositions
      4. Bridge: for every remaining proposition, include it if it shares
         an entity with the seed set (even at lower similarity)
      5. Build dual graph (NetworkX + RDFLib)
    """
    vkg = VKG()

    # Embed proposition texts (use source_text for richer signal)
    prop_texts = [p.source_text or p.triple_str for p in propositions]
    prop_embeddings = embed_texts(prop_texts)
    query_vec = embed_texts([query])[0]
    scores = cosine_similarity(query_vec, prop_embeddings)

    # ── Step 1: Seed ──────────────────────────────────────────────────────
    ranked = np.argsort(scores)[::-1]
    seed_indices = list(ranked[:top_k_seed])
    vkg.seed_indices = seed_indices

    seed_entities: set[str] = set()
    for idx in seed_indices:
        seed_entities.update(propositions[idx].entities)

    min_seed_score = min(scores[i] for i in seed_indices) if seed_indices else 0
    bridge_threshold = min_seed_score * bridge_threshold_ratio

    print(f"  [pillar2] Seed: {len(seed_indices)} propositions, "
          f"{len(seed_entities)} unique entities")
    print(f"  [pillar2] Bridge threshold: {bridge_threshold:.3f} "
          f"(ratio={bridge_threshold_ratio})")

    # ── Step 2: Bridge via shared entities ────────────────────────────────
    bridged_indices: list[int] = []
    for idx in range(len(propositions)):
        if idx in seed_indices:
            continue
        prop = propositions[idx]
        if scores[idx] < bridge_threshold:
            continue
        if _entity_overlap(prop.entities, list(seed_entities)):
            bridged_indices.append(idx)
            # Expand entity set with newly bridged entities
            seed_entities.update(prop.entities)

    vkg.bridged_indices = bridged_indices
    all_indices = seed_indices + bridged_indices
    vkg.propositions = [propositions[i] for i in all_indices]

    print(f"  [pillar2] Bridged: {len(bridged_indices)} additional propositions")
    print(f"  [pillar2] VKG total: {len(vkg.propositions)} propositions")

    # ── Step 3: Build graphs ──────────────────────────────────────────────
    for prop in vkg.propositions:
        subj_uri = URIRef(NS[_safe_uri(prop.subject)])
        obj_uri = URIRef(NS[_safe_uri(prop.object)])
        pred_uri = URIRef(NS[_safe_uri(prop.predicate)])

        # NetworkX: nodes are entities, edges are predicates
        vkg.nx_graph.add_node(subj_uri, label=prop.subject)
        vkg.nx_graph.add_node(obj_uri, label=prop.object)
        vkg.nx_graph.add_edge(
            subj_uri, obj_uri,
            predicate=prop.predicate,
            source=prop.source_text,
        )

        # RDFLib: formal triple
        vkg.rdf_graph.add((subj_uri, pred_uri, obj_uri))
        # Also store source text as annotation
        vkg.rdf_graph.add((subj_uri, NS["source"], Literal(prop.source_text)))

    # Add entity-entity links for shared entities across propositions
    entity_to_props: dict[str, list[Proposition]] = {}
    for prop in vkg.propositions:
        for ent in prop.entities:
            entity_to_props.setdefault(ent, []).append(prop)

    for ent, props in entity_to_props.items():
        if len(props) > 1:
            ent_uri = URIRef(NS[_safe_uri(ent)])
            for prop in props:
                subj_uri = URIRef(NS[_safe_uri(prop.subject)])
                vkg.nx_graph.add_edge(
                    ent_uri, subj_uri,
                    predicate="entity_link",
                    source=f"shared entity: {ent}",
                )

    return vkg
