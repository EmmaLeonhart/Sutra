"""Migrate the weights<->code corpus from a flat CSV layout to per-seed
subdirectories (`s{seed}/...`), so no directory exceeds Hugging Face's
10000-files-per-directory limit (the flat 2x layout has 11520 CSVs in the
root; the HF mirror was rejected 2026-06-01).

For each programmatic entry in `corpus/corpus.jsonl`:
  - move `corpus/<base>.csv` -> `corpus/s<seed>/<base>.csv`
  - rewrite each weight's `csv` field  <base>  ->  s<seed>/<base>
  - rewrite the `source` token  load_matrix("<base>") -> load_matrix("s<seed>/<base>")

Idempotent: entries whose `csv` already contains "/" are skipped. The
matching generator change (weight_to_code_corpus.py) writes this layout
directly, so a fresh regen and this migration produce the same tree.
gemma_corpus.jsonl has no file-backed weights and is left untouched.

Run: python experiments/shard_corpus_to_subdirs.py [--corpus PATH]
Resolution is unchanged for consumers: prepare/eval/consistency all do
os.path.join(corpus_dir, csv), which resolves the subdir transparently.
"""
from __future__ import annotations

import argparse
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(REPO, "corpus"))
    a = ap.parse_args()
    jsonl = os.path.join(a.corpus, "corpus.jsonl")

    entries = [json.loads(l) for l in open(jsonl, encoding="utf-8")]
    moved = skipped = rewritten = 0
    for e in entries:
        subdir = f"s{e['seed']}"
        for w in e.get("weights", []):
            csv = w["csv"]
            if "/" in csv:           # already sharded
                skipped += 1
                continue
            new = f"{subdir}/{csv}"
            src_path = os.path.join(a.corpus, csv)
            dst_path = os.path.join(a.corpus, subdir, csv)
            os.makedirs(os.path.join(a.corpus, subdir), exist_ok=True)
            if os.path.exists(src_path):
                os.replace(src_path, dst_path)
                moved += 1
            elif not os.path.exists(dst_path):
                raise SystemExit(f"missing CSV for {w['csv']} (neither flat nor sharded)")
            # rewrite the source token + the csv field to the sharded path
            e["source"] = e["source"].replace(
                f'load_matrix("{csv}")', f'load_matrix("{new}")')
            w["csv"] = new
            rewritten += 1

    with open(jsonl, "w", encoding="utf-8", newline="\n") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    print(f"migrated {len(entries)} entries: moved={moved} csv-rewritten={rewritten} "
          f"already-sharded={skipped}")


if __name__ == "__main__":
    main()
