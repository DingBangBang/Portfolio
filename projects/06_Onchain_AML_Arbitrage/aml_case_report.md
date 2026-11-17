# AML 可疑地址案例报告（自动生成）

> 由 `aml_rule_engine.py` 生成；分数 = Σ 规则权重 + 组合加成，满分为 100。
> 所有结论都附带 evidence，请结合 KYC / 业务背景人工复核后再处置。

## 数据集 ETH

- 数据源：`transactions_unified.csv`，56285 个地址 / 73875 条转账，自转 184 笔，中位度数 1，最大度数 6443
- 规则命中分布：R01=115，R02=163，R03=133，R04=229，R05=3，R06=1，R07=233，R08=42，R09=23，R11=197，R12=24
- 打分地址数：837

分等级：critical=1，high=41，medium=60，low=735

### Top 案例

| # | 地址 | 分数 | 等级 | 命中规则 | 关键证据 |
| :---: | --- | :---: | :---: | --- | --- |
| 1 | `0xf89d7b9c864f589bbf53a82105107622b35eaa40` | 77.3 | 严重 | R01, R02, R04, R08, R11, R12 | R01 · 向 391 个地址出账，合计 604.1827 ETH，金额熵 0.44 |
| 2 | `0x2bcb6bc69991802124f04a1114ee487ff3fad197` | 71.6 | 高 | R02, R03, R04, R11 | R03 · 多进少出（归集层）：117 进 -> 1 出，流入 24.4670 / 流出 24.0286 ETH |
| 3 | `0x45300136662dd4e58fc0df61e6290dffd992b785` | 70.8 | 高 | R01, R02, R04, R08, R11, R12 | R04 · 流入 797.1178 -> 流出 852.4173 ETH（留存比 1.07），121 进 / 105 出 |
| 4 | `0xee7f2d8257aa658c5895796f070e4046ba8fb37e` | 70.7 | 高 | R02, R03, R04, R11 | R03 · 多进少出（归集层）：62 进 -> 1 出，流入 31.6631 / 流出 33.1263 ETH |
| 5 | `0x035e79ed46655f55c7cee91b4e49d87bc1c170c5` | 70.1 | 高 | R02, R03, R04, R11 | R03 · 多进少出（归集层）：25 进 -> 1 出，流入 7.3658 / 流出 7.2833 ETH |
| 6 | `0xfd3e2d0b52dc74f926682f80678bcef081cb32c1` | 67.5 | 高 | R01, R02, R04, R11 | R04 · 流入 1.7534 -> 流出 1.6967 ETH（留存比 0.97），59 进 / 279 出 |
| 7 | `0xb736c967461aa881fe7bb04ddc3109a5bc790c6b` | 66.8 | 高 | R01, R02, R04, R11 | R04 · 流入 16.8531 -> 流出 16.9644 ETH（留存比 1.01），40 进 / 42 出 |
| 8 | `0x2493ffc838a8467386809ea730b9c792eea7abaf` | 66.7 | 高 | R01, R02, R04, R11 | R04 · 流入 16.5229 -> 流出 16.5660 ETH（留存比 1.00），39 进 / 40 出 |
| 9 | `0xfb19ffd1ff9316b7f5bba076ef4b78e4bbedf4e1` | 66.1 | 高 | R01, R02, R04, R11 | R04 · 流入 26.1583 -> 流出 26.6979 ETH（留存比 1.02），21 进 / 26 出 |
| 10 | `0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511` | 64.7 | 高 | R01, R02, R08, R11 | R01 · 向 334 个地址出账，合计 333.3901 ETH，金额熵 0.44 |

### 建议的下一步（以 Top1 为例）

