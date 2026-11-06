# 06 · 链上反洗钱与套利路径挖掘（Onchain_AML_Arbitrage）

> English version → [README_EN.md](./README_EN.md)

**_地址是点、转账是边，这种数据用 SQL 查多跳会想死，用图数据库刚好。_**

- 主要语言：`Cypher` `Python`
- 核心查询：[neo4j_aml_fanout_ana.cypher](./neo4j_aml_fanout_ana.cypher) · [neo4j_arbitrage_mining.cypher](./neo4j_arbitrage_mining.cypher)
- 结果截图：[AML 图谱](./Neo4j_cypher_analysis_AML.png) · [套利路径](./DeFi%20Arbitrage%20Path%20Discovery%20on%20Neo4j.png)

---

## 1. 为什么用图数据库

链上数据天生是图。想回答「这笔脏钱经过几层拆分最后汇到哪」，在 MySQL 里就是连着写四五层 self join，写一次半小时，查一次还得等；Neo4j 里一条变长路径 `[:SENT*1..3]` 就完了。

这个项目做了两个案例：

- **AML**：找出「一个地址转给很多地址」的拆分结构（fan-out），再把两跳之后的资金流向还原出来；
- **套利**：读 Uniswap V2 池子的储备金算实时汇率，在图上找能转回起点的环，扣掉 0.3% 手续费后看还有没有肉。

## 2. 数据怎么流

```mermaid
flowchart LR
    A[以太坊主网<br/>RPC 节点] -->|web3.py get_block / get_logs| B[原始转账记录]
    B -->|csv| C[transactions.csv<br/>usdt_transfers.csv]
    C -->|unify_csv_format.py<br/>统一表头| D[*_unified.csv]
    [//]: # (D -->|neo4j-admin import| E[(Neo4j<br/>Address -[:SENT]-> Transaction -[:TO]-> Address)])
    D -->|neo4j-admin import| E[("Neo4j<br/>Address -[:SENT]-> Transaction -[:TO]-> Address")]
    E --> F[AML: 拆分追踪<br/>Cypher 变长路径]
    E --> G[套利: 汇率闭环<br/>reduce 连乘]
    H[Uniswap V2 池子] -->|getReserves| I[assets_core.csv<br/>trading_pairs_core.csv]
    I --> E
```

## 3. 数据规模（示例批次）

| 文件 | 内容 | 规模 |
| --- | --- | --- |
| `nodes_addresses.csv` | 地址节点 | 约 56,286 个 |
| `transactions.csv` | 原生转账关系 | 约 73,876 条 |
| `usdt_addresses.csv` | USDT 地址节点 | 约 1,251 个 |
| `usdt_transfers.csv` | USDT Transfer 事件 | 约 1,037 条 |
| `assets_core.csv` / `trading_pairs_core.csv` | 核心代币与汇率关系 | 10 个池子 |

配套 `*_unified.csv` 是统一表头后的版本，`value:string` + `block_number:int`。

## 4. 两个案例的结论

**AML**

- fan-out 查询能直接排出「可疑地址 → 中间地址」的拆分层级，实测样本里最多一个中间地址转给了 17 个下游；
- 两跳路径能把「拆散的钱」重新拼回几组，配合 fan-out 数量基本可以人工判断是不是在拆；
- `aml_analysis.py` 把三条查询串起来，换个地址就能跑。

**套利**

- `USDC → WETH → WBTC → USDC` 三跳，`finalAmount ≈ 1.001377`，扣 0.3% 手续费后净收益约 0.1377%；
- 空间很薄，但这就是 MEV 机器人的目标区间 —— 人工是抢不到的，结论是「不适合手动套利」，这本身也是个有用的结论；
- 顺手做了汇率一致性校验（A→B→A 应该 ≈ 1），**正是这个校验发现我抄错了两个池子地址**。

## 5. 性能（本地单机）

| 环节 | 规模 | 耗时 |
| --- | --- | --- |
| 导出 1,000 个区块的原生转账 | 73,876 条关系 | 约 7 分钟（受 RPC 限制） |
| 导出 10 个区块的 USDT Transfer | 1,037 条 | 约 8 秒 |
| `neo4j-admin import` 批量导入 | 5 万多节点 | 约 30 秒 |
| 三跳套利路径查询 | 10 个池子 | 0.2 秒以内 |
| fan-out 查询 | 5 万节点 | 1 秒左右 |

## 6. 工程结构

