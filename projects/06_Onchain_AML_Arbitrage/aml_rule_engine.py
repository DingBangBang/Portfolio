#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aml_rule_engine.py · 链上反洗钱规则引擎 + 风险评分（v2 新增）

相比 v1（aml_analysis.py 只做「两跳 fan-out + 资金总览」），这一版把可疑行为拆成
12 条可解释规则，加权汇总成 0~100 的风险分，并自动产出：
    aml_alerts.csv        每条告警（地址 + 命中规则 + 证据）
    aml_risk_scores.csv   地址级风险分（可直接回写 Neo4j：LOAD CSV + MATCH）
    aml_summary.json      本次运行的统计口径与命中分布（可复现）
    aml_case_report.md    人类可读的可疑案例卡片（Top-N + 复现用 Cypher）

规则清单（R01~R12）：
    R01 FAN_OUT            拆分转账：单一地址向大量不同地址分散出账
    R02 FAN_IN             资金归集：大量不同地址向同一地址汇总
    R03 SPLIT_MERGE        拆分-归集二部结构（马甲层：少进多出 / 多进少出）
    R04 PASS_THROUGH       快进快出：转入后几乎全额转出（过账账户 / 跑分）
    R05 PEEL_CHAIN         剥洋葱链：每跳留零头、主体资金持续转移
    R06 DUSTING            粉尘攻击：向大量地址发送极小额
    R07 ADDRESS_POISONING  地址投毒：首 4 位 + 尾 4 位与常用地址相同的「李鬼」地址
    R08 ROUND_AMOUNT       整数/临界金额：反复使用整千整万或刚好卡在申报阈值下
    R09 SELF_TRANSFER      自转：同地址多次自转（刷量 / 投毒掩护）
    R10 BLOCK_BURST        同区块批量出账（脚本化批量分发，需要 block_number）
    R11 HUB_CENTRALITY     高中心度枢纽（PageRank 高位 + 高度数）
    R12 LABELED_ENTITY     命中标签库（混币器 / 交易所 / 合约）

用法：
    python3 aml_rule_engine.py                          # 默认跑 ETH + USDT 两个数据集
    python3 aml_rule_engine.py --datasets ETH
    python3 aml_rule_engine.py --write-neo4j            # 额外把风险分写回 Neo4j
    python3 aml_rule_engine.py --top 20 --min-score 30

设计取舍：
  1. 规则阈值集中在 DatasetConfig / RULES 里，便于按业务调参，不散落在代码各处；
  2. 只用标准库（csv / json / statistics），无需 pandas，clone 即可跑；
  3. 分数是「规则加权和」，不是概率——所以报告里始终附 evidence，方便人工复核；
  4. 标签库中的负权重（交易所 / 路由合约）会降低误报，避免把 Uniswap Router 判成拆分洗钱。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from aml_graph import AddressGraph, Edge, percentile_threshold, short_addr

# ============================================================
# 1. 配置
# ============================================================


@dataclass
class DatasetConfig:
    """一个数据集 = 一种资产的转账图。阈值按资产量级分别设置，避免「一刀切」。"""

    name: str
    candidates: List[str]          # 依次尝试的关系 CSV（unified 优先，回退原始文件）
    asset: str
    decimals: int
    dust_amount: float             # 粉尘阈值（低于该金额视为 dust）
    peel_min_amount: float         # 剥洋葱链的最小起手金额
    round_units: List[float]       # 「整数金额」判定单位
    threshold_band: Optional[Tuple[float, float]]  # 临界金额区间（模拟申报阈值下方）
    min_value: float               # 规则的最小金额门槛（过滤噪音）
    fan_out_min: int = 20
    fan_in_min: int = 20


DEFAULT_DATASETS: List[DatasetConfig] = [
    DatasetConfig(
        name="ETH",
        candidates=["transactions_unified.csv", "transactions.csv"],
        asset="ETH",
        decimals=18,
        dust_amount=0.0001,        # 0.0001 ETH ≈ 粉尘
        peel_min_amount=0.01,      # 0.01 ETH 起才值得看剥离链
        round_units=[1.0, 10.0, 100.0],
        threshold_band=(9.0, 10.0),
        min_value=0.05,
        fan_out_min=20,
        fan_in_min=20,
    ),
    DatasetConfig(
        name="USDT",
        candidates=["usdt_transfers_unified.csv", "usdt_transfers.csv"],
        asset="USDT",
        decimals=6,
        dust_amount=0.01,          # 0.01 USDT 的粉尘投递
        peel_min_amount=100.0,
        round_units=[1000.0, 10000.0],
        threshold_band=(9_000.0, 10_000.0),  # 卡在 1 万美元申报线下
        min_value=100.0,
        fan_out_min=10,
        fan_in_min=10,
    ),
]