```cypher
// 1) 拉出该地址 2 跳内的资金网络，人工看结构
MATCH path = (a:Address {address: '0xf89d7b9c864f589bbf53a82105107622b35eaa40'})-[:TRANSFER_TO*1..2]-(b:Address)
RETURN path LIMIT 200;

// 2) 查它和标签地址（混币器 / 交易所）是否有直接或间接接触
MATCH (a:Address {address: '0xf89d7b9c864f589bbf53a82105107622b35eaa40'})-[r:TRANSFER_TO*1..3]-(b:Address)
WHERE b.label IS NOT NULL
RETURN b.label, length(r) AS hops, r;
```

### 全部命中明细（前 30 条）

<details><summary><code>0xf89d7b9c864f589bbf53a82105107622b35eaa40</code> · 77.3 分（严重）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +25）：向 391 个地址出账，合计 604.1827 ETH，金额熵 0.44
- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 665.2814 -> 流出 604.1827 ETH（留存比 0.91），176 进 / 435 出
- **R02 资金归集 FAN_IN**（权重 +17）：132 个地址向其归集，合计 665.2814 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：10 笔整数金额 / 1 笔临界区间金额，收款方 9 个（如 1.00, 108.57, 1.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001990（前 0.5%），总度数 611
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 176 / 扇出 435，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x2bcb6bc69991802124f04a1114ee487ff3fad197</code> · 71.6 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：117 进 -> 1 出，流入 24.4670 / 流出 24.0286 ETH
- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 24.4670 -> 流出 24.0286 ETH（留存比 0.98），120 进 / 85 出
- **R02 资金归集 FAN_IN**（权重 +17）：117 个地址向其归集，合计 24.4670 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001732（前 0.5%），总度数 205

</details>

<details><summary><code>0x45300136662dd4e58fc0df61e6290dffd992b785</code> · 70.8 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 797.1178 -> 流出 852.4173 ETH（留存比 1.07），121 进 / 105 出
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 79 个地址出账，合计 852.4173 ETH，金额熵 0.39
- **R02 资金归集 FAN_IN**（权重 +17）：120 个地址向其归集，合计 797.1178 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：14 笔整数金额 / 0 笔临界区间金额，收款方 7 个（如 6.87, 1.00, 5.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001219（前 0.5%），总度数 226
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 121 / 扇出 105，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0xee7f2d8257aa658c5895796f070e4046ba8fb37e</code> · 70.7 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：62 进 -> 1 出，流入 31.6631 / 流出 33.1263 ETH
- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 31.6631 -> 流出 33.1263 ETH（留存比 1.05），62 进 / 6 出
- **R02 资金归集 FAN_IN**（权重 +16）：62 个地址向其归集，合计 31.6631 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000823（前 0.5%），总度数 68

</details>

<details><summary><code>0x035e79ed46655f55c7cee91b4e49d87bc1c170c5</code> · 70.1 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：25 进 -> 1 出，流入 7.3658 / 流出 7.2833 ETH
- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 7.3658 -> 流出 7.2833 ETH（留存比 0.99），27 进 / 24 出
- **R02 资金归集 FAN_IN**（权重 +15）：25 个地址向其归集，合计 7.3658 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000369（前 0.5%），总度数 51

</details>

<details><summary><code>0xfd3e2d0b52dc74f926682f80678bcef081cb32c1</code> · 67.5 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 1.7534 -> 流出 1.6967 ETH（留存比 0.97），59 进 / 279 出
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 63 个地址出账，合计 1.6967 ETH，金额熵 0.89
- **R02 资金归集 FAN_IN**（权重 +16）：59 个地址向其归集，合计 1.7534 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001581（前 0.5%），总度数 338

</details>

<details><summary><code>0xb736c967461aa881fe7bb04ddc3109a5bc790c6b</code> · 66.8 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 16.8531 -> 流出 16.9644 ETH（留存比 1.01），40 进 / 42 出
- **R01 拆分转账 FAN_OUT**（权重 +18）：向 41 个地址出账，合计 16.9644 ETH，金额熵 0.65
- **R02 资金归集 FAN_IN**（权重 +15）：40 个地址向其归集，合计 16.8531 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000150（前 0.5%），总度数 82

