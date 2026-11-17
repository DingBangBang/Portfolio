// ============================================================================
// neo4j_aml_rules.cypher · 反洗钱规则库（v2 新增，配合 aml_rule_engine.py 使用）
//
// 为什么要有这一份：
//   aml_rule_engine.py 在本地用纯 Python 算分，适合批量扫描和出报告；
//   但真实调查是在 Neo4j Browser / Bloom 里「看图说话」，所以同一套规则需要
//   有 Cypher 版本：可以边点边查、下钻到任意一跳、也能接到 BI 工具。
//
// 使用方式：
//   1) 把 aml_risk_scores.csv 放到 Neo4j 的 import 目录（<NEO4J_HOME>/import）
//   2) 执行【0. 数据准备】里的建模修正与索引
//   3) 逐条执行【2. 规则】，参数在【1. 参数】里统一调
//
// 注意：v1 用 neo4j-admin import 导入时没有写关系类型，两套数据（原生转账 / USDT）
//       默认落在同一关系类型下，而金额单位不同（wei vs 1e6）。下面先用 asset 属性
//       把两套数据分开，否则跨资产聚合金额会得到毫无意义的数字。
// ============================================================================


// ============================================================================
// 0. 数据准备：建模修正 + 索引
// ============================================================================

// 0.1 先看看库里有哪些关系类型（不同导入方式得到的类型名不同）
CALL db.relationshipTypes();

// 0.2 给关系打上资产标签：USDT 转账有 block_number（v1 导出时填了），原生转账为空
MATCH ()-[r:TRANSFER_TO]->()
WHERE r.block_number IS NOT NULL AND r.asset IS NULL
SET r.asset = 'USDT';

MATCH ()-[r:TRANSFER_TO]->()
WHERE r.block_number IS NULL AND r.asset IS NULL
SET r.asset = 'ETH';

// 0.3 金额统一成可读单位（ETH / USDT），避免每条查询都写 /1e18、/1e6
MATCH ()-[r:TRANSFER_TO]->()
WHERE r.amount IS NULL
SET r.amount = CASE r.asset
    WHEN 'USDT' THEN toFloat(r.value) / 1000000.0
    ELSE toFloat(r.value) / 1e18
END;

// 0.4 索引（图探索前必做，否则按地址过滤是全表扫）
CREATE INDEX address_id IF NOT EXISTS FOR (a:Address) ON (a.address);
CREATE INDEX address_risk IF NOT EXISTS FOR (a:Address) ON (a.riskScore);

// 0.5 打过分址加个标签，方便单独探索
MATCH (a:Address) WHERE a.riskScore IS NOT NULL SET a:RiskScored;


// ============================================================================
// 1. 参数（Neo4j Browser 里执行一次即可，作用于当前会话）
// ============================================================================

:param asset => 'USDT';          // 先跑 USDT，再换成 'ETH' 跑一遍
:param fanoutMin => 10;          // 拆分：>=10 个收款方
:param faninMin => 10;           // 归集：>=10 个付款方
:param dust => 0.01;             // 粉尘阈值（USDT 用 0.01，ETH 用 0.0001）
:param roundUnit => 1000.0;      // 「整数金额」单位
:param bandLow => 9000.0;        // 临界金额区间（模拟 1 万美元申报线）
:param bandHigh => 10000.0;


// ============================================================================
// 2. 规则 R01~R12（与 aml_rule_engine.py 一一对应）
// ============================================================================

// R01 拆分转账：一个地址 -> 大量不同地址
MATCH (a:Address)-[r:TRANSFER_TO]->(b:Address)
WHERE r.asset = $asset
WITH a, count(DISTINCT b) AS fanout, sum(r.amount) AS outValue, avg(r.amount) AS avgTicket
WHERE fanout >= $fanoutMin
RETURN a.address AS address, fanout, round(outValue, 4) AS outValue,
       round(avgTicket, 4) AS avgTicket
ORDER BY fanout DESC
LIMIT 50;

// R02 资金归集：大量不同地址 -> 一个地址
MATCH (s:Address)-[r:TRANSFER_TO]->(a:Address)
WHERE r.asset = $asset
WITH a, count(DISTINCT s) AS fanin, sum(r.amount) AS inValue
WHERE fanin >= $faninMin
RETURN a.address AS address, fanin, round(inValue, 4) AS inValue
ORDER BY fanin DESC
LIMIT 50;