# 规则元数据：权重即「单独命中该规则贡献的分值」，severity 用于报告排序解释
RULES: Dict[str, Dict[str, object]] = {
    "R01": {"name_cn": "拆分转账 FAN_OUT", "name_en": "Fan-out splitting", "weight": 18, "severity": "high"},
    "R02": {"name_cn": "资金归集 FAN_IN", "name_en": "Fan-in consolidation", "weight": 15, "severity": "medium"},
    "R03": {"name_cn": "拆分-归集二部结构 SPLIT_MERGE", "name_en": "Split-then-merge", "weight": 22, "severity": "high"},
    "R04": {"name_cn": "快进快出 PASS_THROUGH", "name_en": "Pass-through / mule", "weight": 20, "severity": "high"},
    "R05": {"name_cn": "剥洋葱链 PEEL_CHAIN", "name_en": "Peel chain", "weight": 25, "severity": "critical"},
    "R06": {"name_cn": "粉尘攻击 DUSTING", "name_en": "Dusting attack", "weight": 20, "severity": "high"},
    "R07": {"name_cn": "地址投毒 ADDRESS_POISONING", "name_en": "Address poisoning", "weight": 28, "severity": "critical"},
    "R08": {"name_cn": "整数/临界金额 ROUND_AMOUNT", "name_en": "Round / just-below-threshold amounts", "weight": 12, "severity": "medium"},
    "R09": {"name_cn": "自转 SELF_TRANSFER", "name_en": "Self transfer", "weight": 10, "severity": "low"},
    "R10": {"name_cn": "同区块批量出账 BLOCK_BURST", "name_en": "Same-block burst", "weight": 15, "severity": "medium"},
    "R11": {"name_cn": "高中心度枢纽 HUB_CENTRALITY", "name_en": "Hub centrality", "weight": 8, "severity": "low"},
    "R12": {"name_cn": "实体识别/标签 LABELED_ENTITY", "name_en": "Labeled entity / service heuristic", "weight": 0, "severity": "info"},
}

LEVEL_BANDS: List[Tuple[float, str, str]] = [
    (75.0, "critical", "严重"),
    (50.0, "high", "高"),
    (30.0, "medium", "中"),
    (0.0, "low", "低"),
]


def risk_level(score: float) -> Tuple[str, str]:
    for threshold, level, level_cn in LEVEL_BANDS:
        if score >= threshold:
            return level, level_cn
    return "low", "低"


# ============================================================
# 2. 数据结构
# ============================================================


@dataclass
class Hit:
    """一条规则命中的结果：谁命中、命中了哪条规则、证据是什么。"""

    dataset: str
    address: str
    rule_id: str
    weight: float
    evidence: str
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class AddressRisk:
    dataset: str
    address: str
    score: float
    level: str
    level_cn: str
    hits: List[Hit]

    @property
    def rule_ids(self) -> List[str]:
        return sorted({h.rule_id for h in self.hits})

    @property
    def evidence(self) -> str:
        return " | ".join(f"{h.rule_id}:{h.evidence}" for h in self.hits)

    def metrics_flat(self) -> Dict[str, float]:
        flat: Dict[str, float] = {}
        for hit in self.hits:
            for key, value in hit.metrics.items():
                flat[f"{hit.rule_id}.{key}"] = value
        return flat