</details>

<details><summary><code>0x2493ffc838a8467386809ea730b9c792eea7abaf</code> · 66.7 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 16.5229 -> 流出 16.5660 ETH（留存比 1.00），39 进 / 40 出
- **R01 拆分转账 FAN_OUT**（权重 +18）：向 40 个地址出账，合计 16.5660 ETH，金额熵 0.65
- **R02 资金归集 FAN_IN**（权重 +15）：39 个地址向其归集，合计 16.5229 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000239（前 0.5%），总度数 79

</details>

<details><summary><code>0xfb19ffd1ff9316b7f5bba076ef4b78e4bbedf4e1</code> · 66.1 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 26.1583 -> 流出 26.6979 ETH（留存比 1.02），21 进 / 26 出
- **R01 拆分转账 FAN_OUT**（权重 +18）：向 23 个地址出账，合计 26.6979 ETH，金额熵 0.46
- **R02 资金归集 FAN_IN**（权重 +15）：21 个地址向其归集，合计 26.1583 ETH
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000290（前 0.5%），总度数 47

</details>

<details><summary><code>0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511</code> · 64.7 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +24）：向 334 个地址出账，合计 333.3901 ETH，金额熵 0.44
- **R02 资金归集 FAN_IN**（权重 +15）：45 个地址向其归集，合计 116.9164 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：10 笔整数金额 / 0 笔临界区间金额，收款方 10 个（如 32.01, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000475（前 0.5%），总度数 379

</details>

<details><summary><code>0x95a9bd206ae52c4ba8eecfc93d18eacdd41c88cc</code> · 64.4 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +23）：向 294 个地址出账，合计 335.3842 ETH，金额熵 0.45
- **R02 资金归集 FAN_IN**（权重 +16）：77 个地址向其归集，合计 120.7732 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：10 笔整数金额 / 0 笔临界区间金额，收款方 10 个（如 32.01, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000994（前 0.5%），总度数 371

</details>

<details><summary><code>0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740</code> · 64.3 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +24）：向 310 个地址出账，合计 275.2847 ETH，金额熵 0.43
- **R02 资金归集 FAN_IN**（权重 +16）：50 个地址向其归集，合计 6.6547 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：9 笔整数金额 / 0 笔临界区间金额，收款方 9 个（如 1.00, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000592（前 0.5%），总度数 360

</details>

<details><summary><code>0x28c6c06298d514db089934071355e5743bf21d60</code> · 62.6 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +25）：向 351 个地址出账，合计 1986.3223 ETH，金额熵 0.29
- **R02 资金归集 FAN_IN**（权重 +21）：428 个地址向其归集，合计 6919.9323 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：26 笔整数金额 / 0 笔临界区间金额，收款方 21 个（如 24.99, 14.00, 13.87 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.007415（前 0.5%），总度数 837
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -8）：标签「Binance 14 (hot wallet)」（exchange），权重 -8

</details>

<details><summary><code>0x974caa59e49682cda0ad2bbe82983419a2ecc400</code> · 62.0 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +26）：向 602 个地址出账，合计 201.1408 ETH，金额熵 0.75
- **R02 资金归集 FAN_IN**（权重 +21）：892 个地址向其归集，合计 276.4163 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：5 笔整数金额 / 0 笔临界区间金额，收款方 5 个（如 3.95, 3.00, 1.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.007133（前 0.5%），总度数 1579
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 895 / 扇出 684，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0xa7efae728d2936e78bda97dc267687568dd593f3</code> · 60.8 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +18）：向 21 个地址出账，合计 3283.9446 ETH，金额熵 0.69
- **R02 资金归集 FAN_IN**（权重 +18）：187 个地址向其归集，合计 308.0138 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：19 笔整数金额 / 0 笔临界区间金额，收款方 9 个（如 12.17, 1.00, 26.70 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.002752（前 0.5%），总度数 227