// R03 拆分-归集二部结构：「少进多出」（拆分层）或「多进少出」（归集层）
MATCH (a:Address)<-[rin:TRANSFER_TO]-(s:Address)
WHERE rin.asset = $asset
WITH a, count(DISTINCT s) AS senders, sum(rin.amount) AS inValue
MATCH (a)-[rout:TRANSFER_TO]->(t:Address)
WHERE rout.asset = $asset
WITH a, senders, inValue, count(DISTINCT t) AS receivers, sum(rout.amount) AS outValue
WHERE (senders <= 2 AND receivers >= 5)
   OR (senders >= 5 AND receivers <= 2)
RETURN a.address AS address, senders, receivers,
       round(inValue, 4) AS inValue, round(outValue, 4) AS outValue,
       CASE WHEN receivers >= 5 THEN '少进多出(拆分层)' ELSE '多进少出(归集层)' END AS pattern
ORDER BY receivers DESC
LIMIT 50;

// R04 快进快出（过账账户 / 跑分号）：流出 ≈ 流入
MATCH (a:Address)<-[rin:TRANSFER_TO]-(s:Address)
WHERE rin.asset = $asset
WITH a, count(DISTINCT s) AS inDeg, sum(rin.amount) AS inValue
MATCH (a)-[rout:TRANSFER_TO]->(t:Address)
WHERE rout.asset = $asset
WITH a, inDeg, inValue, count(DISTINCT t) AS outDeg, sum(rout.amount) AS outValue
WHERE inDeg >= 3 AND outDeg >= 3 AND inValue > 0
  AND outValue / inValue >= 0.85 AND outValue / inValue <= 1.15
RETURN a.address AS address, inDeg, outDeg,
       round(inValue, 4) AS inValue, round(outValue, 4) AS outValue,
       round(outValue / inValue, 4) AS forwardRatio
ORDER BY outValue DESC
LIMIT 50;

// R05 剥洋葱链（peel chain）：4~6 跳、每次只留一点零头、主体金额衰减不超过 30%
MATCH p = (a:Address)-[:TRANSFER_TO*4..6]->(z:Address)
WHERE all(r IN relationships(p) WHERE r.asset = $asset)
  AND all(n IN nodes(p) WHERE single(x IN nodes(p) WHERE x = n))
WITH p, [r IN relationships(p) | r.amount] AS amounts
WHERE all(i IN range(0, size(amounts) - 2) WHERE amounts[i + 1] >= 0.7 * amounts[i])
RETURN [n IN nodes(p) | n.address] AS chain,
       size(relationships(p)) AS hops,
       round(amounts[0], 4) AS startAmount,
       round(amounts[size(amounts) - 1], 4) AS endAmount
ORDER BY hops DESC
LIMIT 25;

// R06 粉尘攻击：向大量地址发送极小金额
MATCH (a:Address)-[r:TRANSFER_TO]->(b:Address)
WHERE r.asset = $asset AND r.amount > 0 AND r.amount <= $dust
WITH a, count(r) AS dustCount, count(DISTINCT b) AS receivers,
     sum(r.amount) AS dustTotal, collect(DISTINCT b.address)[..5] AS samples
WHERE dustCount >= 10 AND receivers >= 10
RETURN a.address AS address, dustCount, receivers,
       round(dustTotal, 6) AS dustTotal, samples
ORDER BY dustCount DESC
LIMIT 25;

// R07 地址投毒：首 4 位 + 尾 4 位与常用地址相同，并向其交易对手投过粉尘
MATCH (suspect:Address), (legit:Address)
WHERE suspect <> legit
  AND left(suspect.address, 6) = left(legit.address, 6)
  AND right(suspect.address, 4) = right(legit.address, 4)
MATCH (legit)-[:TRANSFER_TO]-(victim:Address)
MATCH (suspect)-[d:TRANSFER_TO]->(victim)
WHERE d.asset = $asset AND d.amount > 0 AND d.amount <= $dust
RETURN suspect.address AS poisoningAddress,
       legit.address AS mimickedAddress,
       victim.address AS victim,
       count(d) AS dustTransfers
ORDER BY dustTransfers DESC
LIMIT 25;

