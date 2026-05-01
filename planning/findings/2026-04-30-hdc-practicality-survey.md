# Survey: practical I/O and language-ness in HDC implementations

**Date:** 2026-04-30
**Question:** Does Sutra's claim — "the only HDC implementation that
ships a practical end-to-end string-in / string-out path as a
built-in compiler concern" — hold up against the broader HDC
ecosystem?
**Answer:** Yes, but with the claim narrowed. The unique
combination is *programming language with compiler + HDC primitives
+ frozen LLM substrate + built-in string I/O*. No published peer
hits all four.

## Methodology

Surveyed the HDC / VSA software ecosystem via:

1. **Library peers** (TorchHD, OpenHD, HDTorch) — what their
   examples actually do.
2. **Compiler peers** — searched for "HDC compiler," "VSA
   compiler," "hyperdimensional programming language."
3. **HDC + frozen LLM** — papers combining HDC with pretrained
   embeddings.
4. **Cross-checked against the Heddes et al. 2022 TorchHD JMLR
   paper's related-work and the HDCC 2023 paper's related-work
   sections.**

PDFs cached in the gitignored `references/` directory:
`scallop.pdf`, `torchhd.pdf`, `hdcc.pdf`. Re-fetch with
`python scripts/fetch_reference_pdfs.py`.

## Findings by system

### TorchHD (Heddes et al. 2023)

A PyTorch library exposing VSA primitives (bind, bundle,
similarity) and four hypervector types (MAP, HRR, FHRR, BSC).

**Examples in `examples/` directory** (per the GitHub repo):

- `mnist.py`, `mnist_hugging_face.py`, `mnist_nonlinear.py` — digit
  classification
- `voicehd.py` — voice/audio classification
- `emg_hand_gestures.py` — EMG signal classification
- `language_recognition.py` — language ID classification
- `graphhd.py` — graph classification
- `UCI_benchmark_intRVFL.py` — UCI dataset benchmarks
- `classifiers.py`, `reghd.py` — generic classifier / regressor
- `hd_hashing.py` — hash table example
- `random_projection.py` — encoding technique
- `learning_with_hrr.py`, `fractional_power_encoding_kernels.ipynb`
  — encoding scheme tutorials

**Verdict:** All examples are classification or regression tasks.
The user constructs hypervectors (random or hash-derived) for
each input feature and maintains the mapping by hand. No string-in
/ string-out program. No built-in path from external strings to
hypervectors. This matches the TorchHD comparison currently in
`paper/paper.md` §2.1.

### HDCC (Verges, Heddes, Nunes, Givargis, Nicolau 2023)

The first HDC compiler. arXiv:2304.12398. Translates a
description-file format into self-contained C with multithreading
and SIMD.

**Critical detail — what the user writes:**

```
.NAME VOICEHD ;
.WEIGHT_EMBED (VALUE LEVEL 100);
.EMBEDDING (ID RANDOM 617);
.INPUT_DIM 617;
.ENCODING MULTIBUNDLE(BATCHBIND(ID, VALUE));
.CLASSES 27;
.DIMENSIONS 10240;
.TRAIN_SIZE 6238;
.TEST_SIZE 1559;
```

The "embeddings" in HDCC are **random or level hypervectors**, not
pretrained LLM embeddings. From the paper §III.B-D: the language
defines hypervectors via two initializations only, "random" and
"level," both sampled from the hyperspace. No frozen-substrate
support.

**Scope:** explicitly *classification only*. From the abstract:
"translates high-level descriptions of HDC classification methods
into optimized C code." The compiler emits associative-memory
training and cosine-similarity inference — there's no
general-purpose computation, no functional language, no loops, no
hash maps, no I/O beyond classify-this-feature-vector.

**Verdict:** A compiler, but for a narrow DSL aimed at embedded
classification. Not a general programming language. Not for
strings-in / strings-out. Not LLM-substrate.

### OpenHD (Kang et al., per HDCC's related work)

GPU-powered Python framework for HDC classification and
clustering, JIT-like compilation. Same scope as HDCC: classification
applications. Random hypervectors. Not a programming language.

### HDTorch (Genç et al., per HDCC's related work)

Python library with CUDA extensions. Classical and online HDC
learning. Same shape as TorchHD. Not a programming language.

### HDFLIM (arxiv 2602.23588) — HDC + frozen LLM, but not a language

