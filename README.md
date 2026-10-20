# 🗺 Bonnie 的数据分析作品集

> English version → [README_EN.md](./README_EN.md)

我是 Bonnie，一名数据分析师。这里收录了我在电商、交易所（CEX）、内容平台与链上数据等场景下完成的端到端分析项目：从取数、建模到看板与报告的落地，覆盖 **Python / SQL / Cypher** 与常用数据生态工具。

每个项目都为「能看懂结论」而整理：一句话简介 + 项目 README + 核心代码 + 结果产物，一键直达。

## 📚 项目总览

| NO. | 项目 | 一句话简介 | 语言 | 主要库 | 子 README | 核心代码 | 结果展示 |
| :---: | --- | --- | :---: | --- | :---: | :---: | :---: |
| 01 | [Sales_EDA](./projects/01_Sales_EDA) | <sub>基于 Kaggle 化妆品电商 5 个月行为数据，完成漏斗、RFM/用户分层、市场篮子（Apriori）与复购预测的完整 EDA。</sub> | `Python` | `pandas` `numpy` `plotly` `scipy` `scikit-learn` `lifetimes` `mlxtend` | [README](./projects/01_Sales_EDA/README.md) | [Sales_19Dec_overview.ipynb](./projects/01_Sales_EDA/Sales_19Dec_overview.ipynb) | [分析报告 PDF](./projects/01_Sales_EDA/forvisit/forshare_Sales_19Dec_overview.pdf) |
| 02 | [KA_Dashboard_of_CEX(Only Spot without Derivatives)](./projects/02_KA_Dashboard) | <sub>用 SQL 定义 VIP(KA) 分层规则，并从交易、活跃、留存、RFM 等维度搭建看板，落地到 Grafana。</sub> | `SQL` | `MySQL` `TiDB` `Grafana` | [README](./projects/02_KA_Dashboard/README.md) | [ka_dashboard_sql.sql](./projects/02_KA_Dashboard/ka_dashboard_sql.sql) | [看板结构图](./projects/02_KA_Dashboard/Grafana_VIP_Dashboard_v2_Structure.png) |
| 03 | [Periodic_Reports_Automation](./projects/03_Periodic_Reports_Automation) | <sub>交易所周期报表自动化：SQL 取数 → Pandas 汇总 → Jinja2 渲染 HTML → 邮件推送 + 自动截图 + Excel 附件。</sub> | `Python` `SQL` `HTML` | `pandas` `jinja2` `openpyxl` `pyppeteer` | [README](./projects/03_Periodic_Reports_Automation/README.md) | [CEX_weekly_report_for_meeting_brl_NEW.ipynb](./projects/03_Periodic_Reports_Automation/CEX_weekly_report_for_meeting_brl_NEW.ipynb) | [周报成品截图](./projects/03_Periodic_Reports_Automation/CEX_automated_weekly_report.jpg) |
| 💡04 | [Growth_Analysis_Strategy_DS](./projects/04_Customer_Analysis_BA) | <sub>交易所用户全生命周期分析蓝图：注册转化漏斗、RFM+降维细分、流失生存分析、LTV 预测、营销归因与增量 ROI 测算。</sub> | `Python` `SQL` | `pandas` `scikit-learn` `scipy` `statsmodels` `lifetimes` `prophet` | [README](./projects/04_Customer_Analysis_BA/README.md) | [dashboards_generation.py](projects/04_Customer_Analysis_BA/dashboards/app.py)| [Streamlit交互式看板](projects/04_Customer_Analysis_BA/reports/CEX-Customer-Analytics-10-20-2026_05_26_part1.png) |
| 05 | [Online_Retail_Comments_NLP](./projects/05_Comments_NLP) | <sub>从多源爬虫采集电商/社区评论文本，完成中文分词、情感倾向、词云与 LDA 主题聚类的完整 NLP 流程。</sub> | `Python` | `requests` `lxml` `BeautifulSoup` `Selenium` `Scrapy` `jieba` `SnowNLP` `gensim` `pyLDAvis` `wordcloud` | [README](./projects/05_Comments_NLP/README.md) | [LDA 主题聚类实现](./projects/05_Comments_NLP/Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py) | [正面评论词云](./projects/05_Comments_NLP/thesis_project/wordcloud_from_fre_pos.png) |
| 💡06 | [Onchain_AML_Arbitrage](./projects/06_Onchain_AML_Arbitrage) | <sub>基于以太坊链上数据与 Neo4j 图数据库，做反洗钱资金拆分追踪与 Uniswap 多跳套利路径挖掘。</sub> | `Cypher` `Python` | `web3` `neo4j` `pandas` `tqdm` | [README](./projects/06_Onchain_AML_Arbitrage/README.md) | [neo4j_arbitrage_mining.cypher](./projects/06_Onchain_AML_Arbitrage/neo4j_arbitrage_mining.cypher) | [AML 图谱分析](./projects/06_Onchain_AML_Arbitrage/Neo4j_cypher_analysis_AML.png) |

## 🧭 目录结构

```
Portfolio/
├── projects/                       # 对外展示的项目
│   ├── 01_Sales_EDA/
│   ├── 02_KA_Dashboard/
│   ├── 03_Periodic_Reports_Automation/
│   ├── 04_Customer_Analysis_BA/
│   ├── 05_Comments_NLP/
│   └── 06_Onchain_AML_Arbitrage/
└── archive/                        # 仅作历史留存、不对外展示
```

- 每个 `projects/xx_*/` 目录都自带 `README.md`（中文）与 `README_EN.md`（English）。
- `archive/` 存放早期脚手架等非展示内容，详见 [archive/README.md](./archive/README.md)。

## 🙋 关于我

- 关注方向：用户增长与生命周期分析、用户行为科学、BI 指标体系与看板、自然语言处理、链上数据分析。
- 工具栈：`Python`（pandas / scikit-learn / statsmodels / gensim）、`SQL`（MySQL / TiDB / Trino）、`Cypher`（Neo4j）、`Grafana`、`Jupyter`。
- 工作方式：先定义好指标口径与业务问题及可量化成效，再选型方法；结论优先，方法服务于结论。

---

> 说明：仓库中仅保留小体量的样例数据与结果产物；原始数据集、虚拟环境与缓存已在 `.gitignore` 中排除。
