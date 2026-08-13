# Analytics Methodology

## Decision frame

The analysis helps management allocate channel effort, manage dealer service and competitiveness, understand vehicle value/spread, and trust the pipeline. Findings use the synthetic January 2022–December 2025 snapshot and are not external estimates of the Swiss automotive market.

## Grain and denominators

- Inquiry volume, conversion, customer/vehicle attributes, fastest response, quote spread, and final sale value use one row per inquiry.
- Dealer speed, competitiveness, quote rank, anomaly, and dealer win rate use one row per quote.
- Accepted value is reconciled in both facts: the accepted quote amount equals final sale price.
- One-to-many inquiry/quote joins are never used to count conversion without `DISTINCTCOUNT` or prior aggregation.

## Core calculations

- Conversion rate = converted inquiries / inquiries.
- Dealer win rate = accepted quotes / dealer quotes.
- Quote spread (CHF) = highest valid quote − lowest valid quote.
- Relative quote spread = quote spread / lowest valid quote.
- Quote-to-market ratio = quote amount / estimated market value.
- Eight-hour SLA rate = inquiries with a fastest valid response under eight hours / inquiries.
- MoM and YoY growth use equal calendar periods via the date dimension.

## Analytical checks

- Key totals are recomputed from curated fact rows and stored in `analysis_summary.json`.
- Dealer scatter points all use the same dealer grain and quote window; quote volume remains available for reliability context.
- Time trends use 48 monthly observations.
- Response-band charts show inquiry volume to expose sparse tails.
- The response-SLA and referral-versus-social comparisons are repeated within each calendar year to reduce the risk that a portfolio-level result is only a time-mix artefact; 95% Wilson intervals are persisted for the response groups.
- Outliers use both a stable business threshold (0.70–1.08 quote-to-market ratio) and an IQR diagnostic in the notebook.
- Correlations describe association only; no causal claims are made.

## Chart map

| Section | Analytical question | Family | Fields | Supported takeaway |
|---|---|---|---|---|
| Executive trend | Is demand changing? | Line | Month, inquiries | Volume rose with seasonality over four years |
| Conversion trend | Is efficiency stable? | Line + rolling reference | Month, conversion rate | Conversion is broadly stable despite volume growth |
| Channel quality | Which sources convert? | Sorted horizontal bar | Lead source, conversion rate, inquiry volume | Referral channels outperform paid/social sources |
| Dealer performance | Do speed and competitiveness differ? | Scatter | Dealer response, win rate, ratio, volume | Dealers show material performance dispersion |
| Vehicle age | How does quote uncertainty change? | Ordered bar | Age band, relative spread | Older vehicles have higher proportional dispersion |
| Quote distribution | Are there unusual offers? | Histogram/box plot | Quote amount or ratio | Most offers cluster below market value with a small flagged tail |

Palette policy is single-root for trends/ranks, two-root for focal-versus-context comparisons, and colorblind-safe sequential encoding for dealer competitiveness. Standard magnitude bars start at zero; no dual axes or 3D forms are used.

## Limitations

- Data is generated from documented relationships; discovered patterns show analytical method, not evidence about a real marketplace.
- Unobserved acquisition cost means channel analysis measures quality, not ROI.
- Dealer assignment is synthetic and not randomized; dealer comparisons are descriptive.
- Vehicle condition and market value are modeled estimates without external valuation benchmarks.
- December 2025 ends on the 27th for inquiries so every response remains inside the date dimension; monthly volume is therefore a partial-period point and should be labeled if isolated.