</details>

<details><summary><code>0xf7858da8a6617f7c6d0ff2bcafdb6d2eedf64840</code> · 60.5 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +20）：向 124 个地址出账，合计 350.8640 ETH，金额熵 0.63
- **R02 资金归集 FAN_IN**（权重 +15）：45 个地址向其归集，合计 969.7796 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：21 笔整数金额 / 1 笔临界区间金额，收款方 20 个（如 1.00, 2.00, 21.77 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000648（前 0.5%），总度数 179

</details>

<details><summary><code>0x4e5b2e1dc63f6b91cb6cd759936495434c7e972f</code> · 60.4 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +19）：向 93 个地址出账，合计 91.5537 ETH，金额熵 0.63
- **R02 资金归集 FAN_IN**（权重 +16）：75 个地址向其归集，合计 70.5188 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：3 笔整数金额 / 1 笔临界区间金额，收款方 3 个（如 3.01, 4.97, 20.93 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001222（前 0.5%），总度数 176

</details>

<details><summary><code>0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23</code> · 60.0 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +20）：向 118 个地址出账，合计 102.7492 ETH，金额熵 0.60
- **R02 资金归集 FAN_IN**（权重 +15）：25 个地址向其归集，合计 51.0955 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：5 笔整数金额 / 2 笔临界区间金额，收款方 5 个（如 9.05, 6.01, 30.97 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000279（前 0.5%），总度数 159

</details>

<details><summary><code>0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec</code> · 57.6 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：少进多出（拆分层）：2 进 -> 52 出，流入 30000.4270 / 流出 8739.0065 ETH
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 52 个地址出账，合计 8739.0065 ETH，金额熵 0.32
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：21 笔整数金额 / 0 笔临界区间金额，收款方 14 个（如 43.91, 27.49, 65.37 ETH）

</details>

<details><summary><code>0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88</code> · 57.4 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +26）：向 653 个地址出账，合计 222.5853 ETH，金额熵 0.68
- **R02 资金归集 FAN_IN**（权重 +16）：104 个地址向其归集，合计 162.9619 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：5 笔整数金额 / 0 笔临界区间金额，收款方 5 个（如 38.00, 4.00, 21.91 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001578（前 0.5%），总度数 776
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 106 / 扇出 670，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x077d360f11d220e4d5d831430c81c26c9be7c4a4</code> · 56.9 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +22）：向 200 个地址出账，合计 105.6824 ETH，金额熵 0.67
- **R02 资金归集 FAN_IN**（权重 +20）：337 个地址向其归集，合计 125.9230 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：7 笔整数金额 / 0 笔临界区间金额，收款方 4 个（如 5.00, 5.00, 5.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.004589（前 0.5%），总度数 639
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 338 / 扇出 301，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x3cd751e6b0078be393132286c442345e5dc49699</code> · 56.9 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +24）：向 335 个地址出账，合计 399.1711 ETH，金额熵 0.47
- **R02 资金归集 FAN_IN**（权重 +18）：174 个地址向其归集，合计 150.2700 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：12 笔整数金额 / 0 笔临界区间金额，收款方 12 个（如 32.01, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.002184（前 0.5%），总度数 511
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 176 / 扇出 335，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0xb739d0895772dbb71a89a3754a160269068f0d45</code> · 55.7 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +24）：向 323 个地址出账，合计 312.4497 ETH，金额熵 0.45
- **R02 资金归集 FAN_IN**（权重 +17）：117 个地址向其归集，合计 111.0485 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：9 笔整数金额 / 0 笔临界区间金额，收款方 9 个（如 32.01, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001343（前 0.5%），总度数 440
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 117 / 扇出 323，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x71660c4005ba85c37ccec55d0c4493e66fe775d3</code> · 55.5 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +24）：向 304 个地址出账，合计 384.5014 ETH，金额熵 0.47
- **R02 资金归集 FAN_IN**（权重 +17）：132 个地址向其归集，合计 61.0848 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：12 笔整数金额 / 0 笔临界区间金额，收款方 12 个（如 18.08, 32.01, 32.01 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001739（前 0.5%），总度数 438
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 134 / 扇出 304，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x0d0707963952f2fba59dd06f2b425ace40b492fe</code> · 54.6 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +23）：向 255 个地址出账，合计 189.4458 ETH，金额熵 0.45
- **R02 资金归集 FAN_IN**（权重 +17）：137 个地址向其归集，合计 435.1091 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：7 笔整数金额 / 0 笔临界区间金额，收款方 7 个（如 8.89, 40.00, 47.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001204（前 0.5%），总度数 403
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 141 / 扇出 262，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0x80c67432656d59144ceff962e8faf8926599bcf8</code> · 54.1 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +20）：向 131 个地址出账，合计 164.1946 ETH，金额熵 0.87
- **R02 资金归集 FAN_IN**（权重 +19）：254 个地址向其归集，合计 45.8127 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：61 笔整数金额 / 0 笔临界区间金额，收款方 12 个（如 2.00, 3.00, 3.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.002282（前 0.5%），总度数 558
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 345 / 扇出 213，PageRank 前 0.5%），建议人工确认标签后降权

