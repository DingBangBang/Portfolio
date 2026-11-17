#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arbitrage_optimizer.py · AMM 真实成本下的套利最优仓位（v2 新增）

v1（neo4j_arbitrage_mining.cypher）的做法是把各跳 rate 连乘：
    finalAmount = ∏ rate  —— 这是「线性世界」的算法，隐含两个强假设：
      1) 交易无限小，不产生价格冲击（AMM 的滑点被忽略）；
      2) 手续费可以最后统一扣（其实每一步都在扣，而且是扣在「输入量」上）。
    于是得到一个 0.1377% 的「纸面套利」，实际上按 Uniswap 0.3% 手续费计，
    三跳就已经吃掉 ~0.9%，根本不成立。

v2 做的事：
    1) 用恒定乘积公式逐跳模拟（含 0.3% 手续费与价格冲击）：
           amount_out = (R_out * amount_in * (1 - fee)) / (R_in + amount_in * (1 - fee))
    2) 把 gas、闪电贷费、builder tip 折算成 USD 成本；
    3) 用三分搜索求「利润最大的名义仓位」——套利不是越大越好，
       仓位越大滑点越狠，利润是单峰函数，存在唯一最优解；
    4) 输出每个环路的：线性毛价差(bps) / 最优名义本金 / 毛利润 / gas / 净利 / 净 edge(bps)，
       并给出 NEEDS_EDGE（价差不够）/ NEGATIVE（无利可图）判断。

两种数据源：
    --reserves pool_reserves.csv    真实链上储备金（fetch_uniswap_reserves.py 产出）
    --from-rates trading_pairs_core.csv --depth-usd 1000000
        由 v1 的汇率 CSV 反推一份「名义深度」的储备金，用于在没有 RPC 的情况下
        复现整条计算链路（结果会明确标注 source=derived_from_rates，不能当真实深度用）。

用法：
    python3 arbitrage_optimizer.py --from-rates --depth-usd 1000000 --top 10
    python3 arbitrage_optimizer.py --reserves pool_reserves.csv --gas-price-gwei 20
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ============================================================
# 1. 配置与数据结构
# ============================================================


@dataclass
class CostModel:
    """把「链上执行成本」参数集中在一处，方便做敏感性分析。"""

    fee_rate: float = 0.003          # Uniswap V2 每跳手续费 0.3%
    gas_per_hop: int = 150_000       # 每跳约 150k gas（swap + 池子记账）
    gas_overhead: int = 80_000       # 闪贷开仓 / 结算 / 授权等固定开销
    gas_price_gwei: float = 25.0
    eth_price_usd: float = 2500.0
    flashloan_fee_bps: float = 0.9   # Aave V3 闪贷 0.09% = 9 bps
    builder_tip_bps: float = 1.0     # 给 builder 的小费（抢占区块用）
    max_impact_pct: float = 0.02     # 单池最多吃掉 2% 储备，超过就不是「套利」而是「砸盘」

    def gas_cost_usd(self, hops: int) -> float:
        gas_units = self.gas_per_hop * hops + self.gas_overhead
        return gas_units * self.gas_price_gwei * 1e-9 * self.eth_price_usd


@dataclass
class Pool:
    """一个 Uniswap V2 池子（储备金是「人类可读单位」）。"""

    pair_address: str
    pair_name: str
    symbol0: str
    symbol1: str
    reserve0: float
    reserve1: float
    source: str = "onchain"

    @property
    def rate(self) -> float:
        """1 个 token0 能换多少个 token1（线性近似，用于和 v1 结果对照）。"""
        return self.reserve1 / self.reserve0 if self.reserve0 else 0.0


@dataclass
class Hop:
    """环路中的一跳：从 from_symbol 换到 to_symbol，走 pool。"""

    pool: Pool
    from_symbol: str
    to_symbol: str
    reserve_in: float
    reserve_out: float

    @property
    def price(self) -> float:
        return self.reserve_out / self.reserve_in if self.reserve_in else 0.0


