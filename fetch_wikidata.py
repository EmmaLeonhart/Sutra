"""
Fetch all instances of mountain (Q8502) from Wikidata.
Gets English labels and all English aliases for each entity.
Uses POST requests and pagination. Saves to data/mountains.json
"""

import json
import os
import sys
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"
BATCH_SIZE = 5000
MAX_RETRIES = 3


def sparql_query(query):
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                SPARQL_ENDPOINT,
                data={"query": query},
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/sparql-results+json",
                },
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 10 * (attempt + 1)
                print(f"  Retry {attempt+1}/{MAX_RETRIES} in {wait}s... ({e.__class__.__name__})")
                time.sleep(wait)
            else:
                raise


def fetch_labels():
    """Fetch QID + English label for all mountains, paginated."""
    mountains = {}
    offset = 0

    while True:
        query = f"""
SELECT ?item ?itemLabel WHERE {{
  ?item wdt:P31 wd:Q8502 .
  ?item rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "en")
}}
ORDER BY ?item
LIMIT {BATCH_SIZE}
OFFSET {offset}
"""
        print(f"Fetching labels at offset {offset}...")
        bindings = sparql_query(query)
        print(f"  Got {len(bindings)} results")

        for b in bindings:
            qid = b["item"]["value"].split("/")[-1]
            label = b["itemLabel"]["value"]
            mountains[qid] = {"qid": qid, "label": label, "aliases": []}

        if len(bindings) < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        time.sleep(3)

    return mountains


def fetch_aliases(mountains):
    """Fetch English aliases for all mountains, paginated."""
    offset = 0

    while True:
        query = f"""
SELECT ?item ?alias WHERE {{
  ?item wdt:P31 wd:Q8502 .
  ?item skos:altLabel ?alias .
  FILTER(LANG(?alias) = "en")
}}
ORDER BY ?item
LIMIT {BATCH_SIZE}
OFFSET {offset}
"""
        print(f"Fetching aliases at offset {offset}...")
        bindings = sparql_query(query)
        print(f"  Got {len(bindings)} results")

        for b in bindings:
            qid = b["item"]["value"].split("/")[-1]
            alias = b["alias"]["value"]
            if qid in mountains:
                mountains[qid]["aliases"].append(alias)

        if len(bindings) < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        time.sleep(3)

    return mountains


def main():
    mountains = fetch_labels()
    print(f"\nGot {len(mountains)} mountains with labels")

    fetch_aliases(mountains)
    alias_count = sum(1 for m in mountains.values() if m["aliases"])
    print(f"{alias_count} mountains have aliases")

    result = list(mountains.values())

    os.makedirs("data", exist_ok=True)
    out_path = "data/mountains.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(result)} mountains to {out_path}")

    for m in result[:5]:
        aliases_str = ", ".join(m["aliases"][:3]) if m["aliases"] else "(none)"
        print(f"  {m['qid']}: {m['label']} — aliases: {aliases_str}")


if __name__ == "__main__":
    main()
