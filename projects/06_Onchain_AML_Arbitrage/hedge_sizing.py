#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hedge_sizing.py · 套利仓位的对冲成本与仓位决策（v2 新增）

为什么套利还要谈「对冲」：
    1) 原子套利（flash loan 一笔交易内完成）不需要对冲 —— 没有敞口；
    2) 但现实里大量机会是「非原子」的：链上买入 → 跨链/CEX 卖出，中间有几秒到几小时的时滞，
       这时你会持有 WETH/WBTC 这类波动资产，价差 13bps 的利润，价格波动 1% 就直接亏穿；
    3) 所以专业做法是：吃价差的同时，在永续合约上做等值反向（Delta 中性）对冲，
       把「赚价差」变成「赚价差 - 对冲成本」。

本脚本回答三个问题：
    Q1 这笔机会值不值得对冲执行？           → net_edge_after_hedge_bps + decision
    Q2 至少要多少毛价差才能覆盖全部成本？    → required_gross_edge_bps（最有用的一个数）
    Q3 成本假设变了会怎样？                 → --stress 输出压力测试矩阵
另外 `--mode carry` 把同一套成本框架用在「资金费 carry」上（现货多 + 永续空）。

用法：
    python3 hedge_sizing.py --opportunities arbitrage_opportunities.csv
    python3 hedge_sizing.py --stress --holding-hours 1
    python3 hedge_sizing.py --mode carry --funding funding_rates_sample.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

STABLES = {"USDC", "USDT", "DAI", "BUSD", "TUSD", "FRAX", "LUSD"}


# ============================================================
# 1. 成本假设
# ============================================================


@dataclass
class HedgeAssumptions:
    """对冲与资金成本假设（bps / 年化口径，便于和套利 edge 直接相减）。"""

    holding_hours: float = 1.0            # 预期敞口持有时间（下单到平仓）
    perp_taker_fee_bps: float = 4.5        # 永续开仓 + 平仓各一次
    cex_slippage_bps: float = 2.0          # CEX 成交滑点（链上滑点已由 AMM 模拟计入）
    funding_8h_bps: float = 1.2            # 每 8 小时资金费（正数=多头付给空头）
    basis_bps: float = 3.5                 # 永续相对现货的溢价（做空要承担收敛成本）
    capital_cost_apr: float = 0.08         # 保证金占用的机会成本（年化 8%）
    withdraw_fee_usd: float = 1.5          # 提币 / 跨链固定费用
    maintenance_margin_pct: float = 0.005  # 维持保证金率，用于算强平缓冲
    leverage: float = 3.0                  # 实际使用杠杆（不是交易所上限）
    min_edge_bps: float = 5.0              # 低于该净 edge 视为不值得做
    min_profit_usd: float = 20.0           # 绝对利润门槛（覆盖运营成本）
    health_safety_bps: float = 20.0        # 执行缓冲：把理论价差打折，防成交失败


@dataclass
class PerpMarket:
    asset: str
    funding_8h_bps: float
    basis_bps: float
    taker_fee_bps: float
    max_leverage: float
    venue: str = ""


def load_perp_markets(path: str) -> Dict[str, PerpMarket]:
    markets: Dict[str, PerpMarket] = {}
    if not os.path.exists(path):
        return markets
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            asset = (row.get("asset") or "").strip().upper()
            if not asset:
                continue
            markets[asset] = PerpMarket(
                asset=asset,
                funding_8h_bps=float(row.get("funding_rate_8h_bps") or 0),
                basis_bps=float(row.get("basis_bps") or 0),
                taker_fee_bps=float(row.get("perp_taker_fee_bps") or 0),
                max_leverage=float(row.get("max_leverage") or 1),
                venue=(row.get("venue") or "").strip(),
            )
    return markets


# ============================================================
# 2. 对冲成本模型
# ============================================================