@dataclass
class Opportunity:
    cycle_id: str
    path_symbols: List[str]
    path_pools: List[str]
    hops: int
    linear_edge_bps: float        # ∏ rate - 1（v1 线性方法的结果，未扣手续费）
    linear_edge_after_fee_bps: float  # ∏ rate*(1-fee) - 1（线性 + 手续费，仍未计价格冲击）
    optimal_notional_usd: float
    gross_profit_usd: float       # 扣手续费、含价格冲击后的毛利
    gas_usd: float
    flashloan_fee_usd: float
    tip_usd: float
    net_profit_usd: float
    net_edge_bps: float
    price_impact_bps: float       # 最优仓位下，最贵那一跳的价格冲击
    min_pool_depth_usd: float
    break_even_notional_usd: float
    verdict: str

    def as_row(self) -> Dict[str, object]:
        return {
            "cycle_id": self.cycle_id,
            "path": "->".join(self.path_symbols),
            "pools": "|".join(self.path_pools),
            "hops": self.hops,
            "linear_edge_bps": round(self.linear_edge_bps, 4),
            "linear_edge_after_fee_bps": round(self.linear_edge_after_fee_bps, 4),
            "optimal_notional_usd": round(self.optimal_notional_usd, 2),
            "gross_profit_usd": round(self.gross_profit_usd, 6),
            "gas_usd": round(self.gas_usd, 4),
            "flashloan_fee_usd": round(self.flashloan_fee_usd, 4),
            "tip_usd": round(self.tip_usd, 4),
            "net_profit_usd": round(self.net_profit_usd, 6),
            "net_edge_bps": round(self.net_edge_bps, 4),
            "price_impact_bps": round(self.price_impact_bps, 2),
            "min_pool_depth_usd": round(self.min_pool_depth_usd, 2),
            "break_even_notional_usd": (
                round(self.break_even_notional_usd, 2) if math.isfinite(self.break_even_notional_usd) else ""
            ),
            "verdict": self.verdict,
        }


# ============================================================
# 2. 数据加载
# ============================================================


def load_reserves(path: str) -> List[Pool]:
    """读取 fetch_uniswap_reserves.py 产出的储备金 CSV。"""
    pools: List[Pool] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            reserve0 = float(row["reserve0"])
            reserve1 = float(row["reserve1"])
            if reserve0 <= 0 or reserve1 <= 0:
                continue
            pools.append(
                Pool(
                    pair_address=row["pair_address"],
                    pair_name=row.get("pair_name", f"{row['symbol0']}-{row['symbol1']}"),
                    symbol0=row["symbol0"],
                    symbol1=row["symbol1"],
                    reserve0=reserve0,
                    reserve1=reserve1,
                    source=row.get("source", "onchain"),
                )
            )
    return pools


def derive_usd_prices(edges: Iterable[Tuple[str, str, float]], anchor: str = "USDC", anchor_price: float = 1.0) -> Dict[str, float]:
    """
    从交易对汇率反推各代币的 USD 价格（BFS 沿汇率图传播）。

    edges 里的 (a, b, rate) 含义是「1 个 a = rate 个 b」，因此：
        price_a = rate * price_b  ⇒  price_b = price_a / rate
    以 USDC = 1 美元为锚点，逐层传播即可（本项目核心池子都是连通图）。
    """
    adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for a, b, rate in edges:
        if rate <= 0:
            continue
        adj[a].append((b, 1.0 / rate))  # price_b = price_a * (1/rate)
        adj[b].append((a, rate))        # price_a = price_b * rate

    prices: Dict[str, float] = {anchor: anchor_price}
    if anchor not in adj:
        return prices

    dq = deque([anchor])
    while dq:
        current = dq.popleft()
        for neighbor, factor in adj[current]:
            if neighbor in prices:
                continue
            prices[neighbor] = prices[current] * factor
            dq.append(neighbor)
    return prices


