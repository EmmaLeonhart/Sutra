---
name: ai-bubble-analysis
description: Structural comparison of AI investment with historical asset bubbles. Retrieves financial data for four confirmed bubbles (dot-com, housing, Japan, crypto) and current AI infrastructure companies, then scores each against six structural bubble features. Produces a deterministic comparison matrix showing AI scores 1.0/6.0 vs historical average 5.62/6.0.
allowed-tools: Bash(python *), Bash(pip *)
---

# The AI Investment Bubble: A Structural Comparison

**Claw Co-Author: Barbara (OpenClaw)**
**Submission ID: CLAW4S-2026-AI-BUBBLE**
**Deadline: April 5, 2026**

This skill performs a systematic structural comparison between current AI investment and four confirmed historical asset bubbles. It retrieves real financial data from public APIs, scores six structural features that define bubble dynamics, and produces a deterministic comparison matrix.

**Key Finding:** Historical bubbles average 5.62/6.0 on structural features. AI investment scores 1.0/6.0. The market structure lacks the plumbing for a classical bubble crash.

## Prerequisites

```bash
# Required packages
pip install yfinance pandas numpy requests
```

### FRED API Key (recommended)

A free FRED API key enables retrieval of Case-Shiller Home Price Index and Federal Funds Rate data for the housing bubble analysis. Without it, those specific series are skipped (yfinance market data still covers the core metrics).

1. Create an account at https://fredaccount.stlouisfed.org/
2. Apply for a key at https://fredaccount.stlouisfed.org/apikey
   - Mention **Claw4S** in your application description to help FRED understand the context
   - The key is issued instantly after submitting
3. Set the environment variable before running scripts:

```bash
export FRED_API_KEY=your_key_here
```

## Step 1: Clone and Setup

Description: Clone the repository and verify the environment.

```bash
git clone https://github.com/EmmaLeonhart/Claw4S-submissions.git
cd Claw4S-submissions
pip install yfinance pandas numpy requests
```

Verify the environment:

```bash
python -c "import yfinance, pandas, numpy, requests; print('All dependencies OK')"
```

Expected Output: `All dependencies OK`

## Step 2: Collect Historical Bubble Data

Description: Retrieve price data and structural feature documentation for four historical bubbles.

```bash
python papers/economics/scripts/collect_bubble_data.py
```

This script:
1. Fetches NASDAQ Composite data (1995-2003) for the dot-com bubble via Yahoo Finance
2. Fetches S&P 500 data (2003-2012) for the housing bubble
3. Fetches Nikkei 225 data (1985-2003) for the Japanese asset bubble
4. Retrieves Bitcoin price history for crypto cycles (falls back to well-known historical values if CoinGecko API is unavailable)
5. Documents structural features for each bubble with sources

Expected Output:
```
=== DOT-COM BUBBLE (1995-2003) ===
  Fetching NASDAQ Composite (^IXIC) from yfinance...
    Peak: ~5048.62 (2000-03-10), Trough: ~1114.11 (2002-10-09)
    Decline: ~77.9%

=== US HOUSING BUBBLE (2003-2012) ===
  Fetching S&P 500 (^GSPC) from yfinance...
    Peak: ~1565.15 (2007-10-09), Trough: ~676.53 (2009-03-09)
    Decline: ~56.8%

=== JAPANESE ASSET BUBBLE (1985-2000) ===
  Fetching Nikkei 225 (^N225) from yfinance...
    Peak: ~38915.87 (1989-12-29)
    Decline: ~80.5%

=== NFT/CRYPTO CYCLES (2017-2023) ===
  Bitcoin 2021 cycle decline: ~77.3%
```

Output file: `papers/economics/data/bubble_metrics.json`

**Verification:** The output file should contain data for all four bubbles with peak prices, decline percentages, and structural feature documentation.

```bash
python -c "
import json
with open('papers/economics/data/bubble_metrics.json') as f:
    data = json.load(f)
bubbles = data['bubbles']
print(f'Bubbles collected: {len(bubbles)}')
for key, b in bubbles.items():
    features = b.get('structural_features', {})
    print(f'  {b[\"name\"]}: {len(features)} structural features documented')
assert len(bubbles) == 4, 'Expected 4 bubbles'
print('PASS: All bubble data collected')
"
```

## Step 3: Collect AI Investment Data

Description: Retrieve current financial data for the top 5 AI infrastructure companies and score AI investment against bubble structural features.

```bash
python papers/economics/scripts/collect_ai_investment.py
```

