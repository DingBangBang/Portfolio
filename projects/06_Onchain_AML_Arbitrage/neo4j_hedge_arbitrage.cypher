// ============================================================================
// neo4j_hedge_arbitrage.cypher · 套利 + 对冲的图模型（v2 新增）
//
// 和 v1（neo4j_arbitrage_mining.cypher）的关系：
//   v1 把「汇率」直接写成 Asset-[:TRADING_PAIR {rate}]->Asset，只能做线性连乘，
//   回答不了「能塞多大仓位、滑点多少、扣完 gas 还剩多少」；
//   v2 增加三类节点/关系：
//       (:Pool)            流动性池，带 reserve0/reserve1（价格冲击的数据来源）
//       (:Opportunity)     一条已算好的套利机会（含最优仓位、净利、结论）
//       (:PerpMarket)      永续合约资金费/费率，用来算对冲成本与 carry
//   这样图里既有「结构」（路径）也有「经济性」（成本、利润），可直接用于筛选与看板。
//
// 前置：先跑
//   python3 fetch_uniswap_reserves.py            -> pool_reserves.csv
//   python3 arbitrage_optimizer.py --reserves pool_reserves.csv
//   python3 hedge_sizing.py --opportunities arbitrage_opportunities.csv
// 然后把 3 个 CSV 放到 Neo4j 的 import 目录。
// ============================================================================


// ============================================================================
// 0. 约束与索引
// ============================================================================

CREATE CONSTRAINT pool_address IF NOT EXISTS FOR (p:Pool) REQUIRE p.address IS UNIQUE;
CREATE CONSTRAINT opp_id IF NOT EXISTS FOR (o:Opportunity) REQUIRE o.cycleId IS UNIQUE;
CREATE CONSTRAINT perp_asset IF NOT EXISTS FOR (m:PerpMarket) REQUIRE m.asset IS UNIQUE;


// ============================================================================
// 1. 导入池子储备金（价格冲击的基础数据）
// ============================================================================

LOAD CSV WITH HEADERS FROM 'file:///pool_reserves.csv' AS row
MERGE (p:Pool {address: row.pair_address})
SET p.name = row.pair_name,
    p.symbol0 = row.symbol0,
    p.symbol1 = row.symbol1,
    p.reserve0 = toFloat(row.reserve0),
    p.reserve1 = toFloat(row.reserve1),
    p.blockNumber = toInteger(row.block_number),
    p.source = coalesce(row.source, 'onchain')
WITH p
MERGE (a0:Asset {symbol: p.symbol0})
MERGE (a1:Asset {symbol: p.symbol1})
MERGE (a0)-[:PROVIDES {side: 'token0'}]->(p)
MERGE (a1)-[:PROVIDES {side: 'token1'}]->(p)
MERGE (a0)-[:TRADING_PAIR {
        rate: p.reserve1 / p.reserve0,
        pair_address: p.address,
        source: 'v2_reserves'
    }]->(a1)
MERGE (a1)-[:TRADING_PAIR {
        rate: p.reserve0 / p.reserve1,
        pair_address: p.address,
        source: 'v2_reserves'
    }]->(a0)
RETURN count(p) AS poolsLoaded;


// ============================================================================
// 2. 导入套利机会（arbitrage_optimizer.py 的输出）
// ============================================================================

LOAD CSV WITH HEADERS FROM 'file:///arbitrage_opportunities.csv' AS row
MERGE (o:Opportunity {cycleId: row.cycle_id})
SET o.path = row.path,
    o.hops = toInteger(row.hops),
    o.linearEdgeBps = toFloat(row.linear_edge_bps),
    o.linearEdgeAfterFeeBps = toFloat(row.linear_edge_after_fee_bps),
    o.optimalNotionalUsd = toFloat(row.optimal_notional_usd),
    o.grossProfitUsd = toFloat(row.gross_profit_usd),
    o.gasUsd = toFloat(row.gas_usd),
    o.flashloanFeeUsd = toFloat(row.flashloan_fee_usd),
    o.tipUsd = toFloat(row.tip_usd),
    o.netProfitUsd = toFloat(row.net_profit_usd),
    o.netEdgeBps = toFloat(row.net_edge_bps),
    o.priceImpactBps = toFloat(row.price_impact_bps),
    o.minPoolDepthUsd = toFloat(row.min_pool_depth_usd),
    o.verdict = row.verdict