</details>

<details><summary><code>0xbbd0d4d067d5af2065b1b6fd936d93237ae1c56c</code> · 53.8 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：少进多出（拆分层）：1 进 -> 61 出，流入 49.9994 / 流出 21.2204 ETH
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 61 个地址出账，合计 21.2204 ETH，金额熵 0.75
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000359（前 0.5%），总度数 65

</details>

<details><summary><code>0x88dcdd4a0a58b7e2208805d547043c37dca2b6dc</code> · 53.7 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：少进多出（拆分层）：1 进 -> 53 出，流入 49.9996 / 流出 21.7629 ETH
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 53 个地址出账，合计 21.7629 ETH，金额熵 0.82
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000359（前 0.5%），总度数 59

</details>

<details><summary><code>0x389044f3ac7472060a0618116e3624a5f0f20f28</code> · 53.6 分（高）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：少进多出（拆分层）：1 进 -> 51 出，流入 49.9995 / 流出 17.9150 ETH
- **R01 拆分转账 FAN_OUT**（权重 +19）：向 51 个地址出账，合计 17.9150 ETH，金额熵 0.86
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.000359（前 0.5%），总度数 55

</details>

<details><summary><code>0xe4edb277e41dc89ab076a1f049f4a3efa700bce8</code> · 53.3 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +20）：向 141 个地址出账，合计 109.4099 ETH，金额熵 0.79
- **R02 资金归集 FAN_IN**（权重 +18）：192 个地址向其归集，合计 27.9638 ETH
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：29 笔整数金额 / 1 笔临界区间金额，收款方 4 个（如 2.00, 2.00, 2.00 ETH）
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.001786（前 0.5%），总度数 501
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -10）：疑似服务商地址（扇入 289 / 扇出 212，PageRank 前 0.5%），建议人工确认标签后降权

</details>

## 数据集 USDT

- 数据源：`usdt_transfers_unified.csv`，1250 个地址 / 1036 条转账，自转 0 笔，中位度数 1，最大度数 177
- 规则命中分布：R01=1，R02=1，R03=4，R04=4，R06=4，R07=12，R08=2，R10=14，R11=1，R12=1
- 打分地址数：32

分等级：critical=0，high=2，medium=6，low=24

### Top 案例