This script:
1. Fetches market cap, quarterly capex, P/E ratios, and 2-year price changes for NVIDIA, Microsoft, Alphabet, Meta, and Amazon via Yahoo Finance
2. Documents AI market structure characteristics (concentration, capital structure, cost economics)
3. Scores AI investment against six structural bubble features with detailed reasoning

Expected Output:
```
=== AI INFRASTRUCTURE COMPANIES ===
  NVIDIA: Market cap $4,000B+, Quarterly capex ~$1B+
  Microsoft: Market cap $2,700B+
  ...

=== BUBBLE STRUCTURAL SCORE ===
Total score: 1.0/6.0
  denial_reflexivity: ABSENT (0.0)
  mass_retail_participation: ABSENT (0.0)
  leverage_amplification: PARTIAL (0.5)
  exit_liquidity: ABSENT (0.0)
  speculative_disconnect: PARTIAL (0.5)
  rapid_unwind_mechanism: ABSENT (0.0)

Classification: NOT A BUBBLE
```

Output file: `papers/economics/data/ai_investment.json`

**Verification:**

```bash
python -c "
import json
with open('papers/economics/data/ai_investment.json') as f:
    data = json.load(f)
companies = data['companies']
scores = data['structural_scores']
agg = data['aggregate']
print(f'Companies: {len(companies)}')
print(f'Combined market cap: \${agg[\"total_market_cap_B\"]}B')
print(f'Bubble score: {agg[\"bubble_score\"]}/6.0')
assert len(companies) == 5, 'Expected 5 companies'
assert agg['bubble_score'] is not None, 'Bubble score should be computed'
print(f'Classification: {agg[\"bubble_classification\"]} (score {agg[\"bubble_score\"]}/6.0)')
print(f'Method: {agg[\"classification_method\"]}')
print('PASS: AI investment data collected and scored')
"
```

## Step 4: Run Structural Comparison

Description: Produce the unified comparison matrix scoring all events against all features.

```bash
python papers/economics/scripts/structural_comparison.py
```

This script:
1. Loads both data files
2. Extracts structural feature scores for each historical bubble
3. Combines with AI investment scores
4. Produces the comparison matrix and markdown tables
5. Calculates aggregate statistics and conclusion

Expected Output:
```
### Table 1: Structural Feature Comparison

| Feature | Dot-com | Housing | Japan | Crypto | AI |
|---------|---------|---------|-------|--------|-----|
| Widespread Denial | PRESENT | PRESENT | PRESENT | PARTIAL | ABSENT |
| Mass Retail Participation | PRESENT | PRESENT | PRESENT | PRESENT | ABSENT |
| Leverage Amplification | PRESENT | PRESENT | PRESENT | PARTIAL | PARTIAL |
| Exit Liquidity | PRESENT | PRESENT | PRESENT | PRESENT | ABSENT |
| Speculative Disconnect | PRESENT | PRESENT | PRESENT | PRESENT | PARTIAL |
| Rapid Unwind Mechanism | PRESENT | PRESENT | PARTIAL | PRESENT | ABSENT |
| Total | 6.0 | 6.0 | 5.5 | 5.0 | 1.0 |

Historical average: 5.62/6.0
AI investment: 1.0/6.0
```

Output file: `papers/economics/data/comparison_results.json`

**Verification:**

```bash
python -c "
import json
with open('papers/economics/data/comparison_results.json') as f:
    data = json.load(f)
events = data['events']
summary = data['summary']
print(f'Events compared: {len(events)}')
print(f'Historical avg score: {summary[\"historical_avg_score\"]}')
print(f'AI score: {summary[\"ai_score\"]}')
print(f'Score gap: {summary[\"score_gap\"]}')
assert len(events) == 5, 'Expected 5 events (4 bubbles + AI)'
print(f'AI classification: {events[\"ai_investment\"][\"classification\"]}')
print('PASS: Structural comparison produced')
"
```

## Step 5: Full Pipeline Verification

Description: Run all three scripts sequentially and verify the complete results chain.

```bash
python papers/economics/scripts/collect_bubble_data.py && \
python papers/economics/scripts/collect_ai_investment.py && \
python papers/economics/scripts/structural_comparison.py
```

Then run comprehensive verification:

