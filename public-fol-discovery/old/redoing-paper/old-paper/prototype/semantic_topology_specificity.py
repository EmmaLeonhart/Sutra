"""
Semantic Topology: Specificity x Sentence Complexity
=====================================================
X-axis: noun specificity (thing -> Mount Everest)
Y-axis: sentence complexity (bare noun -> complex sentence)

Tests whether specificity and complexity are independent linear
transformations in embedding space.
"""

import json, time, sys, os
import numpy as np
import ollama

# ── Configuration ──────────────────────────────────────────────
MODEL = "mxbai-embed-large"
OUTDIR = os.path.dirname(os.path.abspath(__file__))

# ── Axes ───────────────────────────────────────────────────────
# Origin: "thing" (maximally generic bare noun)
# X-axis: "thing" -> "Mount Everest" (specificity)
# Y-axis: "thing" -> "I love things because they are good" (sentence complexity)

# ── Specificity chains ────────────────────────────────────────
# Each chain: (chain_name, color, [(noun, plural_or_name, pronoun), ...])
# Ordered from generic -> mid -> specific within each chain

CHAINS = [
    ("Geography", "#e74c3c", [
        ("thing", "things", "they"),
        ("place", "places", "they"),
        ("mountain", "mountains", "they"),
        ("Mount Everest", "Mount Everest", "it"),
    ]),
    ("Animals", "#3498db", [
        ("thing", "things", "they"),
        ("creature", "creatures", "they"),
        ("dog", "dogs", "they"),
        ("golden retriever", "golden retrievers", "they"),
    ]),
    ("Food", "#2ecc71", [
        ("thing", "things", "they"),
        ("food", "food", "it"),
        ("pizza", "pizza", "it"),
        ("pepperoni pizza", "pepperoni pizza", "it"),
    ]),
    ("Cities", "#9b59b6", [
        ("thing", "things", "they"),
        ("place", "places", "they"),
        ("city", "cities", "they"),
        ("Tokyo", "Tokyo", "it"),
    ]),
    ("People", "#e67e22", [
        ("thing", "things", "they"),
        ("person", "people", "they"),
        ("scientist", "scientists", "they"),
        ("Albert Einstein", "Albert Einstein", "he"),
    ]),
    ("Vehicles", "#1abc9c", [
        ("thing", "things", "they"),
        ("vehicle", "vehicles", "they"),
        ("car", "cars", "they"),
        ("red Ferrari", "red Ferraris", "they"),
    ]),
    ("Buildings", "#e84393", [
        ("thing", "things", "they"),
        ("structure", "structures", "they"),
        ("tower", "towers", "they"),
        ("Eiffel Tower", "the Eiffel Tower", "it"),
    ]),
    ("Music", "#00b894", [
        ("thing", "things", "they"),
        ("instrument", "instruments", "they"),
        ("violin", "violins", "they"),
        ("Stradivarius violin", "Stradivarius violins", "they"),
    ]),
    ("Astronomy", "#6c5ce7", [
        ("thing", "things", "they"),
        ("celestial body", "celestial bodies", "they"),
        ("planet", "planets", "they"),
        ("Jupiter", "Jupiter", "it"),
    ]),
    ("Nature", "#fd79a8", [
        ("thing", "things", "they"),
        ("plant", "plants", "they"),
        ("flower", "flowers", "they"),
        ("Japanese cherry blossom", "Japanese cherry blossoms", "they"),
    ]),
]

# Complexity levels (templates applied to each noun)
def make_variants(noun, plural, pronoun):
    """Generate sentences at increasing complexity levels."""
    # Use plural for generic nouns, name for proper nouns
    love_target = plural if pronoun == "they" else noun
    be = "are" if pronoun == "they" else "is"
    make = "make" if pronoun == "they" else "makes"

    return [
        ("bare", noun),
        ("simple", f"I love {love_target}"),
        ("reason", f"I love {love_target} because {pronoun} {be} great"),
        ("extended", f"I love {love_target} because {pronoun} {be} great and {pronoun} {make} me happy every single day"),
    ]


# ── Embedding helpers ─────────────────────────────────────────
def embed_texts(texts, batch_size=100):
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = ollama.embed(model=MODEL, input=batch)
        all_vecs.extend(resp["embeddings"])
        if (i + batch_size) % 500 < batch_size:
            print(f"    {min(i+batch_size, len(texts))}/{len(texts)} embedded...")
    return np.array(all_vecs, dtype=np.float64)

