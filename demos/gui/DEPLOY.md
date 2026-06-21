# Deploying the self-optimizing-hero demo online

The warmer/colder hero (`hero_server.py` + `hero_page.html`) is a **dynamic** app:
the page needs a running Python backend that renders each frame on the Sutra
substrate. Static GitHub Pages cannot serve it — it needs a container/VM host.

## What it needs (small)

- Python 3.11+, `torch` (CPU is fine), `numpy`, `Pillow`. That's it.
- **No Ollama / embedding model:** `frame_hero.su` has zero `basis_vector` calls,
  so the render is pure substrate tensor ops.
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