@dataclass
class HedgeCost:
    hedge_instrument: str
    hedge_ratio: float
    perp_fee_bps: float
    cex_slippage_bps: float
    funding_bps: float
    basis_bps: float
    capital_bps: float
    withdraw_bps: float

    @property
    def total_bps(self) -> float:
        return (
            self.perp_fee_bps
            + self.cex_slippage_bps
            + self.funding_bps
            + self.basis_bps
            + self.capital_bps
            + self.withdraw_bps
        )


def calc_hedge_cost(
    instrument: str,
    position_usd: float,
    market: Optional[PerpMarket],
    assumptions: HedgeAssumptions,
    ratio: float = 1.0,
) -> HedgeCost:
    """
    对冲成本拆成 6 项，全部换算成 bps：
        1) 永续开平仓手续费（两次 taker）
        2) CEX 成交滑点
        3) 资金费：做空时正资金费是「收入」，所以取负号
        4) 基差：永续溢价越高，做空建立头寸越贵（按溢价收敛计一次成本）
        5) 保证金占用的资金成本（年化 → 持有期折算）
        6) 提币固定费用（按仓位摊薄）
    """
    perp_fee_bps = 2.0 * (market.taker_fee_bps if market else assumptions.perp_taker_fee_bps)
    funding_8h = market.funding_8h_bps if market else assumptions.funding_8h_bps
    funding_bps = -funding_8h * (assumptions.holding_hours / 8.0)  # 空头收资金费 → 负成本
    basis_bps = abs(market.basis_bps if market else assumptions.basis_bps)
    capital_bps = assumptions.capital_cost_apr * 10_000.0 * assumptions.holding_hours / 8_760.0
    withdraw_bps = (assumptions.withdraw_fee_usd / position_usd * 10_000.0) if position_usd > 0 else 0.0

    return HedgeCost(
        hedge_instrument=instrument,
        hedge_ratio=ratio,
        perp_fee_bps=perp_fee_bps * ratio,
        cex_slippage_bps=assumptions.cex_slippage_bps * ratio,
        funding_bps=funding_bps * ratio,
        basis_bps=basis_bps * ratio,
        capital_bps=capital_bps * ratio,
        withdraw_bps=withdraw_bps,
    )


def pick_hedge_instrument(path_symbols: Sequence[str]) -> str:
    """
    选对冲标的：路径里最「波动」的币（非稳定币优先，多个时取靠前的）。
    全稳定币路径（USDC→USDT→DAI）几乎没有价格风险，用稳定币永续对冲即可。
    """
    for symbol in path_symbols:
        if symbol and symbol not in STABLES:
            return symbol
    return path_symbols[0] if path_symbols else "USDC"


def split_path(path: str) -> List[str]:
    """兼容 "A->B->C" 与 "A>B>C" 两种写法（optimizer 输出的是前者，cycle_id 是后者）。"""
    if "->" in path:
        return [p.strip() for p in path.split("->") if p.strip()]
    return [p.strip() for p in path.split(">") if p.strip()]


def symbol_is_stable(symbol: str) -> bool:
    return symbol.upper() in STABLES


# ============================================================
# 3. 仓位决策
# ============================================================


