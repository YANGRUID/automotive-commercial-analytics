"""Build and optionally execute the reproducible exploratory analysis notebook."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

from .config import PROCESSED_DIR, PROJECT_ROOT
from .utils import configure_logging


LOGGER = configure_logging()
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "exploratory_analysis.ipynb"


def _summary() -> dict[str, object]:
    path = PROCESSED_DIR / "analysis_summary.json"
    if not path.exists():
        raise FileNotFoundError(
            "analysis_summary.json is missing. Run `python -m src.analysis` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_notebook(path: Path = NOTEBOOK_PATH) -> Path:
    """Create a reader-facing analysis notebook with deterministic cells."""

    summary = _summary()
    kpis = summary["kpis"]
    evidence = summary["evidence"]
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3.12"}
    cells = [
        nbf.v4.new_markdown_cell(
            "# Automotive Marketplace Exploratory Analysis\n\n"
            "A reproducible, inquiry-grain and quote-grain analysis of the curated synthetic dataset."
        ),
        nbf.v4.new_markdown_cell(
            "## tl;dr\n\n"
            f"- **{kpis['total_inquiries']:,} curated inquiries produced {kpis['converted_inquiries']:,} conversions** "
            f"for an overall conversion rate of **{kpis['conversion_rate']:.2%}**.\n"
            f"- Inquiries receiving a quote within eight hours converted at **{evidence['conversion_under_8_hours']:.2%}**, "
            f"versus **{evidence['conversion_8_hours_or_more']:.2%}** at eight hours or more. This is an association, not a causal estimate.\n"
            f"- Dealer Referral converted **{evidence['dealer_referral_lift_pp_vs_social']:.2f} percentage points** above Social Media.\n"
            f"- Vehicles aged 10+ years had **{evidence['older_to_newer_relative_spread_ratio']:.2f}x** the relative quote dispersion of vehicles aged 0-2 years.\n"
            f"- The curated layer passed all critical checks; **{kpis['quote_anomalies']:,}** soft quote-to-market anomalies remain flagged for review."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "The analysis supports management decisions on channel quality, dealer competitiveness, response-time SLAs, vehicle mix, and operational data quality. "
            "Conversion metrics use one row per inquiry. Dealer competitiveness and response metrics use one row per dealer quote.\n\n"
            "### Key Assumptions\n\n"
            "- Currency is CHF; dates use the business calendar without intraday timezone logic.\n"
            "- The dataset is synthetic and reproducible with seed 42; results demonstrate analytical method rather than real market estimates.\n"
            "- Associations are not described as causal effects.\n"
            "- Soft quote anomalies remain in the curated layer with a flag; impossible monetary values are quarantined."
        ),
        nbf.v4.new_markdown_cell("## Data\n\n### 1. Load curated tables"),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n\n"
            "PROJECT_ROOT = Path.cwd()\n"
            "if PROJECT_ROOT.name == 'notebooks':\n"
            "    PROJECT_ROOT = PROJECT_ROOT.parent\n"
            "DATA_DIR = PROJECT_ROOT / 'data' / 'processed'\n\n"
            "inquiries = pd.read_csv(DATA_DIR / 'fact_inquiry.csv', parse_dates=['inquiry_date'])\n"
            "quotes = pd.read_csv(DATA_DIR / 'fact_quote.csv', parse_dates=['quote_date'])\n"
            "vehicles = pd.read_csv(DATA_DIR / 'dim_vehicle.csv')\n"
            "dealers = pd.read_csv(DATA_DIR / 'dim_dealer.csv')\n"
            "quality = pd.read_csv(DATA_DIR / 'data_quality_metrics.csv')\n\n"
            "plt.rcParams.update({'figure.figsize': (10, 4.8), 'axes.spines.top': False, 'axes.spines.right': False})\n"
            "BLUE, ORANGE, GOLD, GREY = '#1F4E79', '#D97706', '#B58B00', '#667085'\n"
            "len(inquiries), len(quotes), len(vehicles), len(dealers)"
        ),
        nbf.v4.new_markdown_cell("### 2. Confirm grain, coverage, and missingness"),
        nbf.v4.new_code_cell(
            "overview = pd.DataFrame({\n"
            "    'table': ['fact_inquiry', 'fact_quote', 'dim_vehicle', 'dim_dealer'],\n"
            "    'rows': [len(inquiries), len(quotes), len(vehicles), len(dealers)],\n"
            "    'duplicate_keys': [inquiries.inquiry_id.duplicated().sum(), quotes.quote_id.duplicated().sum(), vehicles.vehicle_id.duplicated().sum(), dealers.dealer_id.duplicated().sum()],\n"
            "})\n"
            "overview"
        ),
        nbf.v4.new_code_cell(
            "missing = (inquiries.isna().mean().mul(100).round(2).rename('missing_pct').to_frame())\n"
            "missing.loc[missing.missing_pct.gt(0)]"
        ),
        nbf.v4.new_markdown_cell(
            "Missing sale price, winning dealer, and days to conversion are expected for non-converted inquiries; required operational fields are complete after transformation."
        ),
        nbf.v4.new_markdown_cell("## Results\n\n### 3. Distribution analysis"),
        nbf.v4.new_code_cell(
            "fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))\n"
            "axes[0].hist(vehicles.estimated_market_value, bins=45, color=BLUE, alpha=0.85)\n"
            "axes[0].set(title='Estimated market value distribution', xlabel='CHF', ylabel='Vehicles')\n"
            "axes[1].hist(quotes.quote_to_market_ratio, bins=45, color=ORANGE, alpha=0.85)\n"
            "axes[1].axvline(1.0, color=GREY, linestyle='--', label='Market value')\n"
            "axes[1].set(title='Quote-to-market ratio distribution', xlabel='Quote / market value', ylabel='Quotes')\n"
            "axes[1].legend(frameon=False)\n"
            "plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "### 4. Quotation spread increases in relative terms as vehicles age"
        ),
        nbf.v4.new_code_cell(
            "age_labels = ['0-2 years', '3-5 years', '6-9 years', '10+ years']\n"
            "age_analysis = (inquiries.assign(vehicle_age_band=pd.cut(inquiries.vehicle_age_at_inquiry, [-1, 2, 5, 9, np.inf], labels=age_labels))\n"
            "    .groupby('vehicle_age_band', observed=True)\n"
            "    .agg(inquiries=('inquiry_id', 'size'), average_spread_chf=('quote_spread', 'mean'), average_spread_pct=('quote_spread_pct', 'mean'))\n"
            "    .reindex(age_labels))\n"
            "age_analysis"
        ),
        nbf.v4.new_code_cell(
            "fig, axis = plt.subplots()\n"
            "axis.bar(age_analysis.index, age_analysis.average_spread_pct * 100, color=BLUE)\n"
            "axis.set(title='Relative quotation spread by vehicle age', ylabel='Average spread (%)', xlabel='Vehicle age at inquiry')\n"
            "axis.grid(axis='y', alpha=0.2); plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell("### 5. Conversion varies materially by lead source"),
        nbf.v4.new_code_cell(
            "lead = (inquiries.groupby('lead_source').agg(inquiries=('inquiry_id', 'size'), conversions=('conversion_flag', 'sum'), conversion_rate=('conversion_flag', 'mean')).sort_values('conversion_rate'))\n"
            "lead"
        ),
        nbf.v4.new_code_cell(
            "fig, axis = plt.subplots()\n"
            "colors = [BLUE if value == lead.conversion_rate.max() else '#A7C0D8' for value in lead.conversion_rate]\n"
            "axis.barh(lead.index, lead.conversion_rate * 100, color=colors)\n"
            "axis.set(title='Conversion rate by lead source', xlabel='Conversion rate (%)', ylabel='')\n"
            "axis.grid(axis='x', alpha=0.2); plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "### 6. Dealer performance is differentiated by competitiveness"
        ),
        nbf.v4.new_code_cell(
            "dealer_performance = (quotes.groupby('dealer_id').agg(quotes=('quote_id', 'size'), wins=('accepted_flag', 'sum'), win_rate=('accepted_flag', 'mean'), average_response_hours=('response_time_hours', 'mean'), quote_to_market_ratio=('quote_to_market_ratio', 'mean')).join(dealers.set_index('dealer_id')[['dealer_name', 'dealer_region']]))\n"
            "dealer_performance.sort_values('win_rate', ascending=False).head(10)"
        ),
        nbf.v4.new_code_cell(
            "fig, axis = plt.subplots()\n"
            "points = axis.scatter(dealer_performance.average_response_hours, dealer_performance.win_rate * 100, c=dealer_performance.quote_to_market_ratio, cmap='cividis', s=35, alpha=0.8)\n"
            "axis.set(title='Dealer response time versus quote win rate', xlabel='Average response time (hours)', ylabel='Quote win rate (%)')\n"
            "figure_colorbar = fig.colorbar(points, ax=axis); figure_colorbar.set_label('Average quote-to-market ratio')\n"
            "axis.grid(alpha=0.2); plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "### 7. Faster first responses are associated with higher inquiry conversion"
        ),
        nbf.v4.new_code_cell(
            "response_labels = ['<4 hours', '4-8 hours', '8-16 hours', '16-24 hours', '24+ hours']\n"
            "response = (inquiries.assign(response_band=pd.cut(inquiries.fastest_response_hours, [-.01, 4, 8, 16, 24, np.inf], labels=response_labels, right=False))\n"
            "    .groupby('response_band', observed=True)\n"
            "    .agg(inquiries=('inquiry_id', 'size'), conversion_rate=('conversion_flag', 'mean'))\n"
            "    .reindex(response_labels))\n"
            "response"
        ),
        nbf.v4.new_code_cell(
            "fig, axis = plt.subplots()\n"
            "axis.bar(response.index, response.conversion_rate * 100, color=ORANGE)\n"
            "axis.set(title='Conversion rate by fastest quote-response band', xlabel='Fastest dealer response', ylabel='Conversion rate (%)')\n"
            "axis.grid(axis='y', alpha=0.2); plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell(
            "### 8. Stability check: the headline comparisons are not driven by one year\n\n"
            "The following tables repeat the response and channel comparisons within each calendar year. "
            "This does not establish causality, but it reduces the risk that the portfolio-level result is a simple time-mix artefact."
        ),
        nbf.v4.new_code_cell(
            "response_year = (inquiries.assign(year=inquiries.inquiry_date.dt.year, under_8h=inquiries.fastest_response_hours.lt(8))\n"
            "    .groupby(['year', 'under_8h']).agg(inquiries=('inquiry_id', 'size'), conversions=('conversion_flag', 'sum'))\n"
            "    .assign(conversion_rate=lambda frame: frame.conversions / frame.inquiries).reset_index())\n"
            "response_pivot = response_year.pivot(index='year', columns='under_8h', values='conversion_rate').rename(columns={False: '8h_or_more', True: 'under_8h'})\n"
            "response_pivot['lift_pp'] = (response_pivot.under_8h - response_pivot['8h_or_more']) * 100\n"
            "response_pivot"
        ),
        nbf.v4.new_code_cell(
            "channel_year = (inquiries.loc[inquiries.lead_source.isin(['Dealer Referral', 'Social Media'])]\n"
            "    .assign(year=lambda frame: frame.inquiry_date.dt.year)\n"
            "    .groupby(['year', 'lead_source']).conversion_flag.mean().unstack())\n"
            "channel_year['referral_lift_pp'] = (channel_year['Dealer Referral'] - channel_year['Social Media']) * 100\n"
            "channel_year"
        ),
        nbf.v4.new_markdown_cell(
            f"The under-eight-hour conversion lift remained positive in every year, ranging from "
            f"**{evidence['response_lift_pp_min_year']:.2f} to {evidence['response_lift_pp_max_year']:.2f} percentage points**. "
            f"Dealer Referral also remained ahead of Social Media each year, by "
            f"**{evidence['referral_lift_pp_min_year']:.2f} to {evidence['referral_lift_pp_max_year']:.2f} percentage points**."
        ),
        nbf.v4.new_markdown_cell("### 9. Correlation analysis at inquiry grain"),
        nbf.v4.new_code_cell(
            "correlation_fields = ['conversion_flag', 'fastest_response_hours', 'quote_spread_pct', 'quote_count', 'vehicle_age_at_inquiry']\n"
            "correlations = inquiries[correlation_fields].corr()\n"
            "correlations.round(3)"
        ),
        nbf.v4.new_code_cell(
            "fig, axis = plt.subplots(figsize=(7, 5.5))\n"
            "image = axis.imshow(correlations, cmap='cividis', vmin=-1, vmax=1)\n"
            "axis.set_xticks(range(len(correlation_fields)), correlation_fields, rotation=40, ha='right')\n"
            "axis.set_yticks(range(len(correlation_fields)), correlation_fields)\n"
            "for row in range(len(correlation_fields)):\n"
            "    for column in range(len(correlation_fields)):\n"
            "        axis.text(column, row, f'{correlations.iloc[row, column]:.2f}', ha='center', va='center', color='white' if abs(correlations.iloc[row, column]) > .45 else 'black', fontsize=8)\n"
            "axis.set_title('Inquiry-grain correlation matrix')\n"
            "fig.colorbar(image, ax=axis, shrink=.8); plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell("### 10. Outlier and data-quality review"),
        nbf.v4.new_code_cell(
            "q1, q3 = quotes.quote_to_market_ratio.quantile([0.25, 0.75])\n"
            "iqr = q3 - q1\n"
            "iqr_outlier = ~quotes.quote_to_market_ratio.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)\n"
            "pd.DataFrame({\n"
            "    'check': ['Business-rule quote anomaly', 'IQR quote-ratio outlier'],\n"
            "    'rows': [quotes.anomaly_flag.sum(), iqr_outlier.sum()],\n"
            "    'rate': [quotes.anomaly_flag.mean(), iqr_outlier.mean()],\n"
            "})"
        ),
        nbf.v4.new_code_cell(
            "quality.assign(rate_percent=quality.rate * 100).sort_values(['stage', 'metric_name'])[['stage', 'metric_name', 'rate_percent']]"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            f"1. **Prioritize an eight-hour dealer response SLA.** Conversion was {evidence['conversion_under_8_hours']:.2%} below eight hours and {evidence['conversion_8_hours_or_more']:.2%} at eight hours or more.\n"
            f"2. **Protect high-quality referral capacity.** Dealer Referral outperformed Social Media by {evidence['dealer_referral_lift_pp_vs_social']:.2f} percentage points.\n"
            f"3. **Use relative spread for older vehicles.** Vehicles aged 10+ years had {evidence['older_to_newer_relative_spread_ratio']:.2f}x the relative quote dispersion of 0-2-year vehicles.\n"
            f"4. **Manage dealer competitiveness explicitly.** The dealer-level correlation between quote-to-market ratio and win rate was {evidence['dealer_competitiveness_win_correlation']:.2f}; this is descriptive, not causal.\n"
            f"5. **Keep anomaly review operational.** {kpis['quote_anomalies']:,} curated positive quotes remain flagged, while hard-invalid rows are quarantined."
        ),
    ]
    notebook["cells"] = cells
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, path)
    LOGGER.info("Built %s", path)
    return path


def execute_notebook(path: Path = NOTEBOOK_PATH) -> Path:
    """Execute the notebook top-to-bottom and save the verified outputs."""

    local_ipython_dir = PROJECT_ROOT / "work" / "ipython"
    local_ipython_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("IPYTHONDIR", str(local_ipython_dir))
    notebook = nbf.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        shutdown_kernel="immediate",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
    )
    executed = client.execute()
    nbf.write(executed, path)
    LOGGER.info("Executed %s successfully", path)
    return path


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    path = build_notebook()
    if args.execute:
        execute_notebook(path)


if __name__ == "__main__":
    main()
