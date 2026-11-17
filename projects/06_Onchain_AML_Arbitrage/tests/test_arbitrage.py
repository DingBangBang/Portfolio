#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_arbitrage.py · AMM 套利优化器与对冲成本模型的单元测试

运行：
    cd 06_Onchain_AML_Arbitrage
    python3 -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage_optimizer import (  # noqa: E402
    CostModel,
    Pool,
    amm_amount_out,
    build_hops,
    build_opportunity,
    derive_usd_prices,
    find_cycles,
    optimize_notional,
    simulate_cycle,
)
from hedge_sizing import (  # noqa: E402
    HedgeAssumptions,
    PerpMarket,
    build_plan,
    carry_analysis,
    calc_hedge_cost,
)


def make_pool(symbol0, symbol1, reserve0, reserve1, pair="0xpair"):
    return Pool(
        pair_address=pair,
        pair_name=f"{symbol0}-{symbol1}",
        symbol0=symbol0,
        symbol1=symbol1,
        reserve0=reserve0,
        reserve1=reserve1,
    )


class AmmMathTest(unittest.TestCase):
    def test_amount_out_monotone_and_bounded(self):
        r_in, r_out = 1000.0, 2000.0
        small = amm_amount_out(1.0, r_in, r_out, 0.003)
        big = amm_amount_out(100.0, r_in, r_out, 0.003)
        self.assertLess(small, big)
        self.assertLess(big, r_out)  # 永远吃不空池子

    def test_zero_input_and_zero_reserves(self):
        self.assertEqual(amm_amount_out(0.0, 1000.0, 2000.0, 0.003), 0.0)
        self.assertEqual(amm_amount_out(1.0, 0.0, 2000.0, 0.003), 0.0)

    def test_fee_reduces_output(self):
        no_fee = amm_amount_out(10.0, 1000.0, 2000.0, 0.0)
        with_fee = amm_amount_out(10.0, 1000.0, 2000.0, 0.003)
        self.assertLess(with_fee, no_fee)
        self.assertAlmostEqual((no_fee - with_fee) / no_fee, 0.003, places=3)

    def test_price_impact_excludes_fee(self):
        pool = make_pool("USDC", "WETH", 1_000_000.0, 400.0)
        cycle = build_hops([pool])["USDC"][0:1]
        tiny = simulate_cycle(cycle, 1.0, 0.003)
        big = simulate_cycle(cycle, 50_000.0, 0.003)
        self.assertLess(tiny.worst_impact, 0.0001)   # $1 几乎无冲击
        self.assertGreater(big.worst_impact, 0.01)  # $5 万明显推动价格


class CycleTest(unittest.TestCase):
    def setUp(self):
        # 三个池子组成三角形：USDC/WETH、WETH/USDT、USDT/USDC
        self.pools = [
            make_pool("USDC", "WETH", 1_000_000.0, 400.0, "0xa"),
            make_pool("WETH", "USDT", 500.0, 1_240_000.0, "0xb"),
            make_pool("USDT", "USDC", 1_000_000.0, 1_001_000.0, "0xc"),
        ]

    def test_cycles_found_and_deduped(self):
        hops = build_hops(self.pools)
        cycles = find_cycles(hops, max_hops=3)
        paths = {"->".join([h.from_symbol for h in c] + [c[0].from_symbol]) for c in cycles}
        self.assertIn("USDC->WETH->USDT->USDC", paths)
        self.assertEqual(len(paths), len(cycles))  # 无重复路径

    def test_same_pool_two_hop_is_excluded(self):
        hops = build_hops([make_pool("USDC", "WETH", 1_000_000.0, 400.0, "0xa")])
        self.assertEqual(find_cycles(hops, max_hops=3), [])

    def test_prices_derived_from_anchor(self):
        prices = derive_usd_prices([(p.symbol0, p.symbol1, p.rate) for p in self.pools])
        self.assertAlmostEqual(prices["USDC"], 1.0, places=9)
        self.assertAlmostEqual(prices["WETH"], 2500.0, places=2)
        self.assertAlmostEqual(prices["USDT"], 1.001, places=3)