@dataclass
class HedgePlan:
    cycle_id: str
    path: str
    hops: int
    linear_edge_bps: float
    onchain_net_edge_bps: float
    hedge_instrument: str
    hedge_ratio: float
    hedge_cost_bps: float
    hedge_cost_breakdown: Dict[str, float]
    net_edge_after_hedge_bps: float
    position_usd: float
    hedge_notional_usd: float
    net_profit_usd: float
    required_gross_edge_bps: float
    edge_shortfall_bps: float
    max_holding_hours: float
    liquidation_buffer_pct: float
    decision: str
    reason: str

    def as_row(self) -> Dict[str, object]:
        return {
            "cycle_id": self.cycle_id,
            "path": self.path,
            "hops": self.hops,
            "linear_edge_bps": round(self.linear_edge_bps, 3),
            "onchain_net_edge_bps": round(self.onchain_net_edge_bps, 3),
            "hedge_instrument": self.hedge_instrument,
            "hedge_ratio": round(self.hedge_ratio, 3),
            "hedge_cost_bps": round(self.hedge_cost_bps, 3),
            "perp_fee_bps": round(self.hedge_cost_breakdown.get("perp_fee_bps", 0.0), 3),
            "cex_slippage_bps": round(self.hedge_cost_breakdown.get("cex_slippage_bps", 0.0), 3),
            "funding_bps": round(self.hedge_cost_breakdown.get("funding_bps", 0.0), 3),
            "basis_bps": round(self.hedge_cost_breakdown.get("basis_bps", 0.0), 3),
            "capital_bps": round(self.hedge_cost_breakdown.get("capital_bps", 0.0), 3),
            "withdraw_bps": round(self.hedge_cost_breakdown.get("withdraw_bps", 0.0), 3),
            "net_edge_after_hedge_bps": round(self.net_edge_after_hedge_bps, 3),
            "position_usd": round(self.position_usd, 2),
            "hedge_notional_usd": round(self.hedge_notional_usd, 2),
            "net_profit_usd": round(self.net_profit_usd, 4),
            "required_gross_edge_bps": round(self.required_gross_edge_bps, 3),
            "edge_shortfall_bps": round(self.edge_shortfall_bps, 3),
            "max_holding_hours": (
                round(self.max_holding_hours, 2) if math.isfinite(self.max_holding_hours) else ""
            ),
            "liquidation_buffer_pct": round(self.liquidation_buffer_pct, 4),
            "decision": self.decision,
            "reason": self.reason,
        }


