#!/usr/bin/env python3
"""Streamlit dashboard backed by dbt marts (DuckDB) with a Redis cache."""
from __future__ import annotations

import hashlib
import pickle
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import settings  # noqa: E402

st.set_page_config(page_title="CEX Customer Analytics", page_icon="📊", layout="wide")


@st.cache_resource
def get_con():
    return duckdb.connect(settings.DUCKDB_PATH, read_only=True)


@st.cache_resource
def get_redis():
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=False)
        client.ping()
        return client
    except Exception:
        return None


def cached_query(sql: str, ttl: int | None = None) -> pd.DataFrame:
    """Redis first, DuckDB second. Cache key = sha1(sql)."""
    ttl = ttl or settings.CACHE_TTL_SECONDS
    client = get_redis()
    key = "ca:" + hashlib.sha1(sql.encode()).hexdigest()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return pickle.loads(raw)
        except Exception:
            pass
    df = get_con().execute(sql).df()
    if client is not None:
        try:
            client.setex(key, ttl, pickle.dumps(df))
        except Exception:
            pass
    return df


@st.cache_data(ttl=300)
def load_kpis():
    return cached_query("""
        select count(*) as users, sum(is_kyc) as kyc_users,
               sum(is_deposited) as depositors, sum(is_trader) as traders,
               sum(gmv) as gmv, sum(revenue) as revenue,
               avg(ltv_90d) as avg_ltv, avg(churn_90d) as churn_rate
        from marts.mart_user_360
    """).iloc[0]


st.sidebar.title("📊 CEX Customer Analytics")
page = st.sidebar.radio("导航", ["总览 Overview", "用户分群 Segmentation", "归因 Attribution",
                                  "渠道 Channels", "实验 Experiments", "预算模拟 Budget", "用户 360"])
st.sidebar.caption(f"Redis: {'connected' if get_redis() is not None else 'offline (fallback)'}")
st.sidebar.caption(f"DuckDB: {Path(settings.DUCKDB_PATH).name}")


if page == "总览 Overview":
    st.title("交易所用户全生命周期 · 总览")
    k = load_kpis()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("注册用户", f"{int(k['users']):,}")
    c2.metric("首次入金转化率", f"{k['depositors']/k['users']:.1%}" if k['users'] else "—")
    c3.metric("交易用户", f"{int(k['traders']):,}")
    c4.metric("手续费收入", f"${k['revenue']:,.0f}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GMV", f"${k['gmv']:,.0f}")
    c2.metric("平均 LTV(90d)", f"${k['avg_ltv']:.2f}")
    c3.metric("90 天流失率", f"{k['churn_rate']:.1%}")
    c4.metric("KYC 完成率", f"{k['kyc_users']/k['users']:.1%}" if k['users'] else "—")

    st.subheader("转化漏斗（最后一天快照）")
    f = cached_query("select * from marts.mart_funnel_daily order by period")
    last = f[f["period"] == f["period"].max()]
    fig = go.Figure(go.Funnel(y=last["step"], x=last["user_cnt"],
                              textinfo="value+percent previous"))
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("每日漏斗趋势")
    piv = f.pivot(index="period", columns="step", values="user_cnt").reset_index()
    st.plotly_chart(px.line(piv, x="period", y=[c for c in piv.columns if c != "period"],
                            labels={"value": "users", "variable": "step"}), use_container_width=True)

elif page == "用户分群 Segmentation":
    st.title("RFM 分群")
    seg = cached_query("select * from marts.mart_segment_summary order by revenue desc")
    st.dataframe(seg, use_container_width=True)
    st.plotly_chart(px.bar(seg, x="rfm_segment", y="users", color="avg_ltv_90d",
                           title="各分群人数与平均 LTV"), use_container_width=True)
    st.plotly_chart(px.treemap(seg, path=["rfm_segment"], values="revenue",
                               title="各分群收入贡献"), use_container_width=True)

