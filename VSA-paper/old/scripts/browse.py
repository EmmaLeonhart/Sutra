"""
Interactive browser for the embedding map data.
Shows triples as readable sentences with resolved labels.

Usage:
  python browse.py                  # list all full items
  python browse.py Q8502            # show all triples for an item
  python browse.py Q8502 --raw      # show raw triple data
  python browse.py --trajectories Q513 # show trajectories for an item
"""

import json
import sys
import io
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_data():
    with open(str(DATA_DIR / "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    # Build label lookup: QID/PID -> label
    labels = {}
    for item in items:
        labels[item["qid"]] = item["label"]

    # Also load properties if available
    try:
        with open(str(DATA_DIR / "properties.json"), "r", encoding="utf-8") as f:
            props = json.load(f)
        for pid, pdata in props.items():
            if pdata.get("label"):
                labels[pid] = pdata["label"]
    except FileNotFoundError:
        pass

    return items, labels


def resolve(val, labels):
    """Turn a value dict into a readable string."""
    if val["type"] == "wikibase-item":
        qid = val["value"]
        label = labels.get(qid, qid)
        return f"{label} ({qid})"
    elif val["type"] == "string":
        return f'"{val["value"]}"'
    elif val["type"] == "monolingualtext":
        return f'"{val["value"]}"@{val.get("language", "?")}'
    elif val["type"] == "quantity":
        return val["value"]
    elif val["type"] == "time":
        return val["value"]
    elif val["type"] == "coordinate":
        return f'{val["latitude"]:.4f}, {val["longitude"]:.4f}'
    else:
        return str(val.get("value", "?"))


def show_item(item, labels):
    """Print all triples for an item in readable form."""
    subj_label = labels.get(item["qid"], item["qid"])
    print(f"\n{'='*70}")
    print(f"{subj_label} ({item['qid']})")
    if item["aliases"]:
        print(f"Aliases: {', '.join(item['aliases'])}")
    print(f"{'='*70}")

    if not item["triples"]:
        print("  (linked-only item — no triples imported)")
        return

    # Group by predicate
    by_pred = {}
    for t in item["triples"]:
        by_pred.setdefault(t["predicate"], []).append(t)

    for pred_id in sorted(by_pred.keys()):
        triples = by_pred[pred_id]
        pred_label = labels.get(pred_id, pred_id)
        print(f"\n  {pred_label} ({pred_id}):")

        for t in triples:
            obj_str = resolve(t["value"], labels)
            rank_mark = "" if t["rank"] == "normal" else f" [{t['rank']}]"
            print(f"    → {obj_str}{rank_mark}")

            for qual in t.get("qualifiers", []):
                qual_label = labels.get(qual["predicate"], qual["predicate"])
                qual_val = resolve(qual["value"], labels)
                print(f"        ├─ {qual_label}: {qual_val}")

            for src in t.get("sources", []):
                src_label = labels.get(src["predicate"], src["predicate"])
                src_val = resolve(src["value"], labels)
                print(f"        └─ [source] {src_label}: {src_val}")


def list_items(items):
    """List all fully imported items."""
    full = [i for i in items if i["triples"]]
    linked = [i for i in items if not i["triples"]]

    print(f"\nFull items ({len(full)}):")
    for item in full:
        n_triples = len(item["triples"])
        n_aliases = len(item["aliases"])
        print(f"  {item['qid']:>10}  {item['label']:<30} {n_triples} triples, {n_aliases} aliases")

    print(f"\nLinked-only items: {len(linked)} (use --all to show)")


def main():
    parser = argparse.ArgumentParser(description="Browse embedding map data")
    parser.add_argument("qid", nargs="?", help="QID to inspect")
    parser.add_argument("--raw", action="store_true", help="Show raw JSON")
    parser.add_argument("--all", action="store_true", help="Show linked-only items too")
    args = parser.parse_args()

    items, labels = load_data()
    item_map = {i["qid"]: i for i in items}

    if args.qid:
        if args.qid in item_map:
            item = item_map[args.qid]
            if args.raw:
                print(json.dumps(item, indent=2, ensure_ascii=False))
            else:
                show_item(item, labels)
        else:
            print(f"Item {args.qid} not found in data")
    else:
        list_items(items)
        if args.all:
            linked = [i for i in items if not i["triples"]]
            print(f"\nLinked-only items ({len(linked)}):")
            for item in linked:
                print(f"  {item['qid']:>10}  {item['label']}")


if __name__ == "__main__":
    main()
