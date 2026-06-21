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
CMD ["python", "demos/gui/hero_server.py"]
