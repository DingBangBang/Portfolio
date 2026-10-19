#!/usr/bin/env python3
"""KPI computation, insight generation and report export."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def compute_kpis(con) -> dict:
    row = con.execute("""
        select count(*) as users,
               sum(is_kyc) as kyc_users,
               sum(is_deposited) as depositors,
               sum(is_trader) as traders,
               sum(gmv) as gmv,
               sum(revenue) as revenue,
               avg(ltv_90d) as avg_ltv_90d,
               avg(churn_90d) as churn_rate
        from marts.mart_user_360
    """).df().iloc[0]
    tx = con.execute("select count(*) as n, sum(quote_amt) as gmv, sum(fee) as fee from staging.stg_transactions").df().iloc[0]
    users = int(row["users"])
    traders = int(row["traders"])
    depositors = int(row["depositors"])
    gmv = float(row["gmv"])
    revenue = float(row["revenue"])
    kpis = {
        "users": users,
        "kyc_users": int(row["kyc_users"]),
        "depositors": depositors,
        "traders": traders,
        "gmv": round(gmv, 2),
        "revenue": round(revenue, 2),
        "tx_count": int(tx["n"]),
        "kyc_rate": round(int(row["kyc_users"]) / users, 4) if users else 0,
        "deposit_rate": round(depositors / users, 4) if users else 0,
        "trade_rate": round(traders / users, 4) if users else 0,
        "deposit_to_trade_rate": round(traders / depositors, 4) if depositors else 0,
        "arpu": round(revenue / users, 4) if users else 0,
        "arppu": round(revenue / traders, 4) if traders else 0,
        "aov": round(float(tx["gmv"]) / int(tx["n"]), 4) if int(tx["n"]) else 0,
        "avg_ltv_90d": round(float(row["avg_ltv_90d"] or 0), 4),
        "churn_rate": round(float(row["churn_rate"] or 0), 4),
        "gmv_per_trader": round(gmv / traders, 2) if traders else 0,
    }
    return kpis


THRESHOLDS = {
    "deposit_rate": {"warn_below": 0.30, "label": "注册→首次入金转化率"},
    "deposit_to_trade_rate": {"warn_below": 0.80, "label": "入金→首笔交易转化率"},
    "churn_rate": {"warn_above": 0.45, "label": "90 天流失率"},
}


def _status(key: str, value: float) -> tuple[bool, str]:
    t = THRESHOLDS.get(key)
    if not t:
        return False, "info"
    if "warn_below" in t and value < t["warn_below"]:
        return True, "alert"
    if "warn_above" in t and value > t["warn_above"]:
        return True, "alert"
    return False, "ok"


def build_insights(kpis: dict, results: dict) -> list[dict]:
    insights = []
    for key in ["deposit_rate", "deposit_to_trade_rate", "churn_rate"]:
        alert, status = _status(key, kpis[key])
        insights.append({
            "title": THRESHOLDS[key]["label"],
            "finding": f"当前 {kpis[key]:.2%}",
            "status": status,
            "suggestion": ("低于阈值，建议优先优化该环节的摩擦点" if alert and "warn_below" in THRESHOLDS[key]
                           else "高于阈值，建议对沉默用户启动召回" if alert else "处于健康区间，保持监控"),
        })

    funnel = results.get("funnel")
    if funnel is not None:
        last = funnel["last_day"].set_index("step")
        if {"kyc", "deposit"} <= set(last.index):
            drop = last.loc["kyc", "user_cnt"] - last.loc["deposit", "user_cnt"]
            insights.append({
                "title": "漏斗最大漏损",
                "finding": f"KYC→首次入金流失 {int(drop):,} 人",
                "status": "alert" if drop > last.loc["kyc", "user_cnt"] * 0.4 else "ok",
                "suggestion": "对已 KYC 未入金人群推送首充奖励 + 简化入金流程",
            })

    attr = results.get("attribution")
    if attr is not None:
        t = attr["table"].set_index("channel")
        gap = (t["markov_chain"] - t["last_touch"]).sort_values(ascending=False)
        top = gap.index[0]
        insights.append({
            "title": "被末次点击低估的渠道",
            "finding": f"{top} 的马尔可夫贡献比末次点击高 {gap.iloc[0] * 100:.1f} 个百分点",
            "status": "info",
            "suggestion": "预算评审改用马尔可夫/Shapley，避免只奖励最后一跳",
        })

    ab = results.get("ab")
    if ab is not None:
        insights.append({
            "title": "A/B 实验结果",
            "finding": f"实验组提升 {ab['rel_lift_pct']}%，p={ab['p_value']:.4f}",
            "status": "ok" if (ab["p_value"] or 1) < 0.05 else "info",
            "suggestion": "显著则全量，不显著则继续扩大样本或改版",
        })

    budget = results.get("budget")
    if budget is not None and len(budget["params"]):
        p = budget["params"].sort_values("marginal_conv_per_dollar", ascending=False)
        insights.append({
            "title": "预算边际回报最高的渠道",
            "finding": f"{p.iloc[0]['channel']}（每美元边际转化 {p.iloc[0]['marginal_conv_per_dollar']:.6f}）",
            "status": "info",
            "suggestion": "在弹性曲线拐点前优先加投该渠道，并设置边际回报下限",
        })

    ltv = results.get("ltv")
    if ltv is not None:
        m = ltv["metrics"]
        insights.append({
            "title": "LTV 模型选型",
            "finding": "；".join(f"{r['model']}: Spearman={r.get('Spearman', 'NA')}" for _, r in m.iterrows()),
            "status": "info",
            "suggestion": "以机器学习为主预测器，BG/NBD 的 P(alive) 作为流失判定特征",
        })
    churn = results.get("churn")
    if churn is not None:
        best = churn["metrics"].sort_values("AUC", ascending=False).iloc[0]
        insights.append({
            "title": "流失预测模型对比",
            "finding": f"{best['model']} AUC={best['AUC']:.4f}，recall={best['recall']:.4f}",
            "status": "ok" if best["AUC"] >= 0.7 else "info",
            "suggestion": "AUC>=0.7 可用于运营圈人；否则补充行为特征后再上线",
        })

    vip = results.get("vip")
    if vip:
        st = vip["stability"]
        insights.append({
            "title": "VIP 分层稳定性",
            "finding": f"等级不变率 {st['stability_rate']:.2%}，升级 {st['upgrades']:,}，降级 {st['downgrades']:,}",
            "status": "ok" if st["stability_rate"] >= 0.8 else "alert",
            "suggestion": "不变率低于 80% 时拉长考核窗口或设置缓冲带，避免大客户抖动",
        })

    ops = results.get("ops")
    if ops is not None and len(ops):
        top = ops.iloc[0]
        insights.append({
            "title": "运营优先级最高的人群",
            "finding": f"{top['segment']}（{top['users']:,} 人，优先级分 {top['priority_score']:,.0f}）",
            "status": "info",
            "suggestion": f"先执行「{top['strategy']}」，目标指标 {top['target_metric']}",
        })

    fa = results.get("funnel_attr")
    if fa:
        t = fa["table"].dropna(subset=["contribution_pct"])
        if len(t):
            top = t.reindex(t["contribution_pct"].abs().sort_values(ascending=False).index).iloc[0]
            insights.append({
                "title": "整体 CVR 变化的最大贡献环节",
                "finding": f"{top['step']} 贡献 {top['contribution_pct']:.1f}%",
                "status": "info",
                "suggestion": "优先修复贡献最大的负向环节，其次巩固正向环节",
            })

    return insights



# Report exporter lives in src/export.py to keep this module focused.
from src.export import save_reports  # noqa: E402,F401
