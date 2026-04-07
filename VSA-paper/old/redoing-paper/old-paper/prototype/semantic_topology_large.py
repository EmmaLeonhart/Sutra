"""Large-scale Semantic Topology — 500 common nouns × 6 variants.

Embeds the 500 most common English nouns plus adjective-modified forms:
  - bare noun: "dog"
  - "powerful dog"
  - "strong dog"
  - "cute dog"
  - "adorable dog"
  - "beautiful dog"

Total: 3,000 embeddings projected onto the gender × cute modifier axes.
Builds Voronoi tessellation from an unbiased frequency-ranked sample
rather than hand-picked items.
"""

import json
import sys
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.colors as mcolors
from scipy.spatial import Voronoi
from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EMBED_MODEL = "mxbai-embed-large"
ADJECTIVES = ["powerful", "strong", "cute", "adorable", "beautiful"]


def normalize(v):
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-10 else v


def embed_batch(texts, batch_size=100):
    """Embed texts in batches for speed."""
    import ollama
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = ollama.embed(model=EMBED_MODEL, input=batch)
        all_vecs.extend(resp["embeddings"])
        if (i // batch_size) % 5 == 0:
            print(f"    {i+len(batch)}/{len(texts)} embedded...")
    return np.array(all_vecs, dtype=np.float32)


def get_common_nouns(n=500):
    """Get the N most common English nouns using wordfreq + NLTK POS tagging."""
    from wordfreq import top_n_list
    from nltk import pos_tag
    import nltk
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)

    # Get a large pool, then filter for nouns
    words = top_n_list('en', 8000)

    # POS tag in isolation — nouns get tagged NN/NNS
    tagged = pos_tag(words)

    # Filter: must be tagged as noun, length > 2, alphabetic only,
    # and not obviously a verb/adjective that gets mistagged
    verb_blocklist = {
        'get', 'look', 'feel', 'give', 'run', 'set', 'let', 'put',
        'show', 'try', 'ask', 'turn', 'start', 'call', 'keep', 'hold',
        'bring', 'happen', 'write', 'provide', 'sit', 'stand', 'lose',
        'pay', 'meet', 'include', 'continue', 'learn', 'change', 'lead',
        'understand', 'watch', 'follow', 'stop', 'create', 'speak',
        'read', 'spend', 'grow', 'open', 'walk', 'win', 'offer',
        'remember', 'consider', 'appear', 'buy', 'wait', 'serve',
        'die', 'send', 'build', 'stay', 'fall', 'cut', 'reach',
        'kill', 'remain', 'suggest', 'raise', 'pass', 'sell', 'require',
        'report', 'pull', 'return', 'explain', 'hope', 'develop',
        'carry', 'break', 'receive', 'agree', 'support', 'hit',
        'produce', 'eat', 'cover', 'catch', 'draw', 'choose',
        'cause', 'wish', 'drop', 'plan', 'push', 'act',
        'something', 'everything', 'nothing', 'anything', 'someone',
    }

    nouns = []
    seen = set()
    for w, tag in tagged:
        if not tag.startswith('NN'):
            continue
        if len(w) <= 2 or not w.isalpha():
            continue
        if w.lower() in verb_blocklist:
            continue
        # Skip plurals if we already have the singular
        base = w.rstrip('s')
        if base in seen and w != base:
            continue
        if w not in seen:
            nouns.append(w)
            seen.add(w)
        if len(nouns) >= n:
            break

    return nouns


def compute_axes():
    """Compute gender and cute modifier axes."""
    from prototype.pillar2_mapping import embed_texts

    gender_vecs = embed_texts(["woman", "man"])
    gender_axis = normalize(gender_vecs[0] - gender_vecs[1])

    cute_vecs = embed_texts(["cute woman", "woman"])
    cute_axis = normalize(cute_vecs[0] - cute_vecs[1])

    dot = float(np.dot(gender_axis, cute_axis))
    print(f"  Axis orthogonality: dot = {dot:.4f}")
    return gender_axis, cute_axis


