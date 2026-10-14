# 06 · 链上反洗钱与套利路径挖掘（Onchain_AML_Arbitrage）

> English version → [README_EN.md](./README_EN.md)

**_基于以太坊链上数据与 Neo4j 图数据库，完成两个案例：AML 资金拆分追踪、Uniswap 多跳套利路径挖掘。_**

- 主要语言：`Cypher` `Python`
- 核心文件：[neo4j_arbitrage_mining.cypher](./neo4j_arbitrage_mining.cypher)
- 结果截图：[AML 图谱分析](./Neo4j_cypher_analysis_AML.png) · [套利路径](./DeFi%20Arbitrage%20Path%20Discovery%20on%20Neo4j.png)

## 1. 项目背景

链上数据天然是「图」：地址是点，转账是边。用关系型数据库做多跳查询（比如「谁的资金经过层层拆分后汇到哪里」）会非常吃力，而图数据库的变长路径查询恰好对口。这个项目用 Neo4j 把两个典型风控 / 交易场景落了下来：

- **案例一 · 反洗钱（AML）**：识别「拆分转账（fan-out）」的可疑地址，并追踪资金的完整链路；
- **案例二 · DeFi 套利**：读取 Uniswap V2 流动性池的实时储备金，计算交易对汇率，挖掘多跳循环套利路径。

## 2. 技术栈

| 环节 | 工具 |
| --- | --- |
| 链上数据读取 | `web3.py`（Infura RPC / Ethereum 主网） |
| 数据处理 | `pandas`（含 `tqdm` 进度条） |
| 图数据库 | `Neo4j`（`neo4j-admin import` 批量导入 + Cypher 查询） |
| Python 驱动 | `neo4j` 官方驱动 |
| 可视化 | Neo4j Browser（图/路径可视化） |

## 3. 数据说明

数据流向：**以太坊主网（Infura RPC）→ web3.py 读取 → Python 计算 → CSV → Neo4j 批量导入 → Cypher 分析**。

| 文件 | 内容 | 规模（示例） |
| --- | --- | --- |
| `nodes_addresses.csv` | 地址节点（`:ID(Address)`） | 约 56,286 个地址 |
| `transactions.csv` | 原生转账关系（from → to，value，hash） | 约 73,876 条 |
| `usdt_addresses.csv` | USDT(ERC-20) 地址节点 | 约 1,251 个地址 |
| `usdt_transfers.csv` | USDT Transfer 事件关系 | 约 1,037 条 |
| `assets_core.csv` / `trading_pairs_core.csv` | 核心代币节点与交易对汇率 | 10 个核心池 |
| `*_unified.csv` | 统一表头后的导入文件（`value:string` + `block_number:int`） | — |

## 4. 核心发现 / 设计要点

**AML 拆分转账追踪**

- 用变长路径查询识别中间地址：从可疑地址出发，找出「一个中间地址转给多个不同接收方」的 fan-out 结构，按 fan-out 数量排序定位可疑节点；
- 追踪「可疑地址 → 中间地址 → 最终接收地址」的两跳资金路径，把分散的转账还原为资金链；
- 用 Python（`aml_analysis.py`）封装查询，对给定地址一键输出「资金进出总览 + 拆分风险地址 + 最终流向」。

**Uniswap 套利路径挖掘**

- 读取 Uniswap V2 核心池的 `getReserves()`，按 `rate = reserve1/reserve0` 计算实时汇率，并写入双向关系 `TRADING_PAIR`；
- 查找「起点=终点」的多跳闭环路径（2~6 跳），用 `reduce(acc * rel.rate)` 连乘各跳汇率得到 `finalAmount`，`> 1` 即存在套利空间；
- 计入 Uniswap 0.3% 手续费（每跳乘 `0.997`）后重新计算净收益，避免「纸面套利」；
- 实测：`USDC → WETH → WBTC → USDC` 三跳路径 `finalAmount ≈ 1.001377`，净收益约 `0.1377%`——空间虽小，但正是高频套利机器人的目标；
- 另做汇率一致性校验（A→B→A 应≈1）、单向交易对检测等数据质量检查。

## 5. 目录结构

```
06_Onchain_AML_Arbitrage/
├── export_transactions.py       # 案例一：导出原生转账 CSV（节点+关系）
├── export_erc20_to_csv.py       # 案例一：导出 USDT(ERC-20) 转账事件 CSV
├── export_erc20.py              # ERC-20 事件读取（含 ABI 加载调试）
├── unify_csv_format.py          # 统一 CSV 表头以适配 neo4j-admin import
├── aml_analysis.py              # 案例一：可疑地址三连分析（Python 驱动）
├── aml_tracing.py               # Neo4j 连接与查询骨架
├── neo4j_aml_fanout_ana.cypher     # 案例一：拆分转账 Cypher
├── fetch_uniswap_rates.py       # 案例二：读取 Uniswap 池储备金并算汇率
├── neo4j_arbitrage_mining.cypher    # 案例二：套利路径挖掘 Cypher（核心代码）
└── *.csv / *.png                # 导入数据与结果截图
```

## 6. 运行方式

**环境**：本地或 Docker 启动 Neo4j（默认 `bolt://localhost:7687`）。

1. **导出链上数据**：把 `export_transactions.py` / `export_erc20_to_csv.py` 里的 `RPC_URL` 换成你自己的 Infura（或其它）节点地址，运行得到 `nodes/transactions/usdt_*` CSV；
2. **统一格式**：运行 `python unify_csv_format.py` 生成 `*_unified.csv`；
3. **批量导入**：
   ```
   neo4j-admin database import full neo4j \
     --nodes=nodes_addresses_fixed.csv \
     --relationships=transactions_unified.csv \
     --nodes=usdt_addresses_fixed.csv \
     --relationships=usdt_transfers_unified.csv
   ```
4. **AML 分析**：在 Neo4j Browser 执行 `neo4j_aml_fanout_ana.cypher`，或运行 `python aml_analysis.py`（记得把 `PASSWORD` 改成你的密码）；
5. **套利挖掘**：运行 `python fetch_uniswap_rates.py` 生成交易对汇率，再导入并执行 `neo4j_arbitrage_mining.cypher`。

> ⚠️ 脚本中的 `RPC_URL / API Key / 密码` 均为历史示例值，请替换为你自己的并妥善保管，切勿提交真实密钥。