WITH o, split(row.path, '->') AS symbols, split(row.pools, '|') AS pools
UNWIND range(0, size(symbols) - 2) AS i
MERGE (from:Asset {symbol: symbols[i]})
MERGE (to:Asset {symbol: symbols[i + 1]})
MERGE (o)-[leg:HAS_LEG {seq: i}]->(from)
SET leg.toSymbol = symbols[i + 1],
    leg.pool = pools[i]
MERGE (from)-[:USES_POOL {opportunity: o.cycleId}]->(to)
RETURN count(DISTINCT o) AS opportunitiesLoaded;


// ============================================================================
// 3. 导入对冲成本（hedge_sizing.py 的输出）与永续市场
// ============================================================================

LOAD CSV WITH HEADERS FROM 'file:///hedge_plan.csv' AS row
MATCH (o:Opportunity {cycleId: row.cycle_id})
MERGE (m:PerpMarket {asset: row.hedge_instrument})
SET m.label = row.hedge_instrument + '-PERP',
    m.hedgeCostBps = toFloat(row.hedge_cost_bps),
    m.fundingBps = toFloat(row.funding_bps),
    m.basisBps = toFloat(row.basis_bps),
    m.perpFeeBps = toFloat(row.perp_fee_bps)
SET o.hedgeCostBps = toFloat(row.hedge_cost_bps),
    o.netEdgeAfterHedgeBps = toFloat(row.net_edge_after_hedge_bps),
    o.requiredGrossEdgeBps = toFloat(row.required_gross_edge_bps),
    o.edgeShortfallBps = toFloat(row.edge_shortfall_bps),
    o.hedgeRatio = toFloat(row.hedge_ratio),
    o.positionUsd = toFloat(row.position_usd),
    o.maxHoldingHours = CASE row.max_holding_hours WHEN '' THEN -1.0 ELSE toFloat(row.max_holding_hours) END,
    o.decision = row.decision
MERGE (o)-[:HEDGED_ON]->(m)
RETURN count(o) AS hedgedOpportunities;


// ============================================================================
// 4. 查询：把「结构」和「经济性」一起筛
// ============================================================================

// 4.1 按净利排序的所有机会（含对冲后净 edge 与结论）
MATCH (o:Opportunity)
RETURN o.path AS path,
       o.hops AS hops,
       round(o.linearEdgeBps, 2) AS grossBps,
       round(o.netEdgeBps, 2) AS onchainNetBps,
       round(o.hedgeCostBps, 2) AS hedgeCostBps,
       round(o.netEdgeAfterHedgeBps, 2) AS netAfterHedgeBps,
       round(o.requiredGrossEdgeBps, 2) AS requiredBps,
       o.decision AS decision
ORDER BY netAfterHedgeBps DESC;

// 4.2 只留可执行的（真实交易的候选池）
MATCH (o:Opportunity)
WHERE o.decision = 'EXECUTE'
RETURN o.path AS path, o.optimalNotionalUsd AS notional, o.netProfitUsd AS netProfit,
       o.netEdgeAfterHedgeBps AS netBps, o.minPoolDepthUsd AS depth
ORDER BY netProfit DESC;

// 4.3 「价差看起来很香、但成本吃不下」的机会 —— 用来解释为什么不交易
MATCH (o:Opportunity)
WHERE o.linearEdgeBps > 0 AND o.netProfitUsd <= 0
RETURN o.path AS path,
       round(o.linearEdgeBps, 2) AS grossBps,
       round(o.netEdgeBps, 2) AS afterFeeAndImpactBps,
       round(o.requiredGrossEdgeBps, 2) AS neededBps,
       o.verdict AS verdict
ORDER BY o.linearEdgeBps DESC;

// 4.4 脏数据筛查：线性价差与 AMM 净利差距过大的路径（通常是无流动性池）
MATCH (o:Opportunity)
WHERE abs(o.linearEdgeBps - o.netEdgeBps) > 500
RETURN o.path AS path, round(o.linearEdgeBps, 2) AS grossBps,
       round(o.netEdgeBps, 2) AS netBps,
       o.minPoolDepthUsd AS depth, o.verdict AS verdict
