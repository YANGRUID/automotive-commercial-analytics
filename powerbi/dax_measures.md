# DAX Measure Library

The semantic model contains 55 explicit measures. They are attached to existing imported tables, not a synthetic measure table: Fact Inquiry (20), Fact Quote (11), Dim Dealer (9), Data Quality Metrics (10), Data Quality Issue Log (1), and Pipeline Run Summary (4). Display folders group them as `Volume`, `Conversion`, `Pricing`, `Dealer`, `Time Intelligence`, and `Data Quality`.

## Volume and conversion

```DAX
Total Inquiries =
DISTINCTCOUNT ( 'Fact Inquiry'[inquiry_id] )

Total Quotes =
DISTINCTCOUNT ( 'Fact Quote'[quote_id] )

Total Quotes by Quote Date =
// Activates the quote-date role and removes only the default inquiry-date path.
// Customer, vehicle, and lead-source filters still reach quotes through Fact Inquiry.
CALCULATE (
    [Total Quotes],
    USERELATIONSHIP ( 'Dim Date'[date], 'Fact Quote'[quote_date] ),
    CROSSFILTER ( 'Dim Date'[date], 'Fact Inquiry'[inquiry_date], NONE )
)

Converted Inquiries =
CALCULATE (
    [Total Inquiries],
    KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () )
)

Conversion Rate =
DIVIDE ( [Converted Inquiries], [Total Inquiries] )

Average Quotes per Inquiry =
DIVIDE ( [Total Quotes], [Total Inquiries] )

Average Days to Conversion =
CALCULATE (
    AVERAGE ( 'Fact Inquiry'[days_to_conversion] ),
    KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () )
)

Inquiries Under 8h SLA =
CALCULATE (
    [Total Inquiries],
    KEEPFILTERS ( 'Fact Inquiry'[fastest_response_hours] < 8 )
)

8h SLA Compliance Rate =
DIVIDE ( [Inquiries Under 8h SLA], [Total Inquiries] )
```

## Pricing and commercial value

```DAX
Average Quote =
AVERAGE ( 'Fact Quote'[quote_amount] )

Maximum Quote =
MAX ( 'Fact Quote'[quote_amount] )

Minimum Quote =
MIN ( 'Fact Quote'[quote_amount] )

Median Quote =
MEDIAN ( 'Fact Quote'[quote_amount] )

Average Highest Quote =
AVERAGE ( 'Fact Inquiry'[highest_quote] )

Average Lowest Quote =
AVERAGE ( 'Fact Inquiry'[lowest_quote] )

Average Quote Spread =
// The persisted spread is calculated once at inquiry grain in the ETL layer.
AVERAGE ( 'Fact Inquiry'[quote_spread] )

Average Quote Spread % =
AVERAGE ( 'Fact Inquiry'[quote_spread_pct] )

Average Sale Value =
CALCULATE (
    AVERAGE ( 'Fact Inquiry'[final_sale_price] ),
    KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () )
)

Total Accepted Quote Value =
CALCULATE (
    SUM ( 'Fact Quote'[quote_amount] ),
    KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () )
)

Quote-to-Market Ratio =
// Ratio of sums is stable under aggregation and avoids averaging small and large quotes equally.
DIVIDE (
    SUM ( 'Fact Quote'[quote_amount] ),
    SUM ( 'Fact Quote'[estimated_market_value] )
)

Average Estimated Market Value =
AVERAGE ( 'Fact Quote'[estimated_market_value] )

Quote Anomalies =
CALCULATE (
    [Total Quotes],
    KEEPFILTERS ( 'Fact Quote'[anomaly_flag] = TRUE () )
)

Quote Anomaly Rate =
DIVIDE ( [Quote Anomalies], [Total Quotes] )
```

## Dealer and response measures

```DAX
Average Response Time =
AVERAGE ( 'Fact Quote'[response_time_hours] )

Average Fastest Response Time =
AVERAGE ( 'Fact Inquiry'[fastest_response_hours] )

Dealer Wins =
CALCULATE (
    [Total Quotes],
    KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () )
)

Dealer Win Rate =
// Quote wins divided by all quotes in the current dealer/filter context.
DIVIDE ( [Dealer Wins], [Total Quotes] )

Average Dealer Competitiveness =
AVERAGE ( 'Fact Quote'[quote_to_market_ratio] )

Dealer Accepted Value =
CALCULATE (
    SUM ( 'Fact Quote'[quote_amount] ),
    KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () )
)

Active Dealers =
CALCULATE (
    DISTINCTCOUNT ( 'Dim Dealer'[dealer_id] ),
    KEEPFILTERS ( 'Dim Dealer'[active_flag] = TRUE () )
)

Dealer Rank =
VAR EligibleDealer = [Total Quotes] >= 250
RETURN
    IF (
        EligibleDealer,
        RANKX (
            FILTER (
                ALLSELECTED (
                    'Dim Dealer'[dealer_id],
                    'Dim Dealer'[dealer_name]
                ),
                CALCULATE ( [Total Quotes] ) >= 250
            ),
            [Dealer Win Rate],
            ,
            DESC,
            DENSE
        )
    )

Dealer Win Rate Top 7 =
IF ( [Dealer Rank] <= 7, [Dealer Win Rate] )

Dealer Accepted Value Top 5 =
VAR DealerValueRank =
    RANKX (
        FILTER (
            ALLSELECTED (
                'Dim Dealer'[dealer_id],
                'Dim Dealer'[dealer_name]
            ),
            CALCULATE ( [Total Quotes] ) >= 250
        ),
        [Dealer Accepted Value],
        ,
        DESC,
        DENSE
    )
RETURN
    IF ( DealerValueRank <= 5, [Dealer Accepted Value] )
```

