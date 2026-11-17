#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_uniswap_reserves.py · 导出 Uniswap V2 池子储备金（v2 新增）

为什么 v1 的 fetch_uniswap_rates.py 不够用：
    v1 只导出「汇率」（rate = reserve1/reserve0），汇率是线性量，无法回答
    「这笔套利最多能塞多大仓位」「塞 10 万美元进去会滑点多少」。
    AMM 的价格冲击是 1/x 型非线性，必须拿到 reserve0/reserve1 才能算。

输出 `pool_reserves.csv`（arbitrage_optimizer.py 的输入）：
    pair_address,pair_name,token0,token1,symbol0,symbol1,decimals0,decimals1,
    reserve0,reserve1,block_number

用法：
    cp .env.example .env          # 填 RPC_URL（用 v1 的 config_loader 读）
    python3 fetch_uniswap_reserves.py
    python3 fetch_uniswap_reserves.py --out pool_reserves.csv --sleep 0.3

注意：reserve0/reserve1 写的是「人类可读单位」（已按 decimals 归一化），
      下游 AMM 公式统一用可读单位计算，避免 1e18 / 1e6 混算导致溢出或精度问题。
      脚本会把链上 symbol 与清单名称比对，不一致会告警（防止再抄错池子地址）。
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from typing import Dict, List, Optional

# 与 fetch_uniswap_rates.py 共用同一份核心池子清单，保证 v1 / v2 口径一致。
# 另外脚本会把链上读到的 symbol 和这里的 name 做一次比对，不一致会打 ⚠️ 提示
# （v1 的踩坑记录⑤就是这么发现池子地址抄错的：地址能不能读不重要，读出来是不是那个币才重要）。
CORE_PAIRS: List[Dict[str, str]] = [
    {"name": "WETH-USDC", "address": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"},
    {"name": "WETH-USDT", "address": "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852"},
    {"name": "WETH-DAI", "address": "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"},
    {"name": "WETH-WBTC", "address": "0xBb2b8038a1640196FbE3e38816F3e67Cba72D940"},
    {"name": "USDC-USDT", "address": "0x3041CbD36888bECc7bbCBc0045E3B1f144466f5f"},
    {"name": "USDC-DAI", "address": "0xAE461cA67B15dc8dc81CE7615e0320dA1A9aB8D5"},
    {"name": "USDT-DAI", "address": "0xeAF1Ac8E89EA0aE13E0f03634A4FF23502527024"},  # 名称不一致时会告警，见 verify_pair_name
    {"name": "WETH-UNI", "address": "0xd3D2E2692501A5c9Ca623199D03426eC77F033f7"},
    {"name": "WETH-LINK", "address": "0x6b5A2219D3DF748a1C3Af2E2B7C16358dF2b636b"},  # 名称不一致时会告警
    {"name": "WETH-AAVE", "address": "0x6C8c6b02E7b6be4F1D2C94aeEa5d3693bbF14E7E"},  # 名称不一致时会告警
]

PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"},
        ],
        "type": "function",
    },
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"},
]

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
]


