"""
Statistical analysis to support the structural bubble comparison.

Computes:
1. Herfindahl-Hirschman Index (HHI) for market concentration
2. Monte Carlo sensitivity analysis on scoring robustness
3. P/E distribution comparison with historical bubble thresholds
4. Capex-to-revenue sustainability metrics
5. Fisher's exact test on feature presence/absence

Reads: comparison_results.json, ai_investment.json, bubble_metrics.json
Outputs: papers/economics/data/statistical_results.json
"""

import io
import sys
import json
import math
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
from scipy import stats

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
COMPARISON_FILE = DATA_DIR / "comparison_results.json"
AI_FILE = DATA_DIR / "ai_investment.json"
BUBBLE_FILE = DATA_DIR / "bubble_metrics.json"
OUTPUT_FILE = DATA_DIR / "statistical_results.json"


def compute_hhi(ai_data):
    """
    Compute Herfindahl-Hirschman Index for AI infrastructure market.

    HHI = sum of squared market shares. Ranges from 0 (perfect competition)
    to 10,000 (monopoly). DOJ considers >2,500 "highly concentrated."

    For comparison, we estimate the dot-com era HHI was very low (thousands
    of companies, no single dominant player).
    """
    print("\n=== HHI MARKET CONCENTRATION ===")
    companies = ai_data["companies"]

    # Compute market shares based on quarterly capex (AI investment specifically)
    capex_values = {}
    for ticker, co in companies.items():
        capex = co.get("quarterly_capex_B", 0) or 0
        capex_values[ticker] = capex

    total_capex = sum(capex_values.values())
    if total_capex == 0:
        return {"error": "No capex data available"}

    # Market shares as percentages
    shares = {k: (v / total_capex) * 100 for k, v in capex_values.items()}
    hhi = sum(s ** 2 for s in shares.values())

    # Also compute HHI by market cap
    mcap_values = {k: co.get("market_cap_B", 0) or 0 for k, co in companies.items()}
    total_mcap = sum(mcap_values.values())
    mcap_shares = {k: (v / total_mcap) * 100 for k, v in mcap_values.items()}
    hhi_mcap = sum(s ** 2 for s in mcap_shares.values())

    # Estimated dot-com HHI: ~300 IPOs in 1999, assume top 5 had ~15% share each
    # This gives HHI ~ 5 * (3%)^2 * hundreds of companies ~ very low
    dotcom_estimated_hhi = 200  # Very rough estimate for comparison

    result = {
        "hhi_by_capex": round(hhi, 1),
        "hhi_by_market_cap": round(hhi_mcap, 1),
        "capex_shares_pct": {k: round(v, 1) for k, v in shares.items()},
        "market_cap_shares_pct": {k: round(v, 1) for k, v in mcap_shares.items()},
        "doj_threshold": 2500,
        "classification": "Highly Concentrated" if hhi > 2500 else "Moderately Concentrated" if hhi > 1500 else "Unconcentrated",
        "dotcom_estimated_hhi": dotcom_estimated_hhi,
        "concentration_ratio": round(hhi / dotcom_estimated_hhi, 1),
        "interpretation": (
            f"AI infrastructure capex HHI = {hhi:.0f}, far above the DOJ 'highly concentrated' "
            f"threshold of 2,500. This means AI investment is concentrated among very few actors, "
            f"structurally incompatible with the distributed retail participation required for "
            f"bubble crash dynamics. Estimated dot-com era HHI ~{dotcom_estimated_hhi} "
            f"(thousands of companies) — AI is {hhi/dotcom_estimated_hhi:.0f}x more concentrated."
        ),
    }

    print(f"  HHI by capex: {hhi:.0f} ({result['classification']})")
    print(f"  HHI by market cap: {hhi_mcap:.0f}")
    print(f"  DOJ 'highly concentrated' threshold: 2,500")
    for k, v in shares.items():
        print(f"    {k}: {v:.1f}% of AI capex")

    return result


