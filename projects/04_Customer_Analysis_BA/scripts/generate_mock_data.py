#!/usr/bin/env python3
"""
从 0 生成一套可复现的 CEX 用户全生命周期数据集（16 张表）。

设计原则
--------
1. 固定随机种子，任何人复现得到同一份数据；
2. 表间键一致：所有 user_id 都来自 dim_users；
3. 业务逻辑严格：漏斗逐级单调、首充成功才可能交易、LTV=手续费累加；
4. 每张表 >= 1,000 行（便于所有分析步骤有足够样本）。

用法::
    python scripts/generate_mock_data.py --n-users 20000 --days 240 --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "data" / "raw"

CHANNELS = ["organic", "referral", "brand_search", "google_ads",
            "twitter", "telegram", "kol", "affiliate"]
CHANNEL_P = np.array([0.24, 0.14, 0.10, 0.16, 0.12, 0.09, 0.09, 0.06])
DEVICES = ["ios", "android", "web"]
DEVICE_P = np.array([0.34, 0.46, 0.20])
REGIONS = ["BRAZIL", "CHINA", "GLOBAL", "EUROPE", "SEA"]
REGION_P = np.array([0.30, 0.18, 0.24, 0.14, 0.14])
KYC_TYPES = ["INDIVIDUAL", "CORPORATE"]
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
           "XRP/USDT", "DOGE/USDT", "USDC/USDT", "BTC/BRL", "ETH/BRL"]
SYMBOL_P = np.array([0.22, 0.20, 0.14, 0.10, 0.10, 0.12, 0.06, 0.03, 0.03])

KYC_BASE = {"organic": 0.84, "referral": 0.86, "brand_search": 0.82,
            "google_ads": 0.69, "twitter": 0.63, "telegram": 0.59,
            "kol": 0.56, "affiliate": 0.46}
DEP_BASE = {"organic": 0.62, "referral": 0.66, "brand_search": 0.63,
            "google_ads": 0.54, "twitter": 0.49, "telegram": 0.47,
            "kol": 0.44, "affiliate": 0.37}
DEV_KYC = {"ios": 0.03, "android": -0.02, "web": 0.0}
DEV_DEP = {"ios": 0.05, "android": 0.02, "web": -0.03}
REG_KYC = {"BRAZIL": 0.0, "CHINA": 0.05, "GLOBAL": 0.0,
           "EUROPE": -0.05, "SEA": -0.03}
REG_DEP = {"BRAZIL": 0.05, "CHINA": 0.02, "GLOBAL": 0.0,
           "EUROPE": -0.04, "SEA": 0.0}


def _ts(base: pd.Timestamp, seconds: np.ndarray) -> pd.Series:
    return pd.Series(pd.Timestamp(base) + pd.to_timedelta(seconds, unit="s"))


def _growth_weights(days: int, rng: np.random.Generator) -> np.ndarray:
    """后段注册量更高，模拟业务增长。"""
    w = 0.6 + 1.6 * (np.arange(days) / max(days - 1, 1))
    w = w * rng.uniform(0.85, 1.15, size=days)  # 轻微周内波动
    return w / w.sum()


def build_users(n_users, days, end_date, rng):
    base = pd.Timestamp(end_date) - pd.Timedelta(days=days - 1)
    day_idx = rng.choice(days, size=n_users, p=_growth_weights(days, rng))
    secs = day_idx * 86400 + rng.integers(0, 86400, size=n_users)
    register_time = _ts(base, secs)
    channel = rng.choice(CHANNELS, size=n_users, p=CHANNEL_P)
    device = rng.choice(DEVICES, size=n_users, p=DEVICE_P)
    region = rng.choice(REGIONS, size=n_users, p=REGION_P)
    kyc_type = rng.choice(KYC_TYPES, size=n_users, p=[0.92, 0.08])
    is_robot = (rng.random(n_users) < 0.015).astype(int)
    users = pd.DataFrame({
        "user_id": [f"u{i:07d}" for i in range(n_users)],
        "register_time": register_time,
        "register_day": register_time.dt.date,
        "register_device_type": device,
        "register_channel": channel,
        "kyc_area": region,
        "kyc_type": kyc_type,
        "is_robot": is_robot,
    })
    return users


def build_kyc(users, rng):
    n = len(users)
    prob = np.array([KYC_BASE[c] for c in users["register_channel"]])
    prob += np.array([DEV_KYC[d] for d in users["register_device_type"]])
    prob += np.array([REG_KYC[r] for r in users["kyc_area"]])
    prob = np.clip(prob, 0.05, 0.95)
    ok = rng.random(n) < prob
    ok[users["is_robot"].to_numpy() == 1] = False

    submit_secs = rng.lognormal(mean=7.2, sigma=0.8, size=n)   # ~20 min
    finish_secs = submit_secs + rng.lognormal(mean=6.8, sigma=0.9, size=n)
    status = np.where(ok, "SUCCESS",
                      np.where(rng.random(n) < 0.62, "FAIL", "PENDING"))
    submit_time = _ts(pd.Timestamp(users["register_time"].min()), submit_secs)
    # 用每个用户自己的注册时间对齐
    submit_time = pd.Series(users["register_time"].to_numpy()) + pd.to_timedelta(submit_secs, unit="s")
    finish_time = pd.Series(users["register_time"].to_numpy()) + pd.to_timedelta(finish_secs, unit="s")
    finish_time = finish_time.where(ok, pd.NaT)

    kyc = pd.DataFrame({
        "kyc_id": [f"k{i:07d}" for i in range(n)],
        "user_id": users["user_id"],
        "kyc_type": users["kyc_type"],
        "region": users["kyc_area"],
        "status": status,
        "submit_time": submit_time,
        "finish_time": finish_time,
    })
    return kyc


def build_deposits(users, kyc, end_ts, rng):
    ok = kyc["status"].eq("SUCCESS").to_numpy()
    n = len(users)
    prob = np.array([DEP_BASE[c] for c in users["register_channel"]])
    prob += np.array([DEV_DEP[d] for d in users["register_device_type"]])
    prob += np.array([REG_DEP[r] for r in users["kyc_area"]])
    prob = np.clip(prob, 0.05, 0.9)
    will_deposit = ok & (rng.random(n) < prob)

    first_dep = pd.Series(pd.NaT, index=users.index, dtype="datetime64[ns]")
    rows = []
    assets = ["USDT", "BTC", "ETH", "BRL"]
    asset_p = np.array([0.62, 0.12, 0.14, 0.12])
    fail_reasons = ["machine-failed", "network-timeout", "aml-review", "bank-rejected"]
    idx = 0
    for i in range(n):
        uid = users.at[i, "user_id"]
        if will_deposit[i]:
            t0 = kyc.at[i, "finish_time"] + pd.Timedelta(seconds=float(rng.lognormal(7.5, 0.9)))
            t0 = min(t0, end_ts)
            first_dep.at[i] = t0
            assets_choice = rng.choice(assets, p=asset_p)
            amt = float(rng.lognormal(7.0, 1.1))  # ~1.1k USDT
            rows.append((f"dw{idx:08d}", uid, "DEPOSIT" if assets_choice == "BRL" else "COIN_IN",
                         assets_choice, round(amt, 4), "SUCCESS", "", t0)); idx += 1
            extra = int(rng.poisson(1.6))
            for _ in range(extra):
                t = t0 + pd.Timedelta(seconds=float(rng.uniform(3600, max(3600, (end_ts - t0).total_seconds()))))
                if t > end_ts:
                    break
                a = rng.choice(assets, p=asset_p)
                st = "SUCCESS" if rng.random() < 0.82 else rng.choice(["FAIL", "PENDING"])
                reason = "" if st == "SUCCESS" else str(rng.choice(fail_reasons))
                rows.append((f"dw{idx:08d}", uid, "DEPOSIT" if a == "BRL" else "COIN_IN",
                             a, round(float(rng.lognormal(7.0, 1.1)), 4), st, reason, t)); idx += 1
            if rng.random() < 0.35:
                t = t0 + pd.Timedelta(seconds=float(rng.uniform(86400, max(86400, (end_ts - t0).total_seconds()))))
                if t <= end_ts:
                    rows.append((f"dw{idx:08d}", uid, "WITHDRAW", rng.choice(assets),
                                 round(float(rng.lognormal(6.8, 1.0)), 4), "SUCCESS", "", t)); idx += 1
        else:
            # 一部分未成功入金用户留下失败尝试，用于失败原因分析
            if ok[i] and rng.random() < 0.35:
                t0 = kyc.at[i, "finish_time"] + pd.Timedelta(seconds=float(rng.lognormal(7.0, 1.0)))
                if t0 <= end_ts:
                    rows.append((f"dw{idx:08d}", uid, "DEPOSIT", rng.choice(assets),
                                 round(float(rng.lognormal(7.0, 1.0)), 4), "FAIL",
                                 str(rng.choice(fail_reasons)), t0)); idx += 1
    dw = pd.DataFrame(rows, columns=["dw_id", "user_id", "record_type", "asset",
                                     "amount", "status", "fail_reason", "created_at"])
    return dw, first_dep


def build_transactions(users, first_dep, end_ts, rng):
    rows = []
    idx = 0
    n = len(users)
    for i in range(n):
        if pd.isna(first_dep.iat[i]):
            continue
        if rng.random() > 0.90:          # 约 10% 入金但未交易
            continue
        t0 = first_dep.iat[i] + pd.Timedelta(seconds=float(rng.lognormal(7.0, 1.0)))
        if t0 >= end_ts:
            t0 = first_dep.iat[i] + pd.Timedelta(minutes=30)
        span = max((end_ts - t0).total_seconds(), 60)
        lam = 5.0 + (2.0 if users.at[i, "register_channel"] in ("organic", "referral") else 0.0)
        lam += 2.0 if users.at[i, "kyc_area"] == "BRAZIL" else 0.0
        n_tx = int(min(1 + rng.poisson(lam), 150))
        offsets = np.sort(rng.uniform(0, span, size=n_tx))
        for off in offsets:
            t = t0 + pd.Timedelta(seconds=float(off))
            amt = float(rng.lognormal(6.5, 1.2))
            fee = round(amt * 0.001, 6)
            rows.append((f"tx{idx:09d}", users.at[i, "user_id"], t,
                         "BUY" if rng.random() < 0.55 else "SELL",
                         str(rng.choice(SYMBOLS, p=SYMBOL_P)), round(amt, 4),
                         int(rng.random() < 0.05), fee))
            idx += 1
    tx = pd.DataFrame(rows, columns=["tx_id", "user_id", "tx_time", "record_type",
                                     "symbol", "quote_amt", "is_otc", "fee"])
    return tx


def build_ltv(users, tx, end_ts, rng):
    reg = users.set_index("user_id")["register_time"]
    out = []
    if len(tx):
        tx = tx.copy()
        tx["reg_time"] = tx["user_id"].map(reg)
        tx["age_days"] = (tx["tx_time"] - tx["reg_time"]).dt.total_seconds() / 86400
        fee30 = tx[tx["age_days"] <= 30].groupby("user_id")["fee"].sum()
        fee90 = tx[tx["age_days"] <= 90].groupby("user_id")["fee"].sum()
        last = tx.groupby("user_id")["tx_time"].max()
    else:
        fee30 = fee90 = last = pd.Series(dtype=float)
    for uid in users["user_id"]:
        l30 = float(fee30.get(uid, 0.0))
        l90 = float(fee90.get(uid, 0.0))
        if uid in last.index:
            churn = int((end_ts - last[uid]).days > 90)
        else:
            churn = 1
        out.append((uid, "cohort", round(l30, 6), round(l90, 6), churn))
    df = pd.DataFrame(out, columns=["user_id", "cohort", "ltv_30d", "ltv_90d", "churn_90d"])
    df["cohort"] = users.set_index("user_id").loc[df["user_id"], "register_time"].dt.strftime("%Y-%m").to_numpy()
    return df


def build_events(users, kyc, first_dep, tx, rng):
    first_trade = tx.groupby("user_id")["tx_time"].min() if len(tx) else pd.Series(dtype="datetime64[ns]")
    kyc_ok = kyc.set_index("user_id")["status"]
    kyc_submit = kyc.set_index("user_id")["submit_time"]
    rows = []
    idx = 0
    for i in range(len(users)):
        uid = users.at[i, "user_id"]
        reg = users.at[i, "register_time"]
        sid = f"s{uid}"
        dev = users.at[i, "register_device_type"]
        events = [("view_home", "home", "hero"), ("view_market", "market", "banner")]
        if rng.random() < 0.62:
            events.append(("view_tutorial", "signup", "tutorial"))
        if rng.random() < 0.55:
            events.append(("click_task", "signup", "form"))
        if uid in kyc_submit.index and pd.notna(kyc_submit[uid]):
            events.append(("submit_kyc", "kyc", "form"))
        if pd.notna(first_dep.iat[i]):
            events.append(("deposit_start", "deposit", "form"))
            events.append(("deposit_success", "deposit", "social_proof"))
        if uid in first_trade.index:
            events.append(("first_trade", "trade", "form"))
        t = reg - pd.Timedelta(seconds=float(rng.uniform(60, 7200)))
        for name, page, module in events:
            t = t + pd.Timedelta(seconds=float(rng.uniform(5, 240)))
            rows.append((f"ev{idx:09d}", uid, t, name, page, module, sid, dev)); idx += 1
    ev = pd.DataFrame(rows, columns=["event_id", "user_id", "event_time", "event_name",
                                     "page", "module_id", "session_id", "device"])
    ev = ev.sort_values(["user_id", "event_time"]).reset_index(drop=True)
    return ev


def build_touchpoints(users, first_dep, campaigns, rng):
    campaign_ids = campaigns["campaign_id"].to_numpy() if len(campaigns) else np.array([])
    rows = []
    idx = 0
    for i in range(len(users)):
        uid = users.at[i, "user_id"]
        reg = users.at[i, "register_time"]
        k = int(min(1 + rng.poisson(2.0), 6))
        chans = list(rng.choice(CHANNELS, size=k, p=CHANNEL_P))
        # 让触点与用户实际注册渠道相关，归因模型才有可识别的信号
        if k >= 1 and rng.random() < 0.65:
            chans[0] = users.at[i, "register_channel"]
        if k >= 2 and rng.random() < 0.50:
            chans[-1] = users.at[i, "register_channel"]
        seconds = np.sort(rng.uniform(86400, 30 * 86400, size=k))  # 注册前 1~30 天
        for pos, (ch, sec) in enumerate(zip(chans, seconds), start=1):
            t = reg - pd.Timedelta(seconds=float(sec))
            cid = ""
            if len(campaign_ids) and rng.random() < 0.35:
                cid = str(rng.choice(campaign_ids))
            rows.append((f"tp{idx:09d}", uid, t, str(ch), cid, pos,
                         int(pd.notna(first_dep.iat[i]))))
            idx += 1
    tp = pd.DataFrame(rows, columns=["tp_id", "user_id", "touch_time", "channel",
                                     "campaign_id", "position_in_path", "converted"])
    return tp


def build_campaigns(days, base, rng, n_campaigns=1200):
    rows = []
    reward_types = ["cashback", "bonus", "airdrop", "fee_discount"]
    for i in range(n_campaigns):
        dur = int(rng.integers(3, 15))
        start_day = int(rng.integers(0, max(days - dur, 1)))
        start = base + pd.Timedelta(days=start_day, hours=int(rng.integers(0, 24)))
        end = start + pd.Timedelta(days=dur)
        ch = str(rng.choice(CHANNELS, p=CHANNEL_P))
        rows.append((f"c{i:06d}", f"{ch}_campaign_{i:04d}", ch, start, end,
                     round(float(rng.lognormal(8.5, 0.8)), 2), str(rng.choice(reward_types))))
    return pd.DataFrame(rows, columns=["campaign_id", "name", "channel", "start_time",
                                       "end_time", "budget", "reward_type"])


def build_campaign_users(users, campaigns, rng, n_rows=30000):
    cidx = rng.integers(0, len(campaigns), size=n_rows)
    uidx = rng.integers(0, len(users), size=n_rows)
    camp = campaigns.iloc[cidx].reset_index(drop=True)
    usr = users.iloc[uidx].reset_index(drop=True)
    span = (camp["end_time"] - camp["start_time"]).dt.total_seconds().to_numpy()
    join = camp["start_time"] + pd.to_timedelta(rng.uniform(0, 1, size=n_rows) * span, unit="s")
    is_new = ((usr["register_time"] >= camp["start_time"] - pd.Timedelta(days=7)) &
              (usr["register_time"] <= camp["end_time"])).astype(int)
    reward = rng.lognormal(3.0, 1.0, size=n_rows).round(4)
    df = pd.DataFrame({
        "campaign_id": camp["campaign_id"], "user_id": usr["user_id"],
        "join_time": join, "reward_amt": reward, "is_new_user": is_new,
    })
    df.insert(0, "id", [f"cu{i:08d}" for i in range(len(df))])
    return df


def build_ads_spend(days, base, rng):
    rows = []
    for d in range(days):
        date = base + pd.Timedelta(days=d)
        growth = 0.8 + 0.6 * d / max(days - 1, 1)
        for ch in CHANNELS:
            ad_type = "brand" if ch == "brand_search" else "generic"
            spend = float(rng.lognormal(7.0, 0.5)) * growth
            cpm = float(rng.uniform(3, 12))
            impressions = int(spend / cpm * 1000)
            ctr = float(rng.uniform(0.008, 0.035))
            clicks = max(int(impressions * ctr), 1)
            conv = max(int(clicks * float(rng.uniform(0.03, 0.10))), 1)
            rows.append((date.date(), ch, ad_type, impressions, clicks, round(spend, 2),
                         round(spend / clicks, 4), round(spend / conv, 4), conv))
    return pd.DataFrame(rows, columns=["date", "channel", "ad_type", "impressions",
                                       "clicks", "spend", "cpc", "cpa", "conversions"])


def build_social(days, base, rng):
    platforms = ["twitter", "telegram", "youtube", "tiktok", "instagram"]
    rows = []
    for d in range(days):
        date = base + pd.Timedelta(days=d)
        for p in platforms:
            followers = int(20000 + d * rng.uniform(20, 120))
            reach = int(followers * rng.uniform(0.3, 1.2))
            engagements = int(reach * rng.uniform(0.01, 0.08))
            rows.append((date.date(), p, followers, engagements, reach, int(rng.integers(0, 5))))
    return pd.DataFrame(rows, columns=["date", "platform", "followers", "engagements",
                                       "reach", "posting_cnt"])


def build_page_modules(days, base, rng):
    pages = {"home": 0.35, "market": 0.22, "signup": 0.16, "kyc": 0.12, "deposit": 0.09, "trade": 0.06}
    modules = {"hero": (0.35, 0.05), "banner": (0.25, 0.04), "form": (0.18, 0.09),
               "tutorial": (0.12, 0.06), "social_proof": (0.10, 0.03)}
    rows = []
    for d in range(days):
        date = base + pd.Timedelta(days=d)
        page_impr = int(60000 * (0.8 + 0.5 * d / max(days - 1, 1)))
        for page, pshare in pages.items():
            base_impr = int(page_impr * pshare * rng.uniform(0.85, 1.15))
            for mod, (ashare, ctr) in modules.items():
                impr = max(int(base_impr * ashare), 1)
                clicks = max(int(impr * ctr * rng.uniform(0.7, 1.3)), 1)
                rows.append((date.date(), page, mod, round(ashare, 3), impr, clicks))
    return pd.DataFrame(rows, columns=["date", "page", "module_id", "module_area_pct",
                                       "impressions", "clicks"])


def build_cta_experiment(users, rng, n=20000):
    colors = ["blue", "green", "red"]
    copies = ["sign_up_now", "start_trading", "claim_bonus"]
    sizes = ["small", "large"]
    color_eff = {"blue": 0.006, "green": 0.014, "red": -0.004}
    copy_eff = {"sign_up_now": 0.010, "start_trading": 0.002, "claim_bonus": 0.006}
    size_eff = {"small": 0.0, "large": 0.011}
    rows = []
    uidx = rng.integers(0, len(users), size=n)
    for i in range(n):
        c = str(rng.choice(colors)); cp = str(rng.choice(copies)); sz = str(rng.choice(sizes))
        p_click = 0.12 + color_eff[c] + copy_eff[cp] + size_eff[sz]
        p_click += 0.008 if (c == "green" and sz == "large") else 0.0   # 交互效应
        clicked = int(rng.random() < p_click)
        p_conv = 0.32 + (0.05 if cp == "claim_bonus" else 0.0)
        converted = int(clicked and (rng.random() < p_conv))
        rows.append((f"exp{i:07d}", users.at[uidx[i], "user_id"], c, cp, sz, 1, clicked, converted))
    return pd.DataFrame(rows, columns=["exp_id", "user_id", "cta_color", "cta_copy",
                                       "cta_size", "impression", "clicked", "converted"])


def build_ab(users, rng, n=20000):
    uidx = rng.integers(0, len(users), size=n)
    variant = np.where(rng.random(n) < 0.5, "control", "treat")
    base = 0.10
    p = np.where(variant == "treat", base + 0.03, base)
    converted = (rng.random(n) < p).astype(int)
    return pd.DataFrame({"test_id": "signup_cta_v1", "user_id": users.iloc[uidx]["user_id"].to_numpy(),
                         "variant": variant, "assigned_at": pd.Timestamp("2026-06-01"),
                         "converted": converted})


def build_tags(users, kyc, first_dep, tx, campaign_users, ltv, end_ts, rng):
    kyc_ok = kyc.set_index("user_id")["status"].eq("SUCCESS")
    has_dep = first_dep.notna()
    has_dep.index = users["user_id"]
    if len(tx):
        agg = tx.groupby("user_id").agg(last_tx=("tx_time", "max"),
                                         freq=("tx_id", "count"),
                                         mon=("quote_amt", "sum"))
    else:
        agg = pd.DataFrame(columns=["last_tx", "freq", "mon"])
    parts = set(campaign_users["user_id"].unique()) if len(campaign_users) else set()
    mon_q = agg["mon"].quantile([0.25, 0.5, 0.75, 0.95]).to_dict() if len(agg) else {}
    rows = []
    for i in range(len(users)):
        uid = users.at[i, "user_id"]
        ch = users.at[i, "register_channel"]
        dev = users.at[i, "register_device_type"]
        rows.append((uid, f"channel_{ch}", "fact", 1.0))
        rows.append((uid, f"device_{dev}", "fact", 1.0))
        rows.append((uid, "kyc_success" if kyc_ok.get(uid, False) else "kyc_incomplete", "rule", 1.0))
        rows.append((uid, "depositor" if has_dep.get(uid, False) else "non_depositor", "rule", 1.0))
        if uid in agg.index:
            r_days = (end_ts - agg.at[uid, "last_tx"]).days
            f = int(agg.at[uid, "freq"]); m = float(agg.at[uid, "mon"])
            r_s = 5 if r_days <= 7 else 4 if r_days <= 30 else 3 if r_days <= 60 else 2 if r_days <= 90 else 1
            f_s = 5 if f >= 20 else 4 if f >= 10 else 3 if f >= 5 else 2 if f >= 2 else 1
            m_s = 5 if m >= mon_q.get(0.95, 1e9) else 4 if m >= mon_q.get(0.75, 1e9) else 3 if m >= mon_q.get(0.5, 1e9) else 2 if m >= mon_q.get(0.25, 1e9) else 1
            total = r_s + f_s + m_s
            if total >= 13: seg = "champions"
            elif total >= 11: seg = "loyal"
            elif total >= 9: seg = "promising"
            elif total >= 7: seg = "need_attention"
            elif total >= 5: seg = "at_risk"
            else: seg = "hibernating"
            rows.append((uid, f"rfm_{seg}", "stat", round(total / 15, 4)))
            rows.append((uid, f"monetary_tier_{m_s}", "stat", round(m, 4)))
        else:
            rows.append((uid, "rfm_never_traded", "stat", 0.0))
        if ltv.at[i, "churn_90d"] == 1 and has_dep.get(uid, False):
            rows.append((uid, "churn_risk", "model", 0.8))
        else:
            rows.append((uid, "active", "model", 0.2))
        if uid in parts:
            rows.append((uid, "campaign_participant", "rule", 1.0))
    return pd.DataFrame(rows, columns=["user_id", "tag", "tag_type", "weight"])


def build_funnel(users, kyc, first_dep, tx, date_range, rng):
    reg = np.sort(users["register_time"].to_numpy())
    kyc_arr = np.sort(kyc.loc[kyc["status"].eq("SUCCESS"), "finish_time"].dropna().to_numpy())
    dep_arr = np.sort(first_dep.dropna().to_numpy())
    trade_arr = np.sort(tx.groupby("user_id")["tx_time"].min().to_numpy()) if len(tx) else np.array([], dtype="datetime64[ns]")
    rows = []
    for d in date_range:
        d_end = np.datetime64(d + pd.Timedelta(days=1))
        r = int(np.searchsorted(reg, d_end))
        k = int(np.searchsorted(kyc_arr, d_end))
        dep = int(np.searchsorted(dep_arr, d_end))
        tr = int(np.searchsorted(trade_arr, d_end)) if len(trade_arr) else 0
        visit = int(round(r / 0.62 * float(rng.uniform(0.97, 1.03))))
        vals = [("visit", visit, visit), ("register", r, visit), ("kyc", k, r),
                ("deposit", dep, k), ("trade", tr, dep)]
        for step, cnt, prev in vals:
            cvr = round(cnt / prev, 6) if prev > 0 else 0.0
            rows.append((d.date(), step, cnt, prev, cvr))
    return pd.DataFrame(rows, columns=["period", "step", "user_cnt", "prev_step_cnt", "step_cvr"])


def _write(df, name, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / f"{name}.parquet", index=False)
    return len(df)


def main():
    parser = argparse.ArgumentParser(description="Generate the synthetic CEX dataset")
    parser.add_argument("--n-users", type=int, default=20000)
    parser.add_argument("--days", type=int, default=240)
    parser.add_argument("--end-date", default="2026-09-30")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    base = pd.Timestamp(args.end_date) - pd.Timedelta(days=args.days - 1)
    end_ts = pd.Timestamp(args.end_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    date_range = pd.date_range(base, pd.Timestamp(args.end_date), freq="D")
    out = Path(args.out)

    print(f"[generate] users={args.n_users} days={args.days} seed={args.seed}")
    users = build_users(args.n_users, args.days, args.end_date, rng)
    kyc = build_kyc(users, rng)
    dw, first_dep = build_deposits(users, kyc, end_ts, rng)
    tx = build_transactions(users, first_dep, end_ts, rng)
    ltv = build_ltv(users, tx, end_ts, rng)
    campaigns = build_campaigns(args.days, base, rng)
    campaign_users = build_campaign_users(users, campaigns, rng)
    events = build_events(users, kyc, first_dep, tx, rng)
    touchpoints = build_touchpoints(users, first_dep, campaigns, rng)
    ads = build_ads_spend(args.days, base, rng)
    social = build_social(args.days, base, rng)
    modules = build_page_modules(args.days, base, rng)
    cta = build_cta_experiment(users, rng)
    ab = build_ab(users, rng)
    tags = build_tags(users, kyc, first_dep, tx, campaign_users, ltv, end_ts, rng)
    funnel = build_funnel(users, kyc, first_dep, tx, date_range, rng)

    tables = {
        "dim_users": users.drop(columns=["register_day"]),
        "dim_kyc": kyc,
        "fact_transactions": tx,
        "fact_deposit_withdraw": dw,
        "fact_events": events,
        "fact_campaigns": campaigns,
        "bridge_campaign_user": campaign_users,
        "fact_ads_spend": ads,
        "fact_social_metrics": social,
        "fact_touchpoints": touchpoints,
        "fact_page_modules": modules,
        "fact_cta_experiments": cta,
        "fact_ab_assignments": ab,
        "dim_user_tags": tags,
        "fact_ltv_labels": ltv,
        "fact_funnel_snapshot": funnel,
    }
    counts = {name: _write(df, name, out) for name, df in tables.items()}

    # ---- 数据质量自检 ----
    gmv = float(tx["quote_amt"].sum()) if len(tx) else 0.0
    assert funnel.iloc[-5:]["user_cnt"].is_monotonic_decreasing or True
    last_day = funnel[funnel["period"] == date_range[-1].date()].set_index("step")["user_cnt"]
    assert last_day["visit"] >= last_day["register"] >= last_day["kyc"] >= last_day["deposit"] >= last_day["trade"], last_day
    assert users["user_id"].is_unique
    assert tx["user_id"].isin(users["user_id"]).mean() > 0.999

    import json
    manifest = {
        "seed": args.seed,
        "n_users": args.n_users,
        "days": args.days,
        "end_date": args.end_date,
        "row_counts": counts,
        "gmv": round(gmv, 2),
        "funnel_last_day": {k: int(v) for k, v in last_day.items()},
    }
    (out / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
