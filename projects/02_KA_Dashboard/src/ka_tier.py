# -*- coding: utf-8 -*-
"""KA 分层的 Python 版，用来做上线前的沙盘推演。

为什么 SQL 之外还要一个 Python 版：
Grafana 那边吃的是 SQL 落好的快照表，改一次规则要等调度、还得走发布。
但上线前我想「这个阈值改成 300 万会降级多少人」这种事反复试十几次，
在 SQL 里改来改去太慢，所以把打分逻辑摘出来写成本地脚本，口径保持一致。

用法：
    python src/ka_tier.py                       # 用 sample_data 的两个快照做对比
    python src/ka_tier.py --use-db              # 连库取当日快照（需先配 .env）
"""

import argparse
import logging
import os
from pathlib import Path

import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ka")

BASE_DIR = Path(__file__).resolve().parent.parent
TIER_ORDER = ["ka0", "ka1", "ka2", "ka3"]  # ka0 = 普通用户


def load_config(path=None):
    """config.yaml 不存在就用 example；数据库密码优先读环境变量。

    密码这块单独说一下：一开始直接写在 yaml 里，后来 push 前自查发现差点把
    测试库密码带出去，从此改成环境变量优先。
    """
    cfg_path = Path(path or os.getenv("KA_CONFIG", BASE_DIR / "config.yaml"))
    if not cfg_path.exists():
        cfg_path = BASE_DIR / "config.example.yaml"

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    try:  # python-dotenv 不是必装，装了就顺手读一下 .env
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    db = cfg.setdefault("db", {})
    db["host"] = os.getenv("KA_DB_HOST", db.get("host"))
    db["port"] = int(os.getenv("KA_DB_PORT", db.get("port", 3306)))
    db["user"] = os.getenv("KA_DB_USER", db.get("user"))
    db["password"] = os.getenv("KA_DB_PASSWORD", db.get("password", ""))
    db["database"] = os.getenv("KA_DB_NAME", db.get("database"))
    cfg["sample_csv"] = str(BASE_DIR / cfg.get("sample_csv", "sample_data/ka_snapshot_sample.csv"))
    cfg["output_dir"] = str(BASE_DIR / cfg.get("output_dir", "outputs"))
    return cfg


def load_snapshot_from_db(cfg, stat_date):
    """从库里取一天的原始指标。

    注意：这里刻意只取「原始两列」，打分在本地算。
    SQL 里那段 case when 分层是给看板用的，两边算法必须一致，
    所以我把 SQL 抄了一遍而不是另起炉灶。
    """
    import pymysql  # 只有真连库时才需要

    db = cfg["db"]
    sql = """
        select cid, last_30d_trade_val, total_auc
        from ba_ka_snapshot
        where stat_date = %s
    """
    conn = pymysql.connect(
        host=db["host"], port=db["port"], user=db["user"],
        password=db["password"], database=db["database"], charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (stat_date,))
            rows = cur.fetchall()
    finally:
        conn.close()

    df = pd.DataFrame(rows, columns=["cid", "last_30d_trade_val", "total_auc"])
    df["stat_date"] = stat_date
    log.info("从库里取到 %s 的 %s 条 KA 指标", stat_date, len(df))
    return df


def load_snapshot_from_csv(cfg):
    df = pd.read_csv(cfg["sample_csv"])
    df["cid"] = df["cid"].astype(str)
    log.info("读样例快照 %s 行，日期：%s", len(df), ",".join(sorted(df["stat_date"].unique())))
    return df


def score_and_tier(df, cfg):
    """score = 近 30 天交易额 + 总资产 * 折算系数，然后按阈值打档。

    阈值从 config 读，方便我一遍遍改着试；写死在代码里的话，
    每次调整都要动源文件，很烦。
    """
    tiers = cfg["tiers"]
    df = df.copy()
    df["score"] = df["last_30d_trade_val"].fillna(0) + df["total_auc"].fillna(0) * cfg.get("auc_weight", 30)

    # 从高往低判，先命中先返回，避免写一堆 and 区间
    def _tier(score):
        if score >= tiers["ka3"]:
            return "ka3"
        if score >= tiers["ka2"]:
            return "ka2"
        if score >= tiers["ka1"]:
            return "ka1"
        return "ka0"

    df["note"] = df["score"].apply(_tier)
    return df