def load_labels(path: str) -> Dict[str, Dict[str, object]]:
    """读取标签库，统一成小写地址 -> 标签字典。"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    labels: Dict[str, Dict[str, object]] = {}
    for item in payload.get("labels", []):
        addr = str(item.get("address", "")).strip().lower()
        if addr:
            labels[addr] = item
    return labels


# ============================================================
# 3. 规则实现（每条规则返回 List[Hit]）
# ============================================================


def rule_fan_out(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """R01 拆分转账：一个地址向 >= fan_out_min 个不同地址出账，且金额分布较平均。"""
    hits: List[Hit] = []
    for addr in graph.nodes:
        receivers = graph.distinct_successors(addr)
        if len(receivers) < cfg.fan_out_min:
            continue
        total_out = graph.out_value(addr)
        if total_out < cfg.min_value:
            continue
        entropy = graph.value_entropy(addr, "out")
        # 拆分特征：收款方多 + 金额分布均匀（熵高）；服务商地址熵也很高，靠标签降权
        weight = RULES["R01"]["weight"] + max(0.0, min(8.0, (len(receivers) - cfg.fan_out_min) / 50.0))
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R01",
                weight=float(weight),
                evidence=f"向 {len(receivers)} 个地址出账，合计 {total_out:.4f} {cfg.asset}，金额熵 {entropy:.2f}",
                metrics={
                    "fan_out": len(receivers),
                    "out_value": round(total_out, 6),
                    "amount_entropy": round(entropy, 4),
                    "avg_ticket": round(total_out / max(1, len(receivers)), 6),
                },
            )
        )
    return hits


def rule_fan_in(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """R02 资金归集：>= fan_in_min 个不同地址向同一地址打款。"""
    hits: List[Hit] = []
    for addr in graph.nodes:
        senders = graph.distinct_predecessors(addr)
        if len(senders) < cfg.fan_in_min:
            continue
        total_in = graph.in_value(addr)
        if total_in < cfg.min_value:
            continue
        weight = RULES["R02"]["weight"] + max(0.0, min(6.0, (len(senders) - cfg.fan_in_min) / 60.0))
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R02",
                weight=float(weight),
                evidence=f"{len(senders)} 个地址向其归集，合计 {total_in:.4f} {cfg.asset}",
                metrics={
                    "fan_in": len(senders),
                    "in_value": round(total_in, 6),
                    "avg_inbound": round(total_in / max(1, len(senders)), 6),
                },
            )
        )
    return hits


def rule_split_merge(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """
    R03 拆分-归集二部结构：马甲层的典型形态是「少进多出」（一层拆分）或「多进少出」（二层归集）。
    比 R01/R02 更严格：同时约束进出两侧的对手方数量，避免把交易所热钱包也算进来。
    """
    hits: List[Hit] = []
    for addr in graph.nodes:
        senders = graph.distinct_predecessors(addr)
        receivers = graph.distinct_successors(addr)
        if len(senders) < 1 or len(receivers) < 1:
            continue

        total_in, total_out = graph.in_value(addr), graph.out_value(addr)
        one_to_many = len(receivers) >= 5 and len(senders) <= 2 and total_out >= cfg.min_value
        many_to_one = len(senders) >= 5 and len(receivers) <= 2 and total_in >= cfg.min_value
        if not (one_to_many or many_to_one):
            continue

        pattern = "少进多出（拆分层）" if one_to_many else "多进少出（归集层）"
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R03",
                weight=float(RULES["R03"]["weight"]),
                evidence=(
                    f"{pattern}：{len(senders)} 进 -> {len(receivers)} 出，"
                    f"流入 {total_in:.4f} / 流出 {total_out:.4f} {cfg.asset}"
                ),
                metrics={
                    "senders": len(senders),
                    "receivers": len(receivers),
                    "in_value": round(total_in, 6),
                    "out_value": round(total_out, 6),
                    "retention": round((total_out - total_in) / total_in, 4) if total_in else 0.0,
                },
            )
        )
    return hits


def rule_pass_through(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """
    R04 快进快出（过账账户 / 跑分号）：转进来的钱几乎原样转走，账户只是个「中转站」。
    用 流出/流入 比值落在 [0.85, 1.15] 判断，并排除进出笔数过少的账户。
    """
    hits: List[Hit] = []
    for addr in graph.nodes:
        if graph.in_degree(addr) < 3 or graph.out_degree(addr) < 3:
            continue
        total_in, total_out = graph.in_value(addr), graph.out_value(addr)
        if total_in < cfg.min_value:
            continue
        ratio = total_out / total_in if total_in else 0.0
        if not (0.85 <= ratio <= 1.15):
            continue
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R04",
                weight=float(RULES["R04"]["weight"]),
                evidence=(
                    f"流入 {total_in:.4f} -> 流出 {total_out:.4f} {cfg.asset}"
                    f"（留存比 {ratio:.2f}），{graph.in_degree(addr)} 进 / {graph.out_degree(addr)} 出"
                ),
                metrics={
                    "in_value": round(total_in, 6),
                    "out_value": round(total_out, 6),
                    "forward_ratio": round(ratio, 4),
                    "in_degree": graph.in_degree(addr),
                    "out_degree": graph.out_degree(addr),
                },
            )
        )
    return hits


def rule_peel_chain(graph: AddressGraph, cfg: DatasetConfig, max_hops: int = 6) -> List[Hit]:
    """
    R05 剥洋葱链：每跳把主体金额转给新地址、同时留一笔小额在自己手里。
    只从「出度 2~20 且金额够大」的地址起手，避免在全图上做指数级搜索。
    """
    hits: List[Hit] = []
    for addr in graph.nodes:
        out_deg = graph.out_degree(addr)
        if out_deg < 2 or out_deg > 20:
            continue
        if graph.out_value(addr) < cfg.peel_min_amount:
            continue
        chain = graph.peel_chain(addr, max_hops=max_hops)
        if len(chain) < 4:
            continue
        path = " -> ".join([short_addr(addr, 4)] + [short_addr(e.dst, 4) for e in chain])
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R05",
                weight=float(RULES["R05"]["weight"]),
                evidence=f"剥离链 {len(chain)} 跳：{path}，起手 {chain[0].amount:.4f} {cfg.asset}",
                metrics={
                    "chain_hops": len(chain),
                    "start_amount": round(chain[0].amount, 6),
                    "end_amount": round(chain[-1].amount, 6),
                    "decay": round(chain[-1].amount / chain[0].amount, 4) if chain[0].amount else 0.0,
                },
            )
        )
    return hits


def rule_dusting(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """
    R06 粉尘攻击 / 垃圾空投：向大量地址发送极小金额，目的是污染对方交易历史，
    为后续「地址投毒」做铺垫（受害者复制历史地址时就会打给攻击者）。
    """
    hits: List[Hit] = []
    for addr in graph.nodes:
        dust_edges = [e for e in graph.out.get(addr, ()) if 0 < e.amount <= cfg.dust_amount]
        receivers = {e.dst for e in dust_edges}
        if len(dust_edges) < 10 or len(receivers) < 10:
            continue
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R06",
                weight=float(RULES["R06"]["weight"]),
                evidence=(
                    f"{len(dust_edges)} 笔粉尘转账（<= {cfg.dust_amount} {cfg.asset}）"
                    f"覆盖 {len(receivers)} 个地址"
                ),
                metrics={
                    "dust_edges": len(dust_edges),
                    "dust_receivers": len(receivers),
                    "dust_total": round(sum(e.amount for e in dust_edges), 8),
                },
            )
        )
    return hits


def rule_address_poisoning(
    graph: AddressGraph, cfg: DatasetConfig, labels: Dict[str, Dict[str, object]]
) -> List[Hit]:
    """
    R07 地址投毒（address poisoning）：攻击者批量生成「首 4 位 + 尾 4 位」与受害者常用地址
    相同的李鬼地址，再向受害者打粉尘，让受害者从历史记录里复制到假地址。

    判定链路：
      1) 按 (前 4 位 hex, 后 4 位 hex) 分组，组内至少 2 个不同地址；
      2) 组内存在真实地址 R，其交易对手 V（V 曾与 R 有过转账）；
      3) 组内另一个地址 A 向 V 发过粉尘 —— 则 A 是投毒地址。
    这是纯图结构 + 金额阈值的「行为型」规则，不依赖外部黑名单。
    """
    groups: Dict[str, List[str]] = defaultdict(list)
    for addr in graph.nodes:
        if len(addr) == 42 and addr.startswith("0x"):
            groups[addr[2:6] + addr[-4:]].append(addr)

    hits: Dict[str, Hit] = {}
    for key, members in groups.items():
        if len(members) < 2:
            continue
        for legit in members:
            contacts = graph.distinct_predecessors(legit) | graph.distinct_successors(legit)
            if not contacts:
                continue
            for suspect in members:
                if suspect == legit or suspect in labels:
                    continue
                dust_edges = [
                    e
                    for e in graph.out.get(suspect, ())
                    if e.dst in contacts and 0 < e.amount <= cfg.dust_amount
                ]
                if not dust_edges:
                    continue
                victims = sorted({short_addr(e.dst, 4) for e in dust_edges})[:3]
                previous = hits.get(suspect)
                # 同一地址可能命中多个「李鬼组」，只保留粉尘笔数最多的那条，避免重复计分
                if previous is not None and previous.metrics["dust_to_shared_contacts"] >= len(dust_edges):
                    continue
                hits[suspect] = Hit(
                    dataset=cfg.name,
                    address=suspect,
                    rule_id="R07",
                    weight=float(RULES["R07"]["weight"]),
                    evidence=(
                        f"与 {short_addr(legit, 4)} 共享地址指纹 {key}，"
                        f"向其 {len(dust_edges)} 个交易对手投递粉尘（如 {', '.join(victims)}）"
                    ),
                    metrics={
                        "collision_group_size": len(members),
                        "dust_to_shared_contacts": len(dust_edges),
                    },
                )
    return list(hits.values())


def _is_round_amount(value: float, units: Sequence[float], tolerance: float = 0.02) -> Optional[float]:
    """判断金额是否「接近整数单位」（误差 tolerance 内），返回命中的单位。"""
    for unit in units:
        if value < unit:
            continue
        nearest = round(value / unit) * unit
        if nearest > 0 and abs(value - nearest) / nearest <= tolerance:
            return unit
    return None


def rule_round_amount(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """
    R08 整数 / 临界金额：反复使用整千整万，或刻意卡在申报阈值下方（structuring / smurfing）。
    这类金额分布是「人为选择」的痕迹，正常交易金额通常带零头。
    """
    hits: List[Hit] = []
    low, high = cfg.threshold_band if cfg.threshold_band else (None, None)

    for addr in graph.nodes:
        outs = graph.out.get(addr, ())
        if len(outs) < 3 or graph.out_value(addr) < cfg.min_value:
            continue

        round_edges: List[Edge] = []
        band_edges: List[Edge] = []
        for edge in outs:
            if edge.amount <= 0:
                continue
            if _is_round_amount(edge.amount, cfg.round_units) is not None:
                round_edges.append(edge)
            if low is not None and high is not None and low <= edge.amount < high:
                band_edges.append(edge)

        receivers = {e.dst for e in round_edges + band_edges}
        if len(receivers) < 3 or len(round_edges) + len(band_edges) < 3:
            continue

        samples = ", ".join(f"{e.amount:.2f}" for e in (round_edges + band_edges)[:3])
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R08",
                weight=float(RULES["R08"]["weight"]),
                evidence=(
                    f"{len(round_edges)} 笔整数金额 / {len(band_edges)} 笔临界区间金额，"
                    f"收款方 {len(receivers)} 个（如 {samples} {cfg.asset}）"
                ),
                metrics={
                    "round_edges": len(round_edges),
                    "threshold_band_edges": len(band_edges),
                    "distinct_receivers": len(receivers),
                },
            )
        )
    return hits


def rule_self_transfer(graph: AddressGraph, cfg: DatasetConfig) -> List[Hit]:
    """R09 自转：同一地址多次转给自己，常见于刷量、投毒掩护、脚本测试。"""
    hits: List[Hit] = []
    for addr in graph.nodes:
        loops = [e for e in graph.out.get(addr, ()) if e.is_self_loop]
        if len(loops) < 2:
            continue
        total = sum(e.amount for e in loops)
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R09",
                weight=float(RULES["R09"]["weight"]),
                evidence=f"{len(loops)} 笔自转，合计 {total:.6f} {cfg.asset}",
                metrics={"self_transfers": len(loops), "self_value": round(total, 8)},
            )
        )
    return hits


def rule_block_burst(graph: AddressGraph, cfg: DatasetConfig, min_burst: int = 3) -> List[Hit]:
    """
    R10 同区块批量出账：同一区块里连续向多个地址打款，是脚本化批量分发的强信号。
    需要 CSV 里有 block_number（原生转账未导出区块号时该规则自动跳过）。
    """
    hits: List[Hit] = []
    for addr in graph.nodes:
        per_block: Dict[int, List[Edge]] = defaultdict(list)
        for edge in graph.out.get(addr, ()):
            if edge.block is not None:
                per_block[edge.block].append(edge)
        bursts = {
            block: edges
            for block, edges in per_block.items()
            if len({e.dst for e in edges}) >= min_burst
        }
        if not bursts:
            continue
        block, edges = max(bursts.items(), key=lambda kv: len(kv[1]))
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R10",
                weight=float(RULES["R10"]["weight"]),
                evidence=(
                    f"区块 {block} 内 {len(edges)} 笔出账覆盖 {len({e.dst for e in edges})} 个地址"
                    f"（共 {len(bursts)} 个突发区块）"
                ),
                metrics={
                    "burst_blocks": len(bursts),
                    "max_edges_in_block": len(edges),
                    "max_distinct_receivers": len({e.dst for e in edges}),
                },
            )
        )
    return hits


def rule_hub_centrality(
    graph: AddressGraph, cfg: DatasetConfig, pagerank: Dict[str, float], top_pct: float = 0.995
) -> List[Hit]:
    """
    R11 高中心度枢纽：PageRank 排在前 0.5% 且度数不低的节点。
    注意这是「中性」信号——交易所热钱包 / 路由合约天然高中心度，
    所以权重只有 8 分，并且会被 R12 的负权重标签抵消。
    """
    hits: List[Hit] = []
    if not pagerank:
        return hits
    threshold = percentile_threshold(list(pagerank.values()), top_pct)
    for addr, score in pagerank.items():
        if score < threshold or graph.degree(addr) < 20:
            continue
        hits.append(
            Hit(
                dataset=cfg.name,
                address=addr,
                rule_id="R11",
                weight=float(RULES["R11"]["weight"]),
                evidence=f"PageRank {score:.6f}（前 {(1 - top_pct) * 100:.1f}%），总度数 {graph.degree(addr)}",
                metrics={"pagerank": round(score, 8), "degree": graph.degree(addr)},
            )
        )
    return hits


def rule_labeled_entity(
    graph: AddressGraph,
    cfg: DatasetConfig,
    labels: Dict[str, Dict[str, object]],
    pagerank: Optional[Dict[str, float]] = None,
    service_weight: float = -10.0,
) -> List[Hit]:
    """
    R12 实体识别：
      1) 外部标签：混币器 +22~24 分、交易所/合约 -8~-15 分（缓解因子）；
      2) 内部启发式服务商识别：扇入>=100 且 扇出>=100 且 PageRank 前 0.5%，
         大概率是交易所热钱包 / 聚合器，给 -10 的缓解权重，压低误报
         （生产环境应换成真实标签；这里只是让「高度数≠可疑」这件事在分数里显式体现）。
    负权重命中同样写入告警表，方便解释「为什么这个高度数地址没被判为可疑」。
    """
    hits: List[Hit] = []
    pr_threshold = 0.0
    if pagerank:
        pr_threshold = percentile_threshold(list(pagerank.values()), 0.995)

    for addr in graph.nodes:
        meta = labels.get(addr)
        if meta:
            weight = float(meta.get("risk_weight", 0) or 0)
            if weight != 0:
                category = str(meta.get("category", "unknown"))
                hits.append(
                    Hit(
                        dataset=cfg.name,
                        address=addr,
                        rule_id="R12",
                        weight=weight,
                        evidence=f"标签「{meta.get('label')}」（{category}），权重 {weight:+.0f}",
                        metrics={"label_weight": weight},
                    )
                )
            continue

        if pagerank and pr_threshold and pagerank.get(addr, 0) >= pr_threshold:
            if graph.in_degree(addr) >= 100 and graph.out_degree(addr) >= 100:
                hits.append(
                    Hit(
                        dataset=cfg.name,
                        address=addr,
                        rule_id="R12",
                        weight=service_weight,
                        evidence=(
                            f"疑似服务商地址（扇入 {graph.in_degree(addr)} / 扇出 {graph.out_degree(addr)}，"
                            f"PageRank 前 0.5%），建议人工确认标签后降权"
                        ),
                        metrics={"service_heuristic": 1.0, "label_weight": service_weight},
                    )
                )
    return hits


# ============================================================
# 4. 引擎：跑规则 -> 打分 -> 输出
# ============================================================


def score_hits(hits: Sequence[Hit], dataset: str) -> List[AddressRisk]:
    """
    把命中按地址聚合成分数：
        score = clip(Σ 规则权重 + 组合加成, 0, 100)
    组合加成：命中 >= 3 条不同规则时 +5，因为「同时出现多种可疑模式」的账户
    比单条规则命中的账户更值得人工介入（这也是行业里常用的 risk stack 做法）。
    """
    by_addr: Dict[str, List[Hit]] = defaultdict(list)
    seen: Set[Tuple[str, str]] = set()
    for hit in hits:
        key = (hit.address, hit.rule_id)
        if key in seen:  # 同一条规则对同一地址只计一次分，避免重复计分放大风险
            continue
        seen.add(key)
        by_addr[hit.address].append(hit)

    results: List[AddressRisk] = []
    for addr, addr_hits in by_addr.items():
        base = sum(h.weight for h in addr_hits)
        bonus = 5.0 if len({h.rule_id for h in addr_hits}) >= 3 else 0.0
        score = max(0.0, min(100.0, base + bonus))
        if score <= 0:
            continue
        level, level_cn = risk_level(score)
        # 权重高的规则排前面，便于报告里「先看最狠的那条」
        addr_hits.sort(key=lambda h: -h.weight)
        results.append(
            AddressRisk(
                dataset=dataset,
                address=addr,
                score=round(score, 1),
                level=level,
                level_cn=level_cn,
                hits=addr_hits,
            )
        )

    results.sort(key=lambda r: (-r.score, r.address))
    return results


def run_dataset(cfg: DatasetConfig, data_dir: str, labels: Dict[str, Dict[str, object]]) -> Tuple[List[Hit], Dict[str, object]]:
    """跑一个数据集的全部规则，返回 (hits, 统计信息)。"""
    path = next((os.path.join(data_dir, c) for c in cfg.candidates if os.path.exists(os.path.join(data_dir, c))), None)
    if path is None:
        raise FileNotFoundError(f"[{cfg.name}] 找不到数据文件，试过: {cfg.candidates}")

    graph = AddressGraph.from_csv(path, asset=cfg.asset, decimals=cfg.decimals)
    pagerank = graph.pagerank()

    hits: List[Hit] = []
    hits += rule_fan_out(graph, cfg)
    hits += rule_fan_in(graph, cfg)
    hits += rule_split_merge(graph, cfg)
    hits += rule_pass_through(graph, cfg)
    hits += rule_peel_chain(graph, cfg)
    hits += rule_dusting(graph, cfg)
    hits += rule_address_poisoning(graph, cfg, labels)
    hits += rule_round_amount(graph, cfg)
    hits += rule_self_transfer(graph, cfg)
    hits += rule_block_burst(graph, cfg)
    hits += rule_hub_centrality(graph, cfg, pagerank)
    hits += rule_labeled_entity(graph, cfg, labels, pagerank)

    stats = graph.stats()
    stats.update(
        {
            "source_file": os.path.basename(path),
            "rule_hit_counts": dict(sorted(Counter(h.rule_id for h in hits).items())),
            "hit_edges": len(hits),
            "scored_addresses": len({h.address for h in hits}),
        }
    )
    return hits, stats


# ---------- 输出 ----------

ALERT_FIELDS = [
    "dataset",
    "address",
    "risk_score",
    "risk_level",
    "risk_level_cn",
    "rule_ids",
    "rule_count",
    "evidence",
    "metrics_json",
]


def write_alerts(risks: Sequence[AddressRisk], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ALERT_FIELDS)
        writer.writeheader()
        for risk in risks:
            writer.writerow(
                {
                    "dataset": risk.dataset,
                    "address": risk.address,
                    "risk_score": risk.score,
                    "risk_level": risk.level,
                    "risk_level_cn": risk.level_cn,
                    "rule_ids": "|".join(risk.rule_ids),
                    "rule_count": len(risk.rule_ids),
                    "evidence": risk.evidence,
                    "metrics_json": json.dumps(risk.metrics_flat(), ensure_ascii=False),
                }
            )


def write_risk_scores(risks: Sequence[AddressRisk], path: str) -> None:
    """地址级风险分，表头刻意写成可与 Cypher LOAD CSV 对齐的形式。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["dataset", "address", "riskScore", "riskLevel", "rules"])
        for risk in risks:
            writer.writerow([risk.dataset, risk.address, risk.score, risk.level, "|".join(risk.rule_ids)])


