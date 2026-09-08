


// 6.4 把 *2..3 改成 *2..6 
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..6]->(end:Asset {symbol: 'USDC'})
RETURN path, length(path) AS steps
LIMIT 20;

// 6.3 快速诊断：查看所有从 USDC 出发到回到 USDC 的路径
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..3]->(end:Asset {symbol: 'USDC'})
RETURN path, length(path) AS steps
LIMIT 20;


// 6.2 检查是否存在单向交易对（只存在 A→B，没有 B→A）
MATCH (a:Asset)-[r:TRADING_PAIR]->(b:Asset)
OPTIONAL MATCH (b)-[r2:TRADING_PAIR]->(a)
WHERE r2 IS NULL
RETURN a.symbol AS from, b.symbol AS to, 'Missing reverse pair' AS issue;

// 6.1 验证汇率一致性（A→B→A 应该约等于 1）
MATCH (a:Asset)-[r1:TRADING_PAIR]->(b:Asset)-[r2:TRADING_PAIR]->(a)
WITH a, b, r1.rate * r2.rate AS round_trip_rate
RETURN a.symbol AS from, b.symbol AS to, 
       toString(round_trip_rate) AS round_trip_rate,
       toString(abs(1 - round_trip_rate)) AS deviation_from_1
ORDER BY deviation_from_1 DESC;


// 6. 数据质量检验


// 5.3 从指定交易对出发，寻找盈利路径（不指定起点为 USDC）
MATCH path = (start:Asset)-[r:TRADING_PAIR*2..4]->(end:Asset)
WHERE start.symbol IN ['WETH', 'WBTC']
  AND end.symbol = start.symbol
  AND length(path) >= 2
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0
RETURN start.symbol, path, toString(finalAmount) AS finalAmount
ORDER BY finalAmount DESC;

// 5.2 找出所有形成三角形的资产组合（3 个资产彼此互联）
MATCH (a:Asset)-[:TRADING_PAIR]->(b:Asset)
MATCH (b)-[:TRADING_PAIR]->(c:Asset)
MATCH (c)-[:TRADING_PAIR]->(a:Asset)
WHERE a.symbol < b.symbol AND b.symbol < c.symbol  // 避免重复
RETURN a.symbol, b.symbol, c.symbol, 
       [ (a)-[r1:TRADING_PAIR]->(b) | r1.rate ] AS a_to_b,
       [ (b)-[r2:TRADING_PAIR]->(c) | r2.rate ] AS b_to_c,
       [ (c)-[r3:TRADING_PAIR]->(a) | r3.rate ] AS c_to_a;

// 5.1 计算每个资产的中心度（有多少种方式可以从它出发到达其他资产）
MATCH (a:Asset)-[:TRADING_PAIR*1..2]->(b:Asset)
WHERE a <> b
RETURN a.symbol, count(DISTINCT b) AS reachable_assets
ORDER BY reachable_assets DESC;


// 5. 市场分析


// 4.3 套利查询 - 考虑 0.3% 的 Uniswap 交易手续费
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate * 0.997) AS finalAmount  // 每步扣除0.3%手续费
WHERE finalAmount > 1.0
RETURN path, 
       toString(finalAmount) AS finalAmount_after_fee,
       toString(finalAmount - 1.0) AS profit_after_fee
ORDER BY finalAmount DESC;

// 4.2 找出所有稳定的套利对（USD 稳定币之间的套利）
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2]->(end:Asset {symbol: 'USDC'})
WHERE length(path) = 2
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0  
RETURN path, toString(finalAmount) AS finalAmount;


// 4.1 计算每对资产的隐含汇率 vs 直接汇率（发现套利窗口）
MATCH (a:Asset)-[r1:TRADING_PAIR]->(b:Asset)
MATCH path = (a)-[r2:TRADING_PAIR*2]->(b)
WHERE length(path) = 2  // 确保只有两步路径
WITH a.symbol AS from, b.symbol AS to, 
     r1.rate AS direct_rate,
     1.0 * reduce(acc = 1.0, rel IN r2 | acc * rel.rate) AS indirect_rate  // 遍历 r2 列表计算
WHERE abs(direct_rate - indirect_rate) > 0.000001  // 过滤掉几乎相等的汇率
RETURN from, to, 
       direct_rate, 
       indirect_rate,
       round(abs(direct_rate - indirect_rate), 6) AS arbitrage_spread,
       toString((direct_rate - indirect_rate) / direct_rate * 100) AS spread_percentage
