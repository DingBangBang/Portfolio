# 03 · Periodic Reports Automation (Periodic_Reports_Automation)

> 中文版 → [README.md](./README.md)

**_A standalone automation project that turns weekly/monthly ops reporting from “manual query + manual tables” into a pipeline that emits HTML / email / Excel automatically._**

- Language: `Python` `SQL` `HTML`
- Core file: [CEX_weekly_report_for_meeting_brl_NEW.ipynb](./CEX_weekly_report_for_meeting_brl_NEW.ipynb)
- Screenshots: [Weekly](./CEX_automated_weekly_report.jpg) · [Monthly](./CEX_automated_monthly_report.jpg)

## 1. Background

Every Monday, ops and management need last week's business snapshot: trading, sign-up conversion, first deposit, deposits/withdrawals, KYC progress, monthly-goal status, etc. Doing it by hand took half a day and was error-prone with inconsistent definitions. I turned it into an automated pipeline so reports are **reproducible, consistent and on time**.

## 2. Stack

| Stage | Tools |
| --- | --- |
| Extraction | `Trino` / SQL (`weekly_br.sql`) |
| Aggregation | `pandas` |
| Templating | `jinja2` (HTML template + 3 tables) |
| Upload / delivery | Object storage + corporate email (HTML body + Excel attachment) |
| Auto screenshot | `pyppeteer` (headless browser, for mobile/weak-network colleagues) |
| Attachment export | `openpyxl` |

## 3. Report contents (DataFrames)

```
1. OVERVIEW
   1.1 transactions / 1.2 balance
2. REGISTER CONVERSION
   2.1 conversion detail / 2.2 first-trade overview / 2.3 channel conversion
3. TRANSACTION
   3.1 count & amount / 3.2 transaction type / 3.3 transaction symbol
4. REAL NAME AUTHENTICATION
   4.1 success rate / 4.2 overview
5. DEPOSIT / WITHDRAW
6. MONTHLY GOALS & PENDING
```

## 4. Key findings / design notes

- **Consistent definitions**: the natural-week definition (Monday-based) is encapsulated once in SQL, so every metric shares the same time window — eliminating manual boundary errors;
- **First-deposit conversion attribution**: breaks down first-deposit success/fail/pending by registration device type and surfaces failure reasons such as `machine-failed` to help ops locate the drop-off;
- **WoW & reward breakdown**: exchange weekly growth and reward amounts (`trademap` / invited / organic) aggregated by week, feeding directly into the weekly meeting;
- **One dataset, many formats**: the same data produces HTML (view), Excel (archive/reuse) and a screenshot (mobile), auto-uploaded to the server.

## 5. Layout

```
03_Periodic_Reports_Automation/
├── CEX_weekly_report_for_meeting_brl_NEW.ipynb  # Weekly report pipeline (core code)
├── retail_weekly_monthly_report_auto.ipynb      # Generalised weekly/monthly framework
├── weekly_br.sql                                # Weekly extraction SQL (incl. first-deposit conversion)
├── CEX_automated_weekly_report.jpg              # Weekly report screenshot
├── CEX_automated_monthly_report.jpg             # Monthly report screenshot
└── automated_report_sample.png                  # Sample report
```

## 6. How to run

1. Prepare a Trino SQL environment and configure the template `templates/html/weekly_report.html`;
2. `pip install pandas jinja2 openpyxl pyppeteer`;
3. Run `CEX_weekly_report_for_meeting_brl_NEW.ipynb`: HTML → upload → auto screenshot → email (with Excel attachment);
4. Email/upload/screenshot functions depend on internal tooling (`report_util`, `cos_util`, …) in production — replace them with your own implementation when reproducing.