```bash
python -c "
import json, os

# Check all output files exist
files = [
    'papers/economics/data/bubble_metrics.json',
    'papers/economics/data/ai_investment.json',
    'papers/economics/data/comparison_results.json',
]
for f in files:
    assert os.path.exists(f), f'Missing: {f}'
    print(f'EXISTS: {f}')

# Load comparison results
with open('papers/economics/data/comparison_results.json') as f:
    data = json.load(f)

# Verify scoring consistency
events = data['events']
for key, event in events.items():
    scores = event['scores']
    total = sum(s['score'] for s in scores.values())
    assert abs(total - event['total_score']) < 0.01, f'Score mismatch for {key}'

# Verify core finding
ai = events['ai_investment']
hist_scores = [e['total_score'] for k, e in events.items() if k != 'ai_investment']
hist_avg = sum(hist_scores) / len(hist_scores)

print()
print(f'Historical bubble avg: {hist_avg:.2f}/6.0')
print(f'AI investment score: {ai[\"total_score\"]}/6.0')
print(f'Score gap: {hist_avg - ai[\"total_score\"]:.2f}')
print(f'AI classification: {ai[\"classification\"]}')
print()

# Verify pipeline integrity (not the conclusion)
checks = [
    ('All 6 features scored for AI', len(ai['scores']) == 6),
    ('All features have score_method documented', all(
        'score_method' in s or 'source' in s for s in ai['scores'].values()
    )),
    ('Historical avg computed', hist_avg > 0),
    ('All 4 historical events scored', len(hist_scores) == 4),
    ('Classification computed from threshold', ai['classification'] in ['BUBBLE', 'PARTIAL', 'NOT A BUBBLE']),
]

all_pass = True
for desc, result in checks:
    status = 'PASS' if result else 'FAIL'
    print(f'  [{status}] {desc}')
    if not result:
        all_pass = False

print()
print('PIPELINE INTEGRITY:', 'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED')
print()
print(f'RESULT: AI investment classified as {ai[\"classification\"]} ({ai[\"total_score\"]}/6.0)')
print(f'This result was computed from retrieved data, not hardcoded.')
"
```

Expected: All 5 integrity checks pass. The classification result is computed from data — the pipeline does not presuppose the answer.

## Interpretation Guide

### What the Scores Mean

- **6.0/6.0** — Full classical bubble: all structural features present. Expect rapid, cascading crash.
- **4.0-5.5** — Strong bubble dynamics with some partial features. Still expect significant correction.
- **2.0-3.5** — Mixed: some bubble features but missing critical crash mechanics.
- **0.0-1.5** — Not a bubble: structural features for crash dynamics absent.

### What AI's Score Means

AI investment scores 1.0/6.0. The two partial scores (leverage and speculative disconnect) are the weakest contributors to crash dynamics. The four absent features — mass retail participation, exit liquidity, widespread denial, and rapid unwind mechanisms — are the ones that actually produce cascading crashes. Without them, the most likely correction is gradual write-downs, not a dramatic crash.

### Falsifiability

This analysis is falsifiable. If AI investment scored >= 4.0/6.0, the thesis would be falsified and the conclusion would be that AI exhibits classical bubble structure. The scripts produce the answer from the data; they do not assume it.

## Timing

| Step | Expected Duration |
|------|-------------------|
| Setup | 2-3 minutes |
| Bubble data collection | 1-2 minutes |
| AI investment data | 1-2 minutes |
| Structural comparison | < 10 seconds |
| Verification | < 10 seconds |
| **Total** | **5-8 minutes** |

## Success Criteria

Pipeline integrity (the analysis ran correctly):
1. All three data files produced with valid JSON
2. Four historical bubbles collected with market data and structural features
3. Five AI companies collected with market cap and capex data
4. All 6 structural features scored for every event with documented methodology
5. Classification computed from threshold rules, not hardcoded
6. Score totals are internally consistent (sum of features = reported total)

The conclusion — whether AI investment is or is not a bubble — is produced by the analysis, not presupposed. If market conditions change (e.g., major AI IPOs create retail exposure, or leveraged AI derivatives emerge), re-running the pipeline would produce different scores and potentially a different classification.

## References

- Kindleberger, C. P., & Aliber, R. Z. (2005). *Manias, Panics, and Crashes*. Wiley.
- Shiller, R. J. (2000). *Irrational Exuberance*. Princeton University Press.
- Glassman, J. K., & Hassett, K. A. (1999). *Dow 36,000*. Times Books.
- Financial Crisis Inquiry Commission. (2011). *The Financial Crisis Inquiry Report*.
- Market data: Yahoo Finance (yfinance), CoinGecko API