ORDER BY abs(o.linearEdgeBps - o.netEdgeBps) DESC
LIMIT 20;

// 4.5 找出被多条机会共用的池子（拥堵点：越多人抢，价差消失越快）
MATCH (o:Opportunity)-[leg:HAS_LEG]->(:Asset)
WITH leg.pool AS pool, collect(DISTINCT o.path) AS paths
WHERE size(paths) > 1
RETURN pool, size(paths) AS sharedBy, paths[..3] AS examples
ORDER BY sharedBy DESC;

// 4.6 参与套利的代币与它们所在的池子深度（判断容量上限）
MATCH (a:Asset)-[:PROVIDES]->(p:Pool)
RETURN a.symbol AS asset, p.name AS pool,
       round(p.reserve0, 4) AS reserve0, round(p.reserve1, 4) AS reserve1
ORDER BY p.name;


// ============================================================================
// 5. 资金费 carry（现货多 + 永续空）的图表达
// ============================================================================

// 5.1 导入 hedge_sizing.py --mode carry 的输出
LOAD CSV WITH HEADERS FROM 'file:///carry_analysis.csv' AS row
MERGE (m:PerpMarket {asset: row.asset})
SET m.venue = row.venue,
    m.funding8hBps = toFloat(row.funding_8h_bps),
    m.fundingApr = toFloat(row.funding_apr),
    m.basisBps = toFloat(row.basis_bps),
    m.roundTripFeeBps = toFloat(row.round_trip_fee_bps),
    m.breakevenDays = CASE row.breakeven_days WHEN '' THEN -1.0 ELSE toFloat(row.breakeven_days) END,
    m.netCarryApr = toFloat(row.net_carry_apr),
    m.carryDecision = row.decision
WITH m
MERGE (a:Asset {symbol: m.asset})
MERGE (a)-[:HAS_PERP]->(m)
RETURN count(m) AS perpMarkets;

// 5.2 排序：哪个币的资金费 carry 年化净收益最高、回本最快
MATCH (m:PerpMarket)
WHERE m.netCarryApr IS NOT NULL
RETURN m.asset AS asset, m.venue AS venue,
       round(m.fundingApr, 2) AS fundingAprPct,
       round(m.netCarryApr, 2) AS netCarryAprPct,
       m.breakevenDays AS breakevenDays,
       m.carryDecision AS decision
ORDER BY netCarryApr DESC;

// 5.3 机会 ↔ 对冲工具 的完整链路（一张图看清「赚价差 + 赚资金费」）
MATCH (o:Opportunity)-[:HEDGED_ON]->(m:PerpMarket)<-[:HAS_PERP]-(a:Asset)
RETURN o.path AS arbPath, m.asset AS hedgeInstrument,
       o.netEdgeAfterHedgeBps AS arbNetBps,
       m.netCarryApr AS carryAprPct,
       o.decision AS arbDecision, m.carryDecision AS carryDecision
LIMIT 50;


// ============================================================================
// 6. 与 v1 的对照查询（保留旧写法，方便说明「为什么要升级」）
// ============================================================================

// 6.1 v1 的线性连乘：只回答「有没有价差」，不回答「能不能赚到」
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
WHERE all(rel IN r WHERE rel.source IS NULL OR rel.source <> 'v2_reserves')
WITH path, 1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS linearFinalAmount
WHERE linearFinalAmount > 1.0
RETURN path, round((linearFinalAmount - 1) * 10000, 2) AS linearEdgeBps
ORDER BY linearEdgeBps DESC
LIMIT 20;

// 6.2 v2：同一批路径，图上直接能看到 AMM 净利与对冲后净 edge
MATCH (o:Opportunity)
WHERE o.path STARTS WITH 'USDC'
RETURN o.path AS path, round(o.linearEdgeBps, 2) AS linearBps,
       round(o.netEdgeBps, 2) AS ammNetBps,
       round(o.netEdgeAfterHedgeBps, 2) AS hedgedNetBps
ORDER BY linearBps DESC;
