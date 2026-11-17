#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aml_graph.py · 链上资金流图的基础数据结构与图算法（v2 新增）

为什么不用 networkx / pandas：
1. 本项目的数据规模（5.6 万地址 / 7.4 万条转账）用纯 Python 的字典邻接表完全够用，
   PageRank 一轮 7 万次边遍历，全图 60 轮也在秒级；
2. 不引入额外依赖，保证 `git clone` 之后 `python3 xxx.py` 就能直接复现（无 pandas 也能跑）；
3. 图算法（PageRank / k-core / Brandes 介数中心性）自己实现一遍，
   面试时可以把「每一步在算什么」讲清楚，而不是调用一个黑盒。

对外提供：
    load_edges(path, asset, decimals) -> AddressGraph     # 读 Neo4j 关系 CSV
    AddressGraph                                          # 邻接表 + 图算法
    edge_rows(path)                                       # 轻量流式读取

数据格式假设（与 unify_csv_format.py 输出一致）：
    :START_ID(Address), :END_ID(Address), value:string|value:long, hash, block_number:int
    原生转账 value 单位是 wei（decimals=18），USDT 的 value 是代币最小单位（decimals=6）。
"""

from __future__ import annotations

import csv
import heapq
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


# ============================================================
# 1. 边（一条转账 = 一条有向边）
# ============================================================


@dataclass(frozen=True)
class Edge:
    """一条转账关系。amount 已归一化（ETH / USDT 等人类可读单位），不是 wei。"""

    src: str
    dst: str
    amount: float
    raw_value: int
    block: Optional[int]
    tx_hash: str

    @property
    def is_self_loop(self) -> bool:
        return self.src == self.dst


# ============================================================
# 2. CSV 读取
# ============================================================


def _detect_columns(header: Sequence[str]) -> Dict[str, int]:
    """按表头自动定位列，兼容 `value:string` / `value:long` / 裸 `value` 三种写法。"""
    idx: Dict[str, int] = {}
    for i, raw in enumerate(header):
        h = (raw or "").strip()
        if h.startswith(":START_ID"):
            idx["src"] = i
        elif h.startswith(":END_ID"):
            idx["dst"] = i
        elif h.startswith("value") or h == "amount":
            idx["value"] = i
        elif h.startswith("hash") or h.startswith("tx_hash"):
            idx["hash"] = i
        elif h.startswith("block_number") or h == "block":
            idx["block"] = i
    missing = {"src", "dst", "value"} - set(idx)
    if missing:
        raise ValueError(f"CSV 表头缺少列: {sorted(missing)}，实际表头: {list(header)}")
    return idx


def _to_int(text: str) -> int:
    """value 列可能是整数串、浮点串或空串，统一转 int（金额用最小单位整数最安全）。"""
    text = (text or "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return 0


def edge_rows(
    path: str,
    asset: str = "ETH",
    decimals: int = 18,
    drop_zero_address: bool = True,
    encoding: str = "utf-8",
) -> Iterator[Edge]:
    """
    流式读取关系 CSV，逐条 yield Edge（大文件也不会一次性吃满内存）。

    drop_zero_address=True 时过滤 0x000...000：原生转账里这是合约创建 / 销毁，
    在资金追踪里没有意义，留着只会污染度分布。
    """
    scale = float(10**decimals)
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return
        idx = _detect_columns(header)

        for row in reader:
            if not row or len(row) <= max(idx["src"], idx["dst"], idx["value"]):
                continue
            src = (row[idx["src"]] or "").strip().lower()
            dst = (row[idx["dst"]] or "").strip().lower()
            if not src or not dst:
                continue
            if drop_zero_address and ZERO_ADDRESS in (src, dst):
                continue

            raw = _to_int(row[idx["value"]])
            block: Optional[int] = None
            if "block" in idx and idx["block"] < len(row):
                text = (row[idx["block"]] or "").strip()
                block = int(text) if text.isdigit() else None
            tx_hash = ""
            if "hash" in idx and idx["hash"] < len(row):
                tx_hash = (row[idx["hash"]] or "").strip()

            yield Edge(
                src=src,
                dst=dst,
                amount=raw / scale,
                raw_value=raw,
                block=block,
                tx_hash=tx_hash,
            )


# ============================================================
# 3. 图结构 + 图算法
# ============================================================


def load_edges(
    path: str,
    asset: str = "ETH",
    decimals: int = 18,
    **kwargs,
) -> List[Edge]:
    """一次性把关系 CSV 读成列表（小文件用；大文件建议用 edge_rows 流式读）。"""
    return list(edge_rows(path, asset=asset, decimals=decimals, **kwargs))


class AddressGraph:
    """
    地址资金流有向图。

    邻接表同时保存出边与入边，因为「拆分」规则看的是出度、「归集」规则看的是入度，
    双份索引换来 O(1) 的方向查询，内存代价可以接受。
    """

    def __init__(self, name: str = "graph", asset: str = "ETH"):
        self.name = name
        self.asset = asset
        self.out: Dict[str, List[Edge]] = defaultdict(list)
        self.inn: Dict[str, List[Edge]] = defaultdict(list)
        self.nodes: Set[str] = set()
        self.edge_count = 0
        self.self_loop_count = 0
        self.total_value = 0.0
        self._pagerank: Optional[Dict[str, float]] = None

    # ---------- 构建 ----------

    def add_edge(self, edge: Edge) -> None:
        self.out[edge.src].append(edge)
        self.inn[edge.dst].append(edge)
        self.nodes.add(edge.src)
        self.nodes.add(edge.dst)
        self.edge_count += 1
        self.total_value += edge.amount
        if edge.is_self_loop:
            self.self_loop_count += 1

    @classmethod
    def from_csv(cls, path: str, asset: str = "ETH", decimals: int = 18, **kwargs) -> "AddressGraph":
        graph = cls(name=path, asset=asset)
        for edge in edge_rows(path, asset=asset, decimals=decimals, **kwargs):
            graph.add_edge(edge)
        return graph

    # ---------- 基础查询 ----------

    def __len__(self) -> int:
        return len(self.nodes)

    def out_degree(self, addr: str) -> int:
        return len(self.out.get(addr, ()))

    def in_degree(self, addr: str) -> int:
        return len(self.inn.get(addr, ()))

    def degree(self, addr: str) -> int:
        return self.out_degree(addr) + self.in_degree(addr)

    def distinct_successors(self, addr: str) -> Set[str]:
        return {e.dst for e in self.out.get(addr, ())}

    def distinct_predecessors(self, addr: str) -> Set[str]:
        return {e.src for e in self.inn.get(addr, ())}

    def out_value(self, addr: str) -> float:
        return math.fsum(e.amount for e in self.out.get(addr, ()))

    def in_value(self, addr: str) -> float:
        return math.fsum(e.amount for e in self.inn.get(addr, ()))

    def amounts(self, addr: str, direction: str = "out") -> List[float]:
        edges = self.out.get(addr, ()) if direction == "out" else self.inn.get(addr, ())
        return [e.amount for e in edges]

    def mean_out_amount(self, addr: str) -> float:
        edges = self.out.get(addr, ())
        return (self.out_value(addr) / len(edges)) if edges else 0.0

    # ---------- 分布类指标（AML 规则直接消费） ----------

    def value_entropy(self, addr: str, direction: str = "out") -> float:
        """
        出账金额的归一化香农熵（0~1）。
        拆分转账的典型特征是「很多笔金额都差不多」，熵会接近 1；
        正常业务账户多是一两笔大额 + 长尾小额，熵明显更低。
        """
        values = [v for v in self.amounts(addr, direction) if v > 0]
        if len(values) < 2:
            return 0.0
        total = math.fsum(values)
        probs = [v / total if total else 0.0 for v in values]
        entropy = -math.fsum(p * math.log(p + 1e-12) for p in probs)
        return entropy / math.log(len(probs))

    def gini(self, values: Sequence[float]) -> float:
        """基尼系数：金额分布的不均等程度（0 = 完全平均，1 = 极端集中）。"""
        vals = sorted(v for v in values if v >= 0)
        n = len(vals)
        total = math.fsum(vals)
        if n == 0 or total == 0:
            return 0.0
        cum = math.fsum(i * v for i, v in enumerate(vals, start=1))
        return (2 * cum) / (n * total) - (n + 1) / n

    # ---------- PageRank ----------

    def pagerank(self, damping: float = 0.85, iterations: int = 60, tol: float = 1e-10) -> Dict[str, float]:
        """
        有向无权 PageRank（多重边按多条处理，符合「转得越多越重要」的直觉）。
        用途：定位资金网络的枢纽节点（交易所热钱包、混币器中转地址、跑分平台归集户）。
        """
        if self._pagerank is not None:
            return self._pagerank

        n = len(self.nodes)
        if n == 0:
            return {}
        rank = {v: 1.0 / n for v in self.nodes}
        out_deg = {v: len(self.out.get(v, ())) for v in self.nodes}
        dangling = [v for v in self.nodes if out_deg[v] == 0]

        for _ in range(iterations):
            new = {v: (1.0 - damping) / n for v in self.nodes}
            dangling_mass = math.fsum(rank[v] for v in dangling)
            if dangling_mass > 0:
                share = damping * dangling_mass / n
                for v in new:
                    new[v] += share
            for u in self.nodes:
                if out_deg[u] == 0:
                    continue
                share = damping * rank[u] / out_deg[u]
                for edge in self.out[u]:
                    new[edge.dst] += share
            diff = math.fsum(abs(new[v] - rank[v]) for v in self.nodes)
            rank = new
            if diff < tol:
                break

        self._pagerank = rank
        return rank

    # ---------- k-core ----------

    def k_core(self) -> Dict[str, int]:
        """
        无向 k-core 分解，返回每个节点的 core number。
        洗钱网络里外围马甲号大多 core=1~2，核心归集层往往 core>=4，
        先剥掉叶子节点能快速缩小人工排查范围。
        实现用「最小度优先剥离 + 堆惰性删除」，复杂度 O(E log V)。
        """
        adj: Dict[str, Set[str]] = {v: set() for v in self.nodes}
        for u in self.nodes:
            for edge in self.out.get(u, ()):
                if edge.dst != u:
                    adj[u].add(edge.dst)
                    adj[edge.dst].add(u)

        deg = {v: len(adj[v]) for v in adj}
        core = {v: 0 for v in adj}
        remaining = set(adj)
        heap: List[Tuple[int, str]] = [(d, v) for v, d in deg.items()]
        heapq.heapify(heap)

        while heap:
            d, v = heapq.heappop(heap)
            if v not in remaining or d != deg[v]:
                continue
            remaining.discard(v)
            core[v] = d
            for w in adj[v]:
                if w in remaining:
                    deg[w] -= 1
                    heapq.heappush(heap, (deg[w], w))
        return core

    # ---------- 弱连通分量 ----------

    def weak_components(self) -> List[Set[str]]:
        """弱连通分量（忽略方向），把资金网络切成互不相干的小团伙。"""
        adj: Dict[str, Set[str]] = {v: set() for v in self.nodes}
        for u in self.nodes:
            for edge in self.out.get(u, ()):
                if edge.dst != u:
                    adj[u].add(edge.dst)
                    adj[edge.dst].add(u)

        seen: Set[str] = set()
        comps: List[Set[str]] = []
        for start in self.nodes:
            if start in seen:
                continue
            comp: Set[str] = set()
            dq = deque([start])
            seen.add(start)
            while dq:
                v = dq.popleft()
                comp.add(v)
                for w in adj[v]:
                    if w not in seen:
                        seen.add(w)
                        dq.append(w)
            comps.append(comp)
        comps.sort(key=len, reverse=True)
        return comps

    # ---------- Brandes 介数中心性（限定子图） ----------

    def betweenness(
        self,
        subset: Optional[Iterable[str]] = None,
        max_sources: int = 300,
        seed: int = 42,
    ) -> Dict[str, float]:
        """
        介数中心性（Brandes 算法，无权有向）。
        全图 5.6 万节点直接算不现实，所以：
          1) 只在「可疑子图」（度数较高的节点）上算；
          2) 起点数超过 max_sources 时按固定随机种子抽样，再按 n/k 放大。
        这正是 AML 里很实用的一招：资金拆分网络中真正的「过桥地址」就是高介数节点。
        """
        nodes = set(subset) if subset is not None else set(self.nodes)
        if not nodes:
            return {}

        succ: Dict[str, List[str]] = {v: [] for v in nodes}
        for v in nodes:
            for edge in self.out.get(v, ()):
                if edge.dst in nodes:
                    succ[v].append(edge.dst)

        sources = sorted(nodes)
        if len(sources) > max_sources:
            sources = random.Random(seed).sample(sources, max_sources)
            scale = len(nodes) / len(sources)
        else:
            scale = 1.0

        bc = {v: 0.0 for v in nodes}
        for s in sources:
            stack: List[str] = []
            preds: Dict[str, List[str]] = {v: [] for v in nodes}
            sigma = {v: 0.0 for v in nodes}
            dist = {v: -1 for v in nodes}
            sigma[s] = 1.0
            dist[s] = 0
            dq = deque([s])
            while dq:
                v = dq.popleft()
                stack.append(v)
                for w in succ[v]:
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        dq.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)

            delta = {v: 0.0 for v in nodes}
            while stack:
                w = stack.pop()
                if sigma[w] > 0:
                    coeff = (1.0 + delta[w]) / sigma[w]
                    for v in preds[w]:
                        delta[v] += sigma[v] * coeff
                if w != s:
                    bc[w] += delta[w]

        return {v: val * scale for v, val in bc.items()}

    # ---------- 剥离链（peel chain） ----------

    def peel_chain(
        self,
        start: str,
        max_hops: int = 8,
        min_forward_ratio: float = 0.7,
        max_peel_ratio: float = 0.2,
    ) -> List[Edge]:
        """
        「剥洋葱」链路：A 把大额转给 B、自己留一点（peel），B 再把大额转给 C……
        这是最经典的洗钱手法之一（链上反洗钱里叫 peel chain）。

        实现：每跳沿着「金额最大的出边」走，要求
          - 下一跳金额 >= min_forward_ratio * 上一跳金额（主体资金在继续跑）
          - 同节点还存在一条占比 <= max_peel_ratio 的「剥皮边」（留零头 / 抽水）
        注意：这是确定性启发式，不是全路径枚举，因此复杂度 O(hops)。
        """
        chain: List[Edge] = []
        current = start
        visited = {start}
        prev_amount: Optional[float] = None

        for _ in range(max_hops):
            outs = [e for e in self.out.get(current, ()) if e.amount > 0]
            if not outs:
                break
            outs.sort(key=lambda e: e.amount, reverse=True)
            main = outs[0]

            peel_edges = [e for e in outs[1:] if e.amount / main.amount <= max_peel_ratio]
            if not peel_edges:
                break
            if prev_amount is not None and main.amount < prev_amount * min_forward_ratio:
                break

            chain.append(main)
            if main.dst in visited:
                break
            visited.add(main.dst)
            prev_amount = main.amount
            current = main.dst

        return chain

    # ---------- 统计 ----------

    def stats(self) -> Dict[str, float]:
        degrees = sorted(self.degree(v) for v in self.nodes)
        n = len(degrees)
        p95 = degrees[int(0.95 * (n - 1))] if n else 0
        return {
            "asset": self.asset,
            "nodes": n,
            "edges": self.edge_count,
            "self_loops": self.self_loop_count,
            "total_value": round(self.total_value, 6),
            "max_degree": degrees[-1] if n else 0,
            "median_degree": degrees[n // 2] if n else 0,
            "p95_degree": p95,
        }


# ============================================================
# 4. 小工具
# ============================================================


def top_n(scores: Dict[str, float], n: int = 10) -> List[Tuple[str, float]]:
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]


def short_addr(addr: str, keep: int = 6) -> str:
    """0x1234...abcd 形式的缩写，报告里用。"""
    if not addr or len(addr) <= 2 * keep + 2:
        return addr
    return f"{addr[: 2 + keep]}...{addr[-keep:]}"


def percentile_threshold(values: Sequence[float], pct: float = 0.99) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, int(pct * (len(vals) - 1))))
    return vals[idx]


if __name__ == "__main__":  # 快速自检：python3 aml_graph.py transactions_unified.csv ETH 18
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "transactions_unified.csv"
    asset = sys.argv[2] if len(sys.argv) > 2 else "ETH"
    decimals = int(sys.argv[3]) if len(sys.argv) > 3 else 18

    graph = AddressGraph.from_csv(path, asset=asset, decimals=decimals)
    print(graph.stats())
    pr = graph.pagerank()
    print("Top PageRank:", [(short_addr(a), round(s, 8)) for a, s in top_n(pr, 5)])
    out_degree = {v: float(graph.out_degree(v)) for v in graph.nodes}
    print("Top out-degree:", [(short_addr(a), int(d)) for a, d in top_n(out_degree, 5)])
