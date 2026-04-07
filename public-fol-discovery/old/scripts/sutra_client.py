"""
SutraDB Python client.

Wraps the SutraDB REST API for inserting triples and vectors.
Used by the import pipeline to save data directly to SutraDB
instead of flat files.
"""

import requests
import json
import time

DEFAULT_ENDPOINT = "http://localhost:3030"


class SutraClient:
    """Client for the SutraDB REST API."""

    def __init__(self, endpoint=DEFAULT_ENDPOINT):
        self.endpoint = endpoint.rstrip("/")
        self.session = requests.Session()

    def health(self):
        """Check if SutraDB is running."""
        try:
            resp = self.session.get(f"{self.endpoint}/health", timeout=5)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def declare_vector_predicate(self, predicate_iri, dimensions=1024, m=16,
                                  ef_construction=200, metric="cosine"):
        """Declare a vector predicate with its HNSW index parameters."""
        resp = self.session.post(
            f"{self.endpoint}/vectors/declare",
            json={
                "predicate": predicate_iri,
                "dimensions": dimensions,
                "m": m,
                "ef_construction": ef_construction,
                "metric": metric,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def insert_triples(self, ntriples_text, batch_size=5000):
        """Insert triples in N-Triples format, batched to avoid timeouts.

        Args:
            ntriples_text: String of N-Triples (one triple per line)
            batch_size: Number of lines per HTTP request

        Returns:
            dict with "inserted" count and "errors" list
        """
        lines = ntriples_text.split("\n")
        total_inserted = 0
        total_errors = []

        for start in range(0, len(lines), batch_size):
            chunk = "\n".join(lines[start:start + batch_size])
            if not chunk.strip():
                continue
            resp = self.session.post(
                f"{self.endpoint}/triples",
                data=chunk,
                headers={"Content-Type": "application/n-triples"},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            total_inserted += result.get("inserted", 0)
            total_errors.extend(result.get("errors", []))
            batch_num = start // batch_size + 1
            total_batches = (len(lines) + batch_size - 1) // batch_size
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"    Triples batch {batch_num}/{total_batches}: {total_inserted} inserted so far")

        return {"inserted": total_inserted, "errors": total_errors}

    def insert_vector(self, predicate_iri, subject_iri, vector):
        """Insert a single vector for a subject under a predicate's HNSW index.

        Args:
            predicate_iri: IRI of the vector predicate
            subject_iri: IRI of the entity this vector belongs to
            vector: list of floats
        """
        resp = self.session.post(
            f"{self.endpoint}/vectors",
            json={
                "predicate": predicate_iri,
                "subject": subject_iri,
                "vector": [float(v) for v in vector],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def insert_vectors_batch(self, predicate_iri, entries):
        """Insert multiple vectors.

        Args:
            predicate_iri: IRI of the vector predicate
            entries: list of (subject_iri, vector) tuples
        """
        inserted = 0
        errors = []
        for subject_iri, vector in entries:
            try:
                self.insert_vector(predicate_iri, subject_iri, vector)
                inserted += 1
            except Exception as e:
                errors.append(f"{subject_iri}: {e}")
        return {"inserted": inserted, "errors": errors}

    def sparql(self, query):
        """Execute a SPARQL query."""
        resp = self.session.get(
            f"{self.endpoint}/sparql",
            params={"query": query},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()


def rdflib_graph_to_ntriples(graph):
    """Serialize an rdflib Graph to N-Triples string."""
    return graph.serialize(format="nt")


def save_to_sutra(client, items, index, emb, embedding_predicate="http://embedding-mapping.local/ontology/hasEmbedding"):
    """Save all data to SutraDB.

    This replaces save_all() + serialize steps. It:
    1. Builds and inserts triples from items
    2. Inserts embeddings as vectors

    Args:
        client: SutraClient instance
        items: list of item dicts
        index: embedding index entries
        emb: numpy array of embeddings
        embedding_predicate: IRI for the vector predicate
    """
    from rdflib import Graph, URIRef, Literal, Namespace, BNode
    from rdflib.namespace import RDF, XSD

    WD = Namespace("http://www.wikidata.org/entity/")
    WDT = Namespace("http://www.wikidata.org/prop/direct/")
    EMB = Namespace("http://embedding-mapping.local/ontology/")

    # Step 1: Build and insert triples
    print("  Building RDF triples...")
    from import_wikidata import build_triples_graph
    g = build_triples_graph(items)
    nt_text = g.serialize(format="nt")
    print(f"  Inserting {len(g)} triples into SutraDB...")
    result = client.insert_triples(nt_text)
    print(f"  Inserted: {result.get('inserted', 0)}, errors: {len(result.get('errors', []))}")

    # Step 2: Insert embeddings as vectors
    if emb.size > 0:
        print(f"  Inserting {len(index)} vectors ({emb.shape[1]}-dim)...")
        batch = []
        for i, entry in enumerate(index):
            qid = entry["qid"]
            # Use the entity IRI as the subject for the vector
            subject_iri = f"http://www.wikidata.org/entity/{qid}"
            # For aliases, create a unique IRI that distinguishes the text
            text_type = entry["type"]
            text = entry["text"]
            if text_type == "alias":
                # Hash the alias text to create a unique vector subject
                import hashlib
                text_hash = hashlib.md5(f"{qid}:{text}".encode()).hexdigest()[:12]
                subject_iri = f"http://embedding-mapping.local/embedding/{qid}/{text_hash}"
            batch.append((subject_iri, emb[i].tolist()))

        # Insert in batches
        batch_size = 100
        total_inserted = 0
        for start in range(0, len(batch), batch_size):
            chunk = batch[start:start + batch_size]
            result = client.insert_vectors_batch(embedding_predicate, chunk)
            total_inserted += result["inserted"]
            if result["errors"]:
                print(f"    Batch {start // batch_size + 1}: {len(result['errors'])} errors")
            if (start // batch_size + 1) % 10 == 0:
                print(f"    Progress: {total_inserted}/{len(batch)} vectors")
        print(f"  Vectors inserted: {total_inserted}")

    return len(g)


def save_trajectories_to_sutra(client, items, index, emb):
    """Compute and save trajectories to SutraDB."""
    from import_wikidata import compute_trajectories_for_items

    print("  Computing trajectories...")
    traj_g, traj_count = compute_trajectories_for_items(items, index, emb)
    if traj_count > 0:
        nt_text = traj_g.serialize(format="nt")
        print(f"  Inserting {traj_count} trajectories ({len(traj_g)} triples) into SutraDB...")
        result = client.insert_triples(nt_text)
        print(f"  Inserted: {result.get('inserted', 0)}")
    return traj_count
