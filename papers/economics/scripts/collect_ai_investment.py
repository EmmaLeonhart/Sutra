"""
Collect current AI investment structure data for bubble comparison.

Sources:
- yfinance: NVIDIA, Microsoft, Google, Meta, Amazon capex and market data
- Manual research: Private market data, market structure

Outputs: papers/economics/data/ai_investment.json
"""

import io
import sys
import json
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "ai_investment.json"

# Top AI infrastructure companies
AI_COMPANIES = {
    "NVDA": "NVIDIA",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet/Google",
    "META": "Meta Platforms",
    "AMZN": "Amazon",
}


def fetch_company_data(ticker, name):
    """Fetch financial data for a major AI company."""
    print(f"  Fetching {name} ({ticker})...")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Market cap
        market_cap = info.get("marketCap", None)

        # Get quarterly financials for capex
        cashflow = stock.quarterly_cashflow
        capex = None
        capex_quarters = {}
        if cashflow is not None and not cashflow.empty:
            # Capital expenditure row
            for label in ["Capital Expenditure", "capitalExpenditure", "CapitalExpenditure"]:
                if label in cashflow.index:
                    capex_series = cashflow.loc[label]
                    capex = float(abs(capex_series.iloc[0]))  # Most recent quarter
                    # Get last 4 quarters
                    for i, (date, val) in enumerate(capex_series.items()):
                        if i < 4 and pd.notna(val):
                            capex_quarters[str(date.date())] = float(abs(val))
                    break

        # Revenue
        revenue = info.get("totalRevenue", None)

        # Stock price history (last 2 years for run-up analysis)
        hist = stock.history(period="2y")
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            price_2y_ago = float(hist["Close"].iloc[0])
            price_change_2y = ((current_price - price_2y_ago) / price_2y_ago) * 100
        else:
            current_price, price_2y_ago, price_change_2y = None, None, None

        result = {
            "name": name,
            "ticker": ticker,
            "market_cap_usd": market_cap,
            "market_cap_B": round(market_cap / 1e9, 1) if market_cap else None,
            "quarterly_capex_usd": capex,
            "quarterly_capex_B": round(capex / 1e9, 1) if capex else None,
            "capex_last_4q": {k: round(v / 1e9, 1) for k, v in capex_quarters.items()},
            "annual_revenue_usd": revenue,
            "annual_revenue_B": round(revenue / 1e9, 1) if revenue else None,
            "current_price": round(current_price, 2) if current_price else None,
            "price_2y_change_pct": round(price_change_2y, 1) if price_change_2y else None,
            "pe_ratio": info.get("trailingPE", None),
            "forward_pe": info.get("forwardPE", None),
        }

        print(f"    Market cap: ${result['market_cap_B']}B" if result['market_cap_B'] else "    Market cap: N/A")
        print(f"    Quarterly capex: ${result['quarterly_capex_B']}B" if result['quarterly_capex_B'] else "    Capex: N/A")
        print(f"    2Y price change: {result['price_2y_change_pct']}%" if result['price_2y_change_pct'] else "    Price: N/A")
        return result
    except Exception as e:
        print(f"    ERROR: {e}")
        return {"name": name, "ticker": ticker, "error": str(e)}


def collect_market_structure():
    """Document AI market structure characteristics relevant to bubble analysis."""
    print("\n=== AI MARKET STRUCTURE ===")
    return {
        "ownership_concentration": {
            "description": "AI infrastructure investment is concentrated among ~5 hyperscalers",
            "detail": "NVIDIA, Microsoft, Google, Meta, Amazon account for vast majority of AI compute capex",
            "comparison": "Dot-com had thousands of publicly traded companies. AI has handful of private + 5 public",
            "source": "Public earnings reports; market observation",
        },
        "private_market_dominance": {
            "description": "Most pure-play AI companies are private",
            "detail": "OpenAI ($157B valuation, private), Anthropic ($61.5B valuation, private), "
                      "xAI ($50B valuation, private). No major pure-play AI IPOs yet",
            "source": "[CITATION NEEDED - Crunchbase/PitchBook valuations, verify current figures]",
            "bubble_implication": "No public market mechanism for mass retail exit = no classic crash dynamic",
        },
        "capital_structure": {
            "description": "AI companies buy physical infrastructure, not market share via subsidies",
            "detail": "Data centers, GPUs, power contracts = real assets with residual value. "
                      "Unlike WeWork/blitzscaling where assets were leases and user subsidies",
            "comparison": "Blitzscaling: burn cash to buy market share. AI: buy compute to provide service",
            "source": "Earnings reports; Anthropic $50B data center announcement (2025)",
        },
        "cost_economics": {
            "description": "Training is lumpy capex; inference has favorable marginal costs",
            "detail": "Training a frontier model costs $100M-$1B+. But inference per query is low and declining. "
                      "Not the continuous cash burn of subsidizing every ride/delivery",
            "source": "[CITATION NEEDED - training cost estimates from Stanford AI Index or similar]",
        },
        "retail_exposure": {
            "description": "Minimal direct retail investor exposure to AI-specific risk",
            "detail": "Retail can buy NVDA/MSFT/GOOG but these are diversified companies. "
                      "Pure AI exposure requires VC fund access or indirect ETFs",
            "comparison": "Dot-com: retail could directly buy hundreds of internet-only stocks. "
                         "AI: retail mostly exposed via diversified tech giants",
            "source": "Market structure analysis",
        },
        "macro_environment": {
            "description": "Tight capital environment limits speculative excess",
            "detail": "Federal funds rate elevated vs 1999 (near-zero) or 2020-2021 (near-zero). "
                      "Reduces speculative capital availability for overvalued AI IPOs",
            "source": "Federal Reserve rate data",
        },
    }


