"""Semantic Topology — Complexity Axes.

Two orthogonal dimensions of increasing complexity, anchored at "Road":
  X-axis: "Road" -> "The Icy Road"      (adjective/descriptor complexity)
  Y-axis: "Road" -> "Roads are Great"   (predicate/opinion complexity)

Key test: "Icy Roads are Great" should land near (+X, +Y) if
the two complexity dimensions are independent and additive.

Projects 500 common nouns and their variants onto this plane.
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


def normalize(v):
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-10 else v


def embed_batch(texts, batch_size=100):
    """Embed texts in batches."""
    import ollama
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = ollama.embed(model=EMBED_MODEL, input=batch)
        all_vecs.extend(resp["embeddings"])
        if (i // batch_size) % 5 == 0:
            print(f"    {i+len(batch)}/{len(texts)} embedded...")
    return np.array(all_vecs, dtype=np.float32)


def compute_axes():
    """Compute complexity axes from Road reference points."""
    from prototype.pillar2_mapping import embed_texts

    # The three reference points
    vecs = embed_texts(["Road", "The Icy Road", "Roads are Great", "Icy Roads are Great"])
    v_road = vecs[0]
    v_icy_road = vecs[1]
    v_roads_great = vecs[2]
    v_icy_great = vecs[3]

    # Axes = displacement from origin
    adj_axis = normalize(v_icy_road - v_road)       # X: adjective complexity
    pred_axis = normalize(v_roads_great - v_road)    # Y: predicate complexity

    dot = float(np.dot(adj_axis, pred_axis))
    print(f"  Axis orthogonality: dot = {dot:.4f}")

    # Test: where does "Icy Roads are Great" land?
    combo_x = float(np.dot(v_icy_great - v_road, adj_axis))
    combo_y = float(np.dot(v_icy_great - v_road, pred_axis))
    adj_x = float(np.dot(v_icy_road - v_road, adj_axis))
    pred_y = float(np.dot(v_roads_great - v_road, pred_axis))

    print(f"\n  Reference point projections (relative to Road):")
    print(f"    Road:                  (0.000, 0.000)  [origin]")
    print(f"    The Icy Road:          ({adj_x:.4f}, {float(np.dot(v_icy_road - v_road, pred_axis)):.4f})")
    print(f"    Roads are Great:       ({float(np.dot(v_roads_great - v_road, adj_axis)):.4f}, {pred_y:.4f})")
    print(f"    Icy Roads are Great:   ({combo_x:.4f}, {combo_y:.4f})")
    print(f"\n  If additive, combo should be ~({adj_x:.4f}, {pred_y:.4f})")
    print(f"  Actual:                              ({combo_x:.4f}, {combo_y:.4f})")
    ratio_x = combo_x / adj_x if adj_x != 0 else 0
    ratio_y = combo_y / pred_y if pred_y != 0 else 0
    print(f"  Ratio (actual/expected): X={ratio_x:.3f}, Y={ratio_y:.3f}")

    return adj_axis, pred_axis, v_road


def get_common_nouns(n=500):
    """Get the N most common English nouns."""
    from wordfreq import top_n_list
    from nltk import pos_tag
    import nltk
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)

    words = top_n_list('en', 8000)
    tagged = pos_tag(words)

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
        base = w.rstrip('s')
        if base in seen and w != base:
            continue
        if w not in seen:
            nouns.append(w)
            seen.add(w)
        if len(nouns) >= n:
            break

    return nouns


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
        new_verts = [vor.vertices[v].tolist() for v in finite_verts]

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
            new_verts.append(far_point.tolist())

        if len(new_verts) < 3:
            polygons.append(np.array([]))
            continue

        vs = np.array(new_verts)
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
    print("SEMANTIC TOPOLOGY — COMPLEXITY AXES")
    print("Road -> The Icy Road (adjective)")
    print("Road -> Roads are Great (predicate)")
    print("=" * 60)

    # Step 1: Compute axes
    print("\n[1/5] Computing complexity axes...")
    adj_axis, pred_axis, v_road = compute_axes()

    # Step 2: Get nouns
    print("\n[2/5] Getting 500 most common nouns...")
    nouns = get_common_nouns(500)
    print(f"  Got {len(nouns)} nouns")

    # Step 3: Build variants
    # For each noun, create:
    #   bare: "dog"
    #   adj:  "The Icy dog"  (adjective complexity)
    #   pred: "dogs are Great"  (predicate complexity)
    #   both: "Icy dogs are Great"  (combined)
    print("\n[3/5] Building text variants...")
    items = []
    for noun in nouns:
        items.append((noun, noun, "bare"))
        items.append((f"The Icy {noun}", f"The Icy {noun}", "adjective"))
        items.append((f"{noun}s are Great", f"{noun}s are Great", "predicate"))
        items.append((f"Icy {noun}s are Great", f"Icy {noun}s are Great", "both"))

    # Also add the reference points explicitly
    items.append(("Road [REF]", "Road", "reference"))
    items.append(("The Icy Road [REF]", "The Icy Road", "reference"))
    items.append(("Roads are Great [REF]", "Roads are Great", "reference"))
    items.append(("Icy Roads are Great [REF]", "Icy Roads are Great", "reference"))

    texts = [item[1] for item in items]
    print(f"  {len(texts)} total items")

    # Step 4: Embed
    print(f"\n[4/5] Embedding {len(texts)} items...")
    t0 = time.time()
    embeddings = embed_batch(texts, batch_size=100)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s ({elapsed/len(texts)*1000:.1f}ms/item)")

    # Project relative to Road origin
    x_coords = (embeddings - v_road) @ adj_axis
    y_coords = (embeddings - v_road) @ pred_axis
    points = np.column_stack([x_coords, y_coords])

    # Save
    results = []
    for i, (label, text, category) in enumerate(items):
        results.append({
            "label": label,
            "text": text,
            "category": category,
            "x_adj": float(x_coords[i]),
            "y_pred": float(y_coords[i]),
        })

    results_path = os.path.join(os.path.dirname(__file__), "semantic_topology_complexity_results.json")
    with open(results_path, "w") as f:
        json.dump({"n_nouns": len(nouns), "n_items": len(items), "items": results}, f, indent=2)

    npz_path = os.path.join(os.path.dirname(__file__), "semantic_topology_complexity_embeddings.npz")
    np.savez_compressed(npz_path, embeddings=embeddings, x=x_coords, y=y_coords)
    print(f"  Saved results and embeddings")

    # Step 5: Analyze and plot
    print("\n[5/5] Analyzing...")
    analyze(results, nouns)
    plot_topology(results, points, len(nouns))
    plot_arrows(results, nouns)


def analyze(results, nouns):
    """Analyze category distributions and additivity."""
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"x": [], "y": []}
        categories[cat]["x"].append(r["x_adj"])
        categories[cat]["y"].append(r["y_pred"])

    print(f"\n{'Category':<15} {'Count':>6} {'Mean X':>8} {'Std X':>8} {'Mean Y':>8} {'Std Y':>8}")
    print("-" * 60)
    for cat in ["bare", "adjective", "predicate", "both", "reference"]:
        if cat not in categories:
            continue
        xs = categories[cat]["x"]
        ys = categories[cat]["y"]
        print(f"{cat:<15} {len(xs):>6} {np.mean(xs):>8.4f} {np.std(xs):>8.4f} "
              f"{np.mean(ys):>8.4f} {np.std(ys):>8.4f}")

    # Additivity test: does "both" = "adjective" + "predicate" - "bare"?
    lookup = {}
    for r in results:
        noun = r["label"].replace("The Icy ", "").replace("Icy ", "").replace("s are Great", "").replace(" [REF]", "")
        if noun not in lookup:
            lookup[noun] = {}
        lookup[noun][r["category"]] = (r["x_adj"], r["y_pred"])

    print(f"\n--- Additivity test: does 'both' = 'adjective' + 'predicate' - 'bare'? ---")
    x_errors, y_errors = [], []
    for noun in nouns[:100]:  # First 100 for stats
        if noun in lookup and all(c in lookup[noun] for c in ["bare", "adjective", "predicate", "both"]):
            bx, by = lookup[noun]["bare"]
            ax, ay = lookup[noun]["adjective"]
            px, py = lookup[noun]["predicate"]
            cx, cy = lookup[noun]["both"]
            # Predicted combo = adj_displacement + pred_displacement
            pred_x = (ax - bx) + (px - bx) + bx  # = ax + px - bx
            pred_y = (ay - by) + (py - by) + by  # = ay + py - by
            x_errors.append(cx - pred_x)
            y_errors.append(cy - pred_y)

    if x_errors:
        print(f"  Mean X error: {np.mean(x_errors):+.4f} (std {np.std(x_errors):.4f})")
        print(f"  Mean Y error: {np.mean(y_errors):+.4f} (std {np.std(y_errors):.4f})")
        print(f"  RMS error:    {np.sqrt(np.mean(np.array(x_errors)**2 + np.array(y_errors)**2)):.4f}")

    # Print reference points
    print(f"\n--- Reference points ---")
    for r in results:
        if r["category"] == "reference":
            print(f"  {r['label']:<30} x={r['x_adj']:+.4f}  y={r['y_pred']:+.4f}")


def plot_topology(results, points, n_nouns):
    """Voronoi tessellation colored by category."""
    x_min = points[:, 0].min() - 0.03
    x_max = points[:, 0].max() + 0.03
    y_min = points[:, 1].min() - 0.03
    y_max = points[:, 1].max() + 0.03
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
        "adjective": "#3498DB",
        "predicate": "#E74C3C",
        "both":      "#9B59B6",
        "reference": "#F1C40F",
    }

    # === PLOT 1: Category Voronoi ===
    fig, ax = plt.subplots(1, 1, figsize=(18, 14))

    for i, polygon in enumerate(polygons):
        if len(polygon) < 3:
            continue
        cat = results[i]["category"]
        color = category_colors.get(cat, "#CCCCCC")
        rgba = list(mcolors.to_rgba(color))
        rgba[3] = 0.25
        poly_patch = MplPolygon(polygon, closed=True,
                                facecolor=rgba, edgecolor="white", linewidth=0.3)
        ax.add_patch(poly_patch)

    # Plot reference points prominently
    for r in results:
        if r["category"] == "reference":
            ax.plot(r["x_adj"], r["y_pred"], "*", color="#F1C40F",
                    markersize=15, markeredgecolor="black", markeredgewidth=1, zorder=10)
            ax.annotate(r["label"].replace(" [REF]", ""),
                        (r["x_adj"], r["y_pred"]),
                        xytext=(8, 8), textcoords="offset points",
                        fontsize=9, fontweight="bold", zorder=11,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8))

    # Sparse labels for bare nouns
    bare_items = [r for r in results if r["category"] == "bare"]
    for i, r in enumerate(bare_items):
        ax.plot(r["x_adj"], r["y_pred"], ".", color="#333333", markersize=1, zorder=5)
        if i % 50 == 0:
            ax.annotate(r["label"], (r["x_adj"], r["y_pred"]),
                        xytext=(3, 3), textcoords="offset points",
                        fontsize=5, alpha=0.6, zorder=6)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel('Adjective Complexity Axis (Road -> The Icy Road)', fontsize=11)
    ax.set_ylabel('Predicate Complexity Axis (Road -> Roads are Great)', fontsize=11)
    ax.set_title(f'Semantic Topology: Two Dimensions of Complexity\n'
                 f'({n_nouns} nouns x 4 variants = {len(results)} items, '
                 f'mxbai-embed-large 1024-dim)',
                 fontsize=13, fontweight='bold')

    handles = [plt.Line2D([0], [0], marker='s', color='w',
               markerfacecolor=category_colors[c], markersize=10, label=c.capitalize())
               for c in ["bare", "adjective", "predicate", "both"]]
    handles.append(plt.Line2D([0], [0], marker='*', color='w',
                   markerfacecolor='#F1C40F', markersize=12,
                   markeredgecolor='black', label='Reference'))
    ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.9)
    ax.axhline(y=0, color='black', linewidth=0.3, alpha=0.3)
    ax.axvline(x=0, color='black', linewidth=0.3, alpha=0.3)
    plt.tight_layout()

    path1 = os.path.join(os.path.dirname(__file__), "semantic_topology_complexity_full.png")
    plt.savefig(path1, dpi=150, bbox_inches="tight")
    print(f"  Category plot saved to {path1}")
    plt.close()

    # === PLOT 2: Heatmap ===
    fig2, ax2 = plt.subplots(1, 1, figsize=(18, 14))

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

    # Reference points
    for r in results:
        if r["category"] == "reference":
            ax2.plot(r["x_adj"], r["y_pred"], "*", color="#F1C40F",
                    markersize=15, markeredgecolor="black", markeredgewidth=1, zorder=10)
            ax2.annotate(r["label"].replace(" [REF]", ""),
                        (r["x_adj"], r["y_pred"]),
                        xytext=(8, 8), textcoords="offset points",
                        fontsize=9, fontweight="bold", zorder=11,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8))

    ax2.set_xlim(x_min, x_max)
    ax2.set_ylim(y_min, y_max)
    ax2.set_xlabel('Adjective Complexity Axis (Road -> The Icy Road)', fontsize=11)
    ax2.set_ylabel('Predicate Complexity Axis (Road -> Roads are Great)', fontsize=11)
    ax2.set_title('Complexity Loadedness Heatmap\n'
                  '(Red = small cells = overloaded / Green = large cells = underloaded)',
                  fontsize=13, fontweight='bold')
    ax2.axhline(y=0, color='black', linewidth=0.3, alpha=0.3)
    ax2.axvline(x=0, color='black', linewidth=0.3, alpha=0.3)
    plt.tight_layout()

    path2 = os.path.join(os.path.dirname(__file__), "semantic_topology_complexity_heatmap.png")
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    print(f"  Heatmap saved to {path2}")
    plt.close()


def plot_arrows(results, nouns):
    """Show displacement arrows for sample nouns across complexity variants."""
    # Build lookup
    lookup = {}
    for r in results:
        if r["category"] == "reference":
            continue
        # Extract base noun from label
        label = r["label"]
        if r["category"] == "bare":
            noun = label
        elif r["category"] == "adjective":
            noun = label.replace("The Icy ", "")
        elif r["category"] == "predicate":
            noun = label.replace("s are Great", "")
        elif r["category"] == "both":
            noun = label.replace("Icy ", "").replace("s are Great", "")
        else:
            continue
        if noun not in lookup:
            lookup[noun] = {}
        lookup[noun][r["category"]] = (r["x_adj"], r["y_pred"])

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))

    sample_nouns = nouns[::17]  # ~30 nouns

    for noun in sample_nouns:
        if noun not in lookup or "bare" not in lookup[noun]:
            continue
        bx, by = lookup[noun]["bare"]
        ax.plot(bx, by, "o", color="#333333", markersize=5, zorder=5)
        ax.annotate(noun, (bx, by), xytext=(4, 4), textcoords="offset points",
                    fontsize=7, alpha=0.8, zorder=6)

        if "adjective" in lookup[noun]:
            ax_, ay = lookup[noun]["adjective"]
            ax.annotate("", xy=(ax_, ay), xytext=(bx, by),
                        arrowprops=dict(arrowstyle="->", color="#3498DB", lw=1.2, alpha=0.7))

        if "predicate" in lookup[noun]:
            px, py = lookup[noun]["predicate"]
            ax.annotate("", xy=(px, py), xytext=(bx, by),
                        arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=1.2, alpha=0.7))

        if "both" in lookup[noun]:
            cx, cy = lookup[noun]["both"]
            ax.annotate("", xy=(cx, cy), xytext=(bx, by),
                        arrowprops=dict(arrowstyle="->", color="#9B59B6", lw=1.2, alpha=0.7))

    # Reference points
    for r in results:
        if r["category"] == "reference":
            ax.plot(r["x_adj"], r["y_pred"], "*", color="#F1C40F",
                    markersize=15, markeredgecolor="black", markeredgewidth=1, zorder=10)

    handles = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#333333',
                   markersize=8, label='Bare noun'),
        plt.Line2D([0], [0], color='#3498DB', lw=2, label='+ Adjective (The Icy X)'),
        plt.Line2D([0], [0], color='#E74C3C', lw=2, label='+ Predicate (Xs are Great)'),
        plt.Line2D([0], [0], color='#9B59B6', lw=2, label='+ Both (Icy Xs are Great)'),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=9)
    ax.set_xlabel('Adjective Complexity (Road -> The Icy Road)', fontsize=11)
    ax.set_ylabel('Predicate Complexity (Road -> Roads are Great)', fontsize=11)
    ax.set_title('Complexity Displacement: How Adjective and Predicate Modify Nouns\n'
                 '(~30 sample nouns, blue=adjective, red=predicate, purple=both)',
                 fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.2)
    ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(x=0, color='black', linewidth=0.5, alpha=0.3)
    plt.tight_layout()

    path = os.path.join(os.path.dirname(__file__), "semantic_topology_complexity_arrows.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Arrows plot saved to {path}")
    plt.close()


if __name__ == "__main__":
    run()