Surfaced this one: HDFLIM does cross-modal alignment between
frozen vision and language foundation models using HDC binding
and bundling, projecting unimodal embeddings into a shared
hyperdimensional space. **This is HDC over frozen LLM
embeddings.** Not a programming language; an application
framework specifically for cross-modal alignment / image
captioning. Single-purpose, not a tool the user writes general
programs in.

This is the closest "HDC + frozen LLM" peer found. It validates
that the combination is a known idea — but as a research point
application, not as a language with a compiler.

### Hyperdimensional Probe (arxiv 2509.25045)

Uses VSA to decode LLM residual-stream activations into
interpretable concepts. Interpretability tool, not a language.

### PathHD (arxiv 2512.09369)

Encoder-free knowledge-graph reasoning combining HDC with a
single LLM call per query. Block-diagonal GHRR hypervectors for
relation paths. Application-specific framework, not a language.

## What Sutra is and the others aren't

Sutra is the unique combination of:

1. **Programming language with a compiler** — `.su` source files
   parse, type-check, lower to PyTorch tensor ops, and execute.
   General-purpose, not classification-specific.
2. **HDC primitives as the operation set** — bind, unbind, bundle,
   similarity, rotation, soft-halt RNN cells; the algebra is the
   computational substrate.
3. **Frozen LLM substrate** — `nomic-embed-text` (768-d,
   mean-centered), with the manifest letting users swap in any
   compatible substrate.
4. **Built-in string I/O** — `basis_vector("...")` and
   `embed("...")` embed strings to vectors at compile time;
   `_VSA.nearest_string(vector)` decodes any vector back to the
   nearest known label. No user-side codebook bookkeeping.

| System | Language? | HDC ops? | Frozen LLM? | Built-in I/O? |
|---|---|---|---|---|
| TorchHD | no (library) | yes | no | no |
| HDCC | yes (DSL) | yes | no (random) | no |
| OpenHD | no (Python framework) | yes | no | no |
| HDTorch | no (library) | yes | no | no |
| HDFLIM | no (app framework) | yes | yes | no |
| Hyperdim. Probe | no (probe) | yes | yes | no |
| PathHD | no (app framework) | yes | yes | no |
| **Sutra** | **yes (compiler)** | **yes** | **yes** | **yes** |

Sutra is the only entry that ticks all four columns. The
combination is the contribution; no individual axis is novel.

## Implications for the paper

The current paper claim — "the only HDC implementation that ships
a practical end-to-end string-in / string-out path as a built-in
compiler concern" — is defensible against this survey. But the
phrasing should make clear that:

1. **HDC + frozen LLM is not novel** (HDFLIM, PathHD,
   Hyperdimensional Probe).
2. **HDC compiler is not novel** (HDCC).
3. **HDC library with multiple binding schemes is not novel**
   (TorchHD).
4. **The integration of (compiler + HDC + frozen LLM + built-in
   I/O) into a single programming language is, to our knowledge,
   novel.**

If a reviewer pushes on "this is just HDC with extras," the
response is: HDCC ships a compiler but for random-hypervector
classification only; HDFLIM ships HDC over frozen LLMs but for a
single application, not as a language; Sutra is what you get
when you take both directions seriously and add an I/O codebook
that closes the program-shaped loop.

## Limitations of this survey

- Not exhaustive. The HDC literature is broad and growing fast.
  This survey hit the named library peers from the TorchHD JMLR
  paper plus the named compiler peer from the HDCC paper, plus
  three recent HDC + frozen-LLM papers found via search.
- Did not survey hardware-implementation HDC papers (HDC on FPGA,
  HDC on neuromorphic chips, etc.) since those are not language
  peers.
- Did not survey domain-specific HDC applications individually
  (HDC for genomics, HDC for tactile sensing, etc.); those use
  the same library / compiler tooling and don't introduce
  alternative *programming-language*-shaped artifacts.

The survey is sufficient to back the "to the authors' knowledge"
qualifier in the paper claim, but a more rigorous future-version
sweep should at minimum check each of: every paper citing
TorchHD, every paper citing HDCC, every recent ACL / EMNLP / ICLR
paper with "hyperdimensional" in the abstract.

## Re-fetch (script in repo)

```bash
python scripts/fetch_reference_pdfs.py --list      # see what's registered
python scripts/fetch_reference_pdfs.py             # fetch all
python scripts/fetch_reference_pdfs.py scallop     # fetch one
```

Adding a new reference: append to `REFERENCES` dict in the script
with `slug -> (canonical url, one-line description)`.
