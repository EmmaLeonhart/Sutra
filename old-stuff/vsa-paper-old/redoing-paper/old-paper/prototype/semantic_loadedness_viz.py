"""Semantic Loadedness Visualization — 2D projection onto gender and "is cute" axes.

Constructs two interpretable axes in embedding space:
  Y-axis: gender direction  = normalize(v_woman - v_man)
  X-axis: "is cute" direction = average displacement from bare nouns to "X is cute" propositions

Then projects a diverse set of words and phrases onto this 2D plane to reveal
semantically overloaded, neurosymbolic, and underloaded regions.

Based on the brainstorming discussion in brainstorming/chatgpt.md.
"""

import json
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from prototype.pillar2_mapping import embed_texts


def normalize(v):
    """Normalize a vector to unit length."""
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-10 else v


def compute_gender_axis():
    """Compute gender direction: v_woman - v_man, normalized."""
    vecs = embed_texts(["woman", "man"])
    axis = vecs[0] - vecs[1]
    return normalize(axis)


def compute_cute_axis():
    """Compute "is cute" transformation axis.

    Average displacement from bare nouns to their "X is cute" propositions.
    This captures the semantic transformation of adding "is cute" to a concept.
    """
    # Use diverse nouns to get a robust "is cute" displacement
    nouns = ["cat", "dog", "baby", "flower", "bird", "rabbit", "frog", "rock"]
    bare = nouns
    propositions = [f"The {n} is cute" for n in nouns]

    bare_vecs = embed_texts(bare)
    prop_vecs = embed_texts(propositions)

    # Average displacement
    displacements = prop_vecs - bare_vecs
    mean_displacement = np.mean(displacements, axis=0)
    return normalize(mean_displacement)


def build_word_set():
    """Build a diverse set of words/phrases spanning the loadedness spectrum.

    Returns list of (label, text_to_embed, category) tuples.
    Categories: gendered, cute, neutral, abstract, proposition, complex
    """
    items = [
        # Gendered terms
        ("man", "man", "gendered"),
        ("woman", "woman", "gendered"),
        ("king", "king", "gendered"),
        ("queen", "queen", "gendered"),
        ("prince", "prince", "gendered"),
        ("princess", "princess", "gendered"),
        ("boy", "boy", "gendered"),
        ("girl", "girl", "gendered"),
        ("husband", "husband", "gendered"),
        ("wife", "wife", "gendered"),

        # Cute things
        ("puppy", "puppy", "cute"),
        ("kitten", "kitten", "cute"),
        ("baby", "baby", "cute"),
        ("bunny", "bunny", "cute"),
        ("duckling", "duckling", "cute"),
        ("teddy bear", "teddy bear", "cute"),

        # Neutral / underloaded
        ("rock", "rock", "neutral"),
        ("mountain", "mountain", "neutral"),
        ("desk", "desk", "neutral"),
        ("salt", "salt", "neutral"),
        ("concrete", "concrete", "neutral"),
        ("gravel", "gravel", "neutral"),
        ("thing", "thing", "neutral"),
        ("object", "object", "neutral"),

        # Abstract concepts
        ("justice", "justice", "abstract"),
        ("democracy", "democracy", "abstract"),
        ("entropy", "entropy", "abstract"),
        ("algorithm", "algorithm", "abstract"),

        # Simple propositions (neurosymbolic zone)
        ("The puppy is cute", "The puppy is cute", "proposition"),
        ("The kitten is cute", "The kitten is cute", "proposition"),
        ("The woman is cute", "The woman is cute", "proposition"),
        ("The man is strong", "The man is strong", "proposition"),
        ("The rock is heavy", "The rock is heavy", "proposition"),
        ("The queen is powerful", "The queen is powerful", "proposition"),

        # Complex / overloaded propositions
        ("De-icing salts applied\nto road surfaces",
         "De-icing salts applied to road surfaces cause corrosion of reinforced concrete bridge decks",
         "complex"),
        ("The adorable puppy\nchased the butterfly",
         "The adorable golden retriever puppy chased the iridescent butterfly through the sunlit meadow",
         "complex"),
        ("Monetary policy affects\ninflation expectations",
         "Central bank monetary policy decisions affect long-term inflation expectations through forward guidance mechanisms",
         "complex"),
        ("Mitochondrial DNA\nmutations cause disease",
         "Mitochondrial DNA mutations in the electron transport chain cause progressive neurodegenerative disease",
         "complex"),
    ]
    return items


