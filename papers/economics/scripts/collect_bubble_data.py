"""
Collect historical bubble data for structural comparison analysis.

Sources:
- yfinance: NASDAQ, Nikkei 225, S&P 500 historical prices
- FRED API: Case-Shiller Home Price Index, Federal Funds Rate, Margin Debt
- CoinGecko API: Bitcoin/crypto market cap history

Outputs: papers/economics/data/bubble_metrics.json
"""

import io
import sys
import json
import os
import time
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import numpy as np
import yfinance as yf
import pandas as pd

# Output path
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "bubble_metrics.json"

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")  # Optional — works without for some series


def fetch_yfinance_data(ticker, start, end, label):
    """Fetch historical price data from Yahoo Finance."""
    print(f"  Fetching {label} ({ticker}) from yfinance...")
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        if data.empty:
            print(f"    WARNING: No data returned for {ticker}")
            return None

        # Handle multi-level columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        close = data["Close"]
        peak_price = float(close.max())
        peak_date = str(close.idxmax().date())
        trough_price = float(close[close.idxmax():].min())
        trough_date = str(close[close.idxmax():].idxmin().date())
        decline_pct = ((peak_price - trough_price) / peak_price) * 100

        # Duration calculations
        peak_dt = datetime.strptime(peak_date, "%Y-%m-%d")
        trough_dt = datetime.strptime(trough_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        runup_months = (peak_dt - start_dt).days / 30.44
        crash_months = (trough_dt - peak_dt).days / 30.44

        result = {
            "ticker": ticker,
            "start_date": start,
            "peak_date": peak_date,
            "trough_date": trough_date,
            "peak_price": round(peak_price, 2),
            "trough_price": round(trough_price, 2),
            "decline_pct": round(decline_pct, 2),
            "runup_months": round(runup_months, 1),
            "crash_months": round(crash_months, 1),
            "data_points": len(close),
        }
        print(f"    Peak: {peak_price:.2f} ({peak_date}), Trough: {trough_price:.2f} ({trough_date})")
        print(f"    Decline: {decline_pct:.1f}%, Run-up: {runup_months:.0f} months, Crash: {crash_months:.0f} months")
        return result
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def fetch_fred_series(series_id, start, end, label):
    """Fetch data from FRED (Federal Reserve Economic Data)."""
    print(f"  Fetching {label} ({series_id}) from FRED...")
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "observation_start": start,
        "observation_end": end,
        "file_type": "json",
    }
    if FRED_API_KEY:
        params["api_key"] = FRED_API_KEY
    else:
        # Use the demo key (limited but functional)
        params["api_key"] = "DEMO_KEY"

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"    WARNING: FRED returned status {resp.status_code}")
            return None
        data = resp.json()
        if "observations" not in data:
            print(f"    WARNING: No observations in FRED response")
            return None

        observations = [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in data["observations"]
            if obs["value"] != "."
        ]

        if not observations:
            print(f"    WARNING: No valid observations")
            return None

        values = [obs["value"] for obs in observations]
        result = {
            "series_id": series_id,
            "start_date": observations[0]["date"],
            "end_date": observations[-1]["date"],
            "data_points": len(observations),
            "peak_value": round(max(values), 2),
            "trough_value": round(min(values), 2),
            "start_value": round(values[0], 2),
            "end_value": round(values[-1], 2),
        }
        print(f"    {len(observations)} observations, range: {min(values):.2f} - {max(values):.2f}")
        return result
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def fetch_coingecko_data():
    """Fetch Bitcoin market cap history from CoinGecko (proxy for crypto bubble)."""
    print("  Fetching Bitcoin market data from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "max", "interval": "daily"}

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"    WARNING: CoinGecko returned status {resp.status_code}")
            # Fall back to manual data
            return _manual_crypto_data()
        data = resp.json()
        prices = data.get("prices", [])
        if not prices:
            return _manual_crypto_data()

        # Convert to pandas for easier analysis
        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("date")

        # Find major cycles
        # Cycle 1: 2017 peak
        c1 = df["2016-01-01":"2019-01-01"]
        if not c1.empty:
            c1_peak = float(c1["price"].max())
            c1_peak_date = str(c1["price"].idxmax().date())
            c1_trough = float(c1["price"][c1["price"].idxmax():].min())
            c1_decline = ((c1_peak - c1_trough) / c1_peak) * 100
        else:
            c1_peak, c1_peak_date, c1_trough, c1_decline = None, None, None, None

        # Cycle 2: 2021 peak
        c2 = df["2020-01-01":"2023-01-01"]
        if not c2.empty:
            c2_peak = float(c2["price"].max())
            c2_peak_date = str(c2["price"].idxmax().date())
            c2_trough = float(c2["price"][c2["price"].idxmax():].min())
            c2_decline = ((c2_peak - c2_trough) / c2_peak) * 100
        else:
            c2_peak, c2_peak_date, c2_trough, c2_decline = None, None, None, None

        result = {
            "source": "coingecko",
            "total_data_points": len(prices),
            "cycle_2017": {
                "peak_price": round(c1_peak, 2) if c1_peak else None,
                "peak_date": c1_peak_date,
                "trough_price": round(c1_trough, 2) if c1_trough else None,
                "decline_pct": round(c1_decline, 1) if c1_decline else None,
            },
            "cycle_2021": {
                "peak_price": round(c2_peak, 2) if c2_peak else None,
                "peak_date": c2_peak_date,
                "trough_price": round(c2_trough, 2) if c2_trough else None,
                "decline_pct": round(c2_decline, 1) if c2_decline else None,
            },
        }
        if c1_peak:
            print(f"    2017 cycle: Peak ${c1_peak:.0f}, decline {c1_decline:.1f}%")
        if c2_peak:
            print(f"    2021 cycle: Peak ${c2_peak:.0f}, decline {c2_decline:.1f}%")
        return result
    except Exception as e:
        print(f"    ERROR: {e}")
        return _manual_crypto_data()