def pools_from_rates(
    rate_csv: str,
    assets_csv: str,
    depth_usd: float = 1_000_000.0,
    anchor: str = "USDC",
    out_path: Optional[str] = None,
) -> List[Pool]:
    """
    用 v1 的 trading_pairs_core.csv（只有汇率、没有储备金）反推一份「名义深度」的储备金。

    做法：以每个池子自己的汇率确定两侧比例，再用 depth_usd 定规模：
        reserve0 = (depth_usd / 2) / price(token0)
        reserve1 = reserve0 * rate
    这样 AMM 模拟里的价差结构与链上快照一致，但「深度」是人为设定的名义值，
    因此输出的 CSV 会带 source=derived_from_rates，避免被误当成真实流动性。
    """
    symbols: Dict[str, str] = {}
    if os.path.exists(assets_csv):
        with open(assets_csv, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                addr = next((row[k] for k in row if k.startswith("assetId")), "")
                symbols[addr.strip().lower()] = (row.get("symbol") or addr[:8]).strip()

    grouped: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
    with open(rate_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            start = next((row[k] for k in row if k.startswith(":START_ID")), "").strip().lower()
            end = next((row[k] for k in row if k.startswith(":END_ID")), "").strip().lower()
            pair = (row.get("pair_address") or "").strip()
            rate_key = next((k for k in row if k.startswith("rate")), "")
            rate = float(row.get(rate_key) or 0)
            grouped[pair].append((start, end, rate))

    triples: List[Tuple[str, str, float]] = []
    for rows in grouped.values():
        # 同一个池子会写正反两行，取第一行当 token0 -> token1 的汇率
        start, end, rate = rows[0]
        if rate <= 0:
            continue
        triples.append((symbols.get(start, start[:8]), symbols.get(end, end[:8]), rate))

    prices = derive_usd_prices(triples, anchor=anchor)

    pools: List[Pool] = []
    for pair, rows in grouped.items():
        start, end, rate = rows[0]
        s0 = symbols.get(start, start[:8])
        s1 = symbols.get(end, end[:8])
        if rate <= 0 or s0 not in prices or s1 not in prices:
            continue
        reserve0 = (depth_usd / 2.0) / prices[s0]
        reserve1 = reserve0 * rate
        pools.append(
            Pool(
                pair_address=pair,
                pair_name=f"{s0}-{s1}",
                symbol0=s0,
                symbol1=s1,
                reserve0=reserve0,
                reserve1=reserve1,
                source="derived_from_rates",
            )
        )

    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "pair_address",
                    "pair_name",
                    "token0",
                    "token1",
                    "symbol0",
                    "symbol1",
                    "decimals0",
                    "decimals1",
                    "reserve0",
                    "reserve1",
                    "source",
                ]
            )
            for pool in pools:
                writer.writerow(
                    [
                        pool.pair_address,
                        pool.pair_name,
                        "",
                        "",
                        pool.symbol0,
                        pool.symbol1,
                        "",
                        "",
                        f"{pool.reserve0:.10f}",
                        f"{pool.reserve1:.10f}",
                        pool.source,
                    ]
                )
    return pools


# ============================================================
# 3. 图：有向边、环路枚举、AMM 模拟
# ============================================================


def build_hops(pools: Sequence[Pool]) -> Dict[str, List[Hop]]:
    """把池子展开成有向边（每个池子贡献正反两条），方便 DFS 找环。"""
    edges: Dict[str, List[Hop]] = defaultdict(list)
    for pool in pools:
        if pool.reserve0 <= 0 or pool.reserve1 <= 0:
            continue
        edges[pool.symbol0].append(Hop(pool, pool.symbol0, pool.symbol1, pool.reserve0, pool.reserve1))
        edges[pool.symbol1].append(Hop(pool, pool.symbol1, pool.symbol0, pool.reserve1, pool.reserve0))
    return edges


def find_cycles(
    edges: Dict[str, List[Hop]],
    max_hops: int = 4,
    max_cycles: int = 2000,
) -> List[List[Hop]]:
    """
    枚举「简单环」（起点=终点、中间节点不重复），跳数 2~max_hops。
    去重技巧：只接受「起点是环中字典序最小的代币」的那一份，避免同一个环被旋转成多份。
    环路方向不同（A→B→C→A 与 A→C→B→A）视为两个机会，因为利润率不同。
    """
    cycles: List[List[Hop]] = []
    seen: Set[Tuple[Tuple[str, str], ...]] = set()
    symbols = sorted(edges)

    for start in symbols:
        stack: List[Hop] = []

        def dfs(current: str, visited: Set[str]) -> None:
            if len(cycles) >= max_cycles or len(stack) >= max_hops:
                return
            for hop in edges[current]:
                nxt = hop.to_symbol
                if nxt == start:
                    if len(stack) + 1 < 2:
                        continue
                    cycle = stack + [hop]
                    # 同一个池子进出两次（A→B→A 走同一个池）不是套利，只是白付手续费
                    if len({h.pool.pair_address for h in cycle}) < len(cycle):
                        continue
                    if start != min(tuple(h.from_symbol for h in cycle)):
                        continue  # 只保留规范旋转
                    key = tuple((h.pool.pair_address, h.from_symbol) for h in cycle)
                    if key in seen:
                        continue
                    seen.add(key)
                    cycles.append(cycle)
                    continue
                if nxt in visited:
                    continue
                stack.append(hop)
                visited.add(nxt)
                dfs(nxt, visited)
                visited.discard(nxt)
                stack.pop()

        dfs(start, {start})
    return cycles


