"""
Collision Map Visualizer
========================
Generates publication-quality plots from the mountain term collision data.
Produces a multi-page figure set saved to plots/ directory.

Run: python plot_collisions.py
"""

import os
import sys
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import FancyBboxPatch
from collections import defaultdict

# Windows Unicode fix (guard against double-wrapping from import)
if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Import everything from the main module
from mountain_collision_map import (
    generate_mountain_terms, HASH_FUNCTIONS,
    hash_md5_8bit, hash_md5_12bit, hash_md5_16bit,
    hash_sha256_16bit,
    hash_crc32_8bit, hash_crc32_12bit, hash_crc32_16bit,
    hash_djb2_8bit, hash_djb2_12bit, hash_djb2_16bit,
    hash_fnv1a_8bit, hash_fnv1a_12bit, hash_fnv1a_16bit,
    hash_sum_mod, hash_length_mod, hash_first_last_byte,
    hash_case_insensitive_md5_16bit, hash_stripped_md5_16bit,
    analyze_collisions,
)

PLOT_DIR = os.path.join(os.path.dirname(__file__), "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# Consistent style
plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#c9d1d9",
    "text.color": "#c9d1d9",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "grid.color": "#21262d",
    "grid.alpha": 0.7,
    "font.family": "monospace",
    "font.size": 10,
})

ACCENT = "#58a6ff"
WARN = "#f0883e"
DANGER = "#f85149"
SAFE = "#3fb950"
PURPLE = "#bc8cff"
CYAN = "#39d2c0"


def get_hash_values(terms, hash_fn):
    return [hash_fn(t) for t in terms]


# =========================================================================
# PLOT 1: Collision Rate Comparison Bar Chart
# =========================================================================
def plot_collision_rates(terms):
    print("  [1/8] Collision rate comparison...")
    fig, ax = plt.subplots(figsize=(14, 7))

    names = []
    rates = []
    colors = []
    for name in sorted(HASH_FUNCTIONS.keys()):
        fn, rng = HASH_FUNCTIONS[name]
        result = analyze_collisions(terms, name, fn, rng)
        names.append(name)
        rates.append(result["collision_rate"] * 100)
        if result["collision_rate"] < 0.05:
            colors.append(SAFE)
        elif result["collision_rate"] < 0.30:
            colors.append(WARN)
        else:
            colors.append(DANGER)

    # Sort by rate
    order = np.argsort(rates)
    names = [names[i] for i in order]
    rates = [rates[i] for i in order]
    colors = [colors[i] for i in order]

    bars = ax.barh(range(len(names)), rates, color=colors, edgecolor="#30363d",
                   height=0.7)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Collision Rate (%)", fontsize=12)
    ax.set_title("Collision Rates Across Hash Functions\n"
                 f"({len(terms)} mountain-related terms)",
                 fontsize=14, fontweight="bold", pad=15)
    ax.axvline(x=50, color=DANGER, linestyle="--", alpha=0.5, label="50% threshold")
    ax.axvline(x=10, color=WARN, linestyle="--", alpha=0.5, label="10% threshold")

    for bar, rate in zip(bars, rates):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{rate:.1f}%", va="center", fontsize=8, color="#8b949e")

    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlim(0, 105)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "01_collision_rates.png"), dpi=150)
    plt.close(fig)