def build_plan(
    row: Dict[str, str],
    position_usd: float,
    market: Optional[PerpMarket],
    assumptions: HedgeAssumptions,
    fee_bps_per_hop: float = 30.0,
    flash_bps: float = 0.9,
    tip_bps: float = 1.0,
) -> HedgePlan:
    """
    用「bps 口径」重算这笔机会的账：
        毛价差(线性)  - 每跳手续费×跳数 - 价格冲击 - gas - 闪贷 - tip - 执行缓冲 = 链上净 edge
        链上净 edge  - 对冲成本                                            = 对冲后净 edge
    再倒推出「要覆盖全部成本，毛价差至少需要多少」（required_gross_edge_bps）。
    """
    path = row["path"]
    symbols = split_path(path)
    hops = int(float(row["hops"]))
    linear = float(row["linear_edge_bps"])
    optimal = float(row["optimal_notional_usd"] or 0)
    gas_usd = float(row["gas_usd"] or 0)

    position = position_usd if position_usd > 0 else max(optimal, 10_000.0)
    # 价格冲击用池子深度估算：两币池深度 D（两侧合计），投入 x 的冲击 ≈ x/(D/2)，上限 50%
    depth = float(row.get("min_pool_depth_usd") or 0)
    impact = min(position / (depth / 2.0), 0.5) * 10_000.0 if depth > 0 else 0.0
    gas_bps = (gas_usd / position * 10_000.0) if position > 0 else 0.0

    onchain_net = (
        linear
        - hops * fee_bps_per_hop
        - impact
        - gas_bps
        - flash_bps
        - tip_bps
        - assumptions.health_safety_bps
    )

    instrument = pick_hedge_instrument(symbols)
    non_stable = [s for s in symbols if not symbol_is_stable(s)]
    ratio = 1.0 if non_stable else 0.3  # 稳定币路径价格风险很低，只做部分名义对冲
    cost = calc_hedge_cost(instrument, position, market, assumptions, ratio=ratio)

    net_after = onchain_net - cost.total_bps
    profit_usd = position * net_after / 10_000.0

    required_gross = (
        hops * fee_bps_per_hop
        + gas_bps
        + flash_bps
        + tip_bps
        + assumptions.health_safety_bps
        + cost.total_bps
        + assumptions.min_edge_bps
    )
    shortfall = required_gross - linear

    # 还能持有多久：资金费 + 资金成本按小时累积（空头收资金费时时间反而站在你这边）
    per_hour_cost = (
        assumptions.capital_cost_apr * 10_000.0 / 8_760.0
        + cost.funding_bps / max(assumptions.holding_hours, 1e-9)
    )
    max_holding = math.inf if per_hour_cost <= 0 else max(0.0, net_after / per_hour_cost)

    liq_buffer = (1.0 / assumptions.leverage) - assumptions.maintenance_margin_pct

    if row.get("verdict") == "DATA_SUSPECT":
        decision = "DATA_SUSPECT"
        reason = "价差量级不合理（脏池 / 极端汇率），先做数据核查，不进入交易决策"
    elif net_after >= assumptions.min_edge_bps and profit_usd >= assumptions.min_profit_usd:
        decision = "EXECUTE"
        reason = f"净 edge {net_after:.1f}bps、仓位利润 ${profit_usd:,.2f}，覆盖门槛"
    elif net_after >= 0:
        decision = "WATCH"
        reason = f"净 edge 仅 {net_after:.1f}bps / 利润 ${profit_usd:,.2f}，未达门槛，等价差扩大"
    else:
        decision = "REJECT"
        reason = f"毛价差比所需低 {shortfall:.1f}bps（需 {required_gross:.1f}bps，实际 {linear:.1f}bps）"

    breakdown = {
        "perp_fee_bps": cost.perp_fee_bps,
        "cex_slippage_bps": cost.cex_slippage_bps,
        "funding_bps": cost.funding_bps,
        "basis_bps": cost.basis_bps,
        "capital_bps": cost.capital_bps,
        "withdraw_bps": cost.withdraw_bps,
    }

    return HedgePlan(
        cycle_id=row["cycle_id"],
        path=path,
        hops=hops,
        linear_edge_bps=linear,
        onchain_net_edge_bps=onchain_net,
        hedge_instrument=instrument,
        hedge_ratio=ratio,
        hedge_cost_bps=cost.total_bps,
        hedge_cost_breakdown=breakdown,
        net_edge_after_hedge_bps=net_after,
        position_usd=position,
        hedge_notional_usd=position * ratio,
        net_profit_usd=profit_usd,
        required_gross_edge_bps=required_gross,
        edge_shortfall_bps=shortfall,
        max_holding_hours=max_holding,
        liquidation_buffer_pct=liq_buffer,
        decision=decision,
        reason=reason,
    )


# ============================================================
# 4. 压力测试与资金费 carry
# ============================================================


STRESS_FIELDS = [
    "cycle_id",
    "path",
    "funding_apr",
    "basis_shift_bps",
    "holding_hours",
    "slippage_multiplier",
    "hedge_cost_bps",
    "net_edge_after_hedge_bps",
    "decision",
]


