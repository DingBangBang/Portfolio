#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_aml_rules.py · AML 图算法与规则引擎的单元测试

运行：
    cd 06_Onchain_AML_Arbitrage
    python3 -m unittest discover -s tests -v

设计思路：用「手工构造的小图」验证每条规则是否真的按预期触发，
比拿真实数据跑一遍更适合做回归（真实数据会随区块变化，断言不稳定）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aml_graph import AddressGraph, Edge, load_edges  # noqa: E402
from aml_rule_engine import (  # noqa: E402
    DatasetConfig,
    Hit,
    risk_level,
    rule_address_poisoning,
    rule_dusting,
    rule_fan_out,
    rule_pass_through,
    rule_round_amount,
    rule_self_transfer,
    rule_split_merge,
    score_hits,
)


def addr(seed: str) -> str:
    """生成一个 42 位的小写地址（便于构造测试图）。"""
    body = (seed * 40)[:40]
    return "0x" + body.lower()


CFG = DatasetConfig(
    name="TEST",
    candidates=[],
    asset="ETH",
    decimals=18,
    dust_amount=0.0001,
    peel_min_amount=0.01,
    round_units=[1.0],
    threshold_band=(9.0, 10.0),
    min_value=0.05,
    fan_out_min=5,
    fan_in_min=5,
)


def build_graph(edges):
    graph = AddressGraph(name="test", asset="ETH")
    for i, (src, dst, amount) in enumerate(edges):
        graph.add_edge(
            Edge(src=src, dst=dst, amount=amount, raw_value=int(amount * 1e18), block=i, tx_hash=f"0x{i:064x}")
        )
    return graph


class GraphAlgorithmTest(unittest.TestCase):
    def test_pagerank_sums_to_one(self):
        graph = build_graph([(addr("a"), addr("b"), 1.0), (addr("b"), addr("c"), 1.0), (addr("c"), addr("a"), 1.0)])
        ranks = graph.pagerank()
        self.assertAlmostEqual(sum(ranks.values()), 1.0, places=6)
        # 环形结构里三个节点应当等价
        values = list(ranks.values())
        self.assertAlmostEqual(max(values), min(values), places=6)

    def test_k_core_on_star_graph(self):
        center = addr("c")
        leaves = [addr(f"l{i}") for i in range(4)]
        graph = build_graph([(center, leaf, 1.0) for leaf in leaves])
        core = graph.k_core()
        self.assertEqual(core[center], 1)
        self.assertEqual(core[leaves[0]], 1)

    def test_betweenness_middle_node_dominates(self):
        a, b, c = addr("a"), addr("b"), addr("c")
        graph = build_graph([(a, b, 1.0), (b, c, 1.0)])
        bc = graph.betweenness(max_sources=10)
        self.assertGreater(bc[b], bc[a])

    def test_csv_loader_handles_both_value_types(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_edges.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(":START_ID(Address),:END_ID(Address),value:long,block_number:int\n")
            f.write(f"{addr('x')},{addr('y')},2000000000000000000,100\n")
        try:
            edges = list(load_edges(path, decimals=18))
        finally:
            os.remove(path)
        self.assertEqual(len(edges), 1)
        self.assertAlmostEqual(edges[0].amount, 2.0)
        self.assertEqual(edges[0].block, 100)


class RuleTest(unittest.TestCase):
    def test_fan_out_detected(self):
        src = addr("f")
        graph = build_graph([(src, addr(f"r{i}"), 0.1) for i in range(6)])
        hits = rule_fan_out(graph, CFG)
        self.assertEqual([h.address for h in hits], [src])
        self.assertEqual(hits[0].metrics["fan_out"], 6)

    def test_split_merge_detected(self):
        mule = addr("m")
        edges = [(addr("in"), mule, 1.0)] + [(mule, addr(f"o{i}"), 0.19) for i in range(5)]
        graph = build_graph(edges)
        hits = rule_split_merge(graph, CFG)
        self.assertTrue(any(h.address == mule for h in hits))

    def test_pass_through_detected(self):
        mule = addr("p")
        edges = [(addr(f"i{i}"), mule, 1.0) for i in range(3)] + [(mule, addr(f"o{i}"), 1.0) for i in range(3)]
        graph = build_graph(edges)
        hits = rule_pass_through(graph, CFG)
        self.assertTrue(any(h.address == mule for h in hits))
        self.assertAlmostEqual(hits[0].metrics["forward_ratio"], 1.0, places=3)

    def test_dusting_detected(self):
        spammer = addr("d")
        graph = build_graph([(spammer, addr(f"v{i}"), 0.00001) for i in range(12)])
        hits = rule_dusting(graph, CFG)
        self.assertEqual([h.address for h in hits], [spammer])
        self.assertEqual(hits[0].metrics["dust_receivers"], 12)

    def test_self_transfer_needs_two_loops(self):
        loop_only_once = build_graph([(addr("s"), addr("s"), 1.0)])
        self.assertEqual(rule_self_transfer(loop_only_once, CFG), [])
        loop_twice = build_graph([(addr("s"), addr("s"), 1.0), (addr("s"), addr("s"), 1.0)])
        self.assertEqual(len(rule_self_transfer(loop_twice, CFG)), 1)

    def test_round_amount_detected(self):
        sender = addr("r")
        graph = build_graph([(sender, addr(f"o{i}"), 1.0) for i in range(3)])
        hits = rule_round_amount(graph, CFG)
        self.assertTrue(any(h.address == sender for h in hits))

    def test_address_poisoning_detected(self):
        # 真实地址 R 与受害者 V 有过转账；攻击者 A 与 R 共享「前 4 + 后 4」指纹，并向 V 打粉尘
        legit = "0x111122223333444455556666777788889999" + "abcd"
        suspect = "0x1111" + "a" * 32 + "abcd"
        victim = addr("v")
        graph = build_graph(
            [
                (victim, legit, 1.0),       # V 与真实地址 R 有正常往来
                (suspect, victim, 0.00001),  # A 向 V 投毒
            ]
        )
        hits = rule_address_poisoning(graph, CFG, labels={})
        self.assertEqual([h.address for h in hits], [suspect.lower()])

    def test_score_dedupes_and_caps(self):
        address = addr("z")
        hits = [
            Hit(dataset="TEST", address=address, rule_id="R01", weight=60.0, evidence="a"),
            Hit(dataset="TEST", address=address, rule_id="R01", weight=60.0, evidence="重复"),
            Hit(dataset="TEST", address=address, rule_id="R02", weight=60.0, evidence="b"),
        ]
        risks = score_hits(hits, "TEST")
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0].score, 100.0)
        self.assertEqual(sorted(risks[0].rule_ids), ["R01", "R02"])

    def test_risk_level_bands(self):
        self.assertEqual(risk_level(99)[0], "critical")
        self.assertEqual(risk_level(60)[0], "high")
        self.assertEqual(risk_level(31)[0], "medium")
        self.assertEqual(risk_level(5)[0], "low")


if __name__ == "__main__":
    unittest.main()