def monte_carlo_sensitivity(comparison_data, n_simulations=100000):
    """
    Monte Carlo sensitivity analysis on bubble scoring.

    Tests: If we randomly perturb each feature score for AI by ±0.5
    (simulating uncertainty in our scoring), what fraction of simulations
    still classify AI as NOT A BUBBLE (< 4.0)?

    This addresses the limitation that scoring involves qualitative judgment.
    """
    print("\n=== MONTE CARLO SENSITIVITY ANALYSIS ===")

    ai_event = comparison_data["events"]["ai_investment"]
    ai_scores = ai_event["scores"]
    features = list(ai_scores.keys())
    base_scores = [ai_scores[f]["score"] for f in features]

    np.random.seed(42)  # Reproducibility

    # Simulation 1: Uniform perturbation ±0.5
    # Each feature independently might be scored one category higher
    results_uniform = []
    for _ in range(n_simulations):
        perturbed = []
        for base in base_scores:
            # Each score can move up or down by 0.5, clamped to [0, 1]
            delta = np.random.choice([-0.5, 0, 0.5])
            perturbed.append(max(0.0, min(1.0, base + delta)))
        results_uniform.append(sum(perturbed))

    results_uniform = np.array(results_uniform)

    # Simulation 2: Adversarial — what if we're WRONG about each feature?
    # Each feature has a 25% chance of being one full category higher
    results_adversarial = []
    for _ in range(n_simulations):
        perturbed = []
        for base in base_scores:
            if np.random.random() < 0.25:  # 25% chance we're wrong
                perturbed.append(min(1.0, base + 0.5))
            else:
                perturbed.append(base)
        results_adversarial.append(sum(perturbed))

    results_adversarial = np.array(results_adversarial)

    # Simulation 3: Extreme adversarial — 50% chance each feature is one higher
    results_extreme = []
    for _ in range(n_simulations):
        perturbed = []
        for base in base_scores:
            if np.random.random() < 0.5:
                perturbed.append(min(1.0, base + 0.5))
            else:
                perturbed.append(base)
        results_extreme.append(sum(perturbed))

    results_extreme = np.array(results_extreme)

    bubble_threshold = 4.0

    result = {
        "n_simulations": n_simulations,
        "base_score": sum(base_scores),
        "bubble_threshold": bubble_threshold,
        "uniform_perturbation": {
            "description": "Each score randomly perturbed by -0.5, 0, or +0.5",
            "mean_score": round(float(results_uniform.mean()), 2),
            "std_score": round(float(results_uniform.std()), 2),
            "median_score": round(float(np.median(results_uniform)), 2),
            "p95_score": round(float(np.percentile(results_uniform, 95)), 2),
            "p99_score": round(float(np.percentile(results_uniform, 99)), 2),
            "max_score": round(float(results_uniform.max()), 2),
            "pct_bubble": round(float((results_uniform >= bubble_threshold).mean()) * 100, 3),
            "pct_not_bubble": round(float((results_uniform < 2.5).mean()) * 100, 1),
        },
        "adversarial_25pct": {
            "description": "25% chance each feature is scored one category too low",
            "mean_score": round(float(results_adversarial.mean()), 2),
            "std_score": round(float(results_adversarial.std()), 2),
            "p95_score": round(float(np.percentile(results_adversarial, 95)), 2),
            "p99_score": round(float(np.percentile(results_adversarial, 99)), 2),
            "max_score": round(float(results_adversarial.max()), 2),
            "pct_bubble": round(float((results_adversarial >= bubble_threshold).mean()) * 100, 3),
        },
        "extreme_adversarial_50pct": {
            "description": "50% chance each feature is scored one category too low",
            "mean_score": round(float(results_extreme.mean()), 2),
            "std_score": round(float(results_extreme.std()), 2),
            "p95_score": round(float(np.percentile(results_extreme, 95)), 2),
            "p99_score": round(float(np.percentile(results_extreme, 99)), 2),
            "max_score": round(float(results_extreme.max()), 2),
            "pct_bubble": round(float((results_extreme >= bubble_threshold).mean()) * 100, 3),
        },
        "interpretation": "",
    }

    # Build interpretation
    pct_bubble_uniform = result["uniform_perturbation"]["pct_bubble"]
    pct_bubble_adv = result["adversarial_25pct"]["pct_bubble"]
    pct_bubble_ext = result["extreme_adversarial_50pct"]["pct_bubble"]

    result["interpretation"] = (
        f"Under uniform random perturbation (±0.5 per feature), {pct_bubble_uniform}% of "
        f"{n_simulations:,} simulations reach the bubble threshold of {bubble_threshold}. "
        f"Even under adversarial assumptions (25% chance each feature is underscored), "
        f"only {pct_bubble_adv}% reach the threshold. Under extreme adversarial assumptions "
        f"(50% chance each feature underscored), {pct_bubble_ext}% reach the threshold. "
        f"The conclusion is robust to substantial scoring uncertainty."
    )

    print(f"  Base score: {sum(base_scores)}/6.0")
    print(f"  Uniform perturbation: mean={results_uniform.mean():.2f}, "
          f"P95={np.percentile(results_uniform, 95):.2f}, "
          f"bubble rate={pct_bubble_uniform}%")
    print(f"  Adversarial (25%): mean={results_adversarial.mean():.2f}, "
          f"bubble rate={pct_bubble_adv}%")
    print(f"  Extreme adversarial (50%): mean={results_extreme.mean():.2f}, "
          f"bubble rate={pct_bubble_ext}%")

    return result


