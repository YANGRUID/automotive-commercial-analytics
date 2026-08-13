# Automotive Commercial Performance — Management Insights

Scope: 99,813 curated inquiries and 343,120 curated dealer quotes from January 2022 through December 2025. The portfolio dataset is synthetic and reproducible with seed 42.

## Executive readout

- Inquiries grew from 21,456 in 2022 to 28,336 in 2025 (+32.1%), while annual conversion remained close to 32%.
- Dealer Referral was the strongest converting source at 38.43%; Social Media was the weakest at 26.81%.
- A first dealer response inside eight hours was associated with a 3.84 percentage-point conversion advantage.
- Accepted quotes were closer to appraised market value and faster than non-accepted quotes.
- Data-quality remediation produced a 100% processed pass rate on the defined rule set while preserving a separate pricing-anomaly review queue.

## Lead-source quality: referral leads convert best; social converts worst

**Observation:** Dealer Referral is the highest-converting lead source, while Social Media is the lowest.

**Evidence:** Dealer Referral produced 16,191 inquiries and 6,222 conversions, a 38.43% conversion rate. Social Media produced 11,556 inquiries and 3,098 conversions, a 26.81% rate. The gap of 11.62 percentage points remained positive in every year. Paid Search also underperformed at 27.99% across 19,110 inquiries.

**Meaning:** Acquisition volume is not a reliable proxy for lead quality. The strongest source converted 1.43 times as often as the weakest, but channel cost is not present in the dataset.

**Action:** Protect dealer-referral partnerships. Review social and paid-search targeting before adding spend, then add acquisition cost and dealer fee data so channel decisions can use contribution rather than conversion alone.

## Dealer outlier: Ticino Autohaus 111 leads on win rate and accepted value

**Observation:** Ticino Autohaus 111 is a clear positive dealer outlier; Eastern Autohaus 142 is the weakest win-rate outlier.

**Evidence:** Ticino Autohaus 111 won 729 of 2,296 quotes (31.75%) and generated CHF 16.92 million of accepted value with a 6.17-hour average response. Eastern Autohaus 142 won 18 of 2,290 quotes (0.79%), generated CHF 0.17 million, and averaged an 86.02% quote-to-market ratio. Across all dealers, the median win rate was 8.18%; every dealer handled more than 1,000 curated quotes.

**Meaning:** The dispersion is not a small-sample artefact. Competitiveness and response speed differ enough to affect marketplace outcomes and dealer economics.

**Action:** Use the Dealer page to review bottom-decile dealers by region and vehicle mix. Pair a minimum-volume ranking threshold with targeted coaching on pricing and response time; do not use rank alone for contract decisions.

## Pricing competitiveness: accepted quotes are closer to market value

**Observation:** Accepted quotes were both more competitive and faster than non-accepted quotes.

**Evidence:** The 32,464 accepted quotes averaged 96.73% of estimated market value and 10.19 response hours. The 310,656 non-accepted quotes averaged 91.57% and 12.28 hours. The differences were 5.17 percentage points in quote-to-market ratio and 2.09 hours in response time.

**Meaning:** Dealers win when they combine credible pricing with timely responses. A low quote is not automatically competitive if it is materially below the appraisal benchmark or arrives too late.

**Action:** Manage dealers with a balanced scorecard: quote-to-market ratio, response time, win rate, quote volume, accepted value, and anomaly rate. Review the 1,162 quotes outside the 0.70–1.08 monitoring band rather than deleting them silently.

## Response time: the eight-hour SLA separates conversion performance

**Observation:** Inquiries receiving a first quote inside eight hours converted more often.

**Evidence:** 80,382 under-eight-hour inquiries converted at 33.27%. The 19,431 inquiries at eight hours or more converted at 29.43%, a 3.84 percentage-point gap. The faster group remained ahead in every year, with annual gaps from 3.27 to 4.19 points.

**Meaning:** Both groups have sufficient volume for an operational SLA comparison. This is a descriptive association, not proof that response speed alone causes the conversion difference.

**Action:** Alert dealers before the eight-hour threshold, report the share of inquiries within SLA, and monitor conversion and volume by response band. Test whether the relationship remains after controlling for vehicle value, type, region, and lead source.

## Data-quality remediation: a high raw score still hid material defects

**Observation:** The raw data was superficially strong, but remediation changed commercially relevant records and made the loaded model internally consistent.

**Evidence:** The raw check-weighted score was 99.947% (7,743,556 passed of 7,747,628 applicable checks). The processed rule set passed 7,710,401 of 7,710,401 checks. The pipeline quarantined 2,735 rejected issue occurrences, imputed 687 missing response times, and downgraded 104 conversions after their accepted quote failed load rules. A separate queue retains 1,162 positive, referentially valid pricing anomalies for review.

**Meaning:** A composite score can hide defects that overstate conversion or break fact consistency. Remediated defects and review-only anomalies must remain separate so the dashboard does not imply that all unusual quotes were rejected.

**Action:** Reconcile raw, curated, rejected, and loaded counts on every run. Alert on any processed critical-rule failure, rising quarantine rate, or conversion downgrade; keep the anomaly queue visible to pricing owners.

## Additional portfolio findings

- SUVs account for 44,327 inquiries and CHF 357.7 million of accepted value (51.45% of the total), with a 33.46% conversion rate.
- Vehicles aged 10+ years have a 16.05% average relative quote spread versus 7.90% for vehicles aged 0–2 years. Monitor both CHF and percentage spread.
- Volkswagen contributes the largest accepted value at CHF 104.7 million. Mercedes-Benz, BMW, and Audi follow through higher ticket sizes rather than materially different conversion rates.
- Total accepted quote value across the four-year period is CHF 695.1 million.

## Caveats

The results describe a synthetic marketplace scenario; they are not causal estimates or claims about a real Swiss company. December 2025 inquiry data ends on December 27 to preserve quote-date integrity. Acquisition cost, dealer fees, and contribution margin are not available.