| # | 地址 | 分数 | 等级 | 命中规则 | 关键证据 |
| :---: | --- | :---: | :---: | --- | --- |
| 1 | `0x0889e9327b98d7d1be3c301a4585ff3330502c9a` | 52.0 | 高 | R04, R08, R10 | R04 · 流入 73189.0290 -> 流出 73189.0290 USDT（留存比 1.00），7 进 / 9 出 |
| 2 | `0x559432e18b281731c054cd703d4b49872be4ed53` | 50.8 | 高 | R01, R08, R10 | R01 · 向 51 个地址出账，合计 20643.5485 USDT，金额熵 0.73 |
| 3 | `0x4cd00e387622c35bddb9b4c962c136462338bc31` | 42.0 | 中 | R03, R04 | R03 · 多进少出（归集层）：7 进 -> 1 出，流入 5392.9526 / 流出 5300.5999 USDT |
| 4 | `0x00009d17b7b809e38f30892cff11650763b80000` | 35.0 | 中 | R06, R10 | R06 · 20 笔粉尘转账（<= 0.01 USDT）覆盖 20 个地址 |
| 5 | `0x0ca8e8d976df3321f6ff0a8cca96536a51565c81` | 35.0 | 中 | R06, R10 | R06 · 12 笔粉尘转账（<= 0.01 USDT）覆盖 12 个地址 |
| 6 | `0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae` | 35.0 | 中 | R04, R10 | R04 · 流入 5113.4767 -> 流出 5113.4767 USDT（留存比 1.00），3 进 / 5 出 |
| 7 | `0x7d9f4ca54131e588fc1fe577973b55fb11231e76` | 35.0 | 中 | R06, R10 | R06 · 177 笔粉尘转账（<= 0.01 USDT）覆盖 173 个地址 |
| 8 | `0xdc4858741e738bb304fc5b290e7b9453da6a5baa` | 35.0 | 中 | R06, R10 | R06 · 22 笔粉尘转账（<= 0.01 USDT）覆盖 22 个地址 |
| 9 | `0x10521a348b3c4aca4c9f807fd0d2445e11db2216` | 28.0 | 低 | R07 | R07 · 与 0x1052...2216 共享地址指纹 10522216，向其 1 个交易对手投递粉尘（如 0xa021...6e48） |
| 10 | `0x122a87b89d6d6244df164642e4545b741247fdc7` | 28.0 | 低 | R07 | R07 · 与 0x122a...fdc7 共享地址指纹 122afdc7，向其 1 个交易对手投递粉尘（如 0x67d5...b892） |

### 建议的下一步（以 Top1 为例）

```cypher
// 1) 拉出该地址 2 跳内的资金网络，人工看结构
MATCH path = (a:Address {address: '0x0889e9327b98d7d1be3c301a4585ff3330502c9a'})-[:TRANSFER_TO*1..2]-(b:Address)
RETURN path LIMIT 200;

// 2) 查它和标签地址（混币器 / 交易所）是否有直接或间接接触
MATCH (a:Address {address: '0x0889e9327b98d7d1be3c301a4585ff3330502c9a'})-[r:TRANSFER_TO*1..3]-(b:Address)
WHERE b.label IS NOT NULL
RETURN b.label, length(r) AS hops, r;
```

### 全部命中明细（前 30 条）

<details><summary><code>0x0889e9327b98d7d1be3c301a4585ff3330502c9a</code> · 52.0 分（高）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 73189.0290 -> 流出 73189.0290 USDT（留存比 1.00），7 进 / 9 出
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910006 内 3 笔出账覆盖 3 个地址（共 1 个突发区块）
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：3 笔整数金额 / 0 笔临界区间金额，收款方 3 个（如 50000.00, 1999.64, 15836.64 USDT）

</details>

<details><summary><code>0x559432e18b281731c054cd703d4b49872be4ed53</code> · 50.8 分（高）</summary>

- **R01 拆分转账 FAN_OUT**（权重 +19）：向 51 个地址出账，合计 20643.5485 USDT，金额熵 0.73
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910006 内 22 笔出账覆盖 20 个地址（共 6 个突发区块）
- **R08 整数/临界金额 ROUND_AMOUNT**（权重 +12）：3 笔整数金额 / 0 笔临界区间金额，收款方 3 个（如 2988.59, 2965.38, 1000.00 USDT）