def run_visualization():
    """Main visualization pipeline."""
    print("=" * 60)
    print("SEMANTIC LOADEDNESS VISUALIZATION")
    print("2D projection: gender axis × 'is cute' axis")
    print("=" * 60)

    # Step 1: Compute axes
    print("\n[1/4] Computing gender axis (v_woman - v_man)...")
    gender_axis = compute_gender_axis()

    print("[2/4] Computing 'is cute' transformation axis...")
    cute_axis = compute_cute_axis()

    # Check orthogonality
    dot = float(np.dot(gender_axis, cute_axis))
    print(f"  Axis orthogonality: dot product = {dot:.4f}")
    print(f"  (0 = perfectly orthogonal, ±1 = parallel)")

    # Step 2: Build and embed word set
    print("\n[3/4] Embedding word set...")
    items = build_word_set()
    texts = [item[1] for item in items]
    embeddings = embed_texts(texts)
    print(f"  Embedded {len(texts)} items")

    # Step 3: Project onto axes
    print("\n[4/4] Projecting onto 2D plane...")
    x_coords = embeddings @ cute_axis    # "is cute" axis
    y_coords = embeddings @ gender_axis  # gender axis

    # Collect results
    results = []
    for i, (label, text, category) in enumerate(items):
        results.append({
            "label": label,
            "text": text,
            "category": category,
            "x_cute": float(x_coords[i]),
            "y_gender": float(y_coords[i]),
        })

    # Print summary table
    print("\n" + "=" * 70)
    print(f"{'Label':<35} {'Cute':>8} {'Gender':>8}  Category")
    print("-" * 70)
    for r in sorted(results, key=lambda x: x["x_cute"], reverse=True):
        print(f"{r['label']:<35} {r['x_cute']:>8.4f} {r['y_gender']:>8.4f}  {r['category']}")

    # Save results
    results_path = os.path.join(os.path.dirname(__file__), "semantic_loadedness_results.json")
    with open(results_path, "w") as f:
        json.dump({
            "axis_dot_product": dot,
            "gender_axis_definition": "normalize(embed('woman') - embed('man'))",
            "cute_axis_definition": "mean displacement from nouns to 'The X is cute' propositions",
            "calibration_nouns": ["cat", "dog", "baby", "flower", "bird", "rabbit", "frog", "rock"],
            "items": results,
        }, f, indent=2)
    print(f"\nResults saved to {results_path}")

    # Step 4: Plot
    plot_2d(results, dot)

    return results


def plot_2d(results, axis_dot_product):
    """Generate 2D scatter plot with category coloring and labels."""

    category_colors = {
        "gendered": "#E74C3C",      # red
        "cute": "#FF69B4",          # pink
        "neutral": "#7F8C8D",       # gray
        "abstract": "#3498DB",      # blue
        "proposition": "#2ECC71",   # green
        "complex": "#9B59B6",       # purple
    }

    category_markers = {
        "gendered": "o",
        "cute": "s",
        "neutral": "D",
        "abstract": "^",
        "proposition": "P",
        "complex": "*",
    }

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))

    # Plot each category
    for cat in category_colors:
        cat_items = [r for r in results if r["category"] == cat]
        if not cat_items:
            continue
        xs = [r["x_cute"] for r in cat_items]
        ys = [r["y_gender"] for r in cat_items]
        ax.scatter(xs, ys,
                   c=category_colors[cat],
                   marker=category_markers[cat],
                   s=120,
                   label=cat.capitalize(),
                   edgecolors="black",
                   linewidths=0.5,
                   zorder=3)

    # Add labels with smart offsets to reduce overlap
    for r in results:
        # Offset based on position to reduce overlap
        x_off, y_off = 8, 6
        ha = "left"

        ax.annotate(r["label"],
                    (r["x_cute"], r["y_gender"]),
                    xytext=(x_off, y_off),
                    textcoords="offset points",
                    fontsize=7,
                    ha=ha,
                    alpha=0.85,
                    zorder=4)

    # Axis labels and title
    ax.set_xlabel('"Is Cute" Transformation Axis →\n(low = semantically generic, high = semantically loaded)',
                  fontsize=11)
    ax.set_ylabel('← Male          Gender Axis          Female →',
                  fontsize=11)
    ax.set_title('Semantic Loadedness: 2D Projection onto Gender × "Is Cute" Axes\n'
                 f'(mxbai-embed-large, 1024-dim; axis dot product = {axis_dot_product:.4f})',
                 fontsize=13, fontweight='bold')

    # Add region annotations
    x_range = ax.get_xlim()
    y_range = ax.get_ylim()

    # Legend
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # Grid
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(x=np.median([r["x_cute"] for r in results]),
               color='orange', linewidth=0.5, alpha=0.3, linestyle='--',
               label='Median cute score')

    plt.tight_layout()

    plot_path = os.path.join(os.path.dirname(__file__), "semantic_loadedness_plot.png")
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {plot_path}")
    plt.close()

    # Also create a zoomed version focused on the single words
    fig2, ax2 = plt.subplots(1, 1, figsize=(14, 10))

    single_words = [r for r in results if r["category"] != "complex" and r["category"] != "proposition"]

    for cat in category_colors:
        cat_items = [r for r in single_words if r["category"] == cat]
        if not cat_items:
            continue
        xs = [r["x_cute"] for r in cat_items]
        ys = [r["y_gender"] for r in cat_items]
        ax2.scatter(xs, ys,
                    c=category_colors[cat],
                    marker=category_markers[cat],
                    s=150,
                    label=cat.capitalize(),
                    edgecolors="black",
                    linewidths=0.5,
                    zorder=3)

    for r in single_words:
        ax2.annotate(r["label"],
                     (r["x_cute"], r["y_gender"]),
                     xytext=(10, 6),
                     textcoords="offset points",
                     fontsize=9,
                     ha="left",
                     alpha=0.9,
                     zorder=4)

    ax2.set_xlabel('"Is Cute" Transformation Axis →', fontsize=11)
    ax2.set_ylabel('← Male          Gender Axis          Female →', fontsize=11)
    ax2.set_title('Single Words Only: Gender × "Is Cute" Projection\n'
                  '(mxbai-embed-large, 1024-dim)',
                  fontsize=13, fontweight='bold')
    ax2.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)

    plt.tight_layout()

    plot_path2 = os.path.join(os.path.dirname(__file__), "semantic_loadedness_words_only.png")
    plt.savefig(plot_path2, dpi=150, bbox_inches="tight")
    print(f"Zoomed plot saved to {plot_path2}")
    plt.close()


if __name__ == "__main__":
    run_visualization()