def amm_amount_out(amount_in: float, reserve_in: float, reserve_out: float, fee_rate: float) -> float:
    """
    恒定乘积公式（Uniswap V2）：
        amount_out = (R_out * amount_in * (1 - fee)) / (R_in + amount_in * (1 - fee))
    手续费是在「输入侧」扣的，这是和线性模型（先乘汇率最后统一扣费）最大的区别。
    """
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0.0
    effective = amount_in * (1.0 - fee_rate)
    return (reserve_out * effective) / (reserve_in + effective)


@dataclass
class Simulation:
    amount_out: float
    worst_impact: float
    impacts: List[float] = field(default_factory=list)


def simulate_cycle(cycle: Sequence[Hop], amount_in: float, fee_rate: float) -> Simulation:
    """
    逐跳模拟，返回最终数量与每一跳的价格冲击。
    价格冲击要单独剔除手续费：executed = out / (amount*(1-fee))，这样
    「冲击」只反映 AMM 曲线被推动的程度，方便和手续费分开归因。
    """
    amount = amount_in
    impacts: List[float] = []
    for hop in cycle:
        spot = hop.price
        out = amm_amount_out(amount, hop.reserve_in, hop.reserve_out, fee_rate)
        effective = amount * (1.0 - fee_rate)
        executed_no_fee = out / effective if effective else 0.0
        impacts.append(max(0.0, 1.0 - executed_no_fee / spot) if spot else 0.0)
        amount = out
    return Simulation(amount_out=amount, worst_impact=max(impacts) if impacts else 0.0, impacts=impacts)


def evaluate(cycle: Sequence[Hop], notional_usd: float, prices: Dict[str, float], costs: CostModel) -> Dict[str, float]:
    """把「名义本金（USD）」翻译成 token 数量，跑一遍 AMM，再折算回 USD 净利。"""
    start = cycle[0].from_symbol
    price = prices.get(start, 0.0)
    if price <= 0 or notional_usd <= 0:
        return {"net": -math.inf, "gross": 0.0, "out_usd": 0.0, "impact": 0.0}

    amount_in = notional_usd / price
    sim = simulate_cycle(cycle, amount_in, costs.fee_rate)
    out_usd = sim.amount_out * price
    gross = out_usd - notional_usd
    gas = costs.gas_cost_usd(len(cycle))
    flash = notional_usd * costs.flashloan_fee_bps / 10_000.0
    tip = notional_usd * costs.builder_tip_bps / 10_000.0
    return {
        "net": gross - gas - flash - tip,
        "gross": gross,
        "out_usd": out_usd,
        "impact": sim.worst_impact,
        "gas": gas,
        "flash": flash,
        "tip": tip,
    }


def max_notional(cycle: Sequence[Hop], prices: Dict[str, float], costs: CostModel) -> float:
    """
    仓位上限：任意一跳最多吃掉该池 2% 的储备（可配），取所有跳里最紧的那个。
    这既是风控约束，也是「真实世界里套利机器人不敢无限加仓」的原因。
    """
    caps: List[float] = []
    for hop in cycle:
        price = prices.get(hop.from_symbol, 0.0)
        if price <= 0:
            continue
        caps.append(hop.reserve_in * price * costs.max_impact_pct)
    return min(caps) if caps else 0.0