def fetch_pair(w3, pair_address: str, meta_cache: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    """读取单个池子的储备金与代币元数据（symbol / decimals 带缓存，避免重复 RPC）。"""
    pair = w3.eth.contract(address=w3.to_checksum_address(pair_address), abi=PAIR_ABI)
    reserve0_raw, reserve1_raw, _ = pair.functions.getReserves().call()
    token0 = pair.functions.token0().call()
    token1 = pair.functions.token1().call()

    for token in (token0, token1):
        if token in meta_cache:
            continue
        contract = w3.eth.contract(address=w3.to_checksum_address(token), abi=ERC20_ABI)
        try:
            meta_cache[token] = {
                "symbol": contract.functions.symbol().call(),
                "decimals": int(contract.functions.decimals().call()),
            }
        except Exception:  # 非标准 ERC-20（代理 / 老币）兜底
            meta_cache[token] = {"symbol": token[:8], "decimals": 18}

    meta0, meta1 = meta_cache[token0], meta_cache[token1]
    decimals0, decimals1 = int(meta0["decimals"]), int(meta1["decimals"])
    return {
        "pair_address": pair_address,
        "token0": token0,
        "token1": token1,
        "symbol0": meta0["symbol"],
        "symbol1": meta1["symbol"],
        "decimals0": decimals0,
        "decimals1": decimals1,
        "reserve0": reserve0_raw / (10**decimals0),
        "reserve1": reserve1_raw / (10**decimals1),
    }


def verify_pair_name(name: str, symbol0: str, symbol1: str) -> Optional[str]:
    """
    校验「清单里的名字」和「链上读到的 symbol」是否一致。
    name 形如 "WETH-USDC"，链上可能返回 ("USDC","WETH")（顺序取决于 token0/token1），
    所以按集合比较，忽略顺序。不一致时返回提示字符串（不中断流程，只报警）。
    """
    expected = {part.strip().upper() for part in name.split("-") if part.strip()}
    actual = {str(symbol0).strip().upper(), str(symbol1).strip().upper()}
    if expected and expected != actual:
        return f"名称 {name} 与链上 symbol {symbol0}/{symbol1} 不一致，请核对池子地址"
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="导出 Uniswap V2 核心池储备金")
    parser.add_argument("--rpc-url", default="", help="以太坊 RPC（默认读 .env / config.yaml / 环境变量）")
    parser.add_argument("--out", default="pool_reserves.csv", help="输出 CSV 路径")
    parser.add_argument("--sleep", type=float, default=None, help="每个池子之间的间隔秒数，避免 RPC 限流")
    args = parser.parse_args(argv)

    # 配置优先级：命令行 > config_loader（.env + config.yaml）> 环境变量
    rpc_url = args.rpc_url or ""
    sleep_seconds = args.sleep
    if not rpc_url or sleep_seconds is None:
        try:
            from config_loader import load_config, require_rpc  # v1 已有的统一配置入口

            cfg = load_config()
            if not rpc_url:
                rpc_url = require_rpc(cfg)
            if sleep_seconds is None:
                sleep_seconds = float(cfg.get("uniswap", {}).get("sleep_seconds", 0.2))
        except SystemExit:
            raise
        except Exception:
            rpc_url = rpc_url or os.environ.get("RPC_URL", "")
            if sleep_seconds is None:
                sleep_seconds = 0.2

    if not rpc_url:
        raise SystemExit("请提供 --rpc-url、配置 .env 里的 RPC_URL，或设置环境变量（勿把真实 API Key 写进仓库）")
    if sleep_seconds is None:
        sleep_seconds = 0.2

    try:
        from web3 import Web3
    except ImportError:
        raise SystemExit("需要 web3：pip install -r requirements.txt")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise SystemExit("❌ RPC 连接失败，请检查 RPC_URL / 代理设置")

    block_number = w3.eth.block_number
    print(f"✅ 连接成功，当前区块 {block_number}")

    meta_cache: Dict[str, Dict[str, object]] = {}
    rows: List[Dict[str, object]] = []
    for pair in CORE_PAIRS:
        try:
            row = fetch_pair(w3, pair["address"], meta_cache)
            row["pair_name"] = pair["name"]
            row["block_number"] = block_number
            rows.append(row)
            print(
                f"✅ {pair['name']:<10} {row['symbol0']}/{row['symbol1']}: "
                f"{row['reserve0']:,.4f} / {row['reserve1']:,.4f}"
            )
            warning = verify_pair_name(pair["name"], row["symbol0"], row["symbol1"])
            if warning:
                print(f"   ⚠️ {warning}")
        except Exception as exc:
            print(f"⚠️ {pair['name']} 读取失败：{exc}")
        time.sleep(sleep_seconds)

    if not rows:
        print("❌ 没有成功读取任何池子")
        return 1

    fieldnames = [
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
        "block_number",
    ]
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})

    print(f"\n✅ 已写出 {args.out}（{len(rows)} 个池子，区块 {block_number}）")
    print("下一步：python3 arbitrage_optimizer.py --reserves pool_reserves.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