## Time intelligence

```DAX
Previous Month Inquiries =
CALCULATE ( [Total Inquiries], DATEADD ( 'Dim Date'[date], -1, MONTH ) )

Month-over-Month Inquiry Growth =
VAR CurrentInquiries = [Total Inquiries]
VAR PreviousInquiries = [Previous Month Inquiries]
RETURN
    DIVIDE ( CurrentInquiries - PreviousInquiries, PreviousInquiries )

Previous Year Inquiries =
CALCULATE ( [Total Inquiries], SAMEPERIODLASTYEAR ( 'Dim Date'[date] ) )

Year-over-Year Inquiry Growth =
VAR CurrentInquiries = [Total Inquiries]
VAR PreviousYearInquiries = [Previous Year Inquiries]
RETURN
    DIVIDE ( CurrentInquiries - PreviousYearInquiries, PreviousYearInquiries )

Previous Month Conversion Rate =
CALCULATE ( [Conversion Rate], DATEADD ( 'Dim Date'[date], -1, MONTH ) )

Conversion Rate Change =
// Percentage-point change, not relative percentage change.
[Conversion Rate] - [Previous Month Conversion Rate]

Rolling 3M Conversion Rate =
VAR LastVisibleDate = MAX ( 'Dim Date'[date] )
VAR ThreeMonthWindow =
    DATESINPERIOD ( 'Dim Date'[date], LastVisibleDate, -3, MONTH )
RETURN
    DIVIDE (
        CALCULATE ( [Converted Inquiries], ThreeMonthWindow ),
        CALCULATE ( [Total Inquiries], ThreeMonthWindow )
    )
```

## Data quality and operations

```DAX
Data Quality Metric Rate =
MAX ( 'Data Quality Metrics'[rate] )

Raw Data Quality Rate =
CALCULATE (
    [Data Quality Metric Rate],
    REMOVEFILTERS ( 'Data Quality Metrics'[stage] ),
    'Data Quality Metrics'[stage] = "Raw"
)

Raw Data Quality Score =
CALCULATE (
    [Data Quality Metric Rate],
    REMOVEFILTERS ( 'Data Quality Metrics'[stage] ),
    REMOVEFILTERS ( 'Data Quality Metrics'[metric_name] ),
    'Data Quality Metrics'[stage] = "Raw",
    'Data Quality Metrics'[metric_name] = "overall_data_quality_score"
)

Processed Data Quality Rate =
CALCULATE (
    [Data Quality Metric Rate],
    REMOVEFILTERS ( 'Data Quality Metrics'[stage] ),
    'Data Quality Metrics'[stage] = "Processed"
)

Data Quality Improvement =
( [Processed Data Quality Rate] - [Raw Data Quality Rate] ) * 100

Data Quality Score =
CALCULATE (
    MAX ( 'Data Quality Metrics'[rate] ),
    'Data Quality Metrics'[stage] = "Processed",
    'Data Quality Metrics'[metric_name] = "overall_data_quality_score"
)

Completeness Rate =
CALCULATE (
    MAX ( 'Data Quality Metrics'[rate] ),
    'Data Quality Metrics'[stage] = "Processed",
    'Data Quality Metrics'[metric_name] = "completeness_rate"
)

Validity Rate =
CALCULATE (
    MAX ( 'Data Quality Metrics'[rate] ),
    'Data Quality Metrics'[stage] = "Processed",
    'Data Quality Metrics'[metric_name] = "validity_rate"
)

Uniqueness Rate =
CALCULATE (
    MAX ( 'Data Quality Metrics'[rate] ),
    'Data Quality Metrics'[stage] = "Processed",
    'Data Quality Metrics'[metric_name] = "uniqueness_rate"
)

Referential Integrity Rate =
CALCULATE (
    MAX ( 'Data Quality Metrics'[rate] ),
    'Data Quality Metrics'[stage] = "Processed",
    'Data Quality Metrics'[metric_name] = "referential_integrity_rate"
)

Affected Rows =
SUM ( 'Data Quality Issue Log'[affected_rows] )

Raw Records =
SUM ( 'Pipeline Run Summary'[raw_records] )

Clean Records =
SUM ( 'Pipeline Run Summary'[clean_records] )

Rejected Records =
SUM ( 'Pipeline Run Summary'[quarantined_records] )

Loaded Records =
SUM ( 'Pipeline Run Summary'[loaded_records] )
```

## Formatting

- Currency measures: `CHF #,0;[Red]-CHF #,0` or display units set per visual.
- Rates: `0.0%`; data-quality cards may use `0.00%` to show small differences.
- Data-quality improvement: `+0.000 "pp";-0.000 "pp";0.000 "pp"`.
- Response time: `0.0 "h"`.
- Growth/change: `+0.0%;-0.0%;0.0%`.
- Counts: whole numbers with thousands separator; use display units only in cards.