</details>

<details><summary><code>0x4cd00e387622c35bddb9b4c962c136462338bc31</code> · 42.0 分（中）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：7 进 -> 1 出，流入 5392.9526 / 流出 5300.5999 USDT
- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 5392.9526 -> 流出 5300.5999 USDT（留存比 0.98），9 进 / 3 出

</details>

<details><summary><code>0x00009d17b7b809e38f30892cff11650763b80000</code> · 35.0 分（中）</summary>

- **R06 粉尘攻击 DUSTING**（权重 +20）：20 笔粉尘转账（<= 0.01 USDT）覆盖 20 个地址
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910007 内 18 笔出账覆盖 18 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x0ca8e8d976df3321f6ff0a8cca96536a51565c81</code> · 35.0 分（中）</summary>

- **R06 粉尘攻击 DUSTING**（权重 +20）：12 笔粉尘转账（<= 0.01 USDT）覆盖 12 个地址
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910003 内 5 笔出账覆盖 5 个地址（共 2 个突发区块）

</details>

<details><summary><code>0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae</code> · 35.0 分（中）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 5113.4767 -> 流出 5113.4767 USDT（留存比 1.00），3 进 / 5 出
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910008 内 3 笔出账覆盖 3 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x7d9f4ca54131e588fc1fe577973b55fb11231e76</code> · 35.0 分（中）</summary>

- **R06 粉尘攻击 DUSTING**（权重 +20）：177 笔粉尘转账（<= 0.01 USDT）覆盖 173 个地址
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910010 内 91 笔出账覆盖 91 个地址（共 2 个突发区块）

</details>

<details><summary><code>0xdc4858741e738bb304fc5b290e7b9453da6a5baa</code> · 35.0 分（中）</summary>

- **R06 粉尘攻击 DUSTING**（权重 +20）：22 笔粉尘转账（<= 0.01 USDT）覆盖 22 个地址
- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910000 内 3 笔出账覆盖 3 个地址（共 4 个突发区块）

</details>

<details><summary><code>0x10521a348b3c4aca4c9f807fd0d2445e11db2216</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x1052...2216 共享地址指纹 10522216，向其 1 个交易对手投递粉尘（如 0xa021...6e48）

</details>

<details><summary><code>0x122a87b89d6d6244df164642e4545b741247fdc7</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x122a...fdc7 共享地址指纹 122afdc7，向其 1 个交易对手投递粉尘（如 0x67d5...b892）

</details>

<details><summary><code>0x122aa4dd4ab7b7d0f8482d3e4e20528fec3ffdc7</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x122a...fdc7 共享地址指纹 122afdc7，向其 1 个交易对手投递粉尘（如 0x67d5...b892）

</details>

<details><summary><code>0x3ee6de042d142c3c23efa5f22699179ea12b608d</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x3ee6...608d 共享地址指纹 3ee6608d，向其 1 个交易对手投递粉尘（如 0x3ccb...0e34）

</details>

<details><summary><code>0x4470236e61902313cdd00f015d86545d172698f2</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x4470...98f2 共享地址指纹 447098f2，向其 1 个交易对手投递粉尘（如 0x6308...2419）

</details>

<details><summary><code>0x546ac82c032aedf86b2e62c313be249d057e7b58</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x546a...7b58 共享地址指纹 546a7b58，向其 1 个交易对手投递粉尘（如 0xd8be...43b3）

</details>

<details><summary><code>0x78ac617c9e601d741b8a1b36eef49825ce2dc79a</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0x78ac...c79a 共享地址指纹 78acc79a，向其 1 个交易对手投递粉尘（如 0x08ec...31a7）

</details>