def _manual_crypto_data():
    """Manually sourced crypto data as fallback."""
    print("    Using manually sourced crypto data (CoinGecko unavailable)")
    return {
        "source": "manual (well-known historical values)",
        "cycle_2017": {
            "peak_price": 19783.06,
            "peak_date": "2017-12-17",
            "trough_price": 3191.30,
            "trough_date": "2018-12-15",
            "decline_pct": 83.9,
            "note": "BTC price from CoinMarketCap historical data",
        },
        "cycle_2021": {
            "peak_price": 68789.63,
            "peak_date": "2021-11-10",
            "trough_price": 15599.05,
            "trough_date": "2022-11-21",
            "decline_pct": 77.3,
            "note": "BTC price from CoinMarketCap historical data",
        },
    }


def collect_dotcom_bubble():
    """Collect data on the dot-com bubble (1995-2003)."""
    print("\n=== DOT-COM BUBBLE (1995-2003) ===")
    result = {"name": "Dot-com Bubble", "period": "1995-2003"}

    # NASDAQ Composite
    result["nasdaq"] = fetch_yfinance_data("^IXIC", "1995-01-01", "2003-12-31", "NASDAQ Composite")

    # S&P 500 for comparison
    result["sp500"] = fetch_yfinance_data("^GSPC", "1995-01-01", "2003-12-31", "S&P 500")

    # Structural features (manually sourced with citations)
    result["structural_features"] = {
        "retail_participation": {
            "value": "HIGH",
            "detail": "Number of online brokerage accounts grew from 1.5M (1997) to 9.7M (2000)",
            "source": "[CITATION NEEDED - SEC/FINRA data on online brokerage growth]",
        },
        "leverage": {
            "value": "HIGH",
            "detail": "NYSE margin debt peaked at $278.5B in March 2000, up from $141B in 1997",
            "source": "FINRA margin statistics",
        },
        "public_float": {
            "value": "HIGH",
            "detail": "486 IPOs in 1999, 406 in 2000. Average first-day return 71% in 1999",
            "source": "[CITATION NEEDED - Jay Ritter IPO data]",
        },
        "denial": {
            "value": "HIGH",
            "detail": "'New economy' narrative; Glassman & Hassett 'Dow 36,000' published 1999",
            "source": "Glassman & Hassett (1999), Dow 36,000",
        },
        "speculative_disconnect": {
            "value": "HIGH",
            "detail": "Median P/E of NASDAQ stocks exceeded 100 at peak; many IPOs had no revenue",
            "source": "[CITATION NEEDED - Shiller P/E data]",
        },
        "rapid_unwind": {
            "value": "HIGH",
            "detail": "NASDAQ fell 78% from peak (5,048) to trough (1,114) over 31 months",
            "source": "Market data (yfinance)",
        },
    }
    return result