def tier_distribution(df):
    """各档人数 + 占比。ka_pct 的分母只算 KA，不含 ka0。"""
    dist = df.groupby("note")["cid"].nunique().reset_index(name="users")
    total = dist["users"].sum()
    ka_total = dist.loc[dist["note"] != "ka0", "users"].sum() or 1
    dist["pct_of_all"] = (dist["users"] / total).round(4)
    dist["pct_of_ka"] = dist.apply(lambda r: 0 if r["note"] == "ka0" else round(r["users"] / ka_total, 4), axis=1)
    # 排序按档位，不按人数，不然图上看不出漏斗形状
    dist["order"] = dist["note"].map({t: i for i, t in enumerate(TIER_ORDER)})
    return dist.sort_values("order").drop(columns="order").reset_index(drop=True)


def compare_two_snapshots(before, after):
    """新旧规则（或前后两天）的等级变动。

    做法很直白：两个快照外连接，一边没有的补成 ka0，
    然后比 note 大小判断升降级。db 那边也是同思路，只是用 join + 子查询。
    """
    b = before[["cid", "note"]].rename(columns={"note": "note_before"})
    a = after[["cid", "note"]].rename(columns={"note": "note_after"})
    merged = b.merge(a, on="cid", how="outer").fillna({"note_before": "ka0", "note_after": "ka0"})

    rank = {t: i for i, t in enumerate(TIER_ORDER)}
    merged["delta"] = merged["note_after"].map(rank) - merged["note_before"].map(rank)
    merged["change"] = "no_change"
    merged.loc[merged["delta"] > 0, "change"] = "upgrade"
    merged.loc[merged["delta"] < 0, "change"] = "downgrade"

    summary = merged.groupby("change")["cid"].nunique().reset_index(name="users")
    return merged, summary


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="KA 分层沙盘推演")
    parser.add_argument("--use-db", action="store_true", help="从 MySQL 取数，默认读样例 CSV")
    parser.add_argument("--date", default=None, help="连库时要取的 stat_date，如 2023-06-01")
    args = parser.parse_args()

    if args.use_db:
        if not args.date:
            raise SystemExit("连库要指定 --date")
        raw = load_snapshot_from_db(cfg, args.date)
        dates = [args.date]
    else:
        raw = load_snapshot_from_csv(cfg)
        dates = sorted(raw["stat_date"].unique())

    scored = score_and_tier(raw, cfg)

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    for d in dates:
        day = scored[scored["stat_date"] == d]
        dist = tier_distribution(day)
        log.info("%s 分层分布：%s", d, dist[["note", "users", "pct_of_all"]].to_dict("records"))
        dist.to_csv(out / ("tier_dist_%s.csv" % d), index=False, encoding="utf-8-sig")

    if len(dates) >= 2:
        _, summary = compare_two_snapshots(
            scored[scored["stat_date"] == dates[0]], scored[scored["stat_date"] == dates[-1]]
        )
        log.info("%s → %s 变动：%s", dates[0], dates[-1], summary.to_dict("records"))
        summary.to_csv(out / "tier_change.csv", index=False, encoding="utf-8-sig")
        log.info("产物写到 %s", out.resolve())

    # 沙盘推演最关心的其实就一件事：降级人数会不会让客服被打爆
    ka0_counts = scored.assign(is_ka0=scored["note"].eq("ka0")).groupby("stat_date")["is_ka0"].sum()
    log.info("按日期看被划到 ka0（不享受权益）的人数：%s", ka0_counts.to_dict())


if __name__ == "__main__":
    main()
