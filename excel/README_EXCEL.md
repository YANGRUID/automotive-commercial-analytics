# Excel Decision Workbook

[`automotive_commercial_analysis.xlsx`](automotive_commercial_analysis.xlsx) is generated from the curated analytical evidence by `src/create_excel_workbook.py`. It is not a hand-edited screenshot or a pasted export.

## What to inspect

- **Executive Summary:** four linked KPI cards and four decisions with evidence, action, and owner.
- **Monthly Performance:** formula-derived conversion and month-over-month growth plus a dual-axis trend chart.
- **Lead Source:** conversion, portfolio lift, value, response time, and formula rank.
- **Dealer Performance:** dealer-grain win rate, volume eligibility, rank, conditional formatting, and response/win scatter plot.
- **Data Quality:** raw-versus-processed counts that reconcile exactly to their displayed rates, plus the treatment log.
- **Field Profile:** generated schema, null rate, distinct count, and sample value for every curated CSV field.

The hidden `KPI_Source` sheet preserves the workbook's input contract. Formulas recalculate when opened in Excel. Run `python -m src.create_excel_workbook` after rebuilding the analysis summary.