def stress_test(
    rows: Sequence[Dict[str, str]],
    markets: Dict[str, PerpMarket],
    base: HedgeAssumptions,
    fee_bps_per_hop: float = 30.0,
    position_usd: float = 0.0,
    funding_aprs: Sequence[float] = (0.0, 0.10, 0.30, 0.60),
    basis_shifts: Sequence[float] = (-20.0, 0.0, 20.0),
    holdings: Sequence[float] = (0.25, 1.0, 4.0),
    slippage_multipliers: Sequence[float] = (1.0, 2.0),
) -> List[Dict[str, object]]:
    """
    对「资金费 / 基差 / 持有时间 / 滑点」做笛卡尔积压力测试：
    目的不是预测，而是回答「这套策略在什么假设下会从赚变亏」，这决定了风控参数。
    """
    out: List[Dict[str, object]] = []
    for row in rows:
        instrument = pick_hedge_instrument(split_path(row["path"]))
        market = markets.get(instrument)
        for apr in funding_aprs:
            funding_8h_bps = apr * 10_000.0 / (3 * 365)
            for basis_shift in basis_shifts:
                for holding in holdings:
                    for mult in slippage_multipliers:
                        assumptions = HedgeAssumptions(
                            holding_hours=holding,
                            perp_taker_fee_bps=base.perp_taker_fee_bps,
                            cex_slippage_bps=base.cex_slippage_bps * mult,
                            funding_8h_bps=funding_8h_bps,
                            basis_bps=(market.basis_bps if market else base.basis_bps) + basis_shift,
                            capital_cost_apr=base.capital_cost_apr,
                            withdraw_fee_usd=base.withdraw_fee_usd,
                            maintenance_margin_pct=base.maintenance_margin_pct,
                            leverage=base.leverage,
                            min_edge_bps=base.min_edge_bps,
                            min_profit_usd=base.min_profit_usd,
                            health_safety_bps=base.health_safety_bps,
                        )
                        plan = build_plan(row, position_usd, market, assumptions, fee_bps_per_hop=fee_bps_per_hop)
                        out.append(
                            {
                                "cycle_id": plan.cycle_id,
                                "path": plan.path,
                                "funding_apr": round(apr, 4),
                                "basis_shift_bps": basis_shift,
                                "holding_hours": holding,
                                "slippage_multiplier": mult,
                                "hedge_cost_bps": round(plan.hedge_cost_bps, 3),
                                "net_edge_after_hedge_bps": round(plan.net_edge_after_hedge_bps, 3),
                                "decision": plan.decision,
                            }
                        )
    return out


CARRY_FIELDS = [
    "asset",
    "venue",
    "funding_8h_bps",
    "funding_apr",
    "basis_bps",
    "round_trip_fee_bps",
    "breakeven_days",
    "net_carry_apr",
    "liquidation_buffer_pct",
    "decision",
]


def carry_analysis(
    markets: Dict[str, PerpMarket],
    assumptions: HedgeAssumptions,
    holding_days: float = 30.0,
) -> List[Dict[str, object]]:
    """
    资金费 carry（现货多 + 永续空）：赚永续多头支付给空头的资金费。
        年化净收益 = 资金费年化 - 开平仓手续费年化 - 基差收敛成本年化 - 保证金资金成本
        breakeven_days = (手续费 + 基差) / 每日资金费 →「至少要持有多久才回本」
    这条曲线的意义：carry 是「时间换收益」，手续费和基差是入场门票，持有越短越不划算。
    """
    rows: List[Dict[str, object]] = []
    for market in markets.values():
        funding_apr = market.funding_8h_bps * 3 * 365 / 100.0  # bps -> %，每天 3 次结算
        round_trip_fee_bps = 2 * market.taker_fee_bps + assumptions.cex_slippage_bps
        daily_funding_bps = market.funding_8h_bps * 3
        breakeven_days = (
            (round_trip_fee_bps + abs(market.basis_bps)) / daily_funding_bps
            if daily_funding_bps > 0
            else math.inf
        )
        annualization = 365.0 / holding_days
        fee_drag_apr = (round_trip_fee_bps / 10_000.0) * annualization
        basis_drag_apr = (abs(market.basis_bps) / 10_000.0) * annualization
        capital_drag_apr = assumptions.capital_cost_apr / max(assumptions.leverage, 1e-9)
        net_apr = funding_apr - fee_drag_apr - basis_drag_apr - capital_drag_apr

        liq_buffer = (
            1.0 / max(min(assumptions.leverage, market.max_leverage), 1e-9)
        ) - assumptions.maintenance_margin_pct
        if net_apr > 0.05 and breakeven_days <= holding_days:
            decision = "CARRY"
        elif net_apr > 0:
            decision = "WATCH"
        else:
            decision = "AVOID"

        rows.append(
            {
                "asset": market.asset,
                "venue": market.venue,
                "funding_8h_bps": market.funding_8h_bps,
                "funding_apr": round(funding_apr, 4),
                "basis_bps": market.basis_bps,
                "round_trip_fee_bps": round(round_trip_fee_bps, 3),
                "breakeven_days": round(breakeven_days, 3) if math.isfinite(breakeven_days) else "",
                "net_carry_apr": round(net_apr, 4),
                "liquidation_buffer_pct": round(liq_buffer, 4),
                "decision": decision,
            }
        )
    rows.sort(key=lambda r: -float(r["net_carry_apr"]))
    return rows


