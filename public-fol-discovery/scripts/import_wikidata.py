"""
Unified Wikidata import pipeline.

Usage:
  python import_wikidata.py Q8502              # import one item
  python import_wikidata.py Q8502 Q513 Q524    # import multiple items
  python import_wikidata.py --instances Q8502 --limit 10  # import instances of a class

For each imported item:
  1. Fetches full properties from Wikidata API
  2. Fetches labels+aliases for all linked QIDs
  3. Generates embeddings for all labels and aliases (mxbai-embed-large)
  4. Stores triples as RDF
  5. Computes trajectories for all new triples

All data is merged into the existing data/ files.
"""

import json
import sys
import io
import os
import time
import argparse
import numpy as np
import requests
import ollama
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, XSD
from pathlib import Path

DATA_DIR = Path(os.environ.get("FOL_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")

WD = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
EMB = Namespace("http://embedding-mapping.local/ontology/")


def load_existing():
    """Load existing data or return empty structures."""
    items = []
    index = []
    emb = np.empty((0, 1024))

    if os.path.exists(str(DATA_DIR / "items.json")):
        with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
            items = json.load(f)
    if os.path.exists(str(DATA_DIR / "embedding_index.json")):
        with open(str(DATA_DIR / "embedding_index.json"), "r", encoding="utf-8") as f:
            index = json.load(f)
    if os.path.exists(str(DATA_DIR / "embeddings.npz")):
        try:
            emb = np.load(str(DATA_DIR / "embeddings.npz"))["vectors"]
        except Exception:
            # Fall back for files saved with older numpy or interrupted writes
            emb = np.load(str(DATA_DIR / "embeddings.npz"), allow_pickle=True)["vectors"]

    return items, index, emb


def save_all(items, index, emb):
    """Save all data files."""
    os.makedirs(str(DATA_DIR), exist_ok=True)
    with open(str(DATA_DIR / "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    with open(str(DATA_DIR / "embedding_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    np.savez_compressed(str(DATA_DIR / "embeddings.npz"), vectors=emb)


def fetch_entity(qid):
    """Fetch a single Wikidata item via the API."""
    resp = requests.get(
        WIKIDATA_API,
        params={
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "languages": "en",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    entities = resp.json().get("entities", {})
    return entities.get(qid)


def fetch_labels_batch(qids):
    """Fetch labels and aliases for a batch of QIDs (up to 50)."""
    resp = requests.get(
        WIKIDATA_API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels|aliases",
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("entities", {})


def get_instances(class_qid, limit):
    """Get instance QIDs of a class via SPARQL."""
    query = f"""
SELECT ?item WHERE {{
  ?item wdt:P31 wd:{class_qid} .
  ?item wikibase:sitelinks ?sitelinks .
}}
ORDER BY DESC(?sitelinks)
LIMIT {limit}
"""
    resp = requests.post(
        SPARQL_ENDPOINT,
        data={"query": query},
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    bindings = resp.json()["results"]["bindings"]
    return [b["item"]["value"].split("/")[-1] for b in bindings]


def extract_value(snak):
    """Extract a usable value from a Wikidata snak."""
    if snak["snaktype"] != "value":
        return {"type": snak["snaktype"], "value": None}

    dv = snak["datavalue"]
    vtype = dv["type"]

    if vtype == "wikibase-entityid":
        return {"type": "wikibase-item", "value": dv["value"]["id"]}
    elif vtype == "string":
        return {"type": "string", "value": dv["value"]}
    elif vtype == "monolingualtext":
        return {"type": "monolingualtext", "value": dv["value"]["text"], "language": dv["value"].get("language", "")}
    elif vtype == "quantity":
        q = dv["value"]
        return {"type": "quantity", "value": q["amount"], "unit": q.get("unit", "")}
    elif vtype == "time":
        return {"type": "time", "value": dv["value"]["time"]}
    elif vtype == "globecoordinate":
        gc = dv["value"]
        return {"type": "coordinate", "latitude": gc["latitude"], "longitude": gc["longitude"]}
    else:
        return {"type": vtype, "value": str(dv["value"])}


def process_entity(entity):
    """Extract label, aliases, and all triples from a Wikidata entity."""
    qid = entity["id"]
    labels = entity.get("labels", {})
    label = labels.get("en", {}).get("value", qid)

    alias_list = entity.get("aliases", {}).get("en", [])
    aliases = [a["value"] for a in alias_list]

    triples = []
    for prop_id, claim_list in entity.get("claims", {}).items():
        for claim in claim_list:
            mainsnak = claim.get("mainsnak", {})
            if not mainsnak:
                continue

            val = extract_value(mainsnak)

            # Extract qualifiers
            qualifiers = []
            for qual_prop, qual_snaks in claim.get("qualifiers", {}).items():
                for snak in qual_snaks:
                    qualifiers.append({
                        "predicate": qual_prop,
                        "value": extract_value(snak),
                    })

            # Extract sources (references)
            sources = []
            for ref in claim.get("references", []):
                ref_snaks = {}
                for ref_prop, snak_list in ref.get("snaks", {}).items():
                    for snak in snak_list:
                        sources.append({
                            "predicate": ref_prop,
                            "value": extract_value(snak),
                        })

            triples.append({
                "subject": qid,
                "predicate": prop_id,
                "value": val,
                "rank": claim.get("rank", "normal"),
                "qualifiers": qualifiers,
                "sources": sources,
            })

    return {
        "qid": qid,
        "label": label,
        "aliases": aliases,
        "triples": triples,
    }


def embed_texts(texts):
    """Embed a list of texts via Ollama."""
    result = ollama.embed(model=EMBED_MODEL, input=texts)
    return np.array([np.array(e) for e in result.embeddings])


def compute_trajectories_for_items(items, index, emb):
    """Compute trajectories for all triples. Returns an RDF graph."""
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

    g = Graph()
    g.bind("wd", WD)
    g.bind("wdt", WDT)
    g.bind("emb", EMB)

    traj_count = 0

    for item in items:
        subj_qid = item["qid"]
        if subj_qid not in qid_embeddings:
            continue

        subj_entries = qid_embeddings[subj_qid]

        for triple in item["triples"]:
            if triple["value"]["type"] != "wikibase-item":
                continue

            obj_qid = triple["value"]["value"]
            if obj_qid not in qid_embeddings:
                continue

            obj_entries = qid_embeddings[obj_qid]
            pred_id = triple["predicate"]
            pred_entries = qid_embeddings.get(pred_id, [])

            # Subject-Object trajectories only.
            # Properties are embedded as entities in the space but do NOT get
            # trajectories with their subject/object — that relationship is not
            # linguistic. Predicate-involving trajectories would require propositional
            # form (full sentence embedding), which is not yet implemented.
            for s_entry in subj_entries:
                s_vec = emb[s_entry["vec_idx"]]

                for o_entry in obj_entries:
                    o_vec = emb[o_entry["vec_idx"]]

                    cos_sim = float(np.dot(s_vec, o_vec) / (
                        np.linalg.norm(s_vec) * np.linalg.norm(o_vec)
                    ))
                    cos_dist = 1.0 - cos_sim
                    euclidean_dist = float(np.linalg.norm(s_vec - o_vec))

                    traj = BNode()
                    g.add((traj, RDF.type, EMB.Trajectory))
                    g.add((traj, EMB.subjectEntity, WD[subj_qid]))
                    g.add((traj, EMB.objectEntity, WD[obj_qid]))
                    g.add((traj, EMB.predicate, WDT[pred_id]))
                    g.add((traj, EMB.subjectText, Literal(s_entry["text"])))
                    g.add((traj, EMB.objectText, Literal(o_entry["text"])))
                    g.add((traj, EMB.subjectTextType, Literal(s_entry["type"])))
                    g.add((traj, EMB.objectTextType, Literal(o_entry["type"])))
                    g.add((traj, EMB.cosineDistance, Literal(round(cos_dist, 6), datatype=XSD.float)))
                    g.add((traj, EMB.cosineSimilarity, Literal(round(cos_sim, 6), datatype=XSD.float)))
                    g.add((traj, EMB.euclideanDistance, Literal(round(euclidean_dist, 6), datatype=XSD.float)))

                    traj_count += 1

    return g, traj_count


def value_to_rdf(val):
    """Convert a value dict to an RDF term."""
    if val["type"] == "wikibase-item":
        return WD[val["value"]]
    elif val["type"] == "string":
        return Literal(val["value"])
    elif val["type"] == "monolingualtext":
        return Literal(val["value"], lang=val.get("language", ""))
    elif val["type"] == "quantity":
        return Literal(val["value"])
    elif val["type"] == "time":
        return Literal(val["value"])
    elif val["type"] == "coordinate":
        return Literal(f"{val['latitude']},{val['longitude']}")
    else:
        return Literal(str(val.get("value", "")))


def build_triples_graph(items):
    """Build RDF graph of all triples with RDF-star for qualifiers and sources."""
    from rdflib import ConjunctiveGraph
    g = Graph()
    g.bind("wd", WD)
    g.bind("wdt", WDT)
    g.bind("emb", EMB)

    for item in items:
        subj = WD[item["qid"]]
        for triple in item["triples"]:
            pred = WDT[triple["predicate"]]
            obj = value_to_rdf(triple["value"])

            # Main triple
            g.add((subj, pred, obj))

            # Qualifiers as RDF-star (statements about the triple)
            for qual in triple.get("qualifiers", []):
                qual_pred = WDT[qual["predicate"]]
                qual_obj = value_to_rdf(qual["value"])
                # Store as reified statement linked to a blank node
                stmt = BNode()
                g.add((stmt, RDF.type, EMB.QualifiedTriple))
                g.add((stmt, EMB.tripleSubject, subj))
                g.add((stmt, EMB.triplePredicate, pred))
                g.add((stmt, EMB.tripleObject, obj))
                g.add((stmt, qual_pred, qual_obj))

            # Sources as reified statements
            for src in triple.get("sources", []):
                src_pred = WDT[src["predicate"]]
                src_obj = value_to_rdf(src["value"])
                stmt = BNode()
                g.add((stmt, RDF.type, EMB.Source))
                g.add((stmt, EMB.tripleSubject, subj))
                g.add((stmt, EMB.triplePredicate, pred))
                g.add((stmt, EMB.tripleObject, obj))
                g.add((stmt, src_pred, src_obj))

    return g


def main():
    parser = argparse.ArgumentParser(description="Import Wikidata items into the embedding map")
    parser.add_argument("qids", nargs="*", help="QIDs to import (e.g. Q8502 Q513)")
    parser.add_argument("--instances", help="Import instances of this class QID")
    parser.add_argument("--limit", type=int, default=10, help="Max instances to fetch (default 10)")
    args = parser.parse_args()

    # Determine which QIDs to import
    qids_to_import = list(args.qids)
    if args.instances:
        print(f"Finding up to {args.limit} instances of {args.instances}...")
        instance_qids = get_instances(args.instances, args.limit)
        print(f"  Found: {instance_qids}")
        qids_to_import.extend(instance_qids)
        if args.instances not in qids_to_import:
            qids_to_import.insert(0, args.instances)

    if not qids_to_import:
        print("No QIDs specified. Usage:")
        print("  python import_wikidata.py Q8502 Q513")
        print("  python import_wikidata.py --instances Q8502 --limit 10")
        return

    # Load existing data
    items, index, emb = load_existing()
    existing_qids = {i["qid"] for i in items}

    # Step 1: Fetch full entities for new QIDs
    new_qids = [q for q in qids_to_import if q not in existing_qids]
    print(f"\n--- Step 1: Fetch full items ---")
    print(f"Requested: {len(qids_to_import)}, already imported: {len(qids_to_import) - len(new_qids)}, new: {len(new_qids)}")

    new_items = []
    for qid in new_qids:
        print(f"  Fetching {qid}...")
        entity = fetch_entity(qid)
        if entity and "missing" not in entity:
            item = process_entity(entity)
            new_items.append(item)
            print(f"    {item['label']}: {len(item['triples'])} triples, {len(item['aliases'])} aliases")
        else:
            print(f"    {qid}: missing/deleted, skipping")
        time.sleep(0.5)

    items.extend(new_items)
    existing_qids = {i["qid"] for i in items}

    # Step 2: Find and fetch linked QIDs + property IDs
    print(f"\n--- Step 2: Fetch linked QIDs and properties ---")
    linked = set()
    properties = set()
    for item in items:
        for t in item["triples"]:
            if t["value"]["type"] == "wikibase-item":
                linked.add(t["value"]["value"])
            properties.add(t["predicate"])
            # Also collect from qualifiers and sources
            for qual in t.get("qualifiers", []):
                if qual["value"]["type"] == "wikibase-item":
                    linked.add(qual["value"]["value"])
                properties.add(qual["predicate"])
            for src in t.get("sources", []):
                if src["value"]["type"] == "wikibase-item":
                    linked.add(src["value"]["value"])
                properties.add(src["predicate"])

    # Properties are entities too — fetch their labels+aliases
    all_needed = linked | properties
    unresolved = sorted(all_needed - existing_qids)
    print(f"Linked QIDs + properties needing labels: {len(unresolved)}")

    for i in range(0, len(unresolved), 50):
        batch = unresolved[i:i + 50]
        print(f"  Fetching batch {i // 50 + 1} ({len(batch)} items)...")
        entities = fetch_labels_batch(batch)

        for qid in batch:
            entity = entities.get(qid, {})
            if "missing" in entity:
                continue
            labels = entity.get("labels", {})
            label = labels.get("en", {}).get("value", qid)
            alias_list = entity.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]
            items.append({"qid": qid, "label": label, "aliases": aliases, "triples": []})

        time.sleep(1)

    # Step 3: Embed new texts
    print(f"\n--- Step 3: Generate embeddings ---")
    embedded_texts = {(e["qid"], e["text"]) for e in index}

    new_texts = []
    new_index_entries = []
    for item in items:
        key = (item["qid"], item["label"])
        if key not in embedded_texts:
            new_texts.append(item["label"])
            new_index_entries.append({"qid": item["qid"], "text": item["label"], "type": "label"})
            embedded_texts.add(key)

        for alias in item["aliases"]:
            key = (item["qid"], alias)
            if key not in embedded_texts:
                new_texts.append(alias)
                new_index_entries.append({"qid": item["qid"], "text": alias, "type": "alias"})
                embedded_texts.add(key)

    if new_texts:
        print(f"Embedding {len(new_texts)} new texts...")
        new_emb = embed_texts(new_texts)
        emb = np.vstack([emb, new_emb]) if emb.size > 0 else new_emb
        index.extend(new_index_entries)
        print(f"  Total embeddings: {emb.shape[0]}")
    else:
        print("No new texts to embed")

    # Step 4: Save data
    print(f"\n--- Step 4: Save ---")
    save_all(items, index, emb)

    # Step 5: Rebuild triples and trajectories
    print(f"\n--- Step 5: Compute triples and trajectories ---")
    triples_g = build_triples_graph(items)
    triples_g.serialize(str(DATA_DIR / "triples.nt"), format="nt")
    print(f"Triples: {len(triples_g)}")

    traj_g, traj_count = compute_trajectories_for_items(items, index, emb)
    traj_g.serialize(str(DATA_DIR / "trajectories.ttl"), format="turtle")
    print(f"Trajectories: {traj_count}")

    print(f"\n--- Done ---")
    print(f"Items: {len(items)}")
    print(f"Embeddings: {emb.shape[0]} x {emb.shape[1]}")
    print(f"RDF triples: {len(triples_g)}")
    print(f"Trajectories: {traj_count}")


if __name__ == "__main__":
    main()