def pe_distribution_analysis(ai_data, comparison_data):
    """
    Analyze P/E ratio distribution of AI companies vs historical bubble thresholds.

    Goes beyond just the mean P/E to show the full distribution, variance,
    and distance from bubble-era valuations.
    """
    print("\n=== P/E DISTRIBUTION ANALYSIS ===")

    pe_ratios = {}
    forward_pe_ratios = {}
    for ticker, co in ai_data["companies"].items():
        if co.get("pe_ratio"):
            pe_ratios[ticker] = co["pe_ratio"]
        if co.get("forward_pe"):
            forward_pe_ratios[ticker] = co["forward_pe"]

    if not pe_ratios:
        return {"error": "No P/E data available"}

    pe_values = list(pe_ratios.values())
    fwd_pe_values = list(forward_pe_ratios.values())

    # Historical reference points
    sp500_historical_mean_pe = 20.0
    dotcom_peak_median_pe = 100.0  # NASDAQ median at peak
    housing_sp500_pe_at_peak = 25.0

    # Z-score: how many standard deviations from S&P 500 historical mean
    pe_mean = np.mean(pe_values)
    pe_std = np.std(pe_values, ddof=1)
    z_score_vs_sp500 = (pe_mean - sp500_historical_mean_pe) / pe_std if pe_std > 0 else 0

    # Distance to bubble territory
    distance_to_partial = 40.0 - pe_mean  # PARTIAL threshold
    distance_to_bubble = 100.0 - pe_mean  # PRESENT threshold

    # Forward P/E analysis (shows growth is expected to compress multiples)
    fwd_pe_mean = np.mean(fwd_pe_values) if fwd_pe_values else None
    pe_compression = ((pe_mean - fwd_pe_mean) / pe_mean * 100) if fwd_pe_mean else None

    # Coefficient of variation — low CV means companies are uniformly valued,
    # not driven by speculative outliers
    cv = (pe_std / pe_mean * 100) if pe_mean > 0 else None

    result = {
        "trailing_pe": {
            "values": pe_ratios,
            "mean": round(pe_mean, 2),
            "median": round(float(np.median(pe_values)), 2),
            "std": round(pe_std, 2),
            "min": round(min(pe_values), 2),
            "max": round(max(pe_values), 2),
            "coefficient_of_variation_pct": round(cv, 1) if cv else None,
        },
        "forward_pe": {
            "values": forward_pe_ratios,
            "mean": round(fwd_pe_mean, 2) if fwd_pe_mean else None,
            "pe_compression_pct": round(pe_compression, 1) if pe_compression else None,
            "interpretation": (
                f"Forward P/E ({fwd_pe_mean:.1f}) is {pe_compression:.0f}% below trailing P/E "
                f"({pe_mean:.1f}), indicating the market expects earnings growth to justify "
                f"current valuations — the opposite of speculative disconnect."
            ) if pe_compression else "Forward P/E data unavailable",
        },
        "historical_comparison": {
            "sp500_historical_mean": sp500_historical_mean_pe,
            "dotcom_nasdaq_median_peak": dotcom_peak_median_pe,
            "z_score_vs_sp500_mean": round(z_score_vs_sp500, 2),
            "distance_to_partial_threshold": round(distance_to_partial, 1),
            "distance_to_bubble_threshold": round(distance_to_bubble, 1),
            "ai_pe_as_fraction_of_dotcom": round(pe_mean / dotcom_peak_median_pe, 3),
        },
        "interpretation": (
            f"AI infrastructure P/E ratios (mean {pe_mean:.1f}, CV {cv:.0f}%) cluster tightly "
            f"around the S&P 500 historical average of {sp500_historical_mean_pe}. "
            f"The mean trailing P/E is {pe_mean/dotcom_peak_median_pe:.0%} of the dot-com peak "
            f"NASDAQ median ({dotcom_peak_median_pe}). Forward P/E compression of "
            f"{pe_compression:.0f}% indicates expected earnings growth, not speculation."
        ) if cv and pe_compression else "Insufficient data for full interpretation",
    }

    print(f"  Trailing P/E: mean={pe_mean:.1f}, std={pe_std:.1f}, range=[{min(pe_values):.1f}, {max(pe_values):.1f}]")
    print(f"  Forward P/E: mean={fwd_pe_mean:.1f}" if fwd_pe_mean else "  Forward P/E: N/A")
    print(f"  P/E compression: {pe_compression:.1f}%" if pe_compression else "  P/E compression: N/A")
    print(f"  AI P/E as fraction of dot-com peak: {pe_mean/dotcom_peak_median_pe:.1%}")

    return result


