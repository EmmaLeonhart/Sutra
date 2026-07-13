# Container for the warmer/colder self-optimizing-hero demo
# (demos/gui/hero_server.py — the a1 demo's "live page at a URL").
#
# The hero render is pure substrate tensor ops: frame_hero.su has ZERO
# basis_vector calls, so it needs only Python + numpy + torch (CPU) + Pillow.
# NO Ollama / embedding model at runtime. sdk/sutra-compiler is path-injected by
# whole_frame.py, so there is nothing to pip-install from the repo.
#
# Build context = repo root.
#   docker build -t sutra-hero .
#   docker run -p 8771:8771 sutra-hero        # open http://127.0.0.1:8771/
#
# Cloud platforms set $PORT; the server reads HOST/PORT (and HERO_SIZE/HERO_SCALE)
# from env. The image defaults HOST=0.0.0.0 so it is reachable in a container.
FROM python:3.12-slim

WORKDIR /app

# CPU-only torch (no CUDA) keeps the image to a sane size. Installed from the
# pytorch CPU index; numpy + Pillow from PyPI.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.1" \
 && pip install --no-cache-dir "numpy>=1.26" "Pillow>=10"

COPY . /app

ENV HOST=0.0.0.0 \
    PORT=8771 \
    HERO_SIZE=48 \
    HERO_SCALE=9 \
    PYTHONUNBUFFERED=1

EXPOSE 8771
# --no-headline is REQUIRED here: the default glyph headline is VSA-encoded and
# loads an in-process embedding model via `from sentence_transformers import
# SentenceTransformer` (sdk/sutra-compiler/.../embedding.py) — a package this
# image deliberately does NOT install (see the torch/numpy/Pillow-only pip step
# and the "NO embedding model at runtime" note above). Without --no-headline the
# container crashes at first frame render with ModuleNotFoundError. --no-headline
# renders the headline as plain text and keeps the image truly dependency-free.
# To ship the richer glyph headline instead, add "sentence-transformers" +
# "transformers" to the pip install AND bake the model at build with a
# `RUN python demos/gui/hero_server.py --warmup` layer, then drop --no-headline.
# (Verified 2026-07-13 from the funding-and-networking checkout: default CMD hit
# the sentence_transformers import; --no-headline serves cleanly and one SPSA
# step morphs the frame.)
CMD ["python", "demos/gui/hero_server.py", "--no-headline"]
