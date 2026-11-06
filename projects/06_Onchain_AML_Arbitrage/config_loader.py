# -*- coding: utf-8 -*-
"""配置和日志的公共入口。

之前每个脚本开头都有一段重复的 RPC_URL / PASSWORD / print，改一个 key 要改五遍，
而且 Infura 的 key 明文躺在代码里。现在统一从 config.yaml + .env 读。
"""

import logging
import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent


def setup_logging(name, level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def load_config(path=None):
    cfg_path = Path(path or os.getenv("ONCHAIN_CONFIG", BASE_DIR / "config.yaml"))
    if not cfg_path.exists():
        cfg_path = BASE_DIR / "config.example.yaml"

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    try:  # 没装 python-dotenv 也能跑，只是环境变量得自己 export
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    cfg["rpc_url"] = os.getenv("RPC_URL", cfg.get("rpc_url", ""))
    neo = cfg.setdefault("neo4j", {})
    neo["uri"] = os.getenv("NEO4J_URI", neo.get("uri", "bolt://localhost:7687"))
    neo["user"] = os.getenv("NEO4J_USER", neo.get("user", "neo4j"))
    neo["password"] = os.getenv("NEO4J_PASSWORD", neo.get("password", ""))
    return cfg


def require_rpc(cfg):
    """RPC 没配就直接退出，别等 requests 报一堆看不懂的错。"""
    if not cfg.get("rpc_url") or "YOUR_PROJECT_ID" in cfg["rpc_url"]:
        raise SystemExit("RPC_URL 没配，先在 .env 里填一个（Infura / Alchemy 免费版就行）")
    return cfg["rpc_url"]
