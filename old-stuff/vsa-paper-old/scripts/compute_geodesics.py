"""
Compute trajectories for all triples where both subject and object have embeddings.
Each trajectory is a line between two specific text embeddings (label or alias)
connected by a triple. Stored as RDF-star: each trajectory is its own object.

Output: data/trajectories.ttl (Turtle with RDF-star)
"""

import json
import sys
import io
import numpy as np
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, XSD
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WD = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
EMB = Namespace("http://embedding-mapping.local/ontology/")


def main():
    # Load items
    with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    # Load embeddings + index
    emb = np.load(str(DATA_DIR / "embeddings.npz"))["vectors"]
    with open(str(DATA_DIR / "embedding_index.json"), "r", encoding="utf-8") as f:
        index = json.load(f)

    # Build lookup: qid -> list of (vector_index, text, type)
    qid_embeddings = {}
    for i, entry in enumerate(index):
        qid = entry["qid"]
        if qid not in qid_embeddings:
            qid_embeddings[qid] = []
        qid_embeddings[qid].append({
            "vec_idx": i,
            "text": entry["text"],
            "type": entry["type"],
        })

    # Build RDF graph
    g = Graph()
    g.bind("wd", WD)
    g.bind("wdt", WDT)
    g.bind("emb", EMB)

    traj_count = 0
    skipped_no_embedding = 0

    for item in items:
        subj_qid = item["qid"]
        if subj_qid not in qid_embeddings:
            continue

        subj_entries = qid_embeddings[subj_qid]

        for triple in item["triples"]:
            # Only process triples pointing to wikibase items
            if triple["value"]["type"] != "wikibase-item":
                continue

            obj_qid = triple["value"]["value"]
            if obj_qid not in qid_embeddings:
                skipped_no_embedding += 1
                continue

            obj_entries = qid_embeddings[obj_qid]
            pred_id = triple["predicate"]

            # Create a trajectory for every (subject_text, object_text) pair
            for s_entry in subj_entries:
                s_vec = emb[s_entry["vec_idx"]]

                for o_entry in obj_entries:
                    o_vec = emb[o_entry["vec_idx"]]

                    # Cosine distance
                    cos_sim = float(np.dot(s_vec, o_vec) / (
                        np.linalg.norm(s_vec) * np.linalg.norm(o_vec)
                    ))
                    cos_dist = 1.0 - cos_sim
                    euclidean_dist = float(np.linalg.norm(s_vec - o_vec))

                    # Create trajectory as a blank node
                    traj = BNode()
                    g.add((traj, RDF.type, EMB.Trajectory))

                    # Link to the triple's components
                    g.add((traj, EMB.subjectEntity, WD[subj_qid]))
                    g.add((traj, EMB.objectEntity, WD[obj_qid]))
                    g.add((traj, EMB.predicate, WDT[pred_id]))

                    # The specific text endpoints
                    g.add((traj, EMB.subjectText, Literal(s_entry["text"])))
                    g.add((traj, EMB.objectText, Literal(o_entry["text"])))
                    g.add((traj, EMB.subjectTextType, Literal(s_entry["type"])))
                    g.add((traj, EMB.objectTextType, Literal(o_entry["type"])))

                    # Distances
                    g.add((traj, EMB.cosineDistance, Literal(round(cos_dist, 6), datatype=XSD.float)))
                    g.add((traj, EMB.cosineSimilarity, Literal(round(cos_sim, 6), datatype=XSD.float)))
                    g.add((traj, EMB.euclideanDistance, Literal(round(euclidean_dist, 6), datatype=XSD.float)))

                    traj_count += 1

    # Save
    g.serialize(str(DATA_DIR / "trajectories.ttl"), format="turtle")

    print(f"Computed {traj_count} trajectories")
    print(f"Skipped {skipped_no_embedding} triples (object has no embedding)")
    print(f"RDF statements: {len(g)}")
    print(f"Saved to data/trajectories.ttl")

    # Stats
    distances = []
    for s, p, o in g.triples((None, EMB.cosineDistance, None)):
        distances.append(float(o))

    if distances:
        distances = np.array(distances)
        print(f"\nTrajectory distance stats:")
        print(f"  Count: {len(distances)}")
        print(f"  Mean cosine distance: {distances.mean():.4f}")
        print(f"  Min: {distances.min():.4f}")
        print(f"  Max: {distances.max():.4f}")
        print(f"  Std: {distances.std():.4f}")


if __name__ == "__main__":
    main()
