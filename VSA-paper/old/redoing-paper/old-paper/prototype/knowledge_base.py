"""Curated corpus, query, and ground truth for the boiling-point demo.

The corpus contains 12 sentences:
  - 4 form a causal chain answering the query
  - 8 are high-similarity distractors that standard RAG will prefer
"""

# ── Corpus ────────────────────────────────────────────────────────────────────

CORPUS = [
    # --- Ground-truth chain (4 sentences) ---
    "Water boils at 100 degrees Celsius at standard atmospheric pressure.",          # C0
    "Atmospheric pressure decreases as altitude increases.",                          # C1
    "The summit of Mount Everest is approximately 8,849 meters above sea level.",     # C2
    "At high altitudes where atmospheric pressure is lower, "
    "water boils at a lower temperature, roughly 70 degrees Celsius on Everest.",     # C3

    # --- Distractors: topically similar, logically irrelevant ---
    "Mount Everest is located on the border between Nepal and Tibet.",                # C4
    "Water is composed of two hydrogen atoms and one oxygen atom.",                   # C5
    "The Dead Sea is the lowest point on Earth's surface.",                           # C6
    "Boiling is a phase transition from liquid to gas.",                              # C7
    "Edmund Hillary and Tenzing Norgay were the first to summit Everest in 1953.",    # C8
    "Pure water freezes at 0 degrees Celsius at standard pressure.",                  # C9
    "The atmospheric pressure at sea level is approximately 101.325 kPa.",            # C10
    "Mount Kilimanjaro is the highest peak in Africa.",                               # C11
]

# ── Query ─────────────────────────────────────────────────────────────────────

QUERY = "At what temperature does water boil on Mount Everest?"

# ── Ground truth ──────────────────────────────────────────────────────────────

# Indices into CORPUS that form the correct reasoning chain
GROUND_TRUTH_INDICES = [0, 1, 2, 3]

GROUND_TRUTH_CHAIN = [CORPUS[i] for i in GROUND_TRUTH_INDICES]

EXPECTED_ANSWER_KEYWORDS = ["70", "lower", "boil"]


def ground_truth_coverage(retrieved: list[str]) -> float:
    """Fraction of the 4 ground-truth sentences present in *retrieved*."""
    hits = sum(1 for gt in GROUND_TRUTH_CHAIN if gt in retrieved)
    return hits / len(GROUND_TRUTH_CHAIN)
