"""
Fetch all Wikidata properties and generate English sentence templates.
Each property gets one or more realization templates with $SUB/$OBJ slots.

Uses the Wikidata API to get property labels and descriptions,
then uses an LLM to generate natural English sentence templates.

Output: data/property_templates.json
"""

import json
import sys
import io
import os
import time
import requests
import ollama
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "embedding-mapping/0.1 (https://github.com/Immanuelle/embedding-mapping)"


def fetch_all_properties():
    """Fetch all Wikidata properties with English labels and descriptions."""
    properties = {}
    continuation = {}

    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": 120,  # Property namespace
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
            # Page title is like "Property:P31"
            pid = page["title"].replace("Property:", "")
            properties[pid] = {"pid": pid}

        if "continue" in data:
            continuation = data["continue"]
            print(f"  Fetched {len(properties)} properties so far...")
        else:
            break

        time.sleep(0.5)

    return properties


def fetch_property_labels_batch(pids):
    """Fetch English labels and descriptions for a batch of property IDs."""
    resp = requests.get(
        WIKIDATA_API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(pids),
            "props": "labels|descriptions|aliases",
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("entities", {})


def generate_realizations(pid, label, description, aliases):
    """Use LLM to generate English sentence templates for a property."""
    alias_str = f" (also known as: {', '.join(aliases)})" if aliases else ""
    desc_str = f" Description: {description}" if description else ""

    prompt = f"""Given this Wikidata property:
- ID: {pid}
- Label: "{label}"{alias_str}{desc_str}

Generate 1-3 natural English sentence templates that express this property as a relationship between a subject ($SUB) and object ($OBJ). Each template should be a different valid English phrasing.

Rules:
- Use $SUB for the subject entity and $OBJ for the object entity
- Keep templates simple and natural
- If the property is about a date, location, or quantity, phrase accordingly
- Output ONLY the templates, one per line, no numbering or bullets"""

    try:
        resp = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3},
        )
        text = resp.message.content.strip()
        # Parse lines, filter empty
        lines = [l.strip().lstrip("•-*0123456789. ") for l in text.split("\n") if l.strip()]
        # Filter lines that don't contain $SUB or $OBJ
        valid = [l for l in lines if "$SUB" in l and "$OBJ" in l]
        return valid if valid else [f"$SUB has {label} $OBJ"]
    except Exception as e:
        print(f"    LLM error for {pid}: {e}")
        return [f"$SUB has {label} $OBJ"]


def main():
    # Check for existing partial progress
    output_path = str(DATA_DIR / "property_templates.json")
    existing = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Resuming: {len(existing)} properties already done")

    # Step 1: Get all property IDs
    print("Fetching all Wikidata properties...")
    properties = fetch_all_properties()
    print(f"Found {len(properties)} properties")

    # Step 2: Fetch labels and descriptions in batches
    pids_to_fetch = sorted(properties.keys())
    print(f"\nFetching labels and descriptions...")

    for i in range(0, len(pids_to_fetch), 50):
        batch = pids_to_fetch[i:i + 50]
        entities = fetch_property_labels_batch(batch)

        for pid in batch:
            entity = entities.get(pid, {})
            if "missing" in entity:
                continue

            label = entity.get("labels", {}).get("en", {}).get("value", pid)
            description = entity.get("descriptions", {}).get("en", {}).get("value", "")
            alias_list = entity.get("aliases", {}).get("en", [])
            aliases = [a["value"] for a in alias_list]

            properties[pid]["label"] = label
            properties[pid]["description"] = description
            properties[pid]["aliases"] = aliases

        if (i // 50) % 10 == 0:
            print(f"  Labels fetched: {min(i + 50, len(pids_to_fetch))}/{len(pids_to_fetch)}")
        time.sleep(0.5)

    # Step 3: Generate realizations
    print(f"\nGenerating sentence templates...")
    templates = dict(existing)  # Start with existing progress

    pids_remaining = [p for p in sorted(properties.keys()) if p not in templates]
    print(f"Properties remaining: {len(pids_remaining)}")

    for idx, pid in enumerate(pids_remaining):
        prop = properties[pid]
        label = prop.get("label", pid)
        description = prop.get("description", "")
        aliases = prop.get("aliases", [])

        realizations = generate_realizations(pid, label, description, aliases)

        templates[pid] = {
            "label": label,
            "description": description,
            "aliases": aliases,
            "realizations": realizations,
        }

        if (idx + 1) % 50 == 0:
            print(f"  Generated: {idx + 1}/{len(pids_remaining)} ({pid}: {label})")
            # Save progress
            os.makedirs(str(DATA_DIR), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)

        time.sleep(0.1)  # Don't hammer Ollama

    # Final save
    os.makedirs(str(DATA_DIR), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(templates)} property templates to {output_path}")

    # Stats
    total_realizations = sum(len(t["realizations"]) for t in templates.values())
    print(f"Total realizations: {total_realizations}")
    print(f"Average per property: {total_realizations / len(templates):.1f}")

    # Show examples
    for pid in ["P31", "P17", "P279", "P625", "P2044"]:
        if pid in templates:
            t = templates[pid]
            print(f"\n  {pid} ({t['label']}):")
            for r in t["realizations"]:
                print(f"    {r}")


if __name__ == "__main__":
    main()