class OptimizerTest(unittest.TestCase):
    def setUp(self):
        # 同一交易对的两个池子出现 5% 价差 → 存在真实的（可执行的）套利
        self.pools = [
            make_pool("USDC", "WETH", 2_000_000.0, 800.0, "0xcheap"),   # 1 WETH = 2500 USDC
            make_pool("USDC", "WETH", 2_000_000.0, 841.0, "0xrich"),    # 1 WETH ≈ 2378 USDC
        ]
        self.prices = derive_usd_prices([(p.symbol0, p.symbol1, p.rate) for p in self.pools])
        self.costs = CostModel(fee_rate=0.003, gas_per_hop=150_000, gas_price_gwei=10.0, eth_price_usd=2500.0)

    def _best_cycle(self):
        """环路有正反两个方向，只有「先买便宜池再卖贵池」的方向有正价差。"""
        cycles = find_cycles(build_hops(self.pools), max_hops=3)
        return max(cycles, key=lambda c: math.prod(hop.price for hop in c))

    def test_opportunity_is_executable_and_sized(self):
        opp = build_opportunity(self._best_cycle(), self.prices, self.costs)
        self.assertGreater(opp.linear_edge_bps, 400.0)
        self.assertGreater(opp.optimal_notional_usd, 0.0)
        self.assertGreater(opp.net_profit_usd, 0.0)
        self.assertEqual(opp.verdict, "EXECUTABLE")
        # 仓位不能超过「吃掉 2% 储备」的上限
        self.assertLessEqual(opp.optimal_notional_usd, 2_000_000.0 * 0.02 + 1.0)

    def test_optimizer_matches_grid_search(self):
        cycle = self._best_cycle()
        _, result = optimize_notional(cycle, self.prices, self.costs)

        from arbitrage_optimizer import evaluate

        grid = [10.0 * (100_000.0 / 10.0) ** (i / 400.0) for i in range(401)]
        grid_best = max(evaluate(cycle, x, self.prices, self.costs)["net"] for x in grid)
        self.assertGreaterEqual(result["net"], grid_best * 0.99)

    def test_no_edge_case_is_flat(self):
        pools = [
            make_pool("USDC", "WETH", 1_000_000.0, 400.0, "0xa"),
            make_pool("WETH", "USDT", 500.0, 1_240_000.0, "0xb"),
            make_pool("USDT", "USDC", 1_000_000.0, 1_001_000.0, "0xc"),
        ]
        hops = build_hops(pools)
        prices = derive_usd_prices([(p.symbol0, p.symbol1, p.rate) for p in pools])
        cycle = find_cycles(hops, max_hops=3)[0]
        sim = simulate_cycle(cycle, 1.0, 0.003)
        self.assertLess(sim.amount_out, 1.0)  # 扣掉手续费后一定变少

        opp = build_opportunity(cycle, prices, self.costs)
        self.assertEqual(opp.verdict, "NO_EDGE")
        self.assertLess(opp.net_profit_usd, 0.0)

    def test_data_suspect_flag(self):
        opp = build_opportunity(self._best_cycle(), self.prices, self.costs, max_sane_edge_bps=100.0)
        self.assertEqual(opp.verdict, "DATA_SUSPECT")


class HedgeTest(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "cycle_id": "USDC>WETH>USDC",
            "path": "USDC->WETH->USDC",
            "hops": "2",
            "linear_edge_bps": "150",
            "optimal_notional_usd": "50000",
            "price_impact_bps": "5",
            "gas_usd": "20",
            "min_pool_depth_usd": "200000000",
            "verdict": "EXECUTABLE",
        }
        row.update(overrides)
        return row

    def test_hedge_cost_components(self):
        market = PerpMarket("WETH", funding_8h_bps=1.2, basis_bps=3.5, taker_fee_bps=4.5, max_leverage=25)
        assumptions = HedgeAssumptions(holding_hours=1.0, cex_slippage_bps=2.0)
        cost = calc_hedge_cost("WETH", 50_000.0, market, assumptions)
        self.assertAlmostEqual(cost.perp_fee_bps, 9.0, places=6)
        self.assertAlmostEqual(cost.funding_bps, -0.15, places=6)  # 空头收资金费
        self.assertGreater(cost.total_bps, 0.0)

    def test_plan_executes_when_edge_is_large(self):
        market = PerpMarket("WETH", funding_8h_bps=1.2, basis_bps=3.5, taker_fee_bps=4.5, max_leverage=25)
        plan = build_plan(self._row(), 50_000.0, market, HedgeAssumptions(), fee_bps_per_hop=30.0)
        self.assertEqual(plan.decision, "EXECUTE")
        self.assertGreater(plan.net_profit_usd, 20.0)
        # 所需毛价差 = 各项成本 + 门槛，一定大于链上净 edge 的缺口
        self.assertGreater(plan.required_gross_edge_bps, 60.0)
        self.assertAlmostEqual(
            plan.required_gross_edge_bps - plan.linear_edge_bps, plan.edge_shortfall_bps, places=6
        )

    def test_plan_rejects_when_edge_too_small(self):
        plan = build_plan(
            self._row(linear_edge_bps="13.77"), 50_000.0, None, HedgeAssumptions(), fee_bps_per_hop=30.0
        )
        self.assertEqual(plan.decision, "REJECT")
        self.assertGreater(plan.edge_shortfall_bps, 0)

    def test_data_suspect_is_not_traded(self):
        plan = build_plan(
            self._row(verdict="DATA_SUSPECT", linear_edge_bps="400000"), 50_000.0, None, HedgeAssumptions()
        )
        self.assertEqual(plan.decision, "DATA_SUSPECT")

    def test_carry_analysis_positive_funding(self):
        markets = {"SOL": PerpMarket("SOL", funding_8h_bps=2.5, basis_bps=6.0, taker_fee_bps=5.0, max_leverage=20)}
        rows = carry_analysis(markets, HedgeAssumptions(), holding_days=30)
        self.assertEqual(len(rows), 1)
        self.assertGreater(float(rows[0]["net_carry_apr"]), 0)
        self.assertEqual(rows[0]["decision"], "CARRY")

    def test_carry_analysis_negative_funding_avoids(self):
        markets = {"ETH": PerpMarket("ETH", funding_8h_bps=-1.0, basis_bps=2.0, taker_fee_bps=4.5, max_leverage=25)}
        rows = carry_analysis(markets, HedgeAssumptions(), holding_days=30)
        self.assertEqual(rows[0]["decision"], "AVOID")


if __name__ == "__main__":
    unittest.main()