def normalize(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ── Main ──────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("SEMANTIC TOPOLOGY: SPECIFICITY x COMPLEXITY")
    print("thing -> Mount Everest (specificity)")
    print("bare noun -> complex sentence (complexity)")
    print("=" * 60)

    # Step 1: Compute axes
    print("\n[1/4] Computing axes...")
    axis_texts = [
        "thing",
        "Mount Everest",
        "I love things because they are good",
    ]
    axis_vecs = embed_texts(axis_texts)
    v_origin = axis_vecs[0]
    spec_axis = normalize(axis_vecs[1] - v_origin)
    comp_axis = normalize(axis_vecs[2] - v_origin)
    dot = float(np.dot(spec_axis, comp_axis))
    print(f"  Axis orthogonality: dot = {dot:.4f}")

    # Check reference projections
    for name, vec in zip(axis_texts, axis_vecs):
        x = float(np.dot(vec - v_origin, spec_axis))
        y = float(np.dot(vec - v_origin, comp_axis))
        print(f"  {name:45s} ({x:+.4f}, {y:+.4f})")

    # Step 2: Build all items
    print("\n[2/4] Building items...")
    items = []  # (text, chain_name, chain_color, specificity_idx, complexity_level, noun)
    unique_texts = []
    text_to_idx = {}

    # Add reference points
    for name, vec in zip(axis_texts, axis_vecs):
        items.append({
            "text": name,
            "chain": "reference",
            "color": "#FFD700",
            "spec_idx": 0,
            "comp_level": "ref",
            "noun": name,
        })
        if name not in text_to_idx:
            text_to_idx[name] = len(unique_texts)
            unique_texts.append(name)

    # Add chain items
    for chain_name, chain_color, nouns in CHAINS:
        for spec_idx, (noun, plural, pronoun) in enumerate(nouns):
            variants = make_variants(noun, plural, pronoun)
            for comp_level, text in variants:
                items.append({
                    "text": text,
                    "chain": chain_name,
                    "color": chain_color,
                    "spec_idx": spec_idx,
                    "comp_level": comp_level,
                    "noun": noun,
                })
                if text not in text_to_idx:
                    text_to_idx[text] = len(unique_texts)
                    unique_texts.append(text)

    print(f"  {len(items)} items ({len(unique_texts)} unique texts)")

    # Step 3: Embed
    print("\n[3/4] Embedding...")
    t0 = time.time()
    embeddings = embed_texts(unique_texts)
    dt = time.time() - t0
    print(f"  Done in {dt:.1f}s ({dt/len(unique_texts)*1000:.1f}ms/item)")

    # Project onto axes
    for item in items:
        vec = embeddings[text_to_idx[item["text"]]]
        item["x"] = float(np.dot(vec - v_origin, spec_axis))
        item["y"] = float(np.dot(vec - v_origin, comp_axis))

    # Save results
    results_path = os.path.join(OUTDIR, "semantic_topology_specificity_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    np.savez_compressed(
        os.path.join(OUTDIR, "semantic_topology_specificity_embeddings.npz"),
        embeddings=embeddings, texts=unique_texts,
    )

    # Step 4: Analyze and plot
    print("\n[4/4] Analyzing...")

    # Print chain trajectories
    comp_levels = ["bare", "simple", "reason", "extended"]
    comp_markers = {"bare": "o", "simple": "s", "reason": "^", "extended": "D", "ref": "*"}

    for chain_name, chain_color, nouns in CHAINS:
        print(f"\n  {chain_name}:")
        chain_items = [it for it in items if it["chain"] == chain_name]
        for noun, _, _ in nouns:
            noun_items = [it for it in chain_items if it["noun"] == noun]
            for it in sorted(noun_items, key=lambda x: comp_levels.index(x["comp_level"])):
                label = it["text"][:50]
                print(f"    {it['comp_level']:10s} {label:50s} ({it['x']:+.3f}, {it['y']:+.3f})")

    # ── Plotting ──────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    # --- Plot 1: Chain trajectories ---
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.suptitle("Semantic Topology: Specificity x Sentence Complexity\n"
                 "(10 chains, 4 specificity levels x 4 complexity levels)",
                 fontsize=13, fontweight="bold")

    # Draw chain trajectories
    for chain_name, chain_color, nouns in CHAINS:
        chain_items = [it for it in items if it["chain"] == chain_name]

        # For each complexity level, draw horizontal line connecting specificity steps
        for cl in comp_levels:
            level_items = [it for it in chain_items if it["comp_level"] == cl]
            # Sort by specificity index
            level_items.sort(key=lambda x: x["spec_idx"])
            if len(level_items) > 1:
                xs = [it["x"] for it in level_items]
                ys = [it["y"] for it in level_items]
                ax.plot(xs, ys, color=chain_color, alpha=0.3, linewidth=1, zorder=1)

        # For each noun, draw vertical line connecting complexity levels
        for noun, _, _ in nouns:
            noun_items = [it for it in chain_items if it["noun"] == noun]
            noun_items.sort(key=lambda x: comp_levels.index(x["comp_level"]))
            if len(noun_items) > 1:
                xs = [it["x"] for it in noun_items]
                ys = [it["y"] for it in noun_items]
                ax.plot(xs, ys, color=chain_color, alpha=0.3, linewidth=1,
                        linestyle="--", zorder=1)

        # Plot points
        for it in chain_items:
            marker = comp_markers.get(it["comp_level"], "o")
            ax.scatter(it["x"], it["y"], c=chain_color, marker=marker,
                      s=60, zorder=3, edgecolors="white", linewidth=0.5)

    # Plot reference points
    ref_items = [it for it in items if it["chain"] == "reference"]
    for it in ref_items:
        ax.scatter(it["x"], it["y"], c="#FFD700", marker="*", s=200,
                  zorder=5, edgecolors="black", linewidth=1)
        ax.annotate(it["text"], (it["x"], it["y"]),
                   textcoords="offset points", xytext=(8, 8),
                   fontsize=8, fontweight="bold",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFD700",
                            alpha=0.8, edgecolor="black"))

    # Label some interesting non-reference points
    # Label the most specific items at highest complexity
    for chain_name, chain_color, nouns in CHAINS:
        # Label the most specific noun at "extended" complexity
        most_specific = nouns[-1][0]
        chain_items = [it for it in items if it["chain"] == chain_name
                      and it["noun"] == most_specific and it["comp_level"] == "bare"]
        if chain_items:
            it = chain_items[0]
            ax.annotate(most_specific, (it["x"], it["y"]),
                       textcoords="offset points", xytext=(5, -12),
                       fontsize=6.5, color=chain_color, alpha=0.8)

    # Legend for chains
    chain_handles = [Line2D([0], [0], color=c, linewidth=2, label=n)
                     for n, c, _ in CHAINS]
    # Legend for complexity markers
    marker_handles = [
        Line2D([0], [0], marker="o", color="grey", linestyle="None",
               markersize=7, label="Bare noun"),
        Line2D([0], [0], marker="s", color="grey", linestyle="None",
               markersize=7, label="I love X"),
        Line2D([0], [0], marker="^", color="grey", linestyle="None",
               markersize=7, label="I love X because..."),
        Line2D([0], [0], marker="D", color="grey", linestyle="None",
               markersize=7, label="I love X because... (extended)"),
        Line2D([0], [0], marker="*", color="#FFD700", linestyle="None",
               markersize=10, label="Reference point"),
    ]
    leg1 = ax.legend(handles=chain_handles, loc="upper left", fontsize=7,
                     title="Specificity chains", title_fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=marker_handles, loc="lower right", fontsize=7,
              title="Complexity level", title_fontsize=8)

    ax.set_xlabel("Specificity Axis (thing -> Mount Everest)", fontsize=11)
    ax.set_ylabel("Sentence Complexity Axis\n(thing -> I love things because they are good)",
                  fontsize=11)
    ax.grid(True, alpha=0.2)

    path1 = os.path.join(OUTDIR, "semantic_topology_specificity_trajectories.png")
    fig.savefig(path1, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"  Trajectory plot saved to {path1}")
    plt.close()

    # --- Plot 2: Grid view (mean positions by specificity x complexity) ---
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.suptitle("Mean Positions: Specificity x Complexity Grid\n"
                 "(averaged across all chains)", fontsize=13, fontweight="bold")

    # Compute mean position for each (spec_idx, comp_level) across chains
    # But only for non-"thing" items (since "thing" is shared across chains)
    grid_means = {}
    for spec_idx in range(4):
        for cl in comp_levels:
            matching = [it for it in items
                       if it["chain"] != "reference"
                       and it["spec_idx"] == spec_idx
                       and it["comp_level"] == cl]
            if matching:
                mx = np.mean([it["x"] for it in matching])
                my = np.mean([it["y"] for it in matching])
                sx = np.std([it["x"] for it in matching])
                sy = np.std([it["y"] for it in matching])
                grid_means[(spec_idx, cl)] = (mx, my, sx, sy, len(matching))

    spec_labels = ["Generic\n(thing/creature/...)", "Category\n(mountain/dog/...)",
                   "Type\n(car/violin/...)", "Specific\n(Mt Everest/Tokyo/...)"]
    comp_colors = {"bare": "#95a5a6", "simple": "#3498db",
                   "reason": "#e74c3c", "extended": "#8e44ad"}

    for cl in comp_levels:
        xs, ys = [], []
        for si in range(4):
            if (si, cl) in grid_means:
                mx, my, sx, sy, n = grid_means[(si, cl)]
                xs.append(mx)
                ys.append(my)
                # Error ellipse
                ax.errorbar(mx, my, xerr=sx, yerr=sy,
                           color=comp_colors[cl], alpha=0.3, capsize=3)
        if xs:
            ax.plot(xs, ys, color=comp_colors[cl], linewidth=2, alpha=0.7,
                   marker="o", markersize=8, label=cl, zorder=3)

    # Add grid labels
    for si in range(4):
        if (si, "bare") in grid_means:
            mx, my, _, _, _ = grid_means[(si, "bare")]
            ax.annotate(spec_labels[si], (mx, my),
                       textcoords="offset points", xytext=(0, -20),
                       fontsize=8, ha="center", color="#555")

    ax.legend(fontsize=9, title="Complexity level")
    ax.set_xlabel("Specificity Axis (thing -> Mount Everest)", fontsize=11)
    ax.set_ylabel("Sentence Complexity Axis", fontsize=11)
    ax.grid(True, alpha=0.2)

    path2 = os.path.join(OUTDIR, "semantic_topology_specificity_grid.png")
    fig.savefig(path2, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"  Grid plot saved to {path2}")
    plt.close()

    # --- Plot 3: Displacement arrows (bare -> extended for each chain) ---
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.suptitle("Specificity x Complexity Displacement\n"
                 "(arrows from bare noun to most complex sentence)",
                 fontsize=13, fontweight="bold")

    for chain_name, chain_color, nouns in CHAINS:
        chain_items = [it for it in items if it["chain"] == chain_name]
        for noun, _, _ in nouns:
            bare = [it for it in chain_items
                   if it["noun"] == noun and it["comp_level"] == "bare"]
            ext = [it for it in chain_items
                  if it["noun"] == noun and it["comp_level"] == "extended"]
            if bare and ext:
                b, e = bare[0], ext[0]
                ax.annotate("", xy=(e["x"], e["y"]), xytext=(b["x"], b["y"]),
                           arrowprops=dict(arrowstyle="->", color=chain_color,
                                         alpha=0.6, linewidth=1.5))
                ax.scatter(b["x"], b["y"], c=chain_color, s=40, zorder=3,
                          marker="o", edgecolors="white", linewidth=0.5)

    # Reference points
    for it in ref_items:
        ax.scatter(it["x"], it["y"], c="#FFD700", marker="*", s=200,
                  zorder=5, edgecolors="black", linewidth=1)
        ax.annotate(it["text"], (it["x"], it["y"]),
                   textcoords="offset points", xytext=(8, 8), fontsize=8,
                   fontweight="bold",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFD700",
                            alpha=0.8))

    # Legend
    chain_handles = [Line2D([0], [0], color=c, linewidth=2, label=n)
                     for n, c, _ in CHAINS]
    ax.legend(handles=chain_handles, loc="upper left", fontsize=7,
              title="Chains", title_fontsize=8)
    ax.set_xlabel("Specificity Axis (thing -> Mount Everest)", fontsize=11)
    ax.set_ylabel("Sentence Complexity Axis", fontsize=11)
    ax.grid(True, alpha=0.2)

    path3 = os.path.join(OUTDIR, "semantic_topology_specificity_arrows.png")
    fig.savefig(path3, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"  Arrows plot saved to {path3}")
    plt.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