def optimize_notional(
    cycle: Sequence[Hop],
    prices: Dict[str, float],
    costs: CostModel,
    min_usd: float = 10.0,
    grid_points: int = 25,
) -> Tuple[float, Dict[str, float]]:
    """
    求利润最大的名义本金。
    先在对数网格上粗扫（避免漏掉单峰区间），再在最优邻域做三分搜索精修。
    净利润关于本金是「凹函数」：线性 edge 带来正斜率、价格冲击带来负二次项，
    固定成本（gas）把整条曲线整体下移 —— 所以既能求最优仓位，也能判断是否根本不值得做。
    """
    cap = max_notional(cycle, prices, costs)
    if cap <= 0:
        return 0.0, evaluate(cycle, 0.0, prices, costs)

    lo = max(min_usd, cap / 10_000.0)
    hi = max(cap, lo * 1.01)

    xs = [lo * (hi / lo) ** (i / (grid_points - 1)) for i in range(grid_points)]
    results = [(x, evaluate(cycle, x, prices, costs)) for x in xs]
    best_x, best_res = max(results, key=lambda item: item[1]["net"])

    idx = xs.index(best_x)
    a = xs[max(0, idx - 1)]
    b = xs[min(len(xs) - 1, idx + 1)]
    for _ in range(80):
        m1 = a + (b - a) / 3.0
        m2 = b - (b - a) / 3.0
        if evaluate(cycle, m1, prices, costs)["net"] < evaluate(cycle, m2, prices, costs)["net"]:
            a = m1
        else:
            b = m2
    refined_x = (a + b) / 2.0
    refined_res = evaluate(cycle, refined_x, prices, costs)
    if refined_res["net"] > best_res["net"]:
        return refined_x, refined_res
    return best_x, best_res


def break_even_notional(
    cycle: Sequence[Hop],
    prices: Dict[str, float],
    costs: CostModel,
    optimal_notional: float,
) -> float:
    """
    最小可盈利本金：利润要先跨过固定成本（gas）才转正。
    在 [1, 最优仓位] 上取对数网格找第一个 net>0 的点，再二分细化。
    """
    if optimal_notional <= 0 or evaluate(cycle, optimal_notional, prices, costs)["net"] <= 0:
        return math.inf

    points = 40
    prev = 1.0
    prev_net = evaluate(cycle, prev, prices, costs)["net"]
    for i in range(1, points + 1):
        x = (optimal_notional) ** (i / points)
        net = evaluate(cycle, x, prices, costs)["net"]
        if net > 0 >= prev_net:
            lo, hi = prev, x
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if evaluate(cycle, mid, prices, costs)["net"] > 0:
                    hi = mid
                else:
                    lo = mid
            return hi
        prev, prev_net = x, net
    return math.inf


def build_opportunity(
    cycle: Sequence[Hop],
    prices: Dict[str, float],
    costs: CostModel,
    min_edge_bps: float = 5.0,
    max_sane_edge_bps: float = 2000.0,
) -> Opportunity:
    """把一条环路算成一个完整的机会记录（含最优仓位、成本拆分与结论）。"""
    linear = 1.0
    linear_after_fee = 1.0
    for hop in cycle:
        linear *= hop.price
        linear_after_fee *= hop.price * (1.0 - costs.fee_rate)

    optimal, result = optimize_notional(cycle, prices, costs)
    break_even = break_even_notional(cycle, prices, costs, optimal)
    notional = optimal
    net_bps = (result["net"] / notional * 10_000.0) if notional > 0 and math.isfinite(result["net"]) else 0.0

    if (linear - 1.0) * 10_000.0 > max_sane_edge_bps:
        # 价差大到离谱，基本是「脏池 / 极端汇率 / 无流动性」导致的数据问题，先查数据再谈交易
        verdict = "DATA_SUSPECT"
    elif result["net"] > 0 and net_bps >= min_edge_bps:
        verdict = "EXECUTABLE"
    elif result["net"] > 0:
        verdict = "MARGINAL"
    elif result["gross"] > 0:
        verdict = "GAS_EATS_IT"
    else:
        verdict = "NO_EDGE"

    depth = min(
        2.0 * min(hop.reserve_in * prices.get(hop.from_symbol, 0.0), hop.reserve_out * prices.get(hop.to_symbol, 0.0))
        for hop in cycle
    )

    return Opportunity(
        cycle_id=">".join([hop.from_symbol for hop in cycle] + [cycle[0].from_symbol]),
        path_symbols=[hop.from_symbol for hop in cycle] + [cycle[0].from_symbol],
        path_pools=[hop.pool.pair_address for hop in cycle],
        hops=len(cycle),
        linear_edge_bps=(linear - 1.0) * 10_000.0,
        linear_edge_after_fee_bps=(linear_after_fee - 1.0) * 10_000.0,
        optimal_notional_usd=notional,
        gross_profit_usd=result["gross"],
        gas_usd=result.get("gas", 0.0),
        flashloan_fee_usd=result.get("flash", 0.0),
        tip_usd=result.get("tip", 0.0),
        net_profit_usd=result["net"] if math.isfinite(result["net"]) else -1e18,
        net_edge_bps=net_bps,
        price_impact_bps=result.get("impact", 0.0) * 10_000.0,
        min_pool_depth_usd=depth,
        break_even_notional_usd=break_even,
        verdict=verdict,
    )


