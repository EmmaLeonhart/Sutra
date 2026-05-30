"""Mirror the `corpus/` submodule to the Hugging Face dataset
EmmaLeonhart/sutra-w2c-corpus (Emma 2026-05-29: weights<->code corpus,
GitHub canonical, periodically pushed to HF).

Run AFTER regenerating the corpus (experiments/weight_to_code_corpus.py
writes into corpus/ by default) and committing + pushing the corpus/
submodule to GitHub. This is the "periodically saving onto Hugging Face"
step. Requires an HF token (HF_TOKEN env var or `huggingface-cli login`).

    py experiments/mirror_corpus_to_hf.py
"""
from __future__ import annotations

import os

from huggingface_hub import create_repo, upload_folder

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CORPUS_DIR = os.path.join(REPO, "corpus")
REPO_ID = "EmmaLeonhart/sutra-w2c-corpus"


def main() -> None:
    if not os.path.isdir(CORPUS_DIR):
        raise SystemExit(
            f"corpus submodule not found at {CORPUS_DIR}; run "
            "`git submodule update --init corpus` first."
        )
    create_repo(REPO_ID, repo_type="dataset", private=False, exist_ok=True)
    url = upload_folder(
        repo_id=REPO_ID,
        repo_type="dataset",
        folder_path=CORPUS_DIR,
        ignore_patterns=[".git", ".git/*", ".gitattributes"],
        commit_message="Mirror Sutra weights<->code corpus",
    )
    print(f"mirrored corpus/ -> https://huggingface.co/datasets/{REPO_ID}")
    print(f"  commit: {url}")


if __name__ == "__main__":
    main()
