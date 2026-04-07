"""
Fetch mountain (Q8502) + 10 instance mountains from Wikidata.
For each item: get QID, English label, English aliases, and ALL properties as triples.
Triples reference other items by QID without needing to import those items.
Saves to data/items.json
"""

import json
import os
import sys
import io
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"


def wikidata_api_get(qid):
    """Fetch a single Wikidata item via the API (more reliable than SPARQL for full items)."""
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
    return resp.json()["entities"][qid]


def get_10_mountains():
    """Get 10 well-known mountains via SPARQL."""
    query = """
SELECT ?item WHERE {
  ?item wdt:P31 wd:Q8502 .
  ?item wikibase:sitelinks ?sitelinks .
}
ORDER BY DESC(?sitelinks)
LIMIT 10
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
        return {"type": "monolingualtext", "value": dv["value"]["text"], "language": dv["value"]["language"]}
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

    # English label
    labels = entity.get("labels", {})
    label = labels.get("en", {}).get("value", qid)

    # English aliases
    alias_list = entity.get("aliases", {}).get("en", [])
    aliases = [a["value"] for a in alias_list]

    # All claims as triples: (qid, property, value)
    triples = []
    for prop_id, claim_list in entity.get("claims", {}).items():
        for claim in claim_list:
            mainsnak = claim.get("mainsnak", {})
            if mainsnak:
                val = extract_value(mainsnak)
                triples.append({
                    "subject": qid,
                    "predicate": prop_id,
                    "value": val,
                    "rank": claim.get("rank", "normal"),
                })

    return {
        "qid": qid,
        "label": label,
        "aliases": aliases,
        "triples": triples,
    }


def main():
    # Get the 10 most notable mountains
    print("Finding 10 most notable mountains...")
    mountain_qids = get_10_mountains()
    print(f"  Got: {mountain_qids}")

    # Add Q8502 (mountain class itself)
    all_qids = ["Q8502"] + mountain_qids
    print(f"\nFetching {len(all_qids)} items: Q8502 + {len(mountain_qids)} mountains")

    items = []
    for qid in all_qids:
        print(f"  Fetching {qid}...")
        entity = wikidata_api_get(qid)
        item = process_entity(entity)
        items.append(item)
        print(f"    {item['label']}: {len(item['triples'])} triples, {len(item['aliases'])} aliases")
        time.sleep(0.5)

    os.makedirs(str(DATA_DIR), exist_ok=True)
    out_path = str(DATA_DIR / "items.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    total_triples = sum(len(i["triples"]) for i in items)
    print(f"\nSaved {len(items)} items ({total_triples} total triples) to {out_path}")


if __name__ == "__main__":
    main()