def render_case_report(
    risks_by_dataset: Dict[str, List[AddressRisk]],
    stats_by_dataset: Dict[str, Dict[str, object]],
    top: int = 10,
) -> str:
    """生成人类可读的 Markdown 案例报告（详情页 / 面试讲解时直接用）。"""
    lines: List[str] = []
    lines.append("# AML 可疑地址案例报告（自动生成）\n")
    lines.append("> 由 `aml_rule_engine.py` 生成；分数 = Σ 规则权重 + 组合加成，满分为 100。")
    lines.append("> 所有结论都附带 evidence，请结合 KYC / 业务背景人工复核后再处置。\n")

    for dataset, risks in risks_by_dataset.items():
        stats = stats_by_dataset.get(dataset, {})
        lines.append(f"## 数据集 {dataset}\n")
        lines.append(
            f"- 数据源：`{stats.get('source_file')}`，"
            f"{stats.get('nodes')} 个地址 / {stats.get('edges')} 条转账，"
            f"自转 {stats.get('self_loops')} 笔，中位度数 {stats.get('median_degree')}，"
            f"最大度数 {stats.get('max_degree')}"
        )
        counts = stats.get("rule_hit_counts", {})
        if counts:
            lines.append("- 规则命中分布：" + "，".join(f"{k}={v}" for k, v in counts.items()))
        lines.append(f"- 打分地址数：{stats.get('scored_addresses')}\n")

        if not risks:
            lines.append("本次运行没有地址达到告警阈值。\n")
            continue

        levels = Counter(r.level for r in risks)
        lines.append(
            "分等级："
            + "，".join(f"{level}={levels.get(level, 0)}" for level in ("critical", "high", "medium", "low"))
            + "\n"
        )

        lines.append("### Top 案例\n")
        lines.append("| # | 地址 | 分数 | 等级 | 命中规则 | 关键证据 |")
        lines.append("| :---: | --- | :---: | :---: | --- | --- |")
        for i, risk in enumerate(risks[:top], start=1):
            top_hit = risk.hits[0]
            evidence = top_hit.evidence.replace("|", "/")
            lines.append(
                f"| {i} | `{risk.address}` | {risk.score} | {risk.level_cn} | "
                f"{', '.join(risk.rule_ids)} | {top_hit.rule_id} · {evidence} |"
            )
        lines.append("")

        top_case = risks[0]
        lines.append("### 建议的下一步（以 Top1 为例）\n")
        lines.append("```cypher")
        lines.append("// 1) 拉出该地址 2 跳内的资金网络，人工看结构")
        lines.append(
            f"MATCH path = (a:Address {{address: '{top_case.address}'}})-[:TRANSFER_TO*1..2]-(b:Address)\n"
            "RETURN path LIMIT 200;"
        )
        lines.append("")
        lines.append("// 2) 查它和标签地址（混币器 / 交易所）是否有直接或间接接触")
        lines.append(f"MATCH (a:Address {{address: '{top_case.address}'}})-[r:TRANSFER_TO*1..3]-(b:Address)")
        lines.append("WHERE b.label IS NOT NULL")
        lines.append("RETURN b.label, length(r) AS hops, r;")
        lines.append("```\n")

        lines.append("### 全部命中明细（前 30 条）\n")
        for risk in risks[:30]:
            lines.append(
                f"<details><summary><code>{risk.address}</code> · {risk.score} 分（{risk.level_cn}）</summary>\n"
            )
            for hit in risk.hits:
                meta = RULES.get(hit.rule_id, {})
                lines.append(f"- **{hit.rule_id} {meta.get('name_cn', '')}**（权重 {hit.weight:+.0f}）：{hit.evidence}")
            lines.append("\n</details>\n")

    return "\n".join(lines)