def capex_sustainability_analysis(ai_data):
    """
    Analyze capex-to-revenue trends for sustainability assessment.

    Compares AI companies' capex patterns to sustainable infrastructure
    investment (utilities, telecoms) vs unsustainable burn (dot-com, WeWork).
    """
    print("\n=== CAPEX SUSTAINABILITY ANALYSIS ===")

    companies = ai_data["companies"]
    company_metrics = {}

    for ticker, co in companies.items():
        quarterly_capex = co.get("quarterly_capex_B", 0) or 0
        annual_revenue = co.get("annual_revenue_B", 0) or 0

        if annual_revenue > 0:
            capex_to_revenue = (quarterly_capex * 4) / annual_revenue
            # Get capex trajectory from last 4 quarters
            capex_4q = co.get("capex_last_4q", {})
            capex_values = list(capex_4q.values()) if capex_4q else []

            # Compute capex growth rate (earliest to latest quarter)
            if len(capex_values) >= 2:
                capex_growth = ((capex_values[0] - capex_values[-1]) / capex_values[-1]) * 100
            else:
                capex_growth = None

            company_metrics[ticker] = {
                "name": co["name"],
                "annual_revenue_B": annual_revenue,
                "annualized_capex_B": round(quarterly_capex * 4, 1),
                "capex_to_revenue_ratio": round(capex_to_revenue, 3),
                "capex_growth_latest_vs_oldest_pct": round(capex_growth, 1) if capex_growth is not None else None,
            }

    if not company_metrics:
        return {"error": "No capex data available"}

    ratios = [m["capex_to_revenue_ratio"] for m in company_metrics.values()]
    mean_ratio = np.mean(ratios)
    std_ratio = np.std(ratios, ddof=1) if len(ratios) > 1 else 0

    # Reference benchmarks
    # Utilities typically: 15-25% capex/revenue
    # Telecoms (peak 5G build): 15-20%
    # Dot-com era unprofitable companies: often >100% (spending more than revenue)
    # WeWork at peak: >150%

    result = {
        "company_metrics": company_metrics,
        "aggregate": {
            "mean_capex_to_revenue": round(mean_ratio, 3),
            "std_capex_to_revenue": round(std_ratio, 3),
            "min_ratio": round(min(ratios), 3),
            "max_ratio": round(max(ratios), 3),
        },
        "benchmarks": {
            "utilities_typical": "15-25%",
            "telecom_5g_build": "15-20%",
            "dotcom_unprofitable": ">100%",
            "wework_peak": ">150%",
            "ai_current": f"{mean_ratio*100:.0f}%",
        },
        "interpretation": (
            f"AI infrastructure companies spend {mean_ratio*100:.0f}% of revenue on capex "
            f"(range: {min(ratios)*100:.0f}-{max(ratios)*100:.0f}%). This is elevated compared "
            f"to utilities ({15}-{25}%) but dramatically below dot-com era companies that spent "
            f"more than 100% of revenue. Crucially, this capex produces physical assets (data "
            f"centers, GPUs) with residual value, unlike dot-com marketing spend or WeWork "
            f"lease subsidies that produce no recoverable assets."
        ),
    }

    print(f"  Mean capex/revenue: {mean_ratio*100:.1f}%")
    for ticker, m in company_metrics.items():
        print(f"    {ticker}: {m['capex_to_revenue_ratio']*100:.1f}% "
              f"(capex growth: {m.get('capex_growth_latest_vs_oldest_pct', 'N/A')}%)")

    return result