def collect_structural_comparison_features():
    """Score AI investment against the 6 bubble structural features."""
    print("\n=== AI STRUCTURAL FEATURE SCORING ===")
    return {
        "denial_reflexivity": {
            "score": 0.0,
            "label": "ABSENT",
            "reasoning": "Public discourse widely questions AI valuations. 'AI bubble' is mainstream media narrative. "
                        "Contrast with dot-com ('new economy') and housing ('prices never fall') where denial was dominant. "
                        "Per the heuristic: if many people are calling it a bubble, it probably isn't one, "
                        "because real bubbles require widespread denial to sustain overvaluation.",
        },
        "mass_retail_participation": {
            "score": 0.0,
            "label": "ABSENT",
            "reasoning": "No mechanism for broad retail AI-specific investment. Major AI companies are private. "
                        "Public companies with AI exposure (NVDA, MSFT) are diversified. "
                        "Dot-com had 486 IPOs in 1999 alone; AI has had essentially zero pure-play IPOs.",
        },
        "leverage_amplification": {
            "score": 0.5,
            "label": "PARTIAL",
            "reasoning": "VC leverage exists (fund-of-funds, SPVs). But no consumer leverage (cf. mortgages in 2008) "
                        "and no derivative multiplication (cf. CDOs). Leverage is contained within sophisticated "
                        "institutional investors who understand the risk, not distributed to retail.",
        },
        "exit_liquidity": {
            "score": 0.0,
            "label": "ABSENT",
            "reasoning": "Private company shares are illiquid. No public market for mass simultaneous exit. "
                        "WeWork demonstrated the fizzle-not-pop pattern: private overvaluations just get written down. "
                        "For a crash, you need the ability to sell at scale, which requires public markets.",
        },
        "speculative_disconnect": {
            "score": 0.5,
            "label": "PARTIAL",
            "reasoning": "Some AI valuations may exceed near-term revenue potential (OpenAI at 100x+ revenue). "
                        "But unlike dot-com, the underlying technology demonstrably works and generates real revenue. "
                        "The question is WHICH companies capture value, not WHETHER the technology has value.",
        },
        "rapid_unwind_mechanism": {
            "score": 0.0,
            "label": "ABSENT",
            "reasoning": "No cascade mechanism. GPU assets can't be liquidated at scale (market would collapse). "
                        "Companies with compute infrastructure will restructure, not evaporate. "
                        "Even severely distressed AI companies look like utilities in bankruptcy, not dot-com zeros.",
        },
    }


def main():
    print("=" * 60)
    print("AI INVESTMENT STRUCTURE DATA COLLECTION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "sources": ["yfinance", "manual research", "public earnings reports"],
            "note": "Private market valuations are approximate and sourced from press reports. "
                    "Items marked [CITATION NEEDED] require verification.",
        },
        "companies": {},
        "market_structure": {},
        "structural_scores": {},
    }

    # Fetch data for each major AI company
    print("\n=== AI INFRASTRUCTURE COMPANIES ===")
    for ticker, name in AI_COMPANIES.items():
        results["companies"][ticker] = fetch_company_data(ticker, name)

    # Market structure analysis
    results["market_structure"] = collect_market_structure()

    # Structural feature scoring
    results["structural_scores"] = collect_structural_comparison_features()

    # Compute aggregate statistics
    companies = results["companies"]
    total_market_cap = sum(
        c.get("market_cap_B", 0) or 0 for c in companies.values()
    )
    total_quarterly_capex = sum(
        c.get("quarterly_capex_B", 0) or 0 for c in companies.values()
    )
    avg_2y_return = sum(
        c.get("price_2y_change_pct", 0) or 0 for c in companies.values()
        if c.get("price_2y_change_pct") is not None
    ) / max(1, sum(1 for c in companies.values() if c.get("price_2y_change_pct") is not None))

    results["aggregate"] = {
        "total_market_cap_B": round(total_market_cap, 1),
        "total_quarterly_capex_B": round(total_quarterly_capex, 1),
        "annualized_capex_B": round(total_quarterly_capex * 4, 1),
        "avg_2y_price_change_pct": round(avg_2y_return, 1),
        "bubble_score": sum(
            s["score"] for s in results["structural_scores"].values()
        ),
        "bubble_score_max": 6.0,
        "bubble_classification": "NOT A BUBBLE",
        "classification_reasoning": "AI investment scores 1.0/6.0 on structural bubble features. "
                                    "Classical bubble mechanics require mass retail participation, "
                                    "leverage amplification, exit liquidity, and rapid unwind mechanisms — "
                                    "none of which are present in the current AI investment structure.",
    }

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Data saved to: {OUTPUT_FILE}")
    print(f"\n=== AGGREGATE SUMMARY ===")
    print(f"Top 5 AI companies combined market cap: ${total_market_cap:.0f}B")
    print(f"Combined quarterly capex: ${total_quarterly_capex:.1f}B (annualized: ${total_quarterly_capex * 4:.1f}B)")
    print(f"Average 2-year stock price change: {avg_2y_return:.1f}%")
    print(f"\n=== BUBBLE STRUCTURAL SCORE ===")
    total_score = results["aggregate"]["bubble_score"]
    print(f"Total score: {total_score}/6.0")
    for feature, data in results["structural_scores"].items():
        print(f"  {feature}: {data['label']} ({data['score']})")
    print(f"\nClassification: {results['aggregate']['bubble_classification']}")


if __name__ == "__main__":
    main()
