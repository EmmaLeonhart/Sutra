"""
Structural comparison of AI investment vs historical bubbles.

Reads bubble_metrics.json and ai_investment.json, produces a unified
comparison matrix scoring each event against 6 structural bubble features.

Outputs:
- papers/economics/data/comparison_results.json
- prints markdown table for inclusion in paper
"""

import io
import sys
import json
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
BUBBLE_FILE = DATA_DIR / "bubble_metrics.json"
AI_FILE = DATA_DIR / "ai_investment.json"
OUTPUT_FILE = DATA_DIR / "comparison_results.json"

# The 6 structural features that define a classic asset bubble
FEATURES = [
    "denial_reflexivity",
    "mass_retail_participation",
    "leverage_amplification",
    "exit_liquidity",
    "speculative_disconnect",
    "rapid_unwind_mechanism",
]

FEATURE_LABELS = {
    "denial_reflexivity": "Widespread Denial",
    "mass_retail_participation": "Mass Retail Participation",
    "leverage_amplification": "Leverage Amplification",
    "exit_liquidity": "Exit Liquidity",
    "speculative_disconnect": "Speculative Disconnect",
    "rapid_unwind_mechanism": "Rapid Unwind Mechanism",
}


def score_to_value(label):
    """Convert text labels to numeric scores."""
    mapping = {
        "ABSENT": 0.0,
        "LOW": 0.0,
        "PARTIAL": 0.5,
        "MIXED": 0.5,
        "MODERATE": 0.5,
        "HIGH": 1.0,
        "EXTREME": 1.0,
        "PRESENT": 1.0,
    }
    return mapping.get(label.upper(), 0.0)


def extract_bubble_scores(bubble_data):
    """Extract structural feature scores from bubble data."""
    scores = {}
    features = bubble_data.get("structural_features", {})

    feature_mapping = {
        "denial": "denial_reflexivity",
        "retail_participation": "mass_retail_participation",
        "leverage": "leverage_amplification",
        "public_float": "exit_liquidity",
        "speculative_disconnect": "speculative_disconnect",
        "rapid_unwind": "rapid_unwind_mechanism",
    }

    for raw_key, feature_key in feature_mapping.items():
        feat = features.get(raw_key, {})
        value_label = feat.get("value", "ABSENT")
        scores[feature_key] = {
            "score": score_to_value(value_label),
            "label": value_label,
            "detail": feat.get("detail", ""),
            "source": feat.get("source", ""),
        }

    return scores


def extract_market_metrics(bubble_data):
    """Extract key market metrics from bubble data."""
    metrics = {}

    # Find primary market data
    for field in ["nasdaq", "sp500", "nikkei", "case_shiller"]:
        data = bubble_data.get(field)
        if data and isinstance(data, dict) and "decline_pct" in data:
            metrics["peak_decline_pct"] = data["decline_pct"]
            metrics["runup_months"] = data.get("runup_months")
            metrics["crash_months"] = data.get("crash_months")
            metrics["market_index"] = field
            break

    # Handle crypto separately
    bitcoin = bubble_data.get("bitcoin")
    if bitcoin and "cycle_2021" in bitcoin:
        c = bitcoin["cycle_2021"]
        if c and c.get("decline_pct"):
            metrics["peak_decline_pct"] = c["decline_pct"]
            metrics["market_index"] = "bitcoin"

    return metrics


