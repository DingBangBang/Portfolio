# 01 · E-commerce Sales EDA (Sales_EDA)

> 中文版 → [README.md](./README.md)

**_A multi-angle exploratory analysis of a Kaggle cosmetics e-commerce dataset._**

- Language: `Python` (Jupyter Notebook)
- Core file: [Sales_19Dec_overview.ipynb](./Sales_19Dec_overview.ipynb)
- Readable artefacts: [Report PDF](./forvisit/forshare_Sales_19Dec_overview.pdf) · [HTML](./forvisit/forshare_Sales_19Dec_overview.html)

## 1. Background

Working on a cosmetics online store's behaviour log, I found the data had many dimensions but the real business questions boiled down to three: **where users drop off, which users are worth investing in, and which products should be recommended together.** This project turns a 3.5M-row event log into actionable answers for those three questions.

- Source: [Ecommerce events history in cosmetics shop (Kaggle)](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop/data)
- Period: 2019-10 ~ 2020-02 (this write-up uses 2019-12)
- Schema: `event_time / event_type / product_id / category_id / category_code / brand / price / user_id / user_session`

## 2. Stack

| Stage | Tools |
| --- | --- |
| Data wrangling | `pandas` `numpy` |
| Visualisation | `plotly` `matplotlib` |
| Statistics | `scipy` `sklearn` |
| Repurchase / churn | `lifetimes` (BG/NBD) |
| Association rules | `mlxtend` (Apriori) |
| Parallel compute | `joblib` |

## 3. Key findings (2019-12)

**Global metrics**

- `UV = 370,154`, `PV = 3,533,286`, ~`9.55` page views per user;
- `28,894` orders, `GMV = $1,077,624.85`, `$42.07` per paying user;
- Event mix: `view 1,728,331` / `cart 927,124` / `remove_from_cart 664,655` / `purchase 213,176`.

**Conversion funnel**

- Viewers `358,212` (96.77%) → cart `83,458` (22.55%) → purchase `25,613` (6.92%);
- Overall churn ~`93.30%`, with a `76.80%` churn among "view-only" users — **the biggest leak is view → cart**, more worth fixing than cart → purchase.

**Repurchase & user value**

- Average purchase frequency `8.32`, repurchase rate `88.64%`;
- RFM + LTV: `champions` have the highest average LTV (~`298.59`), `almost_lost` the lowest (~`74.66`);
- A `lifetimes` BG/NBD model (fitted on `22,137` repeat buyers) predicts future purchases and the probability a customer is still alive, separating true churn from temporary silence.

**Product association**

- Built baskets from `213,176` purchases (`unique_orders = 25,613`, `unique_items = 26,815`) and used Apriori plus a co-occurrence matrix to support bundling and recommendation.

## 4. Layout

```
01_Sales_EDA/
├── Sales_19Dec_overview.ipynb      # Main analysis (core code)
├── Sales_overall_overview.ipynb    # Overall / GROW-model view
├── Sales_monthly_variation.ipynb   # Monthly variation
├── forvisit/                       # Shareable artefacts (PDF / HTML)
├── graph/                          # Exported charts
├── mindmap_beta.png                # Analysis mindmap v1
└── sales_analysis_mindmap.png      # Analysis mindmap
```

## 5. How to run

1. Download the monthly CSVs from Kaggle into a local `data/` folder (excluded via `.gitignore`);
2. `pip install pandas numpy plotly scipy scikit-learn lifetimes mlxtend joblib openpyxl`;
3. Open `Sales_19Dec_overview.ipynb` and run cells top to bottom;
4. Outputs: charts, `formated_data_for_marketing_*.xlsx` and the report PDF.

> Note: the notebook reads data from an absolute local path; change it to your own data directory when reproducing.