def voronoi_finite_polygons_2d(vor, bbox):
    """Reconstruct Voronoi regions clipped to bounding box using Shapely."""
    x_min, y_min, x_max, y_max = bbox
    clip_box = shapely_box(x_min, y_min, x_max, y_max)
    center = vor.points.mean(axis=0)
    radius = max(x_max - x_min, y_max - y_min) * 4

    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    polygons = []
    for p_idx in range(len(vor.points)):
        region_idx = vor.point_region[p_idx]
        vertices = vor.regions[region_idx]

        if not vertices:
            polygons.append(np.array([]))
            continue

        if all(v >= 0 for v in vertices):
            poly_coords = vor.vertices[vertices]
            try:
                sp = ShapelyPolygon(poly_coords)
                clipped = sp.intersection(clip_box)
                if clipped.is_empty or clipped.geom_type != 'Polygon':
                    polygons.append(np.array([]))
                else:
                    polygons.append(np.array(clipped.exterior.coords[:-1]))
            except Exception:
                polygons.append(np.array([]))
            continue

        ridges = all_ridges.get(p_idx, [])
        finite_verts = [v for v in vertices if v >= 0]
        new_vertices_list = [vor.vertices[v].tolist() for v in finite_verts]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue
            t = vor.points[p2] - vor.points[p_idx]
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])
            midpoint = vor.points[[p_idx, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius
            new_vertices_list.append(far_point.tolist())

        if len(new_vertices_list) < 3:
            polygons.append(np.array([]))
            continue

        vs = np.array(new_vertices_list)
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
        vs = vs[np.argsort(angles)]

        try:
            sp = ShapelyPolygon(vs)
            if not sp.is_valid:
                sp = sp.buffer(0)
            clipped = sp.intersection(clip_box)
            if clipped.is_empty or clipped.geom_type != 'Polygon':
                polygons.append(np.array([]))
            else:
                polygons.append(np.array(clipped.exterior.coords[:-1]))
        except Exception:
            polygons.append(np.array([]))

    return polygons


def run():
    print("=" * 60)
    print("LARGE-SCALE SEMANTIC TOPOLOGY")
    print("500 nouns x 6 variants = 3,000 embeddings")
    print("=" * 60)

    # Step 1: Get nouns
    print("\n[1/5] Getting 500 most common English nouns...")
    nouns = get_common_nouns(500)
    print(f"  Got {len(nouns)} nouns")
    print(f"  First 20: {nouns[:20]}")
    print(f"  Last 10: {nouns[-10:]}")

    # Step 2: Build all text variants
    print("\n[2/5] Building text variants...")
    items = []  # (label, text, category)
    for noun in nouns:
        items.append((noun, noun, "bare"))
        for adj in ADJECTIVES:
            items.append((f"{adj} {noun}", f"{adj} {noun}", adj))

    texts = [item[1] for item in items]
    print(f"  {len(texts)} total items to embed")

    # Step 3: Compute axes
    print("\n[3/5] Computing projection axes...")
    gender_axis, cute_axis = compute_axes()

    # Step 4: Embed everything
    print(f"\n[4/5] Embedding {len(texts)} items in batches of 100...")
    t0 = time.time()
    embeddings = embed_batch(texts, batch_size=100)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s ({elapsed/len(texts)*1000:.1f}ms/item)")

    # Project onto axes
    x_coords = embeddings @ cute_axis
    y_coords = embeddings @ gender_axis
    points = np.column_stack([x_coords, y_coords])

    # Save embeddings for reuse
    npz_path = os.path.join(os.path.dirname(__file__), "semantic_topology_large_embeddings.npz")
    np.savez_compressed(npz_path, embeddings=embeddings, x=x_coords, y=y_coords)
    print(f"  Embeddings saved to {npz_path}")

    # Build results
    results = []
    for i, (label, text, category) in enumerate(items):
        results.append({
            "label": label,
            "text": text,
            "category": category,
            "x_cute": float(x_coords[i]),
            "y_gender": float(y_coords[i]),
        })

    results_path = os.path.join(os.path.dirname(__file__), "semantic_topology_large_results.json")
    with open(results_path, "w") as f:
        json.dump({"n_nouns": len(nouns), "n_items": len(items), "items": results}, f, indent=2)
    print(f"  Results saved to {results_path}")

    # Step 5: Analyze and plot
    print("\n[5/5] Analyzing and plotting...")
    analyze_by_category(results)
    analyze_adjective_displacement(results, nouns)
    plot_topology(results, points, len(nouns))


def analyze_by_category(results):
    """Print statistics by category (bare noun vs each adjective)."""
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"x": [], "y": []}
        categories[cat]["x"].append(r["x_cute"])
        categories[cat]["y"].append(r["y_gender"])

    print(f"\n{'Category':<15} {'Count':>6} {'Mean X':>8} {'Std X':>8} {'Mean Y':>8} {'Std Y':>8}")
    print("-" * 60)
    for cat in ["bare"] + ADJECTIVES:
        if cat not in categories:
            continue
        xs = categories[cat]["x"]
        ys = categories[cat]["y"]
        print(f"{cat:<15} {len(xs):>6} {np.mean(xs):>8.4f} {np.std(xs):>8.4f} "
              f"{np.mean(ys):>8.4f} {np.std(ys):>8.4f}")


def analyze_adjective_displacement(results, nouns):
    """Analyze how each adjective shifts nouns along the axes."""
    # Build lookup: noun -> {category -> (x, y)}
    lookup = {}
    for r in results:
        noun = r["text"].split(" ", 1)[-1] if r["category"] != "bare" else r["text"]
        if noun not in lookup:
            lookup[noun] = {}
        lookup[noun][r["category"]] = (r["x_cute"], r["y_gender"])

    print(f"\n--- Mean adjective displacement from bare noun ---")
    print(f"{'Adjective':<15} {'dX (cute)':>10} {'dY (gender)':>10} {'|d|':>8}")
    print("-" * 48)

    for adj in ADJECTIVES:
        dx_list, dy_list = [], []
        for noun in nouns:
            if noun in lookup and "bare" in lookup[noun] and adj in lookup[noun]:
                bx, by = lookup[noun]["bare"]
                ax, ay = lookup[noun][adj]
                dx_list.append(ax - bx)
                dy_list.append(ay - by)
        if dx_list:
            mean_dx = np.mean(dx_list)
            mean_dy = np.mean(dy_list)
            magnitude = np.sqrt(mean_dx**2 + mean_dy**2)
            print(f"{adj:<15} {mean_dx:>+10.4f} {mean_dy:>+10.4f} {magnitude:>8.4f}")


def plot_topology(results, points, n_nouns):
    """Generate Voronoi plots — one by category, one heatmap."""
    x_min = points[:, 0].min() - 0.05
    x_max = points[:, 0].max() + 0.05
    y_min = points[:, 1].min() - 0.05
    y_max = points[:, 1].max() + 0.05
    bbox = (x_min, y_min, x_max, y_max)

    print(f"  Computing Voronoi for {len(points)} points...")
    vor = Voronoi(points)
    polygons = voronoi_finite_polygons_2d(vor, bbox)

    cell_areas = []
    for poly in polygons:
        if len(poly) < 3:
            cell_areas.append(0.0)
        else:
            cell_areas.append(float(ShapelyPolygon(poly).area))
    cell_areas = np.array(cell_areas)

    n_valid = np.sum(cell_areas > 0)
    print(f"  {n_valid}/{len(results)} cells reconstructed")

    category_colors = {
        "bare":      "#333333",
        "powerful":  "#C0392B",
        "strong":    "#E67E22",
        "cute":      "#FF69B4",
        "adorable":  "#FF1493",
        "beautiful": "#9B59B6",
    }

    # === PLOT 1: Category-colored Voronoi ===
    fig, ax = plt.subplots(1, 1, figsize=(20, 14))

    for i, polygon in enumerate(polygons):
        if len(polygon) < 3:
            continue
        cat = results[i]["category"]
        color = category_colors.get(cat, "#CCCCCC")
        rgba = list(mcolors.to_rgba(color))
        rgba[3] = 0.25

        poly_patch = MplPolygon(polygon, closed=True,
                                facecolor=rgba,
                                edgecolor="white",
                                linewidth=0.3)
        ax.add_patch(poly_patch)

    # Only label bare nouns (too many items to label all)
    for i, r in enumerate(results):
        if r["category"] == "bare":
            ax.plot(r["x_cute"], r["y_gender"], ".",
                    color="#333333", markersize=1.5, zorder=5)
            # Only label every 10th noun to avoid overcrowding
            if i % 60 == 0:  # every 10th bare noun (bare = every 6th item)
                ax.annotate(r["label"],
                            (r["x_cute"], r["y_gender"]),
                            xytext=(3, 3), textcoords="offset points",
                            fontsize=5, alpha=0.7, zorder=6)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel('"Cute" Modifier Axis (woman -> cute woman)\n'
                  '(low = semantically generic, high = semantically loaded)', fontsize=11)
    ax.set_ylabel('<-- Male          Gender Axis          Female -->', fontsize=11)
    ax.set_title(f'Semantic Topology: {n_nouns} Common Nouns x 6 Variants ({len(results)} total)\n'
                 f'(mxbai-embed-large 1024-dim, Voronoi on gender x cute modifier)',
                 fontsize=13, fontweight='bold')

    handles = [plt.Line2D([0], [0], marker='s', color='w',
               markerfacecolor=category_colors[c], markersize=10, label=c.capitalize())
               for c in ["bare"] + ADJECTIVES]
    ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.9)
    plt.tight_layout()

    path1 = os.path.join(os.path.dirname(__file__), "semantic_topology_large_full.png")
    plt.savefig(path1, dpi=150, bbox_inches="tight")
    print(f"  Category plot saved to {path1}")
    plt.close()

    # === PLOT 2: Area heatmap ===
    fig2, ax2 = plt.subplots(1, 1, figsize=(20, 14))

    valid_areas = cell_areas[cell_areas > 0]
    if len(valid_areas) > 0:
        log_areas = np.log10(valid_areas + 1e-8)
        norm = plt.Normalize(vmin=log_areas.min(), vmax=log_areas.max())
        cmap = plt.cm.RdYlGn_r

        for i, polygon in enumerate(polygons):
            if len(polygon) < 3 or cell_areas[i] <= 0:
                continue
            log_area = np.log10(cell_areas[i] + 1e-8)
            color = cmap(norm(log_area))
            poly_patch = MplPolygon(polygon, closed=True,
                                    facecolor=(*color[:3], 0.6),
                                    edgecolor="white", linewidth=0.2)
            ax2.add_patch(poly_patch)

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax2, shrink=0.6, pad=0.02)
        cbar.set_label("log10(cell area) -- smaller = more overloaded", fontsize=9)

    # Sparse labels
    for i, r in enumerate(results):
        if r["category"] == "bare" and i % 60 == 0:
            ax2.plot(r["x_cute"], r["y_gender"], ".", color="black", markersize=1.5, zorder=5)
            ax2.annotate(r["label"],
                         (r["x_cute"], r["y_gender"]),
                         xytext=(3, 3), textcoords="offset points",
                         fontsize=5, alpha=0.7, zorder=6)

    ax2.set_xlim(x_min, x_max)
    ax2.set_ylim(y_min, y_max)
    ax2.set_xlabel('"Cute" Modifier Axis (woman -> cute woman)', fontsize=11)
    ax2.set_ylabel('<-- Male          Gender Axis          Female -->', fontsize=11)
    ax2.set_title(f'Semantic Loadedness Heatmap: {len(results)} Voronoi Cells\n'
                  '(Red = small cells = overloaded / Green = large cells = underloaded)',
                  fontsize=13, fontweight='bold')
    plt.tight_layout()

    path2 = os.path.join(os.path.dirname(__file__), "semantic_topology_large_heatmap.png")
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    print(f"  Heatmap saved to {path2}")
    plt.close()

    # === PLOT 3: Adjective displacement arrows for a subset ===
    fig3, ax3 = plt.subplots(1, 1, figsize=(16, 12))

    # Pick 30 evenly-spaced nouns to show displacement arrows
    lookup = {}
    for r in results:
        noun = r["text"].split(" ", 1)[-1] if r["category"] != "bare" else r["text"]
        if noun not in lookup:
            lookup[noun] = {}
        lookup[noun][r["category"]] = (r["x_cute"], r["y_gender"])

    sample_nouns = [results[i * 6]["label"] for i in range(0, 500, 17)]  # ~30 nouns

    adj_colors = {
        "cute": "#FF69B4",
        "adorable": "#FF1493",
        "beautiful": "#9B59B6",
        "powerful": "#C0392B",
        "strong": "#E67E22",
    }

    for noun in sample_nouns:
        if noun not in lookup or "bare" not in lookup[noun]:
            continue
        bx, by = lookup[noun]["bare"]
        ax3.plot(bx, by, "o", color="#333333", markersize=4, zorder=5)
        ax3.annotate(noun, (bx, by), xytext=(4, 4), textcoords="offset points",
                     fontsize=6, alpha=0.8, zorder=6)

        for adj, color in adj_colors.items():
            if adj in lookup[noun]:
                ax_, ay = lookup[noun][adj]
                ax3.annotate("", xy=(ax_, ay), xytext=(bx, by),
                             arrowprops=dict(arrowstyle="->", color=color,
                                             lw=0.8, alpha=0.6))

    handles = [plt.Line2D([0], [0], color=c, lw=2, label=a.capitalize())
               for a, c in adj_colors.items()]
    handles.insert(0, plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor='#333333', markersize=8, label='Bare noun'))
    ax3.legend(handles=handles, loc="upper left", fontsize=9)
    ax3.set_xlabel('"Cute" Modifier Axis (woman -> cute woman)', fontsize=11)
    ax3.set_ylabel('<-- Male          Gender Axis          Female -->', fontsize=11)
    ax3.set_title('Adjective Displacement Arrows: How Modifiers Shift Nouns\n'
                  '(30 sample nouns, 5 adjective directions)',
                  fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.2)
    plt.tight_layout()

    path3 = os.path.join(os.path.dirname(__file__), "semantic_topology_large_arrows.png")
    plt.savefig(path3, dpi=150, bbox_inches="tight")
    print(f"  Arrows plot saved to {path3}")
    plt.close()


if __name__ == "__main__":
    run()
