# 02 · VIP(KA) 分层与看板（KA_Dashboard）

> English version → [README_EN.md](./README_EN.md)

**_用 SQL 定义 KA（大客户 / 高净值 VIP）分层规则，并从交易、活跃、留存、RFM 等维度搭建看板，最终落地在 Grafana。_**

- 主要语言：`SQL`（MySQL / TiDB 语法）
- 核心文件：[ka_dashboard_sql.sql](./ka_dashboard_sql.sql)

## 1. 项目背景

交易平台的运营团队需要一套稳定的「大客户识别 + 分层运营」机制。我负责把「谁是大客户、给到什么等级、等级多久重算一次」这件事用数据说清楚，并把结果做成可实时查看的看板。核心诉求有两个：

1. **分层规则要可解释、可复现**——不能靠人工拍脑袋；
2. **新规则上线前要先做沙盘推演**——避免上线后大客户大面积降级引发客诉。

## 2. 技术栈

| 环节 | 工具 |
| --- | --- |
| 数仓 / 查询 | `MySQL`、`TiDB`（兼容 MySQL 语法） |
| 调度与存储 | 定时任务写入快照表 `ba_user_active_snap` 等 |
| 可视化 | `Grafana` |
| 沙盘推演 | `Python`（`pandas` + `plotly`） |

## 3. 核心发现 / 设计要点

**分层规则设计**

- 以「近 30 天交易额 `last_30d_trade_val`」和「总资产 `total_auc`（可用+冻结+理财）」共同打分，划分 `ka1 / ka2 / ka3` 三档；
- 分层遵循**帕累托原则**：等级越高、人数越少、资产越集中，用漏斗图直观呈现各层人数与资产分布。

**稳定性（reshuffle）**

- 取 **10 个时间节点**做样本，观察同一批用户在新旧规则下的等级变动次数（升级/降级）；
- 通过对比「新旧规则下的调动次数、人数分布、余额分布」来判断新规则是否会引发剧烈抖动——这是上线前的**沙盘推演**，而非事后补救。

**活跃与留存**

- 区分 `DAU / MAU`，并按行为口径拆分登录、交易（`BUY/SELL`）、使用卡券等不同活跃定义，分别统计 KA 在各口径下的占比；
- 结果写入 `ba_user_active_snap`，供 Grafana 直接消费。

## 4. 目录结构

```
02_KA_Dashboard/
├── ka_dashboard_sql.sql               # 核心 SQL（分层规则 + 指标口径 + 快照写入）
├── pretest_hirarchyV2.ipynb           # 新规则上线前的沙盘推演
├── Grafana_VIP_Dashboard_v2_Structure.png  # 看板结构图
└── VIP_hirarchy_system.png            # 分层体系示意
```

## 5. 运行方式

1. 在目标库（MySQL/TiDB）中准备 `ofp_ka_info`、`ofp_user`、`ofp_user_action_log` 等基础表；
2. 按 `ka_dashboard_sql.sql` 中的查询逐段执行，生成分层结果与活跃快照；
3. 沙盘推演：运行 `pretest_hirarchyV2.ipynb`，查看新旧规则的调动次数与分布差异；
4. 在 Grafana 中连接上述结果表，按下图结构搭建面板。

> 说明：SQL 中的库名/表名为脱敏后的业务命名，复现时请替换为你的实际库表。
