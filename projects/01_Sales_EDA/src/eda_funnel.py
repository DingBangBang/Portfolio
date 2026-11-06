# -*- coding: utf-8 -*-
"""把 notebook 里天天要跑的几个口径抽成脚本。

说明一下为什么不重构：
notebook 里那套是边看边写的（画图、试阈值、回退一步再看），硬改成 OOP
反而把自己绕进去。这里只挑「结论要复用」的部分固化：漏斗、复购、粗分层、
日趋势，其余探索过程留在 notebook 里。

用法：
    python src/eda_funnel.py                    # 跑 config.yaml 里的数据
    python src/eda_funnel.py --data xx.csv      # 临时换个文件
"""

import argparse
import json
import logging
import time
from collections import Counter
from pathlib import Path

import pandas as pd

try:  # app.py 里当包 import
    from .config import load_config, BASE_DIR
except ImportError:  # python src/eda_funnel.py 直接跑
    from config import load_config, BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sales_eda")

EVENT_ORDER = ["view", "cart", "purchase"]
PURCHASE_COLS = ["user_id", "user_session", "price", "event_time"]


def read_events(path, chunk_size=500000):
    """分块读 CSV，读一块就聚合一块。

    最早图省事直接 pd.read_csv 整份 12 月数据（1.2G），8G 内存的机器直接
    MemoryError；后来改成逐块读、每块读完只留聚合结果和 purchase 明细。
    """
    users_by_event = {e: set() for e in EVENT_ORDER}
    all_users = set()
    daily_counter = Counter()          # (date, event_type) -> 次数
    purchase_frames = []
    n_rows = 0

    t0 = time.time()
    reader = pd.read_csv(
        path,
        chunksize=int(chunk_size),
        dtype={"user_id": "int64", "product_id": "int64"},
    )
    for chunk in reader:
        n_rows += len(chunk)
        all_users.update(chunk["user_id"].dropna().unique().tolist())
        for e in EVENT_ORDER:
            users_by_event[e].update(chunk.loc[chunk["event_type"] == e, "user_id"].unique().tolist())

        # 日期只取到天，够画趋势了
        chunk_date = pd.to_datetime(chunk["event_time"]).dt.strftime("%Y-%m-%d")
        daily_counter.update(zip(chunk_date.tolist(), chunk["event_type"].tolist()))

        purchase_frames.append(chunk.loc[chunk["event_type"] == "purchase", PURCHASE_COLS].copy())

    purchase = pd.concat(purchase_frames, ignore_index=True) if purchase_frames else pd.DataFrame(columns=PURCHASE_COLS)
    purchase["event_time"] = pd.to_datetime(purchase["event_time"])

    log.info("读完 %s 行，耗时 %.1fs", format(n_rows, ","), time.time() - t0)
    return {
        "n_rows": n_rows,
        "uv": len(all_users),
        "users_by_event": users_by_event,
        "daily_counter": daily_counter,
        "purchase": purchase,
    }


def funnel_stats(data):
    """浏览 → 加购 → 成交。分母统一用 UV，跟报告口径保持一致。"""
    uv = data["uv"] or 1
    steps = []
    for e in EVENT_ORDER:
        cnt = len(data["users_by_event"][e])
        steps.append({"step": e, "users": cnt, "rate_of_uv": round(cnt / uv, 4)})

    purchase = data["purchase"]
    stats = {
        "rows": data["n_rows"],
        "uv": data["uv"],
        "pv": data["n_rows"],
        "orders": int(purchase["user_session"].nunique()),
        "gmv": round(float(purchase["price"].sum()), 2),
        "steps": steps,
    }
    # 相邻两跳的流失，报告里写「最大的漏损在浏览→加购」就是看这个
    stats["drop_off"] = [
        {
            "from": EVENT_ORDER[i],
            "to": EVENT_ORDER[i + 1],
            "lost_rate": round(1 - steps[i + 1]["users"] / max(steps[i]["users"], 1), 4),
        }
        for i in range(len(steps) - 1)
    ]
    return stats


