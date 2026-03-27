"""
Fetch all Wikidata properties with English labels and aliases.
Creates simple propositional templates: "$SUB {label} $OBJ"
Plus one template per alias: "$SUB {alias} $OBJ"

This is a fundamental data file for probing the vector space,
not a database artifact.

Output: data/properties.json
"""

import json
import sys
import io
import os
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"


def fetch_all_property_ids():
    """Get all property IDs from Wikidata."""
    pids = []
    continuation = {}

    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": 120,
            "aplimit": 500,
            "format": "json",
        }
        params.update(continuation)

        resp = requests.get(
            WIKIDATA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for page in data["query"]["allpages"]:
            pid = page["title"].replace("Property:", "")
            pids.append(pid)

        if "continue" in data:
            continuation = data["continue"]
        else:
            break

        time.sleep(0.5)

    return sorted(pids)


def fetch_labels_batch(pids):
    """Fetch English labels and aliases for a batch of property IDs."""
    resp = requests.get(
        WIKIDATA_API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(pids),
            "props": "labels|aliases",
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("entities", {})


def main():
    print("Fetching all Wikidata property IDs...")
    pids = fetch_all_property_ids()
    print(f"Found {len(pids)} properties")

    properties = {}

    for i in range(0, len(pids), 50):
        batch = pids[i:i + 50]
        entities = fetch_labels_batch(batch)

        for pid in batch:
            entity = entities.get(pid, {})
            if "missing" in entity:
                continue

            label = entity.get("labels", {}).get("en", {}).get("value", "")
            alias_list = entity.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]

            # Build realizations: one for the label, one per alias
            realizations = []
            if label:
                realizations.append(f"$SUB {label} $OBJ")
            for alias in aliases:
                realizations.append(f"$SUB {alias} $OBJ")

            properties[pid] = {
                "label": label,
                "aliases": aliases,
                "realizations": realizations,
            }

        done = min(i + 50, len(pids))
        if done % 500 == 0 or done == len(pids):
            print(f"  {done}/{len(pids)} properties fetched")
        time.sleep(0.5)

    os.makedirs(str(DATA_DIR), exist_ok=True)
    with open(str(DATA_DIR / "properties.json"), "w", encoding="utf-8") as f:
        json.dump(properties, f, ensure_ascii=False, indent=2)

    total_realizations = sum(len(p["realizations"]) for p in properties.values())
    print(f"\nSaved {len(properties)} properties to data/properties.json")
    print(f"Total realizations: {total_realizations}")

    # Examples
    for pid in ["P31", "P17", "P279", "P625", "P2044", "P361"]:
        if pid in properties:
            p = properties[pid]
            print(f"\n  {pid} ({p['label']}):")
            for r in p["realizations"][:4]:
                print(f"    {r}")


if __name__ == "__main__":
    main()