// R08 整数 / 临界金额（structuring）：反复使用整千整万，或卡在申报线下
MATCH (a:Address)-[r:TRANSFER_TO]->(b:Address)
WHERE r.asset = $asset
WITH a, r.amount AS amt, b
WHERE abs(amt - round(amt / $roundUnit) * $roundUnit) <= 0.02 * round(amt / $roundUnit) * $roundUnit
   OR (amt >= $bandLow AND amt < $bandHigh)
WITH a, count(*) AS suspiciousEdges, count(DISTINCT b) AS receivers, collect(amt)[..5] AS samples
WHERE suspiciousEdges >= 3 AND receivers >= 3
RETURN a.address AS address, suspiciousEdges, receivers, samples
ORDER BY suspiciousEdges DESC
LIMIT 25;

// R09 自转：同地址多次自转（刷量 / 投毒掩护 / 脚本测试）
MATCH (a:Address)-[r:TRANSFER_TO]->(a)
WHERE r.asset = $asset
WITH a, count(r) AS selfTransfers, sum(r.amount) AS total
WHERE selfTransfers >= 2
RETURN a.address AS address, selfTransfers, round(total, 6) AS total
ORDER BY selfTransfers DESC
LIMIT 25;

// R10 同区块批量出账（脚本化分发）：需要 block_number
MATCH (a:Address)-[r:TRANSFER_TO]->(b:Address)
WHERE r.asset = $asset AND r.block_number IS NOT NULL
WITH a, r.block_number AS block, count(DISTINCT b) AS receivers
WHERE receivers >= 3
RETURN a.address AS address, block, receivers
ORDER BY receivers DESC
LIMIT 25;

// R11 高中心度枢纽（需要 GDS 插件；没有就用 R01/R02 的度数近似）
// CALL gds.graph.project('aml', 'Address', 'TRANSFER_TO');
// CALL gds.pageRank.stream('aml') YIELD nodeId, score
// WITH gds.util.asNode(nodeId) AS n, score
// WHERE score > 0.001
// RETURN n.address AS address, score ORDER BY score DESC LIMIT 50;

// R12 命中标签库：先按【5. 标签库】把标签写成节点属性，再查「谁接触过混币器」
MATCH (a:Address)-[:TRANSFER_TO]-(b:Address)
WHERE b.label IS NOT NULL AND b.category IN ['mixer', 'sanctioned']
WITH a, collect(DISTINCT b.label) AS touchedMixers, count(*) AS edges
RETURN a.address AS address, touchedMixers, edges
ORDER BY edges DESC
LIMIT 50;


// ============================================================================
// 3. 风险分回填（推荐流程：Python 算分 -> CSV -> LOAD CSV，保证两边口径一致）
// ============================================================================

// 3.1 从 aml_risk_scores.csv 回填（文件需放在 <NEO4J_HOME>/import 下）
LOAD CSV WITH HEADERS FROM 'file:///aml_risk_scores.csv' AS row
MATCH (a:Address {address: row.address})
SET a.riskScore = toFloat(row.riskScore),
    a.riskLevel = row.riskLevel,
    a.riskRules = split(row.rules, '|'),
    a.riskDataset = row.dataset
RETURN a.riskLevel AS level, count(*) AS addresses
ORDER BY addresses DESC;

// 3.2 纯库内打分（不需要 Python，口径与 DatasetConfig 对齐，便于做「实时增量」）
MATCH (a:Address)
OPTIONAL MATCH (a)-[rout:TRANSFER_TO]->(t:Address) WHERE rout.asset = $asset
WITH a, count(DISTINCT t) AS fanout, sum(rout.amount) AS outValue
OPTIONAL MATCH (s:Address)-[rin:TRANSFER_TO]->(a) WHERE rin.asset = $asset
WITH a, fanout, outValue, count(DISTINCT s) AS fanin, sum(rin.amount) AS inValue
WITH a, fanout, fanin, outValue, inValue,
     CASE WHEN fanout >= $fanoutMin THEN 18 ELSE 0 END AS s01,
     CASE WHEN fanin >= $faninMin THEN 15 ELSE 0 END AS s02,
     CASE WHEN fanin >= 3 AND fanout >= 3 AND inValue > 0
               AND outValue / inValue >= 0.85 AND outValue / inValue <= 1.15
          THEN 20 ELSE 0 END AS s04