def repurchase_stats(data):
    """复购率 = 买过 2 次及以上的人 / 买过东西的人。"""
    purchase = data["purchase"]
    if purchase.empty:
        return {"paying_users": 0, "repurchase_rate": 0.0, "avg_buy_times": 0.0}

    buy_times = purchase.groupby("user_id")["user_session"].nunique()
    paying = int(buy_times.shape[0])
    return {
        "paying_users": paying,
        "repurchase_rate": round(float((buy_times >= 2).sum() / paying), 4),
        "avg_buy_times": round(float(buy_times.mean()), 2),
    }


def rfm_tiers(data):
    """很粗的 RFM 分层，给运营当个参考，不是主结论。

    阈值是拍脑袋定的，也没做严格验证：当时手头没有留存和成本数据，
    做精细的 RFM 评分意义不大，先按分位数切三刀看看人长什么样。
    """
    cols = ["user_id", "recency_days", "frequency", "monetary", "tier"]
    purchase = data["purchase"]
    if purchase.empty:
        return pd.DataFrame(columns=cols)

    snap = purchase["event_time"].max()
    rfm = purchase.groupby("user_id").agg(
        recency_days=("event_time", lambda s: (snap - s.max()).days),
        frequency=("user_session", "nunique"),
        monetary=("price", "sum"),
    ).reset_index()

    # rank(method="first") 先打散并列值，qcut 才不会因为重复值报 bins 错误
    rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first"), 3, labels=[3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 3, labels=[1, 2, 3]).astype(int)

    def _tier(row):
        if row.r_score == 3 and row.f_score >= 2:
            return "champions"
        if row.f_score == 3:
            return "loyal"
        if row.r_score == 1:
            return "almost_lost"
        return "new"

    rfm["tier"] = rfm.apply(_tier, axis=1)
    return rfm


def daily_events(data):
    """按天 x 行为类型摊开，notebook 里的 engagement 折线就靠它。"""
    counter = data["daily_counter"]
    dates = sorted({d for d, _ in counter})
    return pd.DataFrame(
        [{"date": d, **{e: counter.get((d, e), 0) for e in EVENT_ORDER}} for d in dates]
    )


def run(data_path, output_dir, chunk_size=500000):
    data = read_events(data_path, chunk_size)
    stats = funnel_stats(data)
    stats["repurchase"] = repurchase_stats(data)
    tiers = rfm_tiers(data)
    stats["tiers"] = tiers["tier"].value_counts().to_dict() if not tiers.empty else {}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "funnel_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    tiers.to_csv(out / "rfm_tiers.csv", index=False, encoding="utf-8-sig")
    daily_events(data).to_csv(out / "daily_events.csv", index=False, encoding="utf-8-sig")

    log.info("UV=%s，订单=%s，GMV=%.2f", stats["uv"], stats["orders"], stats["gmv"])
    for s in stats["steps"]:
        log.info("漏斗 %-9s %10s 人 (%.2f%% of UV)", s["step"], format(s["users"], ","), s["rate_of_uv"] * 100)
    log.info("结果写到 %s", out.resolve())
    return stats


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Sales EDA 固化口径")
    parser.add_argument("--data", default=cfg["data_path"], help="原始事件 CSV")
    parser.add_argument("--out", default=cfg["output_dir"], help="输出目录")
    parser.add_argument("--chunk-size", type=int, default=cfg["chunk_size"])
    args = parser.parse_args()

    # 找得到配置里的文件就用它，找不到就先拿样例数据跑通流程（README 里也是这么写的）
    data_path = args.data
    if not Path(data_path).exists():
        sample = BASE_DIR / "sample_data" / "events_sample.csv"
        if data_path == cfg["data_path"] and sample.exists():
            log.warning("没找到 %s，先用样例数据跑一遍", data_path)
            data_path = str(sample)
        else:
            raise SystemExit("找不到数据文件：%s（先把 Kaggle 的 CSV 放到 data/ 下，或改 config.yaml）" % data_path)

    run(data_path, args.out, args.chunk_size)


if __name__ == "__main__":
    main()