# =========================================================================
# PLOT 2: Distribution Heatmaps (8-bit hashes side by side)
# =========================================================================
def plot_distribution_heatmaps(terms):
    print("  [2/8] Distribution heatmaps...")
    hash_8bit = [
        ("MD5-8bit", hash_md5_8bit),
        ("CRC32-8bit", hash_crc32_8bit),
        ("DJB2-8bit", hash_djb2_8bit),
        ("FNV1a-8bit", hash_fnv1a_8bit),
        ("ByteSum-mod256", lambda t: hash_sum_mod(t, 256)),
        ("FirstLastXOR", hash_first_last_byte),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, (name, fn) in enumerate(hash_8bit):
        ax = axes[idx]
        values = get_hash_values(terms, fn)

        # Reshape into 16x16 grid
        grid = np.zeros((16, 16))
        for v in values:
            row = v // 16
            col = v % 16
            grid[row][col] += 1

        im = ax.imshow(grid, cmap="inferno", aspect="equal",
                       interpolation="nearest")
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.set_xlabel("Hash value (low nibble)")
        ax.set_ylabel("Hash value (high nibble)")
        ax.set_xticks(range(0, 16, 4))
        ax.set_xticklabels([f"0x{i:X}" for i in range(0, 16, 4)])
        ax.set_yticks(range(0, 16, 4))
        ax.set_yticklabels([f"0x{i:X}0" for i in range(0, 16, 4)])
        plt.colorbar(im, ax=ax, shrink=0.8, label="Terms per bucket")

    fig.suptitle("Hash Distribution Heatmaps (8-bit / 256 slots)\n"
                 "Bright spots = collision hotspots",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "02_distribution_heatmaps.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# PLOT 3: Bucket Occupancy Histograms
# =========================================================================
def plot_bucket_occupancy(terms):
    print("  [3/8] Bucket occupancy histograms...")
    hashes = [
        ("MD5-8bit", hash_md5_8bit, 256),
        ("DJB2-8bit", hash_djb2_8bit, 256),
        ("ByteSum-mod256", lambda t: hash_sum_mod(t, 256), 256),
        ("FirstLastXOR", hash_first_last_byte, 256),
        ("Length-mod64", lambda t: hash_length_mod(t, 64), 64),
        ("MD5-12bit", hash_md5_12bit, 4096),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, (name, fn, rng) in enumerate(hashes):
        ax = axes[idx]
        buckets = defaultdict(int)
        for t in terms:
            buckets[fn(t)] += 1

        counts = list(buckets.values())
        # Add zeros for empty buckets
        empty = rng - len(buckets)
        counts.extend([0] * empty)

        max_count = max(counts)
        bins = range(0, max_count + 2)
        hist_vals = [counts.count(i) for i in range(max_count + 1)]

        bar_colors = []
        for i in range(max_count + 1):
            if i == 0:
                bar_colors.append(SAFE)
            elif i == 1:
                bar_colors.append(ACCENT)
            else:
                bar_colors.append(DANGER)

        ax.bar(range(max_count + 1), hist_vals, color=bar_colors,
               edgecolor="#30363d", width=0.8)
        ax.set_xlabel("Terms per bucket")
        ax.set_ylabel("Number of buckets")
        ax.set_title(f"{name}\n(range {rng})", fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

        # Annotate
        ax.text(0.95, 0.95, f"Empty: {empty}\nMax: {max_count}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=9, color="#8b949e",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#21262d",
                          edgecolor="#30363d"))

    fig.suptitle("Bucket Occupancy Distribution\n"
                 "Green=empty, Blue=unique, Red=collision",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "03_bucket_occupancy.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# PLOT 4: Collision Rate vs Hash Range (the scaling curve)
# =========================================================================
def plot_scaling_curve(terms):
    print("  [4/8] Scaling curve...")
    fig, ax = plt.subplots(figsize=(12, 7))

    # Group hash functions by algorithm family
    families = {
        "MD5": [
            ("8-bit", hash_md5_8bit, 256),
            ("12-bit", hash_md5_12bit, 4096),
            ("16-bit", hash_md5_16bit, 65536),
        ],
        "CRC32": [
            ("8-bit", hash_crc32_8bit, 256),
            ("12-bit", hash_crc32_12bit, 4096),
            ("16-bit", hash_crc32_16bit, 65536),
        ],
        "DJB2": [
            ("8-bit", hash_djb2_8bit, 256),
            ("12-bit", hash_djb2_12bit, 4096),
            ("16-bit", hash_djb2_16bit, 65536),
        ],
        "FNV1a": [
            ("8-bit", hash_fnv1a_8bit, 256),
            ("12-bit", hash_fnv1a_12bit, 4096),
            ("16-bit", hash_fnv1a_16bit, 65536),
        ],
    }

    family_colors = {
        "MD5": ACCENT, "CRC32": WARN, "DJB2": PURPLE, "FNV1a": CYAN
    }

    for family_name, variants in families.items():
        ranges = []
        rates = []
        for label, fn, rng in variants:
            result = analyze_collisions(terms, f"{family_name}-{label}", fn, rng)
            ranges.append(rng)
            rates.append(result["collision_rate"] * 100)

        ax.plot(ranges, rates, "o-", color=family_colors[family_name],
                label=family_name, markersize=10, linewidth=2.5)

    # Add theoretical birthday bound
    n = len(terms)
    theory_ranges = np.logspace(np.log10(64), np.log10(65536), 100)
    # P(collision) ≈ 1 - e^(-n(n-1)/(2*m)) for n items in m slots
    theory_rates = [(1 - np.exp(-n * (n - 1) / (2 * m))) * 100
                    for m in theory_ranges]
    ax.plot(theory_ranges, theory_rates, "--", color="#8b949e", linewidth=1.5,
            alpha=0.7, label=f"Birthday bound (n={n})")

    # Add weak hashes as separate points
    weak_hashes = [
        ("ByteSum\nmod256", lambda t: hash_sum_mod(t, 256), 256),
        ("Length\nmod64", lambda t: hash_length_mod(t, 64), 64),
        ("FirstLast\nXOR", hash_first_last_byte, 256),
    ]
    for label, fn, rng in weak_hashes:
        result = analyze_collisions(terms, label, fn, rng)
        ax.scatter(rng, result["collision_rate"] * 100, s=200, c=DANGER,
                   marker="X", zorder=10, edgecolors="#30363d", linewidths=1.5)
        ax.annotate(label, (rng, result["collision_rate"] * 100),
                    textcoords="offset points", xytext=(15, -5),
                    fontsize=8, color=DANGER)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Hash Range (bits of output)", fontsize=12)
    ax.set_ylabel("Collision Rate (%)", fontsize=12)
    ax.set_title("Collision Rate vs Hash Space Size\n"
                 "How much space do you need to avoid collisions?",
                 fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-2, 102)

    # Annotate regions
    ax.axhspan(0, 5, alpha=0.05, color=SAFE)
    ax.axhspan(5, 30, alpha=0.05, color=WARN)
    ax.axhspan(30, 100, alpha=0.05, color=DANGER)
    ax.text(65536, 2, "SAFE", color=SAFE, fontsize=11, fontweight="bold",
            ha="right")
    ax.text(65536, 15, "CAUTION", color=WARN, fontsize=11, fontweight="bold",
            ha="right")
    ax.text(65536, 60, "DANGER", color=DANGER, fontsize=11, fontweight="bold",
            ha="right")

    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "04_scaling_curve.png"), dpi=150)
    plt.close(fig)


# =========================================================================
# PLOT 5: Pairwise Semantic Distance Matrix
# =========================================================================
def plot_semantic_distance_matrix(terms):
    print("  [5/8] Semantic distance matrix...")

    semantic_pairs_labels = [
        ("Mountain", "mountain"),
        ("Mountain", "MOUNTAIN"),
        ("Mt. Everest", "Mt Everest"),
        ("Mt Everest", "Everest"),
        ("Mt Everest", "The Mt Everest"),
        ("Mt Everest", "mount everest"),
        ("Mt Everest", "Chomolungma"),
        ("Mt Everest", "Sagarmatha"),
        ("K2", "k2"),
        ("K2", "K-2"),
        ("mountain", "mountains"),
        ("mountain", "montain"),
        ("mountain", "Berg"),
        ("mountain", "Montagne"),
        ("mountain", "山"),
        ("mountain", "hill"),
        ("mountain", "peak"),
        ("Fuji", "Fujisan"),
        ("Fuji", "Mount Fuji"),
        ("Mt Doom", "Orodruin"),
        ("Mt Olympus", "Olympus"),
    ]

    test_hashes = [
        ("MD5\n8b", hash_md5_8bit, 256),
        ("CRC32\n8b", hash_crc32_8bit, 256),
        ("DJB2\n8b", hash_djb2_8bit, 256),
        ("FNV1a\n8b", hash_fnv1a_8bit, 256),
        ("ByteSum\n256", lambda t: hash_sum_mod(t, 256), 256),
        ("1stLast\nXOR", hash_first_last_byte, 256),
        ("CaseIns\nMD5-16", hash_case_insensitive_md5_16bit, 65536),
        ("Stripped\nMD5-16", hash_stripped_md5_16bit, 65536),
    ]

    pair_labels = [f"{a} / {b}" for a, b in semantic_pairs_labels]
    hash_labels = [name for name, _, _ in test_hashes]

    # Build distance matrix (normalized to [0, 1])
    matrix = np.zeros((len(semantic_pairs_labels), len(test_hashes)))
    for j, (hname, fn, rng) in enumerate(test_hashes):
        for i, (a, b) in enumerate(semantic_pairs_labels):
            va = fn(a)
            vb = fn(b)
            dist = abs(va - vb)
            wrap_dist = min(dist, rng - dist)
            matrix[i, j] = wrap_dist / rng  # Normalize

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(matrix, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=0.5)

    ax.set_xticks(range(len(hash_labels)))
    ax.set_xticklabels(hash_labels, fontsize=9, ha="center")
    ax.set_yticks(range(len(pair_labels)))
    ax.set_yticklabels(pair_labels, fontsize=8)

    # Annotate cells
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            text = "SAME" if val == 0 else f"{val:.3f}"
            color = "#ffffff" if val < 0.15 else "#000000"
            fontweight = "bold" if val == 0 else "normal"
            ax.text(j, i, text, ha="center", va="center", fontsize=7,
                    color=color, fontweight=fontweight)

    plt.colorbar(im, ax=ax, shrink=0.6, label="Normalized distance (0=collision)")
    ax.set_title("Semantic Pair Distance Matrix\n"
                 "Do related terms land nearby or far apart?",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Hash Function", fontsize=12)
    ax.set_ylabel("Semantic Pair", fontsize=12)

    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "05_semantic_distance_matrix.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# PLOT 6: Ring Visualization (hash values on a circle)
# =========================================================================
def plot_hash_rings(terms):
    print("  [6/8] Hash rings...")

    # Pick a subset of interesting terms for legibility
    highlight_terms = [
        "mountain", "Mountain", "MOUNTAIN",
        "Mount Everest", "Mt. Everest", "Everest",
        "Chomolungma", "Sagarmatha",
        "K2", "k2", "K-2",
        "Fuji", "Fujisan", "Fujiyama",
        "Mont Blanc",
        "Kilimanjaro",
        "Denali",
        "hill", "peak", "summit",
        "Berg", "Montagne", "山", "산",
    ]

    ring_hashes = [
        ("MD5-8bit", hash_md5_8bit, 256),
        ("DJB2-8bit", hash_djb2_8bit, 256),
        ("ByteSum-mod256", lambda t: hash_sum_mod(t, 256), 256),
        ("FirstLastXOR", hash_first_last_byte, 256),
    ]

    # Color categories
    categories = {
        "Everest variants": ["Mount Everest", "Mt. Everest", "Everest",
                            "Chomolungma", "Sagarmatha"],
        "Mountain word": ["mountain", "Mountain", "MOUNTAIN",
                         "Berg", "Montagne", "山", "산"],
        "K2 variants": ["K2", "k2", "K-2"],
        "Fuji variants": ["Fuji", "Fujisan", "Fujiyama"],
        "Related concepts": ["hill", "peak", "summit"],
        "Other peaks": ["Mont Blanc", "Kilimanjaro", "Denali"],
    }

    cat_colors = {
        "Everest variants": DANGER,
        "Mountain word": ACCENT,
        "K2 variants": WARN,
        "Fuji variants": PURPLE,
        "Related concepts": CYAN,
        "Other peaks": SAFE,
    }

    term_to_cat = {}
    for cat, ts in categories.items():
        for t in ts:
            term_to_cat[t] = cat

    fig, axes = plt.subplots(2, 2, figsize=(16, 16),
                              subplot_kw={"projection": "polar"})
    axes = axes.flatten()

    for idx, (hname, fn, rng) in enumerate(ring_hashes):
        ax = axes[idx]
        ax.set_facecolor("#161b22")

        # Plot all terms as faint background dots
        all_vals = get_hash_values(terms, fn)
        all_angles = [2 * np.pi * v / rng for v in all_vals]
        ax.scatter(all_angles, [1.0] * len(all_angles),
                   s=3, alpha=0.15, color="#8b949e")

        # Plot highlight terms
        for term in highlight_terms:
            val = fn(term)
            angle = 2 * np.pi * val / rng
            cat = term_to_cat.get(term, "Other")
            color = cat_colors.get(cat, "#8b949e")

            ax.scatter([angle], [0.85], s=80, c=color, zorder=10,
                       edgecolors="#ffffff", linewidths=0.5)

            # Label (stagger radius to reduce overlap)
            label_r = 1.15 + 0.12 * (hash(term) % 3)
            ax.annotate(term, xy=(angle, 0.85),
                        xytext=(angle, label_r),
                        fontsize=6, color=color,
                        ha="center", va="center",
                        arrowprops=dict(arrowstyle="-", color=color,
                                        alpha=0.3, lw=0.5))

        ax.set_title(f"{hname}\n(range 0–{rng - 1})",
                     fontsize=12, fontweight="bold", pad=20)
        ax.set_ylim(0, 1.5)
        ax.set_yticks([])
        ax.grid(True, alpha=0.2)

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
               markersize=8, label=cat)
        for cat, c in cat_colors.items()
    ]
    fig.legend(handles=legend_elements, loc="lower center",
               ncol=3, fontsize=10, framealpha=0.8,
               facecolor="#161b22", edgecolor="#30363d")

    fig.suptitle("Hash Ring Visualization\n"
                 "Where do related terms land on the hash circle?",
                 fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(os.path.join(PLOT_DIR, "06_hash_rings.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# PLOT 7: Normalization Effect (before/after stripping)
# =========================================================================
def plot_normalization_effect(terms):
    print("  [7/8] Normalization effect...")

    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    hash_configs = [
        ("Raw MD5-16bit\n(case-sensitive)", hash_md5_16bit, 65536),
        ("Case-Insensitive MD5-16bit\n(lowered)", hash_case_insensitive_md5_16bit, 65536),
        ("Stripped MD5-16bit\n(no articles/punct/case)", hash_stripped_md5_16bit, 65536),
    ]

    for idx, (name, fn, rng) in enumerate(hash_configs):
        ax = axes[idx]

        buckets = defaultdict(list)
        for t in terms:
            buckets[fn(t)].append(t)

        # Histogram of bucket sizes
        sizes = [len(v) for v in buckets.values()]
        # Add empty buckets
        sizes.extend([0] * (rng - len(buckets)))

        max_size = max(sizes)
        size_counts = [sizes.count(i) for i in range(max_size + 1)]

        # Only plot non-empty counts (skip 0-bucket count for readability)
        x = list(range(1, max_size + 1))
        y = size_counts[1:]

        bar_colors = [ACCENT if s == 1 else WARN if s <= 3 else DANGER
                      for s in x]
        ax.bar(x, y, color=bar_colors, edgecolor="#30363d")
        ax.set_xlabel("Terms per bucket")
        ax.set_ylabel("Number of buckets")
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

        # Stats
        collision_buckets = sum(1 for s in sizes if s > 1)
        max_bucket = max(sizes)
        total_collisions = sum(s - 1 for s in sizes if s > 1)
        ax.text(0.95, 0.95,
                f"Collision buckets: {collision_buckets}\n"
                f"Total collisions: {total_collisions}\n"
                f"Max bucket: {max_bucket}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=9, color="#c9d1d9",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#21262d",
                          edgecolor="#30363d"))

    fig.suptitle("Effect of Input Normalization on Collisions\n"
                 "Stripping articles/case/punctuation intentionally merges variants",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "07_normalization_effect.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# PLOT 8: The Money Plot — Combined Dashboard
# =========================================================================
def plot_dashboard(terms):
    print("  [8/8] Combined dashboard...")

    fig = plt.figure(figsize=(24, 16))
    gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.4, wspace=0.35)

    # --- Panel A: Collision rate bars (top-left, spanning 2 cols) ---
    ax_a = fig.add_subplot(gs[0, :2])
    names_rates = []
    for name in sorted(HASH_FUNCTIONS.keys()):
        fn, rng = HASH_FUNCTIONS[name]
        result = analyze_collisions(terms, name, fn, rng)
        names_rates.append((name, result["collision_rate"] * 100, rng))
    names_rates.sort(key=lambda x: x[1])

    colors = [SAFE if r < 5 else WARN if r < 30 else DANGER
              for _, r, _ in names_rates]
    ax_a.barh(range(len(names_rates)), [r for _, r, _ in names_rates],
              color=colors, edgecolor="#30363d", height=0.7)
    ax_a.set_yticks(range(len(names_rates)))
    ax_a.set_yticklabels([n for n, _, _ in names_rates], fontsize=7)
    ax_a.set_xlabel("Collision Rate (%)")
    ax_a.set_title("A) Collision Rates", fontsize=12, fontweight="bold")
    ax_a.grid(axis="x", alpha=0.3)

    # --- Panel B: Scaling curve (top-right, spanning 2 cols) ---
    ax_b = fig.add_subplot(gs[0, 2:])
    families = {
        "MD5": [(hash_md5_8bit, 256), (hash_md5_12bit, 4096),
                (hash_md5_16bit, 65536)],
        "CRC32": [(hash_crc32_8bit, 256), (hash_crc32_12bit, 4096),
                  (hash_crc32_16bit, 65536)],
        "DJB2": [(hash_djb2_8bit, 256), (hash_djb2_12bit, 4096),
                 (hash_djb2_16bit, 65536)],
        "FNV1a": [(hash_fnv1a_8bit, 256), (hash_fnv1a_12bit, 4096),
                  (hash_fnv1a_16bit, 65536)],
    }
    fcolors = {"MD5": ACCENT, "CRC32": WARN, "DJB2": PURPLE, "FNV1a": CYAN}
    for fname, variants in families.items():
        xs, ys = [], []
        for fn, rng in variants:
            r = analyze_collisions(terms, fname, fn, rng)
            xs.append(rng)
            ys.append(r["collision_rate"] * 100)
        ax_b.plot(xs, ys, "o-", color=fcolors[fname], label=fname,
                  markersize=8, linewidth=2)

    ax_b.set_xscale("log", base=2)
    ax_b.set_xlabel("Hash Range")
    ax_b.set_ylabel("Collision Rate (%)")
    ax_b.set_title("B) Scaling: Rate vs Hash Space", fontsize=12,
                    fontweight="bold")
    ax_b.legend(fontsize=8)
    ax_b.grid(True, alpha=0.3)

    # --- Panel C–F: Four heatmaps (middle row) ---
    heatmap_hashes = [
        ("MD5-8bit", hash_md5_8bit),
        ("DJB2-8bit", hash_djb2_8bit),
        ("ByteSum-256", lambda t: hash_sum_mod(t, 256)),
        ("FirstLastXOR", hash_first_last_byte),
    ]
    for idx, (name, fn) in enumerate(heatmap_hashes):
        ax = fig.add_subplot(gs[1, idx])
        values = get_hash_values(terms, fn)
        grid = np.zeros((16, 16))
        for v in values:
            grid[v // 16][v % 16] += 1
        im = ax.imshow(grid, cmap="inferno", aspect="equal",
                       interpolation="nearest")
        letter = chr(ord("C") + idx)
        ax.set_title(f"{letter}) {name}", fontsize=10, fontweight="bold")
        ax.set_xticks([0, 8, 15])
        ax.set_yticks([0, 8, 15])
        plt.colorbar(im, ax=ax, shrink=0.7)

    # --- Panel G: Normalization comparison (bottom-left, 2 cols) ---
    ax_g = fig.add_subplot(gs[2, :2])
    norm_hashes = [
        ("Raw\nMD5-16", hash_md5_16bit, 65536),
        ("CaseIns\nMD5-16", hash_case_insensitive_md5_16bit, 65536),
        ("Stripped\nMD5-16", hash_stripped_md5_16bit, 65536),
    ]
    x_pos = range(len(norm_hashes))
    collision_counts = []
    max_buckets = []
    for name, fn, rng in norm_hashes:
        r = analyze_collisions(terms, name, fn, rng)
        collision_counts.append(r["total_collisions"])
        max_buckets.append(r["max_bucket_size"])

    bar_width = 0.35
    ax_g.bar([x - bar_width / 2 for x in x_pos], collision_counts,
             bar_width, label="Total collisions", color=ACCENT)
    ax_g.bar([x + bar_width / 2 for x in x_pos], max_buckets,
             bar_width, label="Max bucket size", color=WARN)
    ax_g.set_xticks(x_pos)
    ax_g.set_xticklabels([n for n, _, _ in norm_hashes])
    ax_g.set_ylabel("Count")
    ax_g.set_title("G) Normalization Effect", fontsize=12, fontweight="bold")
    ax_g.legend(fontsize=9)
    ax_g.grid(axis="y", alpha=0.3)

    # --- Panel H: Semantic pair scatter (bottom-right, 2 cols) ---
    ax_h = fig.add_subplot(gs[2, 2:])
    pairs = [
        ("Mountain", "mountain"), ("Mt Everest", "Everest"),
        ("Mt Everest", "Chomolungma"), ("K2", "k2"),
        ("mountain", "Berg"), ("mountain", "山"),
        ("mountain", "hill"), ("Fuji", "Fujisan"),
        ("Mt Doom", "Orodruin"), ("Mt Olympus", "Olympus"),
    ]
    pair_labels = [f"{a}/{b}" for a, b in pairs]

    hash_fns_for_scatter = [
        ("MD5-8", hash_md5_8bit, 256),
        ("CRC32-8", hash_crc32_8bit, 256),
        ("DJB2-8", hash_djb2_8bit, 256),
    ]

    y_positions = np.arange(len(pairs))
    scatter_colors = [ACCENT, WARN, PURPLE]
    for hidx, (hname, fn, rng) in enumerate(hash_fns_for_scatter):
        dists = []
        for a, b in pairs:
            va, vb = fn(a), fn(b)
            d = min(abs(va - vb), rng - abs(va - vb))
            dists.append(d / rng)  # Normalize

        offset = (hidx - 1) * 0.25
        ax_h.barh(y_positions + offset, dists, height=0.2,
                  color=scatter_colors[hidx], label=hname, alpha=0.85)

    ax_h.set_yticks(y_positions)
    ax_h.set_yticklabels(pair_labels, fontsize=8)
    ax_h.set_xlabel("Normalized Distance (0 = collision)")
    ax_h.set_title("H) Semantic Pair Distances", fontsize=12,
                    fontweight="bold")
    ax_h.legend(fontsize=8)
    ax_h.grid(axis="x", alpha=0.3)

    fig.suptitle(f"Mountain Term Collision Analysis Dashboard — "
                 f"{len(terms)} terms × {len(HASH_FUNCTIONS)} hash functions",
                 fontsize=16, fontweight="bold", y=0.99, color="#ffffff")

    fig.savefig(os.path.join(PLOT_DIR, "08_dashboard.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)


# =========================================================================
# MAIN
# =========================================================================
def main():
    print()
    print("Generating plots...")
    print()

    terms = generate_mountain_terms()
    print(f"  Loaded {len(terms)} terms.")
    print()

    plot_collision_rates(terms)
    plot_distribution_heatmaps(terms)
    plot_bucket_occupancy(terms)
    plot_scaling_curve(terms)
    plot_semantic_distance_matrix(terms)
    plot_hash_rings(terms)
    plot_normalization_effect(terms)
    plot_dashboard(terms)

    print()
    print(f"All plots saved to {PLOT_DIR}/")
    print("  01_collision_rates.png        — Bar chart of all hash function collision rates")
    print("  02_distribution_heatmaps.png  — 16×16 heatmaps for 8-bit hashes")
    print("  03_bucket_occupancy.png       — How many terms per bucket")
    print("  04_scaling_curve.png          — Collision rate vs hash space size")
    print("  05_semantic_distance_matrix.png — Do related terms land nearby?")
    print("  06_hash_rings.png             — Polar/ring visualization of term positions")
    print("  07_normalization_effect.png    — Raw vs case-insensitive vs stripped")
    print("  08_dashboard.png              — Combined multi-panel overview")
    print()


if __name__ == "__main__":
    main()