<details><summary><code>0xa003c6521ad2937b44856e81fd3dcab31b90ce6d</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0xa003...ce6d 共享地址指纹 a003ce6d，向其 1 个交易对手投递粉尘（如 0x5c0a...626b）

</details>

<details><summary><code>0xa93b23f9f7c05a11da51d4097439642438160355</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0xa93b...0355 共享地址指纹 a93b0355，向其 1 个交易对手投递粉尘（如 0xef24...b999）

</details>

<details><summary><code>0xcbc105c9b008fd3483d280de17721f66d7a74f67</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0xcbc1...4f67 共享地址指纹 cbc14f67，向其 1 个交易对手投递粉尘（如 0x564f...b707）

</details>

<details><summary><code>0xcbc1d7791c8684b9018fa13d45a1bc9e75404f67</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0xcbc1...4f67 共享地址指纹 cbc14f67，向其 1 个交易对手投递粉尘（如 0x564f...b707）

</details>

<details><summary><code>0xe7639abea7491645e89a10f3ebb47dfcb5bbc933</code> · 28.0 分（低）</summary>

- **R07 地址投毒 ADDRESS_POISONING**（权重 +28）：与 0xe763...c933 共享地址指纹 e763c933，向其 1 个交易对手投递粉尘（如 0x8e6f...f3f9）

</details>

<details><summary><code>0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23</code> · 22.0 分（低）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：5 进 -> 2 出，流入 3431.5252 / 流出 64.3300 USDT

</details>

<details><summary><code>0x64cdaa89629fe003eaa31b480d8b63372d109a53</code> · 22.0 分（低）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：5 进 -> 1 出，流入 24027.9071 / 流出 1070.7098 USDT

</details>

<details><summary><code>0xb9afbddac010786cfd9b89115e1fb895e5bc164e</code> · 22.0 分（低）</summary>

- **R03 拆分-归集二部结构 SPLIT_MERGE**（权重 +22）：多进少出（归集层）：7 进 -> 1 出，流入 2323.7624 / 流出 1854.5000 USDT

</details>

<details><summary><code>0x28c6c06298d514db089934071355e5743bf21d60</code> · 20.6 分（低）</summary>

- **R02 资金归集 FAN_IN**（权重 +16）：49 个地址向其归集，合计 117596.3744 USDT
- **R11 高中心度枢纽 HUB_CENTRALITY**（权重 +8）：PageRank 0.021855（前 0.5%），总度数 58
- **R12 实体识别/标签 LABELED_ENTITY**（权重 -8）：标签「Binance 14 (hot wallet)」（exchange），权重 -8

</details>

<details><summary><code>0x4997db14d45af82636f4f1cf73658d0316fbe8d2</code> · 20.0 分（低）</summary>

- **R04 快进快出 PASS_THROUGH**（权重 +20）：流入 260.4853 -> 流出 260.4853 USDT（留存比 1.00），3 进 / 3 出

</details>

<details><summary><code>0x18e296053cbdf986196903e889b7dca7a73882f6</code> · 15.0 分（低）</summary>

- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910009 内 3 笔出账覆盖 3 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x477b8d5ef7c2c42db84deb555419cd817c336b6f</code> · 15.0 分（低）</summary>

- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910003 内 4 笔出账覆盖 4 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x50ef5ed097913c223827636890cfb9ed492f5955</code> · 15.0 分（低）</summary>

- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910001 内 4 笔出账覆盖 4 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x6872b6630a3afcd3117191a8403c2002e13df7de</code> · 15.0 分（低）</summary>

- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910006 内 3 笔出账覆盖 3 个地址（共 1 个突发区块）

</details>

<details><summary><code>0x8feab81d36e7576107d5de0758c1b839be31b4f6</code> · 15.0 分（低）</summary>

- **R10 同区块批量出账 BLOCK_BURST**（权重 +15）：区块 25910010 内 3 笔出账覆盖 3 个地址（共 1 个突发区块）

</details>
