"""
Generate publication figures for the Economics paper.

Figures:
1. Structural feature comparison heatmap (5 events × 6 features)
2. Market metrics comparison (peak declines and timelines)

Output: papers/economics/figures/
"""

import io
import sys
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
FIG_DIR = SCRIPT_DIR.parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def fig1_structural_heatmap():
    """Figure 1: Feature comparison heatmap."""
    with open(str(DATA_DIR / 'comparison_results.json'), encoding='utf-8') as f:
        data = json.load(f)

    events = data['events']
    features = data['metadata']['features']

    feature_labels = {
        'denial_reflexivity': 'Widespread\nDenial',
        'mass_retail_participation': 'Mass Retail\nParticipation',
        'leverage_amplification': 'Leverage\nAmplification',
        'exit_liquidity': 'Exit\nLiquidity',
        'speculative_disconnect': 'Speculative\nDisconnect',
        'rapid_unwind_mechanism': 'Rapid Unwind\nMechanism',
    }

    event_names = [e['name'] for e in events.values()]
    matrix = []
    for event in events.values():
        row = [event['scores'].get(f, {}).get('score', 0) for f in features]
        matrix.append(row)

    matrix = np.array(matrix)
    feat_labels = [feature_labels.get(f, f) for f in features]

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    cmap = plt.cm.RdYlGn_r  # Red = present (bubble), green = absent
    im = ax.imshow(matrix, cmap=cmap, aspect='auto', vmin=0, vmax=1)

    ax.set_xticks(range(len(feat_labels)))
    ax.set_xticklabels(feat_labels, fontsize=9, ha='center')
    ax.set_yticks(range(len(event_names)))
    ax.set_yticklabels(event_names, fontsize=10)

    # Annotate cells
    for i in range(len(event_names)):
        for j in range(len(features)):
            val = matrix[i, j]
            text = 'X' if val >= 1.0 else '~' if val >= 0.5 else '-'
            color = 'white' if val >= 0.7 else 'black'
            ax.text(j, i, text, ha='center', va='center', fontsize=14,
                    fontweight='bold', color=color)

    # Add total scores on the right
    for i, event in enumerate(events.values()):
        ax.text(len(features) + 0.3, i, f"{event['total_score']}/6",
                ha='left', va='center', fontsize=11, fontweight='bold')

    ax.set_title('Structural Bubble Feature Comparison\n(X = Present, ~ = Partial, - = Absent)',
                 fontsize=13, pad=15)

    plt.colorbar(im, ax=ax, shrink=0.8, label='Feature Score')
    plt.tight_layout()

    path = FIG_DIR / 'fig1_structural_heatmap.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def fig2_market_metrics():
    """Figure 2: Peak declines and crash timelines."""
    with open(str(DATA_DIR / 'comparison_results.json'), encoding='utf-8') as f:
        data = json.load(f)

    events = data['events']

    names = []
    declines = []
    colors = []

    for key, event in events.items():
        metrics = event.get('market_metrics', {})
        decline = metrics.get('peak_decline_pct')
        if decline and key != 'ai_investment':
            names.append(event['name'])
            declines.append(decline)
            colors.append('#e74c3c')

    # Add AI as different color
    ai = events.get('ai_investment', {})
    ai_metrics = ai.get('market_metrics', {})
    ai_return = ai_metrics.get('avg_2y_price_change_pct', 0)
    names.append('AI Investment\n(2Y avg return)')
    declines.append(-ai_return)  # Negative because it's a gain not loss
    colors.append('#2ecc71')

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    bars = ax.barh(range(len(names)), declines, color=colors, edgecolor='white', linewidth=1.5)

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel('Peak-to-Trough Decline (%)', fontsize=11)
    ax.set_title('Market Performance: Historical Bubbles vs AI Investment', fontsize=13)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.grid(True, alpha=0.3, axis='x')

    # Annotate values
    for bar, val in zip(bars, declines):
        label = f'{val:.1f}%' if val > 0 else f'+{-val:.1f}%'
        x_pos = bar.get_width() + 1 if val > 0 else bar.get_width() - 5
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                label, ha='left' if val > 0 else 'right',
                va='center', fontsize=10, fontweight='bold')

    ax.invert_yaxis()
    plt.tight_layout()

    path = FIG_DIR / 'fig2_market_metrics.png'
    fig.savefig(str(path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")


def main():
    print("=" * 60)
    print("GENERATING FIGURES FOR ECONOMICS PAPER")
    print("=" * 60)

    print("\nFigure 1: Structural feature heatmap")
    fig1_structural_heatmap()

    print("Figure 2: Market metrics comparison")
    fig2_market_metrics()

    print(f"\nAll figures saved to: {FIG_DIR}")


if __name__ == "__main__":
    main()