def collect_housing_bubble():
    """Collect data on the 2008 US housing bubble (2003-2012)."""
    print("\n=== US HOUSING BUBBLE (2003-2012) ===")
    result = {"name": "US Housing Bubble", "period": "2003-2012"}

    # S&P 500 during crisis
    result["sp500"] = fetch_yfinance_data("^GSPC", "2003-01-01", "2012-12-31", "S&P 500")

    # Case-Shiller Home Price Index from FRED
    result["case_shiller"] = fetch_fred_series("CSUSHPISA", "2003-01-01", "2012-12-31",
                                                "Case-Shiller US Home Price Index")
    time.sleep(1)  # Rate limit FRED

    # Federal funds rate
    result["fed_funds"] = fetch_fred_series("FEDFUNDS", "2003-01-01", "2012-12-31",
                                            "Federal Funds Rate")

    result["structural_features"] = {
        "retail_participation": {
            "value": "HIGH",
            "detail": "Homeownership rate peaked at 69.2% (2004). Subprime loans ~20% of originations by 2006",
            "source": "US Census Bureau; Inside Mortgage Finance",
        },
        "leverage": {
            "value": "EXTREME",
            "detail": "Average LTV exceeded 80%; many loans 100%+ LTV. CDO notional values in trillions",
            "source": "[CITATION NEEDED - FCIC Report data]",
        },
        "public_float": {
            "value": "HIGH",
            "detail": "MBS widely held by pension funds, banks, retail investors globally",
            "source": "Financial Crisis Inquiry Commission Report (2011)",
        },
        "denial": {
            "value": "HIGH",
            "detail": "'Housing prices never decline nationally' was consensus. Bernanke (2005): 'no bubble'",
            "source": "Bernanke Congressional testimony, 2005",
        },
        "speculative_disconnect": {
            "value": "HIGH",
            "detail": "Home prices 70% above historical trend relative to rents and income",
            "source": "[CITATION NEEDED - Case-Shiller price-to-rent data]",
        },
        "rapid_unwind": {
            "value": "HIGH",
            "detail": "S&P 500 fell 57% from Oct 2007 to Mar 2009. Cascading bank failures, AIG bailout",
            "source": "Market data; TARP records",
        },
    }
    return result


def collect_japan_bubble():
    """Collect data on the Japanese asset bubble (1985-2000)."""
    print("\n=== JAPANESE ASSET BUBBLE (1985-2000) ===")
    result = {"name": "Japanese Asset Bubble", "period": "1985-2000"}

    # Nikkei 225
    result["nikkei"] = fetch_yfinance_data("^N225", "1985-01-01", "2003-12-31", "Nikkei 225")

    result["structural_features"] = {
        "retail_participation": {
            "value": "HIGH",
            "detail": "Japanese household stock ownership peaked; land speculation widespread among individuals",
            "source": "[CITATION NEEDED - Bank of Japan financial statistics]",
        },
        "leverage": {
            "value": "EXTREME",
            "detail": "Bank lending grew ~10% annually 1985-1989. Land used as collateral for further land purchases",
            "source": "[CITATION NEEDED - BOJ lending statistics]",
        },
        "public_float": {
            "value": "HIGH",
            "detail": "Tokyo Stock Exchange was world's largest by market cap in 1989. Highly liquid public markets",
            "source": "World Federation of Exchanges historical data",
        },
        "denial": {
            "value": "HIGH",
            "detail": "'Japan as Number One' narrative. Imperial Palace grounds worth more than all California real estate",
            "source": "Vogel (1979), Japan as Number One; widely cited comparison",
        },
        "speculative_disconnect": {
            "value": "HIGH",
            "detail": "Nikkei P/E exceeded 70 at peak. Land prices 5-10x reasonable valuations",
            "source": "[CITATION NEEDED - BOJ land price survey data]",
        },
        "rapid_unwind": {
            "value": "MODERATE",
            "detail": "Nikkei fell ~60% by 1992 but full recovery took 30+ years (slow deflation, not panic crash)",
            "source": "Market data (yfinance)",
        },
    }
    return result


