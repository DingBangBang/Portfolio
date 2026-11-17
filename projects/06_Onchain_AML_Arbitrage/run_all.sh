#!/usr/bin/env bash
# run_all.sh · 一键复现 v2 全流程（不需要 RPC / Neo4j，全部跑本地 CSV + 纯标准库计算）
#
# 用法：
#   cd projects/06_Onchain_AML_Arbitrage
#   bash run_all.sh
#
# 想接真实链上数据时：
#   export RPC_URL="https://mainnet.infura.io/v3/<your-key>"
#   python3 fetch_uniswap_reserves.py
#   python3 arbitrage_optimizer.py --reserves pool_reserves.csv
set -euo pipefail

cd "$(dirname "$0")"

echo "=== 1/4 AML 规则引擎 ==="
python3 aml_rule_engine.py --top 10

echo
echo "=== 2/4 套利最优仓位（无 RPC 时用汇率反推名义深度） ==="
python3 arbitrage_optimizer.py --from-rates --depth-usd 20000000 --top 6

echo
echo "=== 3/4 对冲成本与仓位决策（含压力测试） ==="
python3 hedge_sizing.py --stress

echo
echo "=== 4/4 资金费 carry ==="
python3 hedge_sizing.py --mode carry

echo
echo "=== 单元测试 ==="
python3 -m unittest discover -s tests

echo
echo "✅ 全部完成：aml_alerts.csv / aml_risk_scores.csv / aml_case_report.md"
echo "            arbitrage_opportunities.csv / pool_reserves_sample.csv"
echo "            hedge_plan.csv / hedge_stress_test.csv / carry_analysis.csv"