OUTPUT_FIELDS = [
    "cycle_id",
    "path",
    "pools",
    "hops",
    "linear_edge_bps",
    "linear_edge_after_fee_bps",
    "optimal_notional_usd",
    "gross_profit_usd",
    "gas_usd",
    "flashloan_fee_usd",
    "tip_usd",
    "net_profit_usd",
    "net_edge_bps",
    "price_impact_bps",
    "min_pool_depth_usd",
    "break_even_notional_usd",
    "verdict",
]


def write_opportunities(opportunities: Sequence[Opportunity], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for opp in opportunities:
            writer.writerow(opp.as_row())


def print_table(opportunities: Sequence[Opportunity], top: int = 10) -> None:
    header = (
        f"{'路径':<32}{'线性bps':>10}{'扣费bps':>10}{'最优$':>12}"
        f"{'毛利$':>10}{'gas$':>8}{'净利$':>10}{'净bps':>9}  结论"
    )
    print(header)
    print("-" * 130)
    for opp in opportunities[:top]:
        print(
            f"{opp.cycle_id:<32}"
            f"{opp.linear_edge_bps:>10.2f}"
            f"{opp.linear_edge_after_fee_bps:>10.2f}"
            f"{opp.optimal_notional_usd:>12,.0f}"
            f"{opp.gross_profit_usd:>10.2f}"
            f"{opp.gas_usd:>8.2f}"
            f"{opp.net_profit_usd:>10.2f}"
            f"{opp.net_edge_bps:>10.2f}  {opp.verdict}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AMM 真实成本下的套利最优仓位（v2）")
    parser.add_argument("--reserves", default="", help="pool_reserves.csv（真实链上储备金）")
    parser.add_argument("--from-rates", action="store_true", help="由汇率 CSV 反推名义深度储备金（无 RPC 时用）")
    parser.add_argument("--rates-csv", default="trading_pairs_core.csv")
    parser.add_argument("--assets-csv", default="assets_core.csv")
    parser.add_argument("--depth-usd", type=float, default=1_000_000.0, help="--from-rates 时每个池子的名义深度（美元）")
    parser.add_argument("--emit-reserves", default="pool_reserves_sample.csv", help="--from-rates 时写出的储备金文件")
    parser.add_argument("--out", default="arbitrage_opportunities.csv")
    parser.add_argument("--max-hops", type=int, default=4)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--min-edge-bps", type=float, default=5.0, help="净 edge 达到多少 bps 才算可执行")
    parser.add_argument("--fee-bps", type=float, default=30.0, help="每跳手续费（bps），Uniswap V2 = 30")
    parser.add_argument("--gas-price-gwei", type=float, default=25.0)
    parser.add_argument("--eth-price", type=float, default=2500.0)
    parser.add_argument("--gas-per-hop", type=int, default=150_000)
    parser.add_argument("--flashloan-fee-bps", type=float, default=0.9)
    parser.add_argument("--builder-tip-bps", type=float, default=1.0)
    parser.add_argument("--max-impact-pct", type=float, default=0.02)
    parser.add_argument("--min-pool-depth-usd", type=float, default=10_000.0, help="低于该深度的池子不参与计算（过滤垃圾池）")
    parser.add_argument("--max-sane-edge-bps", type=float, default=2000.0, help="线性价差超过该值的环路标记为 DATA_SUSPECT")
    args = parser.parse_args(argv)

    costs = CostModel(
        fee_rate=args.fee_bps / 10_000.0,
        gas_per_hop=args.gas_per_hop,
        gas_price_gwei=args.gas_price_gwei,
        eth_price_usd=args.eth_price,
        flashloan_fee_bps=args.flashloan_fee_bps,
        builder_tip_bps=args.builder_tip_bps,
        max_impact_pct=args.max_impact_pct,
    )

    if args.reserves:
        pools = load_reserves(args.reserves)
        source_desc = args.reserves
    elif args.from_rates:
        pools = pools_from_rates(
            args.rates_csv,
            args.assets_csv,
            depth_usd=args.depth_usd,
            out_path=args.emit_reserves,
        )
        source_desc = f"{args.rates_csv}（名义深度 ${args.depth_usd:,.0f}，source=derived_from_rates）"
    else:
        raise SystemExit("请指定 --reserves <csv> 或 --from-rates")

    if not pools:
        raise SystemExit("没有可用池子，请检查输入文件")

    edges = build_hops(pools)
    prices = derive_usd_prices([(p.symbol0, p.symbol1, p.rate) for p in pools])

    # 深度过滤：低于阈值的池子（垃圾币 / 刚建池）不参与套利，否则会算出荒唐的价差
    if args.min_pool_depth_usd > 0:
        def depth_of(pool: Pool) -> float:
            price0 = prices.get(pool.symbol0, 0.0)
            price1 = prices.get(pool.symbol1, 0.0)
            return 2.0 * min(pool.reserve0 * price0, pool.reserve1 * price1)

        kept = [p for p in pools if depth_of(p) >= args.min_pool_depth_usd]
        dropped = len(pools) - len(kept)
        if dropped:
            print(f"⚠️ 过滤掉 {dropped} 个深度 < ${args.min_pool_depth_usd:,.0f} 的池子")
        pools = kept
        edges = build_hops(pools)
        if not pools:
            raise SystemExit("所有池子都被深度阈值过滤掉了，请调低 --min-pool-depth-usd")

    cycles = find_cycles(edges, max_hops=args.max_hops)
    if not cycles:
        raise SystemExit("没有找到闭环路径（2 跳以上），请检查池子是否连通")

    print(f"数据源：{source_desc}")
    print(f"池子 {len(pools)} 个 / 代币 {len(edges)} 个 / 闭环路径 {len(cycles)} 条")
    print("价格（USD，USDC 锚定）：" + "，".join(f"{k}={v:,.4f}" for k, v in sorted(prices.items())))
    print(
        f"成本假设：手续费 {args.fee_bps:.0f}bps/跳，gas {args.gas_per_hop:,}/跳 + 固定 "
        f"{costs.gas_overhead:,}，gas price {args.gas_price_gwei} gwei，ETH ${args.eth_price:,.0f}，"
        f"闪贷 {args.flashloan_fee_bps}bps，tip {args.builder_tip_bps}bps\n"
    )

    opportunities = [
        build_opportunity(
            cycle,
            prices,
            costs,
            min_edge_bps=args.min_edge_bps,
            max_sane_edge_bps=args.max_sane_edge_bps,
        )
        for cycle in cycles
    ]
    opportunities.sort(key=lambda o: o.net_profit_usd, reverse=True)
    print_table(opportunities, top=args.top)

    best_net = opportunities[0]
    best_paper = max(opportunities, key=lambda o: o.linear_edge_bps)
    print(
        f"\n纸面价差最大：{best_paper.cycle_id} · 线性 {best_paper.linear_edge_bps:+.2f}bps "
        f"→ 扣手续费 {best_paper.linear_edge_after_fee_bps:+.2f}bps "
        f"→ 最优仓位 ${best_paper.optimal_notional_usd:,.0f} 时净利 ${best_paper.net_profit_usd:,.4f}"
    )
    print(
        f"净利最好的一条：{best_net.cycle_id} · 净利 ${best_net.net_profit_usd:,.4f}"
        f"（{best_net.verdict}），最优仓位 ${best_net.optimal_notional_usd:,.0f}，"
        f"净 edge {best_net.net_edge_bps:+.2f}bps"
    )
    executable = [o for o in opportunities if o.verdict == "EXECUTABLE"]
    print(f"可执行机会：{len(executable)} / {len(opportunities)} 条")
    print(
        f"仓位上限由最浅的池子决定（min pool depth ≈ ${best_paper.min_pool_depth_usd:,.0f}，"
        f"最多吃 {args.max_impact_pct:.1%} 储备）"
    )

    write_opportunities(opportunities, args.out)
    print(f"\n✅ 已写出 {args.out}（{len(opportunities)} 条）")
    print("下一步：python3 hedge_sizing.py --opportunities " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
