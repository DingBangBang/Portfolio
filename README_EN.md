# 🗺 Bonnie's Data Analytics Portfolio

> 中文版 → [README.md](./README.md)

I'm Bonnie, a data analyst. This repo collects end-to-end analytical projects I have built across e-commerce, crypto exchanges (CEX), content platforms and on-chain data — from data extraction and modelling all the way to dashboards and reports, using **Python / SQL / Cypher** and the usual data stack.

Every project is organised so the takeaways are easy to follow: a one-line summary, a project README, the core code, and the result artefact — one click each.

## 📚 Projects

| NO. | Project | Summary | Language | Key libraries | Sub README | Core code | Result |
| :---: | --- | --- | :---: | --- | :---: | :---: | :---: |
| 01 | [Sales_EDA](./projects/01_Sales_EDA) | Full EDA on 5 months of Kaggle cosmetics e-commerce behaviour data: funnel, RFM/segmentation, market-basket (Apriori) and repurchase prediction. | `Python` | `pandas` `numpy` `plotly` `scipy` `scikit-learn` `lifetimes` `mlxtend` | [README](./projects/01_Sales_EDA/README_EN.md) | [Sales_19Dec_overview.ipynb](./projects/01_Sales_EDA/Sales_19Dec_overview.ipynb) | [Report PDF](./projects/01_Sales_EDA/forvisit/forshare_Sales_19Dec_overview.pdf) |
| 02 | [KA_Dashboard](./projects/02_KA_Dashboard) | SQL-defined VIP(KA) tiering plus a dashboard across transactions, activity, retention and RFM, delivered in Grafana. | `SQL` | `MySQL` `TiDB` `Grafana` | [README](./projects/02_KA_Dashboard/README_EN.md) | [ka_dashboard_sql.sql](./projects/02_KA_Dashboard/ka_dashboard_sql.sql) | [Dashboard structure](./projects/02_KA_Dashboard/Grafana_VIP_Dashboard_v2_Structure.png) |
| 03 | [Periodic_Reports_Automation](./projects/03_Periodic_Reports_Automation) | Automated periodic exchange reports: SQL → Pandas → Jinja2 HTML → email delivery + auto screenshot + Excel attachment. | `Python` `SQL` `HTML` | `pandas` `jinja2` `openpyxl` `pyppeteer` | [README](./projects/03_Periodic_Reports_Automation/README_EN.md) | [CEX_weekly_report_for_meeting_brl_NEW.ipynb](./projects/03_Periodic_Reports_Automation/CEX_weekly_report_for_meeting_brl_NEW.ipynb) | [Weekly report screenshot](./projects/03_Periodic_Reports_Automation/CEX_automated_weekly_report.jpg) |
| 04 | [Customer_Analysis_BA](./projects/04_Customer_Analysis_BA) | A blueprint for full-lifecycle exchange user analytics: sign-up funnel, RFM + dimensionality reduction, churn survival analysis, LTV prediction, marketing attribution and incremental ROI. | `Python` `SQL` | `pandas` `scikit-learn` `scipy` `statsmodels` `lifetimes` `prophet` | [README](./projects/04_Customer_Analysis_BA/README_EN.md) | [Implementation plan (pending)](./projects/04_Customer_Analysis_BA/README_EN.md#5-implementation-plan) | [Result TODO](./projects/04_Customer_Analysis_BA/README_EN.md#10-deliverables) |
| 05 | [Comments_NLP](./projects/05_Comments_NLP) | End-to-end NLP on e-commerce/community reviews: multi-source crawling, Chinese tokenisation, sentiment, word clouds and LDA topic clustering. | `Python` | `requests` `lxml` `BeautifulSoup` `Selenium` `Scrapy` `jieba` `SnowNLP` `gensim` `pyLDAvis` `wordcloud` | [README](./projects/05_Comments_NLP/README_EN.md) | [LDA topic clustering](./projects/05_Comments_NLP/Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py) | [Positive word cloud](./projects/05_Comments_NLP/thesis_project/wordcloud_from_fre_pos.png) |
| 06 | [Onchain_AML_Arbitrage](./projects/06_Onchain_AML_Arbitrage) | AML fund-splitting tracing and Uniswap multi-hop arbitrage path mining on Ethereum data with a Neo4j graph database. | `Cypher` `Python` | `web3` `neo4j` `pandas` `tqdm` | [README](./projects/06_Onchain_AML_Arbitrage/README_EN.md) | [neo4j_arbitrage_mining.cypher](./projects/06_Onchain_AML_Arbitrage/neo4j_arbitrage_mining.cypher) | [AML graph analysis](./projects/06_Onchain_AML_Arbitrage/Neo4j_cypher_analysis_AML.png) |

## 🧭 Layout

```
Portfolio/
├── projects/                       # showcase projects
│   ├── 01_Sales_EDA/
│   ├── 02_KA_Dashboard/
│   ├── 03_Periodic_Reports_Automation/
│   ├── 04_Customer_Analysis_BA/
│   ├── 05_Comments_NLP/
│   └── 06_Onchain_AML_Arbitrage/
└── archive/                        # kept for history only, not showcased
```

- Each `projects/xx_*/` folder ships with `README.md` (中文) and `README_EN.md` (English).
- `archive/` holds early scaffolding and other non-showcase material — see [archive/README_EN.md](./archive/README_EN.md).

## 🙋 About me

- Focus areas: user growth & lifecycle analytics, BI metrics and dashboards, NLP, on-chain data analysis.
- Toolbox: `Python` (pandas / scikit-learn / statsmodels / gensim), `SQL` (MySQL / TiDB / Trino), `Cypher` (Neo4j), `Grafana`, `Jupyter`.
- Working style: define metric definitions and the business question first, then pick methods; conclusions over complexity.

---

> Note: this repo only keeps small sample data and result artefacts; raw datasets, virtualenvs and caches are excluded via `.gitignore`.
