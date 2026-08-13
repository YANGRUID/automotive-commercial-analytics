# Power BI Desktop final checklist

Use this checklist after the PBIP opens successfully. These are manual runtime checks; the repository does not claim they have passed until they are completed in Power BI Desktop.

## Date-table behavior

The semantic model uses the explicit `Dim Date` table for report time intelligence. The final Desktop save persisted two hidden local date tables for non-report date columns and one hidden date template. No PBIR visual references these hidden objects.

Inquiry and quotation analysis must continue to use `Dim Date`. Do not replace those report bindings with automatic hierarchies from `Dim Customer[customer_created_date]` or `Data Quality Metrics[assessment_date]`.

## Refresh and model checks

1. Enter the PostgreSQL credentials described in [POWERBI_POSTGRESQL_CONNECTION.md](POWERBI_POSTGRESQL_CONNECTION.md).
2. Refresh all nine imported tables.
3. Confirm `Dim Date` contains 1,461 rows from 2022-01-01 through 2025-12-31.
4. In Model view, confirm `Fact Inquiry[inquiry_date]` → `Dim Date[date]` is active.
5. Confirm `Fact Quote[quote_date]` → `Dim Date[date]` is inactive.
6. Confirm the three Desktop-generated date tables remain hidden and are not referenced by report visuals.
7. Confirm `Total Quotes by Quote Date` returns values; it deliberately activates the inactive quote-date relationship.

## Report checks

1. Confirm all five pages open and all 59 visuals render.
2. Test each date slicer and confirm it filters through `Dim Date[date]`.
3. On **Executive Overview**, confirm the month axis uses `Dim Date[Month Start]` and is chronological.
4. Confirm all 21 top KPI cards show both a label and a value at 100% zoom: five on **Executive Overview** and four on each remaining page.
5. Confirm **Dealer Performance** shows exactly seven dealers in the win-rate chart and five in the accepted-value chart; confirm **Executive Overview** shows five accepted-value dealers.
6. Test cross-filtering, tooltips, card formatting, and empty-state behavior.
7. Save, close, and reopen `AutomotiveCommercialAnalytics.pbip` before recording Desktop validation as passed.