def write_neo4j_scores(risks: Sequence[AddressRisk], uri: str, user: str, password: str) -> None:
    """
    把风险分写回 Neo4j：补齐 `(a:Address {address})` 上的 riskScore / riskLevel / riskRules，
    之后所有 Cypher 都能直接按分数过滤（图探索页面里特别好用）。
    """
    try:
        from neo4j import GraphDatabase  # 延迟导入：没装 neo4j 也不影响本地跑规则
    except ImportError:
        raise RuntimeError("未安装 neo4j 官方驱动，请先 `pip install neo4j` 或去掉 --write-neo4j")

    query = """
    UNWIND $rows AS row
    MATCH (a:Address {address: row.address})
    SET a.riskScore = row.score,
        a.riskLevel = row.level,
        a.riskRules = row.rules,
        a.riskDataset = row.dataset
    RETURN count(a) AS updated
    """
    rows = [
        {
            "address": r.address,
            "score": r.score,
            "level": r.level,
            "rules": r.rule_ids,
            "dataset": r.dataset,
        }
        for r in risks
    ]
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            updated = session.run(query, rows=rows).single()["updated"]
            print(f"✅ 已回写 {updated} 个地址的风险分到 Neo4j")
    finally:
        driver.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="链上 AML 规则引擎 + 风险评分（v2）")
    parser.add_argument("--data-dir", default=".", help="CSV 所在目录")
    parser.add_argument("--out-dir", default=".", help="输出目录")
    parser.add_argument(
        "--datasets",
        default="ETH,USDT",
        help="要跑的数据集，逗号分隔（可选：ETH / USDT）",
    )
    parser.add_argument("--labels", default="aml_labels.json", help="标签库 JSON 路径")
    parser.add_argument("--top", type=int, default=10, help="报告展示的案例数量")
    parser.add_argument("--min-score", type=float, default=0.0, help="只保留 >= 该分数的地址")
    parser.add_argument("--write-neo4j", action="store_true", help="把风险分写回 Neo4j")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD", ""))
    args = parser.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    labels_path = args.labels if os.path.isabs(args.labels) else os.path.join(args.data_dir, args.labels)
    labels = load_labels(labels_path)
    wanted = {d.strip().upper() for d in args.datasets.split(",") if d.strip()}

    risks_by_dataset: Dict[str, List[AddressRisk]] = {}
    stats_by_dataset: Dict[str, Dict[str, object]] = {}
    all_risks: List[AddressRisk] = []

    for cfg in DEFAULT_DATASETS:
        if cfg.name not in wanted:
            continue
        print(f"\n=== 数据集 {cfg.name} ===")
        hits, stats = run_dataset(cfg, args.data_dir, labels)
        scored = score_hits(hits, cfg.name)
        stats["scored_addresses"] = len(scored)  # 去重后真正被打分的地址数
        risks = scored
        if args.min_score > 0:
            risks = [r for r in risks if r.score >= args.min_score]
        risks_by_dataset[cfg.name] = risks
        stats_by_dataset[cfg.name] = stats
        all_risks.extend(risks)

        print(
            f"  地址 {stats['nodes']} 个 / 转账 {stats['edges']} 条；"
            f"规则命中 {len(hits)} 次，覆盖 {len(risks)} 个地址"
        )
        levels = Counter(r.level for r in risks)
        print(
            "  风险分布："
            + "，".join(f"{level}={levels.get(level, 0)}" for level in ("critical", "high", "medium", "low"))
        )
        print("  Top 5：")
        for risk in risks[:5]:
            print(f"    {risk.score:5.1f} [{risk.level_cn}] {risk.address}  {','.join(risk.rule_ids)}")

    all_risks.sort(key=lambda r: (-r.score, r.address))
    alerts_path = os.path.join(args.out_dir, "aml_alerts.csv")
    scores_path = os.path.join(args.out_dir, "aml_risk_scores.csv")
    summary_path = os.path.join(args.out_dir, "aml_summary.json")
    report_path = os.path.join(args.out_dir, "aml_case_report.md")

    write_alerts(all_risks, alerts_path)
    write_risk_scores(all_risks, scores_path)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_by": "aml_rule_engine.py",
                "rule_catalog": RULES,
                "dataset_stats": stats_by_dataset,
                "alerts": len(all_risks),
                "level_distribution": dict(Counter(r.level for r in all_risks)),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(render_case_report(risks_by_dataset, stats_by_dataset, top=args.top))

    print(f"\n✅ 输出：{alerts_path}\n✅ 输出：{scores_path}\n✅ 输出：{summary_path}\n✅ 输出：{report_path}")

    if args.write_neo4j:
        if not args.neo4j_password:
            raise SystemExit("使用 --write-neo4j 时请提供 --neo4j-password 或环境变量 NEO4J_PASSWORD")
        write_neo4j_scores(all_risks, args.neo4j_uri, args.neo4j_user, args.neo4j_password)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