WITH a, s01 + s02 + s04 AS score,
     [x IN [CASE WHEN fanout >= $fanoutMin THEN 'R01' END,
            CASE WHEN fanin  >= $faninMin THEN 'R02' END,
            CASE WHEN s04 > 0 THEN 'R04' END] WHERE x IS NOT NULL] AS rules
WHERE score > 0
SET a.riskScore = toFloat(score),
    a.riskLevel = CASE WHEN score >= 75 THEN 'critical'
                       WHEN score >= 50 THEN 'high'
                       WHEN score >= 30 THEN 'medium'
                       ELSE 'low' END,
    a.riskRules = rules
RETURN a.riskLevel AS level, count(*) AS addresses
ORDER BY addresses DESC;


// ============================================================================
// 4. 调查视角（拿到告警之后怎么往下查）
// ============================================================================

// 4.1 打开某个可疑地址的 2 跳资金网络（人工看结构）
MATCH p = (a:Address {address: '0xcbc105c9b008fd3483d280de17721f66d7a74f67'})-[:TRANSFER_TO*1..2]-(b:Address)
RETURN p
LIMIT 200;

// 4.2 可疑地址 3 跳内是否接触过混币器 / 交易所
MATCH p = (a:Address {address: '0xcbc105c9b008fd3483d280de17721f66d7a74f67'})-[:TRANSFER_TO*1..3]-(b:Address)
WHERE b.label IS NOT NULL
RETURN b.label AS label, b.category AS category, length(p) AS hops, p
ORDER BY hops ASC
LIMIT 20;

// 4.3 「资金最终去了哪里」：沿出边一直走到没有下家（或达到 6 跳）
MATCH p = (a:Address {address: '0xcbc105c9b008fd3483d280de17721f66d7a74f67'})-[:TRANSFER_TO*1..6]->(z:Address)
WHERE NOT (z)-[:TRANSFER_TO]->(:Address)
RETURN [n IN nodes(p) | n.address] AS pathToDrain, size(relationships(p)) AS hops
LIMIT 25;

// 4.4 高风险地址扎堆的团伙（同一邻域里多个高风险节点互相转账）
MATCH (a:Address)-[:TRANSFER_TO*1..3]-(b:Address)
WHERE a.riskScore >= 50 AND b.riskScore >= 50 AND a <> b
RETURN a.address AS addressA, a.riskScore AS scoreA,
       b.address AS addressB, b.riskScore AS scoreB,
       count(*) AS paths
ORDER BY paths DESC
LIMIT 30;

// 4.5 导出给合规 / 风控系统的处置清单
MATCH (a:Address)
WHERE a.riskScore >= 50
RETURN a.address AS address, a.riskScore AS riskScore, a.riskLevel AS riskLevel,
       a.riskRules AS rules, a.riskDataset AS dataset
ORDER BY riskScore DESC;


// ============================================================================
// 5. 标签库（示例，与 aml_labels.json 保持一致；生产环境请换成内部/商业名单）
// ============================================================================

UNWIND [
  {address: '0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc', label: 'Tornado Cash 0.1 ETH pool', category: 'mixer', weight: 22},
  {address: '0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936', label: 'Tornado Cash 1 ETH pool', category: 'mixer', weight: 22},
  {address: '0x910cbd523d972eb0a6f4cae4618ad62622b39dbf', label: 'Tornado Cash 10 ETH pool', category: 'mixer', weight: 24},
  {address: '0xa160cdab225685da1d56aa342ad8841c3b53f291', label: 'Tornado Cash 100 ETH pool', category: 'mixer', weight: 24},
  {address: '0x7a250d5630b4cf539739df2c5dacb4c659f2488d', label: 'Uniswap V2 Router02', category: 'dex_router', weight: -12},
  {address: '0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad', label: 'Uniswap Universal Router', category: 'dex_router', weight: -12},
  {address: '0x28c6c06298d514db089934071355e5743bf21d60', label: 'Binance 14 (hot wallet)', category: 'exchange', weight: -8},
  {address: '0xdac17f958d2ee523a2206206994597c13d831ec7', label: 'Tether: USDT contract', category: 'token_contract', weight: -15}
] AS row
MATCH (a:Address {address: row.address})
SET a.label = row.label, a.category = row.category, a.labelWeight = row.weight
RETURN count(a) AS labeledNodes;
