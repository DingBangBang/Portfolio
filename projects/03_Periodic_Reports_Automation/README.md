# 03 · 周期报表自动化（Periodic_Reports_Automation）

> English version → [README_EN.md](./README_EN.md)

**_一个独立完成的自动化项目：把每周/每月的运营报表，从「手工取数 + 手工做表」变成「一条流水线自动产出 HTML / 邮件 / Excel」。_**

- 主要语言：`Python` `SQL` `HTML`
- 核心文件：[CEX_weekly_report_for_meeting_brl_NEW.ipynb](./CEX_weekly_report_for_meeting_brl_NEW.ipynb)
- 结果截图：[周报](./CEX_automated_weekly_report.jpg) · [月报](./CEX_automated_monthly_report.jpg)

## 1. 项目背景

每到周一，运营和管理层都要一份上周的经营速览：交易、注册转化、首充、出入金、实名进度、月度目标完成情况等。手工做一次要花大半天，且容易出错、口径不一致。我把这套流程做成了自动化流水线，让报表**可复现、口径统一、准时送达**。

## 2. 技术栈

| 环节 | 工具 |
| --- | --- |
| 取数 | `Trino` / SQL（`weekly_br.sql`） |
| 数据汇总 | `pandas` |
| 模板渲染 | `jinja2`（HTML 模板 + 3 个表格） |
| 上传 / 分发 | 对象存储 + 企业邮件（带 HTML 正文与 Excel 附件） |
| 自动截图 | `pyppeteer`（无头浏览器，供移动端/弱网同事查看） |
| 附件导出 | `openpyxl` |

## 3. 报表内容（DataFrames 清单）

```
1. 概览 OVERVIEW
   1.1 交易 transaction
   1.2 余额 balance
2. 注册转化 REGISTER CONVERSION
   2.1 转化明细 / 2.2 首交易概览 / 2.3 分渠道转化
3. 交易 TRANSACTION
   3.1 笔数与金额 / 3.2 交易类型 / 3.3 交易币种
4. 实名认证 REAL NAME AUTHENTICATION
   4.1 成功率 / 4.2 概览
5. 充提 DEPOSIT / WITHDRAW
6. 月度目标 MONTHLY GOALS & PENDING
```

## 4. 核心发现 / 设计要点

- **口径统一**：把「自然周」的定义（周一起算）统一封装在 SQL 里，所有指标复用同一时间口径，杜绝手工做表的边界误差；
- **首充转化率归因**：按注册设备类型拆解首充成功/失败/待处理，并定位 `machine-failed` 等失败原因占比，帮助运营定位失败环节；
- **周环比与奖励拆解**：交易所周涨幅、奖励金额（`trademap` / 邀请 / 自然）按周聚合，直接服务周会议题；
- **一次性交付多格式**：同一份数据同时产出 HTML（看）、Excel（存/复用）、截图（移动端），并自动上传到服务器留档。

## 5. 目录结构

```
03_Periodic_Reports_Automation/
├── CEX_weekly_report_for_meeting_brl_NEW.ipynb  # 周报主流程（核心代码）
├── retail_weekly_monthly_report_auto.ipynb      # 通用化周报/月报框架
├── weekly_br.sql                                # 周报取数 SQL（含首充转化等口径）
├── CEX_automated_weekly_report.jpg              # 周报成品截图
├── CEX_automated_monthly_report.jpg             # 月报成品截图
└── automated_report_sample.png                  # 报表样张
```

## 6. 运行方式

1. 准备 SQL 取数环境（Trino），并配置好模板目录 `templates/html/weekly_report.html`；
2. 安装依赖：`pip install pandas jinja2 openpyxl pyppeteer`；
3. 运行 `CEX_weekly_report_for_meeting_brl_NEW.ipynb`：产出 HTML → 上传 → 自动截图 → 发送邮件（含 Excel 附件）；
4. 邮件/上传/截图相关函数在正式环境依赖公司内部工具（`report_util`、`cos_util` 等），复现时请替换为你的实现。