# ============================================================
# 5. 输出与命令行
# ============================================================


PLAN_FIELDS = [
    "cycle_id",
    "path",
    "hops",
    "linear_edge_bps",
    "onchain_net_edge_bps",
    "hedge_instrument",
    "hedge_ratio",
    "hedge_cost_bps",
    "perp_fee_bps",
    "cex_slippage_bps",
    "funding_bps",
    "basis_bps",
    "capital_bps",
    "withdraw_bps",
    "net_edge_after_hedge_bps",
    "position_usd",
    "hedge_notional_usd",
    "net_profit_usd",
    "required_gross_edge_bps",
    "edge_shortfall_bps",
    "max_holding_hours",
    "liquidation_buffer_pct",
    "decision",
    "reason",
]


def write_csv(rows: Sequence[Dict[str, object]], path: str, fields: Sequence[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def load_opportunities(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def print_plan_table(plans: Sequence[HedgePlan], top: int = 10) -> None:
    header = (
        f"{'路径':<30}{'毛bps':>9}{'链上净':>9}{'对冲':>8}"
        f"{'对冲后':>9}{'需毛bps':>9}{'缺口':>8}  决策"
    )
    print(header)
    print("-" * 118)
    for plan in plans[:top]:
        print(
            f"{plan.path:<30}"
            f"{plan.linear_edge_bps:>9.2f}"
            f"{plan.onchain_net_edge_bps:>9.2f}"
            f"{plan.hedge_cost_bps:>8.2f}"
            f"{plan.net_edge_after_hedge_bps:>9.2f}"
            f"{plan.required_gross_edge_bps:>9.2f}"
            f"{plan.edge_shortfall_bps:>8.2f}"
            f"  {plan.decision}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="套利仓位的对冲成本与仓位决策（v2）")
    parser.add_argument("--opportunities", default="arbitrage_opportunities.csv")
    parser.add_argument("--funding", default="funding_rates_sample.csv", help="永续资金费/费率样本")
    parser.add_argument("--out", default="hedge_plan.csv")
    parser.add_argument("--mode", choices=["inventory", "carry"], default="inventory")
    parser.add_argument("--position-usd", type=float, default=0.0, help="参考仓位（0 = 用优化器的最优仓位，下限 1 万）")
    parser.add_argument("--holding-hours", type=float, default=1.0)
    parser.add_argument("--leverage", type=float, default=3.0)
    parser.add_argument("--fee-bps", type=float, default=30.0, help="链上每跳手续费（bps）")
    parser.add_argument("--min-edge-bps", type=float, default=5.0)
    parser.add_argument("--min-profit-usd", type=float, default=20.0)
    parser.add_argument("--stress", action="store_true", help="输出压力测试矩阵")
    parser.add_argument("--stress-out", default="hedge_stress_test.csv")
    parser.add_argument("--stress-top", type=int, default=3, help="压力测试只跑毛价差最大的前 N 条路径")
    parser.add_argument("--hold-days", type=float, default=30.0, help="carry 模式的持有天数")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args(argv)

    assumptions = HedgeAssumptions(
        holding_hours=args.holding_hours,
        leverage=args.leverage,
        min_edge_bps=args.min_edge_bps,
        min_profit_usd=args.min_profit_usd,
    )
    markets = load_perp_markets(args.funding)

    if args.mode == "carry":
        if not markets:
            raise SystemExit(f"未找到 {args.funding}，请先准备永续资金费样本")
        rows = carry_analysis(markets, assumptions, holding_days=args.hold_days)
        write_csv(rows, "carry_analysis.csv", CARRY_FIELDS)
        print(f"{'资产':<6}{'场所':<16}{'资金费年化%':>12}{'基差bps':>10}{'往返费bps':>11}{'回本天数':>10}{'净carry年化':>12}  决策")
        print("-" * 100)
        for row in rows:
            print(
                f"{row['asset']:<6}{str(row['venue']):<16}{float(row['funding_apr']):>12.2f}"
                f"{float(row['basis_bps']):>10.1f}{float(row['round_trip_fee_bps']):>11.1f}"
                f"{str(row['breakeven_days']):>10}{float(row['net_carry_apr']):>12.2f}  {row['decision']}"
            )
        print("\n✅ 已写出 carry_analysis.csv")
        return 0

    rows = load_opportunities(args.opportunities)
    if not rows:
        raise SystemExit(f"{args.opportunities} 为空，请先跑 arbitrage_optimizer.py")

    plans: List[HedgePlan] = []
    for row in rows:
        instrument = pick_hedge_instrument(split_path(row["path"]))
        plans.append(
            build_plan(
                row,
                args.position_usd,
                markets.get(instrument),
                assumptions,
                fee_bps_per_hop=args.fee_bps,
            )
        )
    plans.sort(key=lambda p: -p.linear_edge_bps)

    print(f"对冲标的资金费样本：{args.funding}（未命中的币用默认假设）")
    print_plan_table(plans, top=args.top)
    decisions = {d: sum(1 for p in plans if p.decision == d) for d in ("EXECUTE", "WATCH", "REJECT")}
    print(f"\n决策分布：EXECUTE={decisions['EXECUTE']}，WATCH={decisions['WATCH']}，REJECT={decisions['REJECT']}")
    worst = max(plans, key=lambda p: p.edge_shortfall_bps)
    print(
        f"成本门槛最高的一条：{worst.path} 需要毛价差 {worst.required_gross_edge_bps:.1f}bps，"
        f"当前 {worst.linear_edge_bps:.1f}bps，缺口 {worst.edge_shortfall_bps:.1f}bps"
    )
    if markets:
        top_carry = carry_analysis(markets, assumptions, holding_days=args.hold_days)[0]
        print(
            f"参考：资金费 carry 年化净收益最高的是 {top_carry['asset']} "
            f"{float(top_carry['net_carry_apr']):.2f}%（回本 {top_carry['breakeven_days']} 天）"
        )

    write_csv([plan.as_row() for plan in plans], args.out, PLAN_FIELDS)
    print(f"\n✅ 已写出 {args.out}（{len(plans)} 条）")

    if args.stress:
        stress_rows = stress_test(
            sorted(rows, key=lambda r: -float(r["linear_edge_bps"]))[: args.stress_top],
            markets,
            assumptions,
            fee_bps_per_hop=args.fee_bps,
            position_usd=args.position_usd,
        )
        write_csv(stress_rows, args.stress_out, STRESS_FIELDS)
        worst_row = min(stress_rows, key=lambda r: float(r["net_edge_after_hedge_bps"]))
        best_row = max(stress_rows, key=lambda r: float(r["net_edge_after_hedge_bps"]))
        print(
            f"✅ 压力测试 {len(stress_rows)} 个场景 → {args.stress_out}\n"
            f"   最差场景 {worst_row['cycle_id']} net={worst_row['net_edge_after_hedge_bps']}bps"
            f"（funding APR {worst_row['funding_apr']}, basis {worst_row['basis_shift_bps']}bps, "
            f"hold {worst_row['holding_hours']}h）\n"
            f"   最好场景 {best_row['cycle_id']} net={best_row['net_edge_after_hedge_bps']}bps"
        )
        positive = [r for r in stress_rows if float(r["net_edge_after_hedge_bps"]) > 0]
        print(f"   压力测试中净 edge 为正的场景：{len(positive)} / {len(stress_rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
