# Model Reproducibility Manifest

## mxbai-embed-large

- **Ollama tag:** `mxbai-embed-large:latest`
- **Ollama model ID:** `468836162de7`
- **GGUF blob SHA256:** `819c2adf5ce6df2b6bd2ae4ca90d2a69f060afeb438d0c171db57daa02e39c3d`
- **Size:** 669 MB (639 MB GGUF blob)
- **Embedding dimensions:** 1024
- **Architecture:** BERT-based, mixed-precision
- **Tokenizer:** WordPiece
- **Source:** mixedbread-ai/mxbai-embed-large-v1

## Retrieving the exact model

```bash
# Option 1: Pull from Ollama (may get newer version)
ollama pull mxbai-embed-large

# Option 2: Verify SHA256 matches
ollama show mxbai-embed-large --modelfile
# FROM line should reference blob ending in ...819c2adf5ce6df2b6bd2ae...
```

## Why this model is committed

This paper analyzes specific tokenizer and embedding behavior of this exact model version.
Results may not reproduce with a different model version. The GGUF weights are stored
via Git LFS in `model/mxbai-embed-large.gguf`.

## Model stored in this repo

The model blob is stored at `model/mxbai-embed-large.gguf` using Git LFS.
To restore after clone:
```bash
git lfs pull
```