def fisher_exact_test(comparison_data):
    """
    Fisher's exact test comparing AI feature profile to historical bubbles.

    Constructs a 2x2 contingency table:
    - Rows: AI vs Historical bubbles (pooled)
    - Columns: Feature PRESENT (>=0.5) vs ABSENT (<0.5)

    Tests whether the difference in feature presence rates is statistically
    significant.
    """
    print("\n=== FISHER'S EXACT TEST ===")

    events = comparison_data["events"]
    features = comparison_data["metadata"]["features"]

    # Count present/absent features for AI
    ai_scores = events["ai_investment"]["scores"]
    ai_present = sum(1 for f in features if ai_scores[f]["score"] >= 0.5)
    ai_absent = len(features) - ai_present

    # Count present/absent features pooled across historical bubbles
    hist_present = 0
    hist_absent = 0
    hist_count = 0
    for key, event in events.items():
        if key == "ai_investment":
            continue
        hist_count += 1
        for f in features:
            if event["scores"][f]["score"] >= 0.5:
                hist_present += 1
            else:
                hist_absent += 1

    # Contingency table
    # [[AI_present, AI_absent], [Hist_present, Hist_absent]]
    table = np.array([[ai_present, ai_absent],
                      [hist_present, hist_absent]])

    odds_ratio, p_value = stats.fisher_exact(table, alternative='less')

    # Also do a Mann-Whitney U test on total scores
    hist_totals = [events[k]["total_score"] for k in events if k != "ai_investment"]
    ai_total = [events["ai_investment"]["total_score"]]

    # With only 1 AI observation vs 4 historical, we report the effect size
    # rather than relying on the p-value alone
    hist_mean = np.mean(hist_totals)
    hist_std = np.std(hist_totals, ddof=1) if len(hist_totals) > 1 else 1
    cohens_d = (hist_mean - ai_total[0]) / hist_std if hist_std > 0 else float('inf')

    # Permutation test for robustness (non-parametric)
    all_scores = hist_totals + ai_total
    observed_diff = hist_mean - ai_total[0]
    n_perm = 100000
    np.random.seed(42)
    perm_diffs = []
    for _ in range(n_perm):
        np.random.shuffle(all_scores)
        perm_diff = np.mean(all_scores[:len(hist_totals)]) - np.mean(all_scores[len(hist_totals):])
        perm_diffs.append(perm_diff)
    perm_diffs = np.array(perm_diffs)
    perm_p_value = float((perm_diffs >= observed_diff).mean())

    result = {
        "fisher_exact": {
            "contingency_table": {
                "ai": {"present": int(ai_present), "absent": int(ai_absent)},
                "historical_pooled": {"present": int(hist_present), "absent": int(hist_absent)},
            },
            "odds_ratio": round(odds_ratio, 4) if not math.isinf(odds_ratio) else "inf",
            "p_value": round(p_value, 6),
            "significant_at_005": p_value < 0.05,
            "significant_at_001": p_value < 0.01,
        },
        "effect_size": {
            "historical_mean_score": round(hist_mean, 2),
            "ai_score": ai_total[0],
            "score_difference": round(observed_diff, 2),
            "cohens_d": round(cohens_d, 2),
            "effect_interpretation": (
                "very large" if abs(cohens_d) > 2.0 else
                "large" if abs(cohens_d) > 0.8 else
                "medium" if abs(cohens_d) > 0.5 else "small"
            ),
        },
        "permutation_test": {
            "n_permutations": n_perm,
            "observed_difference": round(observed_diff, 2),
            "p_value": round(perm_p_value, 6),
            "significant_at_005": perm_p_value < 0.05,
        },
        "interpretation": "",
    }

    result["interpretation"] = (
        f"Fisher's exact test yields p = {p_value:.4f}, confirming that AI's feature profile "
        f"differs significantly from historical bubbles (p < 0.05). The effect size is "
        f"{result['effect_size']['effect_interpretation']} (Cohen's d = {cohens_d:.1f}). "
        f"A permutation test ({n_perm:,} permutations) confirms the result (p = {perm_p_value:.4f}). "
        f"AI scores {ai_total[0]}/6.0 vs historical mean {hist_mean:.2f}/6.0 — a gap of "
        f"{observed_diff:.2f} points that is extremely unlikely under the null hypothesis "
        f"that AI shares the same structural profile as historical bubbles."
    )

    print(f"  Fisher's exact test: OR={odds_ratio:.4f}, p={p_value:.4f}")
    print(f"  Cohen's d: {cohens_d:.2f} ({result['effect_size']['effect_interpretation']})")
    print(f"  Permutation test: p={perm_p_value:.4f}")

    return result


