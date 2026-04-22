"""king - man + woman across multiple embedding substrates.

User ask (2026-04-22): test the classic analogy across several frozen
LLM embedding spaces to see where it works cleanly (queen wins) and
where it fails (king wins, or a near-neighbor like princess/monarch).
The thesis the user suspects: some substrates retain enough logical
structure to get the analogy right under naive arithmetic, others
collapse to the input vector.

This harness compiles `king_queen_naive.su` once per embedding model,
runs the analogy, and prints a side-by-side ranking. Ollama models
that were installed locally at 2026-04-22:

- nomic-embed-text  (768-dim, mean-centered default per CLAUDE.md)
- mxbai-embed-large (1024-dim — CLAUDE.md flags a diacritic defect,
  but the (king, queen, man, woman, …) vocabulary is ASCII, so the
  defect shouldn't apply; testing anyway to confirm)
- all-minilm        (384-dim, small/fast)

Models that are NOT embedding models (gemma3, llama*, deepseek) are
skipped — they are chat models, not embedders.

Usage: python examples/_king_queen_multi_substrate.py

The output includes the full candidate ranking for each substrate so
you can see not just whether queen wins, but by how much, and what
the near-neighbors look like. That's the interesting data — a narrow
queen-win on one substrate and a wide queen-win on another tell very
different stories about how much compositional structure the substrate
retains.
"""
from __future__ import annotations

import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen_numpy import translate_module, NumpyCodegen  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


# Known-installed embedding models as of 2026-04-22, with their native
# dims. Dim is passed so the runtime doesn't have to guess / truncate.
EMBEDDING_MODELS = [
    ("nomic-embed-text",    768),
    ("mxbai-embed-large",  1024),
    ("all-minilm",          384),
]


def compile_with_model(path: str, llm_model: str, dim: int) -> types.ModuleType:
    """Compile a .su file against a specific embedding backend.

    Passes llm_model + runtime_dim to NumpyCodegen so the generated
    module's _VSA instance uses the requested substrate. The rest of
    the compilation (lexer, parser, AST) is model-independent.
    """
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    cg = NumpyCodegen(llm_model=llm_model, runtime_dim=dim)
    py_src = cg.translate(module)
    mod = types.ModuleType(f"_kq_{llm_model.replace('-', '_')}")
    mod.__file__ = f"<{path} @ {llm_model}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def rank_candidates(mod, v: np.ndarray) -> list[tuple[str, float]]:
    """Return (name, cosine_score) sorted high-to-low for the full codebook."""
    names_and_vecs = [
        ("king",     mod.king),
        ("queen",    mod.queen),
        ("man",      mod.man),
        ("woman",    mod.woman),
        ("prince",   mod.prince),
        ("princess", mod.princess),
        ("boy",      mod.boy),
        ("girl",     mod.girl),
        ("ruler",    mod.ruler),
        ("monarch",  mod.monarch),
        ("husband",  mod.husband),
        ("wife",     mod.wife),
        ("father",   mod.father),
        ("mother",   mod.mother),
    ]
    out = []
    vn = np.linalg.norm(v) + 1e-12
    for nm, cv in names_and_vecs:
        cvn = np.linalg.norm(cv) + 1e-12
        s = float(np.dot(v, cv) / (vn * cvn))
        out.append((nm, s))
    out.sort(key=lambda x: -x[1])
    return out


def summarize(ranked: list[tuple[str, float]]) -> str:
    """One-line summary: winner, margin to 2nd place, did queen win?"""
    top, top_score = ranked[0]
    runner, runner_score = ranked[1]
    margin = top_score - runner_score
    # Find queen's rank
    queen_rank = next(i for i, (n, _) in enumerate(ranked) if n == "queen") + 1
    return (f"top={top:<9} ({top_score:+.3f})  "
            f"2nd={runner:<9} ({runner_score:+.3f})  "
            f"margin={margin:+.3f}  queen_rank={queen_rank}")


def print_ranking(title: str, ranked: list[tuple[str, float]]) -> None:
    print(f"\n  {title}:")
    for i, (nm, score) in enumerate(ranked, 1):
        mark = ""
        if nm == "queen":
            mark = "  <-- queen"
        elif nm == "king":
            mark = "  <-- king (input)"
        elif nm in ("man", "woman"):
            mark = f"  <-- {nm} (input)"
        print(f"    {i:2}. {nm:<10} cos={score:+.4f}{mark}")


def main() -> int:
    print("=" * 72)
    print("king - man + woman across multiple embedding substrates")
    print("=" * 72)
    print(f"Program: {os.path.basename(os.path.join(HERE, 'king_queen_naive.su'))}")
    print(f"Formula: argmax_cosine(bundle(displacement(king, man), woman), candidates)")
    print(f"Substrates: {', '.join(m for m, _ in EMBEDDING_MODELS)}")
    print()

    per_model_summary = []
    for model, dim in EMBEDDING_MODELS:
        print("-" * 72)
        print(f"Substrate: {model} (dim={dim})")
        print("-" * 72)
        try:
            mod = compile_with_model(
                os.path.join(HERE, "king_queen_naive.su"),
                llm_model=model,
                dim=dim,
            )
        except Exception as e:
            print(f"  FAILED to compile/load on {model}: {e}")
            per_model_summary.append((model, f"error: {type(e).__name__}: {e}"))
            continue

        v0 = mod.analogy  # bundle(displacement(king, man), woman), normalized
        ranked = rank_candidates(mod, v0)
        print_ranking(f"analogy vector ranked against 14 candidates (inputs included)",
                      ranked)

        # Also show the exclude-inputs variant (word2vec-benchmark convention)
        ranked_excl = [(n, s) for n, s in ranked if n not in {"king", "man", "woman"}]
        print_ranking(f"same, with (king, man, woman) excluded from candidates",
                      ranked_excl)

        per_model_summary.append((model, summarize(ranked)))

    # Final side-by-side summary
    print()
    print("=" * 72)
    print("Summary (full-candidate-pool, inputs included):")
    print("=" * 72)
    for model, summary in per_model_summary:
        print(f"  {model:<22}  {summary}")

    print()
    print("Interpretation:")
    print("- queen_rank=1 with a positive margin means the naive analogy works")
    print("  on that substrate without needing input-exclusion tricks.")
    print("- queen_rank=2 with king as top means the substrate has the known")
    print("  'input dominates result' failure mode. Input-exclusion (word2vec-")
    print("  benchmark convention) rescues queen in those cases.")
    print("- A narrow margin (<0.05) between top and 2nd is a fragile result —")
    print("  perturbation-sensitive. The Monte-Carlo attractor experiment")
    print("  (WIP, see todo.md) characterizes how robust each substrate's")
    print("  answer is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
