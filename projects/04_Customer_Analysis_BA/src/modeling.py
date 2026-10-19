#!/usr/bin/env python3
"""
Core modelling & analysis library (README section 6).

每个函数读取 dbt marts/staging 层，返回 pandas DataFrame 或 dict，
可单独调用，也可由 ``run_all`` 统一执行。
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "warehouse.duckdb"


def connect(read_only: bool = True):
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def q(con, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


# ----------------------------------------------------------------
# 6.1 RFM + dimensionality reduction
# ----------------------------------------------------------------
def rfm_segmentation(con) -> dict:
    user = q(con, "select * from marts.mart_user_360 where rfm_segment is not null")
    feats = user[["recency_days", "frequency", "monetary"]].fillna(0)
    X = (feats - feats.mean()) / feats.std(ddof=0).replace(0, 1)

    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score

    best_k, best_score, best_labels = 2, -1, None
    for k in range(2, 7):
        lab = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
        score = silhouette_score(X, lab)
        if score > best_score:
            best_k, best_score, best_labels = k, score, lab
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)
    out = user[["user_id", "rfm_segment", "monetary", "ltv_90d"]].copy()
    out["cluster"] = best_labels
    out["pc1"], out["pc2"] = coords[:, 0], coords[:, 1]
    card = out.groupby("cluster").agg(
        users=("user_id", "count"), avg_monetary=("monetary", "mean"),
        avg_ltv_90d=("ltv_90d", "mean")).reset_index()
    return {"k": best_k, "silhouette": round(float(best_score), 4),
            "explained_var": round(float(pca.explained_variance_ratio_.sum()), 4),
            "assignments": out, "personas": card}


# ----------------------------------------------------------------
# 6.2 Conversion funnel
# ----------------------------------------------------------------
def funnel_analysis(con) -> dict:
    daily = q(con, "select * from marts.mart_funnel_daily order by period")
    last = daily[daily["period"] == daily["period"].max()].set_index("step")
    by_channel = q(con, """
        select register_channel as channel, count(*) as users,
               sum(is_kyc) as kyc_users, sum(is_deposited) as depositors,
               sum(is_trader) as traders,
               avg(is_kyc) as kyc_rate, avg(is_deposited) as deposit_rate,
               avg(is_trader) as trade_rate
        from marts.mart_user_360 group by 1 order by users desc
    """)
    by_device = q(con, """
        select register_device_type as device, count(*) as users,
               avg(is_deposited) as deposit_rate
        from marts.mart_user_360 group by 1 order by deposit_rate desc
    """)
    return {"daily": daily, "last_day": last.reset_index(),
            "by_channel": by_channel, "by_device": by_device}


# ----------------------------------------------------------------
# 6.3 Behavioural sequence + t-test (first hour)
# ----------------------------------------------------------------
def behavioural_sequences(con) -> pd.DataFrame:
    ev = q(con, """
        select e.user_id, e.event_name, e.event_time, u.register_time
        from staging.stg_events e join staging.stg_users u using (user_id)
    """)
    ev["in_first_hour"] = (pd.to_datetime(ev["event_time"]) - pd.to_datetime(ev["register_time"])).dt.total_seconds().between(0, 3600)
    flags = (ev[ev["in_first_hour"]]
             .assign(v=1)
             .pivot_table(index="user_id", columns="event_name", values="v", aggfunc="max", fill_value=0))
    for c in ["view_tutorial", "click_task", "submit_kyc", "deposit_start"]:
        if c not in flags.columns:
            flags[c] = 0
    target = q(con, "select user_id, is_deposited from marts.mart_user_360")
    m = target.merge(flags.reset_index(), on="user_id", how="left").fillna(0)
    from scipy.stats import ttest_ind
    rows = []
    for c in ["view_tutorial", "click_task", "submit_kyc", "deposit_start"]:
        a = m.loc[m["is_deposited"] == 1, c]
        b = m.loc[m["is_deposited"] == 0, c]
        t, p = ttest_ind(a, b, equal_var=False)
        rows.append({"behaviour": c, "deposited_mean": round(float(a.mean()), 4),
                     "non_deposited_mean": round(float(b.mean()), 4),
                     "diff": round(float(a.mean() - b.mean()), 4),
                     "t_stat": round(float(t), 3), "p_value": float(p)})
    return pd.DataFrame(rows).sort_values("diff", ascending=False)


# ----------------------------------------------------------------
# 6.4 User flow path graph
# ----------------------------------------------------------------
def flow_paths(con, top_n: int = 30) -> dict:
    ev = q(con, """
        select session_id, user_id, event_time, event_name, page, module_id
        from staging.stg_events order by session_id, event_time
    """)
    ev["next_event"] = ev.groupby("session_id")["event_name"].shift(-1)
    edges = (ev.dropna(subset=["next_event"])
               .groupby(["event_name", "next_event"]).size()
               .reset_index(name="weight")
               .sort_values("weight", ascending=False)
               .head(top_n))
    sessions = (ev.groupby("session_id")["event_name"]
                  .apply(lambda s: " > ".join(s)).reset_index(name="path"))
    top_paths = sessions["path"].value_counts().head(top_n).reset_index()
    top_paths.columns = ["path", "sessions"]
    return {"edges": edges, "top_paths": top_paths, "n_sessions": int(ev["session_id"].nunique())}


# ----------------------------------------------------------------
# 6.9 Four attribution models: first / last / position / Markov
# ----------------------------------------------------------------
def _paths_from_touchpoints(tp: pd.DataFrame):
    tp = tp.sort_values(["user_id", "position_in_path"])
    paths = tp.groupby("user_id")["channel"].apply(list)
    conv = tp.groupby("user_id")["converted"].max()
    return paths.to_dict(), conv.to_dict(), sorted(tp["channel"].unique())


def _linear_weights(paths: dict, conv: dict, channels, mode: str) -> pd.Series:
    out = {c: 0.0 for c in channels}
    for uid, path in paths.items():
        if not conv.get(uid):
            continue
        n = len(path)
        if mode == "first":
            out[path[0]] += 1
        elif mode == "last":
            out[path[-1]] += 1
        elif mode == "position":
            if n == 1:
                out[path[0]] += 1
            elif n == 2:
                out[path[0]] += 0.5; out[path[1]] += 0.5
            else:
                out[path[0]] += 0.4; out[path[-1]] += 0.4
                for ch in path[1:-1]:
                    out[ch] += 0.2 / (n - 2)
    s = pd.Series(out)
    return s / s.sum() if s.sum() else s


def _markov_shares(paths: dict, conv: dict, channels) -> pd.Series:
    """Markov chain removal effect (Anderl et al.).

    Removing a channel redirects every transition into it (and all of its
    outgoing transitions) to the NULL state, i.e. paths that need that
    channel are treated as lost rather than re-routed.
    """
    states = ["START"] + list(channels) + ["CONVERSION", "NULL"]
    idx = {s: i for i, s in enumerate(states)}
    C = np.zeros((len(states), len(states)), dtype=float)
    for uid, path in paths.items():
        prev = "START"
        for ch in path:
            C[idx[prev], idx[ch]] += 1
            prev = ch
        C[idx[prev], idx["CONVERSION" if conv.get(uid) else "NULL"]] += 1

    def pconv(remove=None):
        P = C.copy()
        row = P.sum(axis=1)
        row[row == 0] = 1.0
        P = P / row[:, None]
        if remove is not None:
            rc, null = idx[remove], idx["NULL"]
            P[:, null] += P[:, rc]          # transitions into removed -> NULL
            P[:, rc] = 0.0
            P[rc, :] = 0.0                  # removed state absorbs to NULL
            P[rc, null] = 1.0
        active = ["START"] + [c for c in channels if c != remove]
        ti = [idx[s] for s in active]
        ci = idx["CONVERSION"]
        Q = P[np.ix_(ti, ti)]
        R = P[np.ix_(ti, [ci])]
        N = np.linalg.inv(np.eye(len(ti)) - Q)
        return float((N @ R).ravel()[0])

    base = pconv()
    if base <= 0:
        return pd.Series({c: 0.0 for c in channels})
    effects = {c: max(base - pconv(remove=c), 0.0) for c in channels}
    s = pd.Series(effects)
    return s / s.sum() if s.sum() else s


def attribution_models(con, n_folds: int = 5) -> dict:
    tp = q(con, "select user_id, channel, position_in_path, converted from staging.stg_touchpoints")
    paths, conv, channels = _paths_from_touchpoints(tp)

    full = pd.DataFrame({
        "first_touch": _linear_weights(paths, conv, channels, "first"),
        "last_touch": _linear_weights(paths, conv, channels, "last"),
        "position_based": _linear_weights(paths, conv, channels, "position"),
        "markov_chain": _markov_shares(paths, conv, channels),
    })
    full["markov_vs_last_pct"] = ((full["markov_chain"] - full["last_touch"]) /
                                   full["last_touch"].replace(0, np.nan) * 100).round(2)

    # ---- error / stability: 5-fold split ----
    uids = np.array(list(paths.keys()))
    rng = np.random.default_rng(42)
    rng.shuffle(uids)
    folds = np.array_split(uids, n_folds)
    fold_rows = []
    for fold in folds:
        sub_paths = {u: paths[u] for u in fold}
        sub_conv = {u: conv[u] for u in fold}
        row = {"first_touch": _linear_weights(sub_paths, sub_conv, channels, "first"),
               "last_touch": _linear_weights(sub_paths, sub_conv, channels, "last"),
               "position_based": _linear_weights(sub_paths, sub_conv, channels, "position"),
               "markov_chain": _markov_shares(sub_paths, sub_conv, channels)}
        fold_rows.append(pd.DataFrame(row))
    fold_stack = pd.concat(fold_rows)
    stability = fold_stack.groupby(level=0).std().mean(axis=1)
    full["stability_std"] = stability.round(4)

    # reconstruction error: fold-mean share vs full share
    fold_mean = fold_stack.groupby(level=0).mean()
    recon = (fold_mean - full[["first_touch", "last_touch", "position_based", "markov_chain"]]).abs().mean(axis=1)
    full["reconstruction_error"] = recon.round(4)

    base_cvr = float(np.mean(list(conv.values()))) if conv else 0.0
    return {"table": full.reset_index().rename(columns={"index": "channel"}),
            "base_conversion_rate": round(base_cvr, 4),
            "n_users": len(paths), "n_touchpoints": len(tp),
            "recommended": "markov_chain"}


# ----------------------------------------------------------------
# 6.10 Channel quality grading + Shapley attribution
# ----------------------------------------------------------------
def channel_shapley(con) -> pd.DataFrame:
    tp = q(con, "select user_id, channel, position_in_path from staging.stg_touchpoints")
    u = q(con, "select user_id, is_deposited, revenue from marts.mart_user_360")
    tp = tp.merge(u, on="user_id", how="left").fillna({"revenue": 0, "is_deposited": 0})
    channels = sorted(tp["channel"].unique())
    user_paths = tp.groupby("user_id")["channel"].apply(set).to_dict()
    user_rev = u.set_index("user_id")["revenue"].fillna(0).to_dict()
    converted = u.set_index("user_id")["is_deposited"].fillna(0).to_dict()

    def value(subset):
        if not subset:
            return 0.0
        return sum(user_rev.get(uid, 0.0) for uid, chs in user_paths.items()
                   if converted.get(uid) and chs & subset)

    n = len(channels)
    from math import factorial
    cache = {}
    def v(s):
        key = frozenset(s)
        if key not in cache:
            cache[key] = value(set(key))
        return cache[key]
    shap = {c: 0.0 for c in channels}
    for c in channels:
        others = [x for x in channels if x != c]
        for r in range(len(others) + 1):
            for S in combinations(others, r):
                w = factorial(r) * factorial(n - r - 1) / factorial(n)
                shap[c] += w * (v(set(S) | {c}) - v(set(S)))
    df = pd.DataFrame({"channel": channels, "shapley_revenue": [shap[c] for c in channels]})
    total = df["shapley_revenue"].sum()
    df["shapley_share"] = (df["shapley_revenue"] / total).round(4) if total else 0.0
    perf = q(con, "select * from marts.mart_channel_performance")
    df = df.merge(perf[["channel", "ad_spend", "signups", "depositors", "revenue", "roi", "cpa"]],
                  on="channel", how="left")
    df["roi"] = df["roi"].fillna(0)
    df = df.sort_values("shapley_share", ascending=False).reset_index(drop=True)
    df["grade"] = pd.cut(df.index, bins=[-1, 1, 3, 5, len(df)], labels=["S", "A", "B", "C"])
    df["inflation_flag"] = (df["shapley_share"] < df["shapley_share"].median()) & (df["roi"] < df["roi"].median())
    return df


# ----------------------------------------------------------------
# 6.5 LTV: BG/NBD + Gamma-Gamma vs ML regression
# ----------------------------------------------------------------
def ltv_models(con) -> dict:
    df = q(con, """
        select user_id, register_date, register_channel, register_device_type,
               kyc_area, frequency, monetary, recency_days, tx_cnt, gmv, revenue,
               ltv_30d, ltv_90d, first_trade_time
        from marts.mart_user_360 where is_trader = 1
    """)
    df["register_date"] = pd.to_datetime(df["register_date"])
    cat = ["register_channel", "register_device_type", "kyc_area"]
    num = ["frequency", "monetary", "recency_days", "tx_cnt", "gmv", "revenue"]
    X = pd.concat([df[num].fillna(0), pd.get_dummies(df[cat], drop_first=True)], axis=1)
    y = df["ltv_90d"].fillna(0)
    cutoff = df["register_date"].quantile(0.8)
    tr, te = df["register_date"] <= cutoff, df["register_date"] > cutoff
    from scipy.stats import spearmanr
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    try:
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42, verbose=-1)
        algo = "LightGBM"
    except Exception:
        from sklearn.ensemble import HistGradientBoostingRegressor
        model = HistGradientBoostingRegressor(random_state=42)
        algo = "HistGradientBoosting(GBDT fallback)"
    model.fit(X[tr], y[tr])
    pred = np.clip(model.predict(X[te]), 0, None)
    ml_metrics = {"model": algo, "MAE": round(float(mean_absolute_error(y[te], pred)), 4),
                  "RMSE": round(float(np.sqrt(mean_squared_error(y[te], pred))), 4),
                  "Spearman": round(float(spearmanr(y[te], pred).statistic), 4),
                  "n_train": int(tr.sum()), "n_test": int(te.sum())}

    # ---- BG/NBD + Gamma-Gamma ----
    tx = q(con, "select user_id, tx_time, quote_amt from staging.stg_transactions")
    anchor = pd.to_datetime(tx["tx_time"]).max()
    tx["tx_time"] = pd.to_datetime(tx["tx_time"])
    g = tx.groupby("user_id").agg(first=("tx_time", "min"), last=("tx_time", "max"),
                                   n=("tx_id" if "tx_id" in tx.columns else "quote_amt", "count"),
                                   monetary=("quote_amt", "mean"))
    summary = pd.DataFrame({
        "frequency": (g["n"] - 1).clip(lower=0),
        "recency": (g["last"] - g["first"]).dt.days,
        "T": (anchor - g["first"]).dt.days.clip(lower=1),
        "monetary_value": g["monetary"],
    })
    bg_metrics = {"model": "BG/NBD + Gamma-Gamma", "status": "skipped"}
    try:
        from lifetimes import BetaGeoFitter, GammaGammaFitter
        bgf = None
        for pen in (0.5, 1.0, 2.0):
            try:
                cand = BetaGeoFitter(penalizer_coef=pen)
                cand.fit(summary["frequency"], summary["recency"], summary["T"], show_progress=False)
                bgf = cand
                break
            except Exception:
                continue
        if bgf is None:
            raise RuntimeError("BG/NBD failed to converge after penalizer retries")
        pred_purchases = bgf.predict(90, summary["frequency"], summary["recency"], summary["T"])
        repeat = summary[summary["frequency"] > 0]
        ggf = GammaGammaFitter(penalizer_coef=0.01)
        ggf.fit(repeat["frequency"], repeat["monetary_value"])
        clv = ggf.customer_lifetime_value(
            bgf, repeat["frequency"], repeat["recency"], repeat["T"],
            repeat["monetary_value"], time=3, discount_rate=0.01) * 0.001  # spend -> fee revenue
        actual = df.set_index("user_id")["ltv_90d"]
        joined = clv.to_frame("predicted_clv").join(actual, how="inner").dropna()
        bg_metrics = {"model": "BG/NBD + Gamma-Gamma", "status": "ok",
                      "MAE": round(float(mean_absolute_error(joined["ltv_90d"], joined["predicted_clv"])), 4),
                      "RMSE": round(float(np.sqrt(mean_squared_error(joined["ltv_90d"], joined["predicted_clv"]))), 4),
                      "Spearman": round(float(spearmanr(joined["ltv_90d"], joined["predicted_clv"]).statistic), 4),
                      "n_train": int(len(summary)), "n_test": int(len(joined))}
    except Exception as exc:  # pragma: no cover
        bg_metrics["error"] = str(exc)[:200]

    pred_df = df.loc[te, ["user_id", "ltv_90d"]].copy()
    pred_df["predicted_ltv_90d"] = pred
    metrics = pd.DataFrame([ml_metrics, bg_metrics])
    return {"metrics": metrics, "predictions": pred_df, "cutoff": str(cutoff.date())}


# ----------------------------------------------------------------
# 6.7 Funnel attribution + Cox survival (hazard ratios)
# ----------------------------------------------------------------
def survival_cox(con) -> pd.DataFrame:
    df = q(con, """
        select user_id, register_time, kyc_finish_time, first_deposit_time,
               register_channel, register_device_type, kyc_area, is_robot
        from marts.mart_user_360
    """)
    df["register_time"] = pd.to_datetime(df["register_time"])
    df["kyc_finish_time"] = pd.to_datetime(df["kyc_finish_time"])
    df["first_deposit_time"] = pd.to_datetime(df["first_deposit_time"])
    anchor = df["register_time"].max() + pd.Timedelta(days=1)
    end = df["first_deposit_time"].fillna(df["kyc_finish_time"]).fillna(anchor)
    df["duration"] = ((end - df["register_time"]).dt.total_seconds() / 86400).clip(lower=1)
    df["event"] = df["first_deposit_time"].notna().astype(int)
    feats = pd.get_dummies(df[["register_channel", "register_device_type", "kyc_area"]], drop_first=True)
    feats["is_robot"] = df["is_robot"].astype(int)
    feats["duration"] = df["duration"].values
    feats["event"] = df["event"].values
    from lifelines import CoxPHFitter
    cph = CoxPHFitter(penalizer=0.01)
    cph.fit(feats, duration_col="duration", event_col="event")
    s = cph.summary[["coef", "exp(coef)", "p"]].copy()
    s.columns = ["coef", "hazard_ratio", "p_value"]
    s["hazard_ratio"] = s["hazard_ratio"].round(3)
    s["p_value"] = s["p_value"].round(5)
    return s.sort_values("hazard_ratio", ascending=False).reset_index().rename(columns={"index": "feature"})


# ----------------------------------------------------------------
# 6.6 ROI variation attribution waterfall (ANOVA + contribution)
# ----------------------------------------------------------------
def roi_waterfall(con) -> dict:
    perf = q(con, "select * from marts.mart_channel_performance where ad_spend > 0")
    total_spend = perf["ad_spend"].sum()
    total_rev = perf["revenue"].sum()
    overall = total_rev / total_spend if total_spend else 0
    perf["spend_share"] = perf["ad_spend"] / total_spend if total_spend else 0
    perf["contribution"] = (perf["roi"].fillna(0) - overall) * perf["spend_share"]
    waterfall = perf[["channel", "roi", "spend_share", "contribution"]].copy()
    waterfall["cumulative"] = waterfall["contribution"].cumsum()

    daily = q(con, "select * from marts.mart_budget_elasticity")
    daily["cvr"] = daily["conversions"] / daily["clicks"].replace(0, np.nan)
    anova_rows = []
    try:
        import statsmodels.api as sm
        from statsmodels.formula.api import ols
        m = ols("conversions_per_dollar ~ C(channel)", data=daily.dropna()).fit()
        tab = sm.stats.anova_lm(m, typ=2).reset_index().rename(columns={"index": "effect"})
        anova_rows = tab.to_dict("records")
    except Exception as exc:
        anova_rows = [{"error": str(exc)[:200]}]
    return {"overall_roi": round(float(overall), 4), "waterfall": waterfall,
            "anova": pd.DataFrame(anova_rows)}


# ----------------------------------------------------------------
# 6.8 Campaign / airdrop incremental ROI (DID)
# ----------------------------------------------------------------
def campaign_incremental_roi(con) -> dict:
    camp = q(con, """
        select c.campaign_id, c.name, c.channel, c.start_time, c.end_time, c.budget,
               count(cu.user_id) as participants, sum(cu.reward_amt) as reward_cost
        from staging.stg_campaigns c
        join staging.stg_campaign_users cu using (campaign_id)
        group by 1,2,3,4,5,6 order by participants desc limit 5
    """)
    tx = q(con, "select user_id, tx_time, quote_amt from staging.stg_transactions")
    tx["tx_time"] = pd.to_datetime(tx["tx_time"])
    users = q(con, "select user_id, register_channel, register_time from staging.stg_users")
    cu = q(con, "select campaign_id, user_id from staging.stg_campaign_users")
    rows = []
    for _, c in camp.iterrows():
        start = pd.to_datetime(c["start_time"])
        pre0, post1 = start - pd.Timedelta(days=28), start + pd.Timedelta(days=28)
        treated = set(cu.loc[cu["campaign_id"] == c["campaign_id"], "user_id"])
        control = set(users.loc[(users["register_channel"] == c["channel"]) &
                                (~users["user_id"].isin(treated)), "user_id"])
        def mean_rev(group, lo, hi):
            sub = tx[tx["user_id"].isin(group) & (tx["tx_time"] >= lo) & (tx["tx_time"] < hi)]
            return sub["quote_amt"].sum() / max(len(group), 1)
        tp, tq = mean_rev(treated, pre0, start), mean_rev(treated, start, post1)
        cp, cq = mean_rev(control, pre0, start), mean_rev(control, start, post1)
        did = (tq - tp) - (cq - cp)
        cost = float(c["reward_cost"] or 0)
        rows.append({"campaign_id": c["campaign_id"], "name": c["name"], "channel": c["channel"],
                     "participants": int(c["participants"]), "cost": round(cost, 2),
                     "treated_pre": round(tp, 2), "treated_post": round(tq, 2),
                     "control_pre": round(cp, 2), "control_post": round(cq, 2),
                     "incremental_per_user": round(did, 2),
                     "incremental_revenue": round(did * len(treated), 2),
                     "incremental_roi": round(did * len(treated) / cost, 4) if cost else None})
    return {"table": pd.DataFrame(rows)}


# ----------------------------------------------------------------
# 6.11 Ad cost vs social performance (4-step correlation)
# ----------------------------------------------------------------
def ads_social_correlation(con) -> dict:
    ads = q(con, "select * from marts.mart_budget_elasticity")
    ads["date"] = pd.to_datetime(ads["date"])
    daily = ads.groupby("date").agg(spend=("spend", "sum"), clicks=("clicks", "sum"),
                                    conversions=("conversions", "sum")).reset_index()
    daily["cpc"] = daily["spend"] / daily["clicks"].replace(0, np.nan)
    social = q(con, "select * from staging.stg_social")
    social["date"] = pd.to_datetime(social["date"])
    soc = social.groupby("date").agg(engagements=("engagements", "sum"),
                                     reach=("reach", "sum")).reset_index()
    df = daily.merge(soc, on="date", how="inner").sort_values("date")
    df["eng_rate"] = df["engagements"] / df["reach"].replace(0, np.nan)
    df = df.dropna(subset=["eng_rate", "cpc"])

    base = float(df["eng_rate"].corr(df["cpc"]))
    lag_rows = []
    for k in range(0, 8):
        c = float(df["eng_rate"].shift(k).corr(df["cpc"]))
        lag_rows.append({"lag_days": k, "corr": round(c, 4)})
    # partial correlation controlling for budget
    def resid(y, x):
        import statsmodels.api as sm
        return sm.OLS(y, sm.add_constant(x)).fit().resid
    pr = float(np.corrcoef(resid(df["eng_rate"], df["spend"]),
                           resid(df["cpc"], df["spend"]))[0, 1])
    seg_rows = []
    for ad_type in ["brand", "generic"]:
        sub = ads[ads["ad_type"] == ad_type].groupby("date").agg(
            spend=("spend", "sum"), clicks=("clicks", "sum")).reset_index()
        sub["cpc"] = sub["spend"] / sub["clicks"].replace(0, np.nan)
        s = sub.merge(df[["date", "eng_rate"]], on="date", how="inner").dropna()
        seg_rows.append({"segment": ad_type, "corr": round(float(s["eng_rate"].corr(s["cpc"])), 4),
                         "n_days": int(len(s))})
    matrix = pd.DataFrame([
        {"step": "1_base", "segment": "all", "corr": round(base, 4), "n_days": len(df)},
        {"step": "2_lag_best", "segment": "all",
         "corr": min(lag_rows, key=lambda r: r["corr"])["corr"],
         "best_lag_days": min(lag_rows, key=lambda r: r["corr"])["lag_days"], "n_days": len(df)},
        {"step": "3_partial", "segment": "all", "corr": round(pr, 4), "n_days": len(df)},
        *[{"step": "4_segment", **r} for r in seg_rows],
    ])
    return {"matrix": matrix, "lag_table": pd.DataFrame(lag_rows), "daily": df}


# ----------------------------------------------------------------
# 6.12 Page module efficiency + DEA
# ----------------------------------------------------------------
def module_efficiency(con) -> dict:
    df = q(con, "select * from marts.mart_module_efficiency")
    from scipy.optimize import linprog
    effs = []
    X = np.column_stack([df["impressions"].to_numpy(float), df["area_pct"].to_numpy(float) * 1e6])
    Y = df["clicks"].to_numpy(float).reshape(-1, 1)
    n = len(df)
    for i in range(n):
        # min theta  s.t.  sum_j lam_j x_j <= theta x_i ; sum_j lam_j y_j >= y_i
        c = np.r_[np.zeros(n), 1.0]
        A_ub = np.vstack([np.c_[X.T, -X[i]], np.c_[-Y.T, np.zeros(1)]])
        b_ub = np.r_[np.zeros(X.shape[1]), -Y[i, 0]]
        bounds = [(0, None)] * n + [(0, None)]
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
        effs.append(float(res.x[-1]) if res.success else np.nan)
    df["dea_efficiency"] = np.round(effs, 4)
    df["efficiency_rank"] = df["dea_efficiency"].rank(ascending=False, method="min")
    return {"table": df.sort_values("dea_efficiency", ascending=False)}


# ----------------------------------------------------------------
# 6.13 CTA full-factorial + random-forest importance
# ----------------------------------------------------------------
def cta_factorial(con) -> dict:
    df = q(con, "select * from staging.stg_cta")
    main = []
    for factor in ["cta_color", "cta_copy", "cta_size"]:
        g = df.groupby(factor).agg(n=("converted", "size"), cvr=("converted", "mean")).reset_index()
        g["factor"] = factor
        g = g.rename(columns={factor: "level"})
        main.append(g[["factor", "level", "n", "cvr"]])
    main_df = pd.concat(main, ignore_index=True)
    main_df["cvr"] = main_df["cvr"].round(4)
    # two-way interactions
    inter = (df.groupby(["cta_color", "cta_size"])["converted"].mean()
               .reset_index().rename(columns={"converted": "cvr"}))
    inter["cvr"] = inter["cvr"].round(4)
    # ANOVA main effects
    anova = None
    try:
        import statsmodels.api as sm
        from statsmodels.formula.api import ols
        m = ols("converted ~ C(cta_color) + C(cta_copy) + C(cta_size) + C(cta_color):C(cta_size)", data=df).fit()
        anova = sm.stats.anova_lm(m, typ=2).reset_index().rename(columns={"index": "effect"})
    except Exception:
        pass
    # random forest importance
    from sklearn.ensemble import RandomForestClassifier
    X = pd.get_dummies(df[["cta_color", "cta_copy", "cta_size"]], drop_first=False)
    rf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    rf.fit(X, df["converted"])
    imp = pd.DataFrame({"feature": X.columns, "importance": np.round(rf.feature_importances_, 3)})
    return {"main_effects": main_df, "interaction": inter, "anova": anova,
            "importance": imp.sort_values("importance", ascending=False)}


# ----------------------------------------------------------------
# 6.14 Multiple logistic regression + interactions
# ----------------------------------------------------------------
def logistic_model(con) -> pd.DataFrame:
    df = q(con, """
        select is_deposited, register_channel, register_device_type, kyc_area, is_robot
        from marts.mart_user_360
    """)
    import statsmodels.formula.api as smf
    formula = ("is_deposited ~ C(register_channel) + C(register_device_type) + "
               "C(kyc_area) + is_robot + C(register_channel):C(register_device_type)")
    m = smf.logit(formula, data=df).fit(disp=False, maxiter=200)
    res = pd.DataFrame({"term": m.params.index, "coef": m.params.values,
                        "odds_ratio": np.exp(m.params.values), "p_value": m.pvalues.values})
    res[["coef", "odds_ratio", "p_value"]] = res[["coef", "odds_ratio", "p_value"]].round(4)
    return res.sort_values("p_value")


# ----------------------------------------------------------------
# 6.15 A/B test
# ----------------------------------------------------------------
def ab_test(con) -> dict:
    df = q(con, "select variant, converted from staging.stg_ab")
    g = df.groupby("variant")["converted"].agg(["count", "sum", "mean"]).reset_index()
    g.columns = ["variant", "n", "conversions", "cvr"]
    c = g.set_index("variant").loc["control"]
    t = g.set_index("variant").loc["treat"]
    p1, p2 = c["cvr"], t["cvr"]
    p = (c["conversions"] + t["conversions"]) / (c["n"] + t["n"])
    se = np.sqrt(p * (1 - p) * (1 / c["n"] + 1 / t["n"]))
    z = (p2 - p1) / se if se else np.nan
    from scipy.stats import chi2_contingency, norm
    pval = float(2 * (1 - norm.cdf(abs(z)))) if se else np.nan
    ci = (p2 - p1 - 1.96 * se, p2 - p1 + 1.96 * se)
    chi2, srm_p, _, _ = chi2_contingency([[c["conversions"], c["n"] - c["conversions"]],
                                          [t["conversions"], t["n"] - t["conversions"]]])
    srm_chi2, srm_p2, _, _ = chi2_contingency([[c["n"], c["n"]], [t["n"], t["n"]]])
    return {"table": g.round(4), "abs_lift": round(float(p2 - p1), 4),
            "rel_lift_pct": round(float((p2 - p1) / p1 * 100), 2) if p1 else None,
            "z": round(float(z), 3), "p_value": pval,
            "ci95": (round(float(ci[0]), 4), round(float(ci[1]), 4)),
            "srm_p_value": round(float(srm_p2), 4)}


# ----------------------------------------------------------------
# 6.18 Budget elasticity + management simulator
# ----------------------------------------------------------------
def budget_elasticity(con) -> dict:
    import statsmodels.api as sm
    daily = q(con, "select * from marts.mart_budget_elasticity")
    daily["date"] = pd.to_datetime(daily["date"])
    rows = []
    for ch, g in daily.groupby("channel"):
        if len(g) < 5:
            continue
        X = sm.add_constant(np.log1p(g["spend"]))
        m = sm.OLS(g["conversions"], X).fit()
        b0, b1 = float(m.params.iloc[0]), float(m.params.iloc[1])
        cur_spend = float(g["spend"].mean())
        cur_conv = float(g["conversions"].mean())
        rows.append({"channel": ch, "intercept": round(b0, 4), "log_spend_coef": round(b1, 4),
                     "current_daily_spend": round(cur_spend, 2),
                     "current_daily_conversions": round(cur_conv, 2),
                     "marginal_conv_per_dollar": round(b1 / (cur_spend + 1), 6)})
    params = pd.DataFrame(rows)

    total = daily.groupby("date")["conversions"].sum().asfreq("D").fillna(0)
    method = "STL(period=7)"
    try:
        from statsmodels.tsa.seasonal import STL
        stl = STL(total, period=7, robust=True).fit()
        decomp = pd.DataFrame({"date": total.index, "observed": total.values,
                               "trend": stl.trend.values, "seasonal": stl.seasonal.values,
                               "resid": stl.resid.values})
    except Exception as exc:
        decomp = pd.DataFrame({"date": total.index, "observed": total.values})
        method = f"fallback: {exc}"
    return {"params": params, "decomposition": decomp, "method": method}


def simulate_budget(params: pd.DataFrame, assumptions: dict) -> pd.DataFrame:
    """Pure function used by the dashboard "what-if" simulator."""
    rows = []
    for ch, new_spend in assumptions.items():
        sub = params[params["channel"] == ch]
        if sub.empty:
            continue
        r = sub.iloc[0]
        pred = r["intercept"] + r["log_spend_coef"] * np.log1p(new_spend)
        rows.append({"channel": ch, "current_daily_spend": r["current_daily_spend"],
                     "assumed_daily_spend": new_spend,
                     "current_daily_conversions": r["current_daily_conversions"],
                     "predicted_daily_conversions": round(max(pred, 0), 2),
                     "delta_conversions": round(max(pred, 0) - r["current_daily_conversions"], 2)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------
# 6.19 OKR attribution stripping / assist value
# ----------------------------------------------------------------
def okr_attribution(con) -> pd.DataFrame:
    attr = attribution_models(con)["table"].set_index("channel")
    shap = channel_shapley(con).set_index("channel")
    out = pd.DataFrame({
        "last_touch_share": attr["last_touch"],
        "markov_share": attr["markov_chain"],
        "shapley_share": shap["shapley_share"],
    }).fillna(0)
    out["markov_vs_last_pct"] = ((out["markov_share"] - out["last_touch_share"]) /
                                 out["last_touch_share"].replace(0, np.nan) * 100).round(2)
    out["shapley_vs_last_pct"] = ((out["shapley_share"] - out["last_touch_share"]) /
                                  out["last_touch_share"].replace(0, np.nan) * 100).round(2)
    return out.sort_values("markov_share", ascending=False)


# ----------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------
def run_all(con) -> tuple[dict, dict]:
    tasks = {
        "funnel": funnel_analysis,
        "rfm": rfm_segmentation,
        "behaviour": behavioural_sequences,
        "flow": flow_paths,
        "attribution": attribution_models,
        "shapley": channel_shapley,
        "ltv": ltv_models,
        "survival": survival_cox,
        "roi_waterfall": roi_waterfall,
        "campaign": campaign_incremental_roi,
        "ads_social": ads_social_correlation,
        "modules": module_efficiency,
        "cta": cta_factorial,
        "logistic": logistic_model,
        "ab": ab_test,
        "budget": budget_elasticity,
        "okr": okr_attribution,
    }
    results, errors = {}, {}
    for name, fn in tasks.items():
        try:
            results[name] = fn(con)
        except Exception as exc:  # keep the pipeline running, report upstream
            errors[name] = f"{type(exc).__name__}: {exc}"
            results[name] = None
    return results, errors