ORDER BY arbitrage_spread DESC;


// 4. 利润计算


// 3.4 查找 WETH 到 WBTC 的最优路径（经过最少跳数且汇率最好）
MATCH path = shortestPath((weth:Asset {symbol: 'WETH'})-[*]-(wbtc:Asset {symbol: 'WBTC'}))
RETURN path;

// 3.3 查找从 USDC 出发到所有其他资产的最短路径
MATCH path = shortestPath((usdc:Asset {symbol: 'USDC'})-[*]-(other:Asset))
WHERE other.symbol <> 'USDC'
RETURN other.symbol, path;

// 3.2 查找所有从 USDC 出发的 3 步路径（不要求回到起点）
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*3]->(end:Asset)
RETURN path;

// 3.1 找出图中最长的简单路径（路径最长不超过 5 步）
MATCH path = (start:Asset)-[r:TRADING_PAIR*1..5]->(end:Asset)
WHERE start <> end
AND all(n IN nodes(path) WHERE single(x IN nodes(path) WHERE x = n))
RETURN path, length(path) AS pathLength
ORDER BY pathLength DESC
LIMIT 5;


// 3. 深度路径分析


// 2.6 放宽查询条件，用 *2..5 或 *2..6 增加路径长度：
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..6]->(end:Asset {symbol: 'USDC'})
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0
RETURN path, 
       toString(finalAmount) AS finalAmount,
       toString(finalAmount - 1.0) AS profit
ORDER BY finalAmount DESC;



// 2.5 查看所有 2-4 步路径（不限制盈利）
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
RETURN path, length(path) AS pathLength
LIMIT 50;

// 2.4 不使用 APOC 的版本
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
WHERE length(path) >= 2
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0
RETURN path, 
       toString(finalAmount) AS finalAmount,
       toString(finalAmount - 1.0) AS profit
ORDER BY finalAmount DESC;
// finalAmount = 1.0013768403096863, profit = 0.0.0013768403096863224 USDC 比最初投入的多了 0.137684%，存在套利机会。

'''
可视化图解读
图中显示了 4 个节点和 7 条关系：

节点：USDC、WETH、USDT、DAI（4 个资产）

关系：TRADING_PAIR（7 条交易对关系）

从可视化图来看，找到的 3 条套利路径应该是：

路径	说明
USDC → WETH → USDC	两步循环（直接套利）
USDC → USDT → WETH → USDC	三步循环
USDC → DAI → WETH → USDC	三步循环
每条路径的 finalAmount 都大于 1，说明按照当前汇率，用 1 USDC 出发，经过兑换后再回到 USDC，能得到超过 1 USDC 的结果。

图模型是正确的，并且真实地从 Uniswap V2 数据中捕捉到了套利机会。
'''





// 修复版查询3：发现所有盈利路径（2-4步）需要安装APOC库。移除起终点都必须是USDC这个限制，用更宽松的条件，只要求路径中除了首尾外没有重复节点：
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
WHERE size(nodes(path)) = size(apoc.coll.toSet(nodes(path))) + 1  // 除了首尾外，中间节点不重复
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0
RETURN path, 
       toString(finalAmount) AS finalAmount,
       toString(finalAmount - 1.0) AS profit
ORDER BY finalAmount DESC;

// 2.3 发现所有盈利路径（2-4步）
MATCH path = (start:Asset {symbol: 'USDC'})-[r:TRADING_PAIR*2..4]->(end:Asset {symbol: 'USDC'})
WHERE all(n IN nodes(path) WHERE single(x IN nodes(path) WHERE x = n))
WITH start, path, 
     1.0 * reduce(acc = 1.0, rel IN r | acc * rel.rate) AS finalAmount
WHERE finalAmount > 1.0
RETURN path, finalAmount - 1.0 AS profit
ORDER BY profit DESC;

// 2.2 三步循环套利（USDC → WETH → WBTC → USDC）
MATCH path = (start:Asset {symbol: 'USDC'})-[r1:TRADING_PAIR]->(a1:Asset)
                                        -[r2:TRADING_PAIR]->(a2:Asset)
                                        -[r3:TRADING_PAIR]->(end:Asset {symbol: 'USDC'})