def collect_nft_crypto():
    """Collect data on NFT/crypto cycles (2017-2023)."""
    print("\n=== NFT/CRYPTO CYCLES (2017-2023) ===")
    result = {"name": "NFT/Crypto Cycles", "period": "2017-2023"}

    # Bitcoin price data
    result["bitcoin"] = fetch_coingecko_data()
    time.sleep(1)

    result["structural_features"] = {
        "retail_participation": {
            "value": "HIGH",
            "detail": "Coinbase had 98M verified users by Q4 2021. NFT market dominated by retail",
            "source": "Coinbase Q4 2021 earnings; Chainalysis 2022 report",
        },
        "leverage": {
            "value": "MODERATE",
            "detail": "Significant DeFi leverage and exchange margin trading, but less than traditional finance",
            "source": "[CITATION NEEDED - DeFi Llama TVL data]",
        },
        "public_float": {
            "value": "HIGH",
            "detail": "Crypto markets operate 24/7 with near-instant settlement. Highly liquid for BTC/ETH",
            "source": "Market structure observation",
        },
        "denial": {
            "value": "MIXED",
            "detail": "Crypto community actively trained members to dismiss 'FUD'. But external skepticism was high",
            "source": "Cultural observation; strategic discussion analysis",
        },
        "speculative_disconnect": {
            "value": "HIGH",
            "detail": "NFT market reached $25B in 2021 sales. Many projects had no utility beyond speculation",
            "source": "[CITATION NEEDED - DappRadar/NonFungible.com annual report]",
        },
        "rapid_unwind": {
            "value": "HIGH",
            "detail": "BTC fell 77% (2021 cycle). NFT floor prices collapsed 90%+. FTX/Luna/3AC cascading failures",
            "source": "Market data; public reporting on FTX collapse",
        },
    }
    return result


def main():
    print("=" * 60)
    print("HISTORICAL BUBBLE DATA COLLECTION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "sources": ["yfinance", "FRED API", "CoinGecko API", "manual research"],
            "note": "Some structural features are manually sourced from published reports. "
                    "Items marked [CITATION NEEDED] require verification before final publication.",
        },
        "bubbles": {},
    }

    results["bubbles"]["dotcom"] = collect_dotcom_bubble()
    results["bubbles"]["housing_2008"] = collect_housing_bubble()
    results["bubbles"]["japan"] = collect_japan_bubble()
    results["bubbles"]["nft_crypto"] = collect_nft_crypto()

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Data saved to: {OUTPUT_FILE}")
    print(f"Bubbles collected: {len(results['bubbles'])}")

    # Summary table
    print(f"\n{'Bubble':<25} {'Peak-Trough Decline':<25} {'Crash Duration'}")
    print("-" * 70)
    for key, bubble in results["bubbles"].items():
        name = bubble["name"]
        # Find the primary market data
        for field in ["nasdaq", "sp500", "nikkei", "bitcoin"]:
            data = bubble.get(field)
            if data and isinstance(data, dict):
                if "decline_pct" in data:
                    decline = f"{data['decline_pct']:.1f}%"
                    crash = f"{data.get('crash_months', 'N/A')} months"
                    print(f"{name:<25} {decline:<25} {crash}")
                    break
                elif "cycle_2021" in data:
                    c = data["cycle_2021"]
                    if c and c.get("decline_pct"):
                        print(f"{name:<25} {c['decline_pct']:.1f}% (2021 cycle)    N/A")
                    break


if __name__ == "__main__":
    main()