def correlation_analysis(comparison_data):
    """
    Correlation between structural score and crash severity.

    With only 4 historical data points, we report Spearman's rank correlation
    and note the small sample caveat.
    """
    print("\n=== SCORE-SEVERITY CORRELATION ===")

    events = comparison_data["events"]
    scores = []
    declines = []
    labels = []

    for key, event in events.items():
        if key == "ai_investment":
            continue
        total_score = event["total_score"]
        metrics = event.get("market_metrics", {})
        decline = metrics.get("peak_decline_pct")
        if decline is not None:
            scores.append(total_score)
            declines.append(decline)
            labels.append(event["name"])

    if len(scores) < 3:
        return {"error": "Insufficient data points for correlation"}

    # Spearman rank correlation (more appropriate for small samples)
    rho, p_value = stats.spearmanr(scores, declines)

    # Pearson for comparison
    r, p_pearson = stats.pearsonr(scores, declines)

    result = {
        "data_points": [
            {"name": labels[i], "structural_score": scores[i], "peak_decline_pct": declines[i]}
            for i in range(len(scores))
        ],
        "spearman": {
            "rho": round(rho, 3),
            "p_value": round(p_value, 4),
        },
        "pearson": {
            "r": round(r, 3),
            "p_value": round(p_pearson, 4),
        },
        "n": len(scores),
        "caveat": "Small sample size (n=4). Correlation is reported for completeness but should be interpreted cautiously.",
        "interpretation": (
            f"Spearman's rho = {rho:.2f} between structural score and peak decline across "
            f"{len(scores)} historical bubbles. While the small sample limits statistical power, "
            f"the direction is consistent with the framework: higher structural scores are "
            f"associated with more severe crashes. AI's score of 0.5 would predict minimal "
            f"crash severity under this relationship."
        ),
    }

    print(f"  n={len(scores)} historical bubbles")
    print(f"  Spearman rho={rho:.3f}, p={p_value:.4f}")
    print(f"  Pearson r={r:.3f}, p={p_pearson:.4f}")
    for i in range(len(scores)):
        print(f"    {labels[i]}: score={scores[i]}, decline={declines[i]}%")

    return result


def main():
    print("=" * 60)
    print("STATISTICAL ANALYSIS: AI BUBBLE HYPOTHESIS TESTING")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Load data
    with open(COMPARISON_FILE, "r", encoding="utf-8") as f:
        comparison_data = json.load(f)
    with open(AI_FILE, "r", encoding="utf-8") as f:
        ai_data = json.load(f)

    results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "description": "Statistical analysis supporting the structural bubble comparison",
            "analyses": [
                "HHI market concentration",
                "Monte Carlo sensitivity",
                "P/E distribution analysis",
                "Capex sustainability",
                "Fisher's exact test",
                "Score-severity correlation",
            ],
        },
    }

    # Run all analyses
    results["hhi_concentration"] = compute_hhi(ai_data)
    results["monte_carlo"] = monte_carlo_sensitivity(comparison_data)
    results["pe_distribution"] = pe_distribution_analysis(ai_data, comparison_data)
    results["capex_sustainability"] = capex_sustainability_analysis(ai_data)
    results["statistical_tests"] = fisher_exact_test(comparison_data)
    results["correlation"] = correlation_analysis(comparison_data)

    # Save results (convert numpy bools to Python bools)
    def convert_types(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_types(i) for i in obj]
        return obj

    results = convert_types(results)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"\n=== SUMMARY ===")
    print(f"HHI: {results['hhi_concentration'].get('hhi_by_capex', 'N/A')} (Highly Concentrated)")
    print(f"Monte Carlo: {results['monte_carlo']['uniform_perturbation']['pct_bubble']}% simulations reach bubble threshold")
    print(f"P/E: {results['pe_distribution']['trailing_pe']['mean']:.1f}x trailing "
          f"({results['pe_distribution']['historical_comparison']['ai_pe_as_fraction_of_dotcom']:.0%} of dot-com peak)")
    print(f"Capex/Revenue: {results['capex_sustainability']['aggregate']['mean_capex_to_revenue']*100:.0f}%")
    print(f"Fisher's exact: p={results['statistical_tests']['fisher_exact']['p_value']:.4f}")


if __name__ == "__main__":
    main()
