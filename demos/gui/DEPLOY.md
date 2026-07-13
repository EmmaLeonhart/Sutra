# Deploying the self-optimizing-hero demo online

The warmer/colder hero (`hero_server.py` + `hero_page.html`) is a **dynamic** app:
the page needs a running Python backend that renders each frame on the Sutra
substrate. Static GitHub Pages cannot serve it — it needs a container/VM host.

## What it needs (small)

- Python 3.11+, `torch` (CPU is fine), `numpy`, `Pillow`. That's it —
  **when run with `--no-headline`** (which the Dockerfile now does by default).
- **No Ollama daemon needed.** The *frame* render (`frame_hero.su`) has zero
  `basis_vector` calls, so it is pure substrate tensor ops.
- **Caveat (corrected 2026-07-13):** the *headline* is separate from the frame.
  The default glyph headline is VSA-encoded and loads an in-process embedding
  model (`nomic-embed-text-v1.5`, ~hundreds of MB) via `sentence_transformers` —
  NOT part of torch. So the dependency-free claim holds **only with
  `--no-headline`** (headline shown as plain text). The container CMD uses
  `--no-headline`; without it, the image would need `sentence-transformers` +
  `transformers` installed and the model baked at build (`--warmup`), or it
  crashes at first render. Verified end-to-end from the funding-and-networking
  checkout on 2026-07-13.
- `sdk/sutra-compiler` is path-injected by `whole_frame.py` — nothing to install
  from the repo.
- The server reads `HOST`, `PORT`, `HERO_SIZE`, `HERO_SCALE` from env.

## Local container (verifies the deploy artifact)

```
docker build -t sutra-hero .          # from the Sutra repo root
docker run -p 8771:8771 sutra-hero    # open http://127.0.0.1:8771/
```

## Hosting options (all use the root Dockerfile)

- **Hugging Face Spaces (Docker SDK)** — recommended; free, torch-friendly, gives
  a public `*.hf.space` URL. Create a Space (SDK: Docker), push this repo's
  contents (or sync from GitHub); HF builds the Dockerfile and runs it. The Space
  `README.md` needs the HF front-matter (`sdk: docker`, `app_port: 8771`).
- **Render / Railway / Fly.io** — point at the GitHub repo, Docker build,
  expose `$PORT`. The Dockerfile already binds `0.0.0.0:$PORT`.
- **Any container host / Cloud Run** — `docker build` + run; set `$PORT` if the
  platform requires a specific port.

Link the resulting URL from `sutra.topazcomputing.com` / `topazcomputing.com`.

## Known limitation (v1)

`HeroBridge` holds a **single shared** steering state — every visitor steers the
same hero. Fine for a one-viewer demo (Emma driving, an investor watching, a
pilot founder trying it). For many simultaneous independent visitors, add
per-session isolation (a cookie → a capped dict of bridges with LRU eviction).
Substrate render is a few seconds per frame on CPU; "2-5 fps is plenty" per the
a1 spec.