```
06_Onchain_AML_Arbitrage/
├── config_loader.py             # 统一的配置/日志入口（RPC、Neo4j 都从这读）
├── config.example.yaml          # 区块范围、输出文件名、池子 sleep 间隔
├── .env.example                 # RPC_URL / NEO4J_PASSWORD
├── docker-compose.yml           # 本地 Neo4j 5
├── export_transactions.py       # 原生转账 → CSV
├── export_erc20_to_csv.py       # USDT Transfer 事件 → CSV
├── export_erc20.py              # 调试版（功能重复，留着备查）
├── unify_csv_format.py          # 统一表头，适配 neo4j-admin import
├── aml_analysis.py              # 可疑地址三连分析
├── aml_tracing.py               # 连接 smoke test
├── fetch_uniswap_rates.py       # 读池子储备金算汇率
├── neo4j_aml_fanout_ana.cypher  # AML 查询
├── neo4j_arbitrage_mining.cypher # 套利查询
└── *.csv / *.png                # 导入数据与结果截图
```

## 7. 怎么跑

```bash
cp .env.example .env            # 填 RPC_URL 和 Neo4j 密码
docker compose up -d            # Neo4j：7474 / 7687
pip install -r requirements.txt

python export_transactions.py        # 先导一小段区块试试
python unify_csv_format.py           # 统一表头
# 导入（容器里执行，CSV 已经挂到 /import）
docker exec -it onchain_neo4j neo4j-admin database import full neo4j \
  --nodes=/import/nodes_addresses_fixed.csv \
  --relationships=/import/transactions_unified.csv

python aml_analysis.py               # 换 config 里的 suspect_address 即可
python fetch_uniswap_rates.py        # 套利用的汇率
```

## 8. 踩坑记录 & 妥协方案

**① Infura 免费额度被打爆**
免费版一天 10 万次请求，我一开始想扫全链，跑了半小时就被限流，返回一堆 429。
后来两个办法：只导指定区块区间；每次 RPC 调用之间 `sleep(0.2)`。很慢，但不用付费。

**② `get_logs` 一次最多 10000 条**
USDT 这种高频合约，10 个区块就能超。脚本里加了个判断，把提示直接打出来（"缩小区块范围"），免得下次又踩。

**③ value 用 `long` 导入直接溢出**
Wei 是 18 位小数，大额转账超过 Java long 的范围，`neo4j-admin import` 报错但错误信息很不直观，排查了半天。
改成 `value:string` 就好了。`unify_csv_format.py` 这个脚本就是为这件事写的 —— 其实就是为了改个表头，专门写个脚本有点傻，但比重导一遍省事。

**④ Neo4j import 对表头极其严格**
表头列名、列顺序、类型后缀，任何一处不一致都会整批失败，而且报错只说哪一行，不说哪一列。
这也是为什么会有 `*_unified.csv` 和 `*_fixed.csv` 两套文件 —— 文件名难看，但省了我重新造数据。

**⑤ 池子地址抄错两个**
`WETH-UNI`、`WETH-LINK` 的池子地址第一次是从某篇博客抄的，早就失效了。
发现方式很偶然：做汇率一致性校验时，A→B→A 连乘出来是 0.7 而不是 1，说明地址错了。改完之后全部 ≈ 1.0。

**⑥ `0xSuspicious001` 是我编的地址**
示例数据里的可疑地址是造的，不是真实案件。真实分析时把 `config.yaml` 里的 `suspect_address` 换成链上地址即可。

**⑦ 之前 Infura 的 key 明文写在五个脚本里**
push 前自查发现的，已经轮换，现在统一从 `.env` 读，仓库里搜不到 key。

## 9. 未来打算（TODO）

- [ ] RPC 还是用免费额度，想接一个付费节点（Alchemy），扫全链就不会被限流；
- [ ] 导入方式想从「整库重导」改成增量，现在每次加新数据都要重建一次库；
- [ ] Cypher 里的地址还是半硬编码，想全部参数化，做成 `--address` 传参；
- [ ] 套利只看了 Uniswap V2，V3 的集中流动性算起来完全不一样，暂时不敢碰；
- [ ] 想给每个区块加时间戳属性，现在只能靠块高估时间，查起来不方便。

## 10. 致谢 / 开发说明

- Cypher 查询、两跳追踪思路、套利收益计算（含手续费）是从0到1搭建并实际验证过策略和逻辑都是确确实实能有Profit的；
- `config_loader.py`、`docker-compose.yml`、`unify_csv_format.py` 的思路骨架伪代码由Agent辅助生成，而后我在此基础上丰富；
- 脚本里的 RPC / 密码已全部改为环境变量，示例地址和密钥均为占位符；数据来源是以太坊公开链上数据。
