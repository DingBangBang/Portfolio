# 01 · 电商销售数据 EDA（Sales_EDA）

> English version → [README_EN.md](./README_EN.md)

**_基于 Kaggle 化妆品电商数据的多维度探索性分析。_**

- 主要语言：`Python`（Jupyter Notebook）
- 核心文件：[Sales_19Dec_overview.ipynb](./Sales_19Dec_overview.ipynb)
- 便于阅读的成品：[分析报告 PDF](./forvisit/forshare_Sales_19Dec_overview.pdf) · [HTML](./forvisit/forshare_Sales_19Dec_overview.html)

## 1. 项目背景

我在处理一份化妆品在线商店的行为日志时发现：原始数据维度很多，但真正的业务问题其实集中在三件事——**用户在哪个环节流失、哪些用户值得投入、哪些商品应该一起推荐**。这个项目就是围绕这三件事，把一份 350 万行的行为日志拆成可执行的结论。

- 数据来源：[Ecommerce events history in cosmetics shop (Kaggle)](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop/data)
- 时间范围：2019-10 ~ 2020-02（本文以 2019-12 月为例）
- 数据结构：`event_time / event_type / product_id / category_id / category_code / brand / price / user_id / user_session`

## 2. 技术栈

| 环节 | 工具 |
| --- | --- |
| 数据处理 | `pandas` `numpy` |
| 可视化 | `plotly` `matplotlib` |
| 统计分析 | `scipy` `sklearn` |
| 复购 / 流失建模 | `lifetimes`（BG/NBD） |
| 关联规则 | `mlxtend`（Apriori） |
| 并行计算 | `joblib` |

## 3. 核心发现（以 2019-12 数据为例）

**全局指标**

- 总访客 `UV = 370,154`，总浏览量 `PV = 3,533,286`，人均浏览约 `9.55` 次；
- 总订单 `28,894`，总成交额 `GMV = $1,077,624.85`，人均消费 `$42.07`；
- 行为分布：`view 1,728,331` / `cart 927,124` / `remove_from_cart 664,655` / `purchase 213,176`。

**转化漏斗**

- 浏览用户 `358,212`（96.77%）→ 加购用户 `83,458`（22.55%）→ 成交用户 `25,613`（6.92%）；
- 整体流失率约 `93.30%`，其中「只浏览未加购」人群流失率达 `76.80%`——**最大的漏损发生在浏览→加购这一跳**，比加购→成交更值得优化。

**复购与用户价值**

- 平均购买频次 `8.32` 次，复购率 `88.64%`；
- RFM 分层 + LTV：`champions` 群体平均 LTV 最高（约 `298.59`），`almost_lost` 最低（约 `74.66`）；
- 用 `lifetimes` 的 BG/NBD 模型（拟合 `22,137` 名有复购行为的用户）预测「未来购买次数」与「客户存活概率」，用于区分「真流失」与「暂时沉默」。

**商品关联**

- 基于 `213,176` 条购买记录构建购物篮（`unique_orders = 25,613`、`unique_items = 26,815`），用 Apriori 挖掘频繁项集与共现矩阵，支撑搭售与推荐。

## 4. 目录结构

```
01_Sales_EDA/
├── Sales_19Dec_overview.ipynb      # 主分析（核心代码）
├── Sales_overall_overview.ipynb    # 总体/GROW 模型视角
├── Sales_monthly_variation.ipynb   # 月度波动
├── forvisit/                       # 对外分享产物（PDF / HTML）
├── graph/                          # 导出的图表
├── mindmap_beta.png                # 分析思维导图 v1
└── sales_analysis_mindmap.png      # 分析思维导图
```

## 5. 运行方式

1. 从 Kaggle 下载各月份 CSV，放到本地 `data/` 目录（该目录已在 `.gitignore` 中排除）；
2. 安装依赖：`pip install pandas numpy plotly scipy scikit-learn lifetimes mlxtend joblib openpyxl`；
3. 打开 `Sales_19Dec_overview.ipynb`，按标题顺序执行即可；
4. 输出：图表、Excel（`formated_data_for_marketing_*.xlsx`）与分析报告 PDF。

> 说明：Notebook 内的数据读取路径为本机绝对路径，复现时请改为自己的数据目录。