elif page == "归因 Attribution":
    st.title("流量归因模型对比")
    path = settings.REPORTS_DIR / "attribution_comparison.csv"
    if path.exists():
        df = pd.read_csv(path)
        st.dataframe(df, use_container_width=True)
        fig = go.Figure()
        for col in ["first_touch", "last_touch", "position_based", "markov_chain"]:
            if col in df.columns:
                fig.add_bar(x=df["channel"], y=df[col], name=col)
        fig.update_layout(barmode="group", title="首次 / 末次 / 位置 / 马尔可夫 归因份额")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("请先运行 `python main.py` 生成归因报告。")

elif page == "渠道 Channels":
    st.title("渠道质量")
    ch = cached_query("select * from marts.mart_channel_performance order by roi desc nulls last")
    st.dataframe(ch, use_container_width=True)
    st.plotly_chart(px.scatter(ch, x="ad_spend", y="revenue", size="signups", color="roi",
                               hover_name="channel", title="花费 vs 收入"), use_container_width=True)
    path = settings.REPORTS_DIR / "channel_shapley.csv"
    if path.exists():
        st.subheader("Shapley 归因与渠道分级")
        st.dataframe(pd.read_csv(path), use_container_width=True)

elif page == "实验 Experiments":
    st.title("实验结果")
    exp = cached_query("select * from marts.mart_experiment_results order by experiment, variant")
    st.dataframe(exp, use_container_width=True)
    st.plotly_chart(px.bar(exp, x="variant", y="cvr", color="experiment",
                           title="各实验变体转化率"), use_container_width=True)
    path = settings.REPORTS_DIR / "cta_feature_importance.csv"
    if path.exists():
        st.subheader("CTA 属性重要性（随机森林）")
        st.dataframe(pd.read_csv(path), use_container_width=True)

elif page == "预算模拟 Budget":
    st.title("季度预算弹性模拟器")
    daily = cached_query("select * from marts.mart_budget_elasticity")
    daily["date"] = pd.to_datetime(daily["date"])
    params = []
    for ch, g in daily.groupby("channel"):
        if len(g) < 5:
            continue
        b1, b0 = np.polyfit(np.log1p(g["spend"]), g["conversions"], 1)
        params.append({"channel": ch, "intercept": b0, "log_spend_coef": b1,
                       "current_daily_spend": g["spend"].mean(),
                       "current_daily_conversions": g["conversions"].mean()})
    params = pd.DataFrame(params)
    st.dataframe(params.round(3), use_container_width=True)
    st.subheader("调整每日预算（美元）")
    assumptions = {}
    cols = st.columns(4)
    for i, r in params.iterrows():
        assumptions[r["channel"]] = cols[i % 4].number_input(
            r["channel"], min_value=0.0, value=float(round(r["current_daily_spend"], 2)), step=50.0)
    if st.button("运行模拟", type="primary"):
        rows = []
        for _, r in params.iterrows():
            s = assumptions[r["channel"]]
            pred = max(r["intercept"] + r["log_spend_coef"] * np.log1p(s), 0)
            rows.append({"channel": r["channel"], "current_daily_spend": r["current_daily_spend"],
                         "assumed_daily_spend": s, "current_daily_conversions": r["current_daily_conversions"],
                         "predicted_daily_conversions": round(pred, 2),
                         "delta_conversions": round(pred - r["current_daily_conversions"], 2)})
        res = pd.DataFrame(rows)
        st.dataframe(res, use_container_width=True)
        st.metric("预计每日总转化变化", f"{res['delta_conversions'].sum():+.1f}")

elif page == "用户 360":
    st.title("用户 360 视图")
    uid = st.text_input("输入 user_id，例如 u0000001")
    if uid:
        df = cached_query(f"select * from marts.mart_user_360 where user_id = '{uid}'")
        if df.empty:
            st.warning("未找到该用户")
        else:
            st.dataframe(df.T, use_container_width=True)
    else:
        st.dataframe(cached_query("select * from marts.mart_user_360 limit 100"), use_container_width=True)