WHERE start <> a1 AND a1 <> a2 AND a2 <> end
WITH start, path, 
     1.0 * r1.rate * r2.rate * r3.rate AS finalAmount
RETURN path, finalAmount, finalAmount - 1.0 AS profit, toString(finalAmount) AS finalAmount_full, toString(finalAmount - 1.0) AS profit_full
ORDER BY profit DESC;
// 用 1 USDC → WETH → WBTC → USDC，计算经过 3 次兑换后最终得到的 USDC 数量。
// finalAmount = 1.0013768403096863, profit = 0.0013768403096863，说明经过三步兑换后，最终得到的 USDC 比最初投入的多了 0.137684%，存在套利机会。
// finalAmount = 1.0013768403096863, profit = 0.0013768403096863
// finalAmount_full = 1.001376840309686300, profit_full = 0.001376840309686300
// 经过三步兑换
// 套利空间虽然小，但正是高频交易的核心

// 2.1 两步循环套利（USDC → WETH → USDC）
MATCH path = (start:Asset {symbol: 'USDC'})-[r1:TRADING_PAIR]->(mid:Asset)
                                        -[r2:TRADING_PAIR]->(end:Asset {symbol: 'USDC'})
WHERE start <> mid AND mid <> end
WITH start, path, 
     1.0 * r1.rate * r2.rate AS finalAmount
RETURN path, finalAmount, finalAmount - 1.0 AS profit, toString(finalAmount) AS finalAmount_full, toString(finalAmount - 1.0) AS profit_full
ORDER BY profit DESC;
// 用 1 USDC 买 WETH，再把 WETH 卖回 USDC，看最终能得到多少 USDC。如果profit > 1，就有套利机会。
// finalAmount = 1.0000000000000002, profit = 2.220446049250313e-16，说明经过两步兑换后，最终得到的 USDC 比最初投入的多了 0.000000022%，几乎没有套利机会。
// finalAmount_full = 1.0000000000000002220446049250313080847263336181640625, profit_full = 2.2204460492503130847263336181640625e-16
// 都是主流稳定币池，套利空间通常很小（< 0.1%），但在真实的 DeFi 市场中，这些微小的价差正是套利机器人争抢的对象

// 2. 执行套利查询


// 1.6 查看所有资产及其连接的交易对数量
MATCH (a:Asset)-[r:TRADING_PAIR]->()
RETURN a.symbol, count(r) AS degree
ORDER BY degree DESC;

// 1.5 查看所有交易对及其双向汇率
MATCH (a:Asset)-[r:TRADING_PAIR]->(b:Asset)
RETURN a.symbol AS from, b.symbol AS to, r.rate AS rate
ORDER BY a.symbol, b.symbol;

// 1.4 查看汇率偏离 1 的程度（对于稳定币对特别有用）
MATCH (a:Asset)-[r:TRADING_PAIR]->(b:Asset)
WHERE a.symbol IN ['USDC', 'USDT', 'DAI'] AND b.symbol IN ['USDC', 'USDT', 'DAI']
RETURN a.symbol, b.symbol, r.rate, round(abs(1 - r.rate), 6) AS deviation
ORDER BY deviation DESC;

// 1.3  查看完整的图结构（可视化）
MATCH path = (a:Asset)-[r:TRADING_PAIR]->(b:Asset)
RETURN path;

// 1.2 查看所有交易对关系
MATCH (a:Asset)-[r:TRADING_PAIR]->(b:Asset) 
RETURN a.symbol, r.rate, b.symbol, r.pair_address;

// 1.1 查看所有资产节点
MATCH (a:Asset) RETURN a.assetId, a.symbol, a.decimals;


// 1. 初步查看当前数据库结构


// 测试数据库是否为空
MATCH (n) RETURN n LIMIT 1

// 核心思路是：通过 Uniswap V2 的智能合约获取实时流动性池数据，计算真实汇率，再导入 Neo4j 进行套利路径分析。
// 数据流向：以太坊主网（Infura RPC）→ web3.py 读取 Uniswap V2 流动性池 → Python 计算汇率 → CSV 文件 → Neo4j 批量导入 → Cypher 套利查询
// 与案例一的区别是，这里的数据来源不是交易记录，而是Uniswap V2 流动性池的实时储备金（Reserves），从中计算出每个交易对的实际汇率;