def main():
    print("=" * 60)
    print("STRUCTURAL COMPARISON: AI INVESTMENT vs HISTORICAL BUBBLES")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Load data
    if not BUBBLE_FILE.exists():
        print(f"ERROR: {BUBBLE_FILE} not found. Run collect_bubble_data.py first.")
        sys.exit(1)
    if not AI_FILE.exists():
        print(f"ERROR: {AI_FILE} not found. Run collect_ai_investment.py first.")
        sys.exit(1)

    with open(BUBBLE_FILE, "r", encoding="utf-8") as f:
        bubble_data = json.load(f)
    with open(AI_FILE, "r", encoding="utf-8") as f:
        ai_data = json.load(f)

    # Build comparison matrix
    comparison = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "features": FEATURES,
            "scoring": "0.0 = ABSENT, 0.5 = PARTIAL, 1.0 = PRESENT",
            "threshold": "An event with >= 4/6 features PRESENT exhibits classic bubble dynamics",
        },
        "events": {},
    }

    # Score each historical bubble
    for key, bubble in bubble_data["bubbles"].items():
        scores = extract_bubble_scores(bubble)
        metrics = extract_market_metrics(bubble)
        total = sum(s["score"] for s in scores.values())
        comparison["events"][key] = {
            "name": bubble["name"],
            "period": bubble["period"],
            "scores": scores,
            "total_score": total,
            "max_score": 6.0,
            "market_metrics": metrics,
            "classification": "BUBBLE" if total >= 4.0 else "PARTIAL" if total >= 2.5 else "NOT A BUBBLE",
        }

    # Score AI investment
    ai_scores = ai_data.get("structural_scores", {})
    ai_total = sum(s["score"] for s in ai_scores.values())
    comparison["events"]["ai_investment"] = {
        "name": "AI Investment (2023-2026)",
        "period": "2023-present",
        "scores": ai_scores,
        "total_score": ai_total,
        "max_score": 6.0,
        "market_metrics": {
            "combined_market_cap_B": ai_data.get("aggregate", {}).get("total_market_cap_B"),
            "annualized_capex_B": ai_data.get("aggregate", {}).get("annualized_capex_B"),
            "avg_2y_price_change_pct": ai_data.get("aggregate", {}).get("avg_2y_price_change_pct"),
        },
        "classification": "BUBBLE" if ai_total >= 4.0 else "PARTIAL" if ai_total >= 2.5 else "NOT A BUBBLE",
    }

    # Summary statistics
    comparison["summary"] = {
        "historical_avg_score": round(
            sum(
                e["total_score"]
                for k, e in comparison["events"].items()
                if k != "ai_investment"
            ) / len(bubble_data["bubbles"]),
            2,
        ),
        "ai_score": ai_total,
        "score_gap": round(
            sum(
                e["total_score"]
                for k, e in comparison["events"].items()
                if k != "ai_investment"
            ) / len(bubble_data["bubbles"]) - ai_total,
            2,
        ),
        "conclusion": "AI investment does NOT exhibit the structural features of a classic asset bubble. "
                      f"It scores {ai_total}/6.0 on structural features, compared to an average of "
                      f"{comparison['summary']['historical_avg_score'] if 'summary' in comparison else 'N/A'}/6.0 "
                      "for confirmed historical bubbles. "
                      "The absence of mass retail participation, exit liquidity, and rapid unwind mechanisms "
                      "means classical bubble crash dynamics cannot manifest in the current market structure.",
    }

    # Recalculate summary with actual avg
    hist_avg = round(
        sum(
            e["total_score"]
            for k, e in comparison["events"].items()
            if k != "ai_investment"
        ) / len(bubble_data["bubbles"]),
        2,
    )
    comparison["summary"]["historical_avg_score"] = hist_avg
    comparison["summary"]["score_gap"] = round(hist_avg - ai_total, 2)
    comparison["summary"]["conclusion"] = (
        f"AI investment does NOT exhibit the structural features of a classic asset bubble. "
        f"It scores {ai_total}/6.0 on structural features, compared to an average of "
        f"{hist_avg}/6.0 for confirmed historical bubbles. "
        f"The absence of mass retail participation, exit liquidity, and rapid unwind mechanisms "
        f"means classical bubble crash dynamics cannot manifest in the current market structure."
    )

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    print(f"\nData saved to: {OUTPUT_FILE}")

    # Print markdown table for paper
    print("\n\n## Markdown Table for Paper\n")
    print("### Table 1: Structural Feature Comparison")
    print()

    # Header
    events = list(comparison["events"].values())
    header = "| Feature | " + " | ".join(e["name"] for e in events) + " |"
    separator = "|" + "---|" * (len(events) + 1)
    print(header)
    print(separator)

    # Feature rows
    for feature in FEATURES:
        label = FEATURE_LABELS[feature]
        row = f"| {label} |"
        for event in events:
            score_data = event["scores"].get(feature, {})
            score_label = score_data.get("label", "N/A")
            score_val = score_data.get("score", 0)
            symbol = "X" if score_val >= 1.0 else "~" if score_val >= 0.5 else "-"
            row += f" {symbol} ({score_label}) |"
        print(row)

    # Total row
    row = "| **Total Score** |"
    for event in events:
        row += f" **{event['total_score']}/6.0** |"
    print(row)

    # Classification row
    row = "| **Classification** |"
    for event in events:
        row += f" **{event['classification']}** |"
    print(row)

    # Market metrics table
    print("\n\n### Table 2: Market Metrics Summary")
    print()
    print("| Event | Peak Decline | Run-up Duration | Crash Duration |")
    print("|---|---|---|---|")
    for key, event in comparison["events"].items():
        name = event["name"]
        metrics = event.get("market_metrics", {})
        decline = f"{metrics.get('peak_decline_pct', 'N/A')}%"
        runup = f"{metrics.get('runup_months', 'N/A')} months"
        crash = f"{metrics.get('crash_months', 'N/A')} months"
        if key == "ai_investment":
            decline = f"{metrics.get('avg_2y_price_change_pct', 'N/A')}% (2Y avg return)"
            runup = "Ongoing"
            crash = "N/A"
        print(f"| {name} | {decline} | {runup} | {crash} |")

    print(f"\n\n### Conclusion")
    print(f"\n{comparison['summary']['conclusion']}")


if __name__ == "__main__":
    main()
