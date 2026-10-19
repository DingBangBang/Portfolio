#!/usr/bin/env python3
"""Bilingual single-page data story for the CEX lifecycle analytics project."""
from __future__ import annotations

import hashlib
import json
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
from dashboards.i18n import GITHUB, SECTIONS, UI  # noqa: E402

st.set_page_config(page_title="CEX Customer Analytics", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], section.main > div,
section[data-testid=stMain] {scroll-behavior: smooth;}
.block-container {padding-top: 1.6rem; max-width: 1480px;}
[data-testid="stMetric"] {
    background: linear-gradient(180deg,#ffffff,#f6f8fa);
    border: 1px solid #e5e7eb; border-radius: 14px;
    padding: 14px 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
[data-testid="stMetricLabel"] {color:#57606a;}
.tag {display:inline-block; background:#eef2ff; color:#3730a3; padding:3px 11px;
      border-radius:999px; font-size:12px; font-weight:700; letter-spacing:.03em;}
.ctx {background:#f8fafc; border-left:4px solid #94a3b8; padding:11px 15px;
      border-radius:8px; margin:6px 0 8px 0; font-size:.94rem;}
.ctx.alt {border-left-color:#f59e0b; background:#fffbeb;}
.fields {color:#57606a; font-size:.88rem; border-left:3px solid #d0d7de;
         padding:6px 0 6px 12px; margin:6px 0 14px 0; background:#fafbfc;}
.insight {background:#ffffff; border:1px solid #e5e7eb; border-radius:14px;
          padding:6px 18px 10px 18px; margin:8px 0 26px 0; box-shadow:0 1px 2px rgba(16,24,40,.04);}
.ins {padding:11px 0 11px 14px; margin:6px 0; font-size:.95rem; line-height:1.55;}
.ins.what {border-left:4px solid #2563eb;}
.ins.why {border-left:4px solid #d97706;}
.ins.act {border-left:4px solid #059669;}
.ins .lbl {font-weight:700;}
.hero {background:linear-gradient(120deg,#0b1f3a 0%,#143d6b 55%,#1d6fb8 100%);
       color:#fff; padding:26px 30px; border-radius:18px; margin:6px 0 18px 0;}
.hero h1 {color:#fff; margin:0 0 6px 0; font-size:2rem;}
.hero p {color:#cfe3ff; margin:0; font-size:1rem;}
.warnbox {background:#fff8e6; border-left:5px solid #d4a72c; padding:12px 16px;
          border-radius:8px; margin:8px 0 18px 0;}
a {text-decoration:none;}
</style>
""", unsafe_allow_html=True)


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


def _rget(key):
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return pickle.loads(raw) if raw else None
    except Exception:
        return None


def _rset(key, value, ttl=300):
    client = get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl, pickle.dumps(value))
    except Exception:
        pass


@st.cache_data(ttl=300)
def query(sql: str) -> pd.DataFrame:
    key = "q:" + hashlib.sha1(sql.encode()).hexdigest()
    cached = _rget(key)
    if cached is not None:
        return cached
    df = get_con().execute(sql).df()
    _rset(key, df)
    return df


@st.cache_data(ttl=300)
def load_csv(name: str) -> pd.DataFrame:
    path = settings.RESULTS_DIR / name
    if not path.exists():
        return pd.DataFrame()
    key = f"file:{name}:{int(path.stat().st_mtime)}"
    cached = _rget(key)
    if cached is not None:
        return cached
    df = pd.read_csv(path)
    _rset(key, df)
    return df


@st.cache_data(ttl=300)
def load_json(name: str) -> dict:
    path = settings.RESULTS_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x, digits: int = 2) -> str:
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except Exception:
        return "—"


def fmt_pct_df(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].map(lambda v: pct(v))
    for c in out.columns:
        if c not in cols and pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(2)
    return out


def warn(text: str):
    st.markdown(f"<div class='warnbox'>{text}</div>", unsafe_allow_html=True)


def chart(fig, height: int = 420):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=52, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------- language
_query_lang = str(st.query_params.get("lang", "zh")).lower()
_default = 1 if _query_lang.startswith("en") else 0
_top_left, _top_right = st.columns([6, 2])
with _top_right:
    _choice = st.radio(UI["zh"]["language"], ["中文", "English"], index=_default,
                       horizontal=True, label_visibility="collapsed")
LANG = "en" if _choice == "English" else "zh"
T = UI[LANG]
ZH = LANG == "zh"


def label(zh: str, en: str) -> str:
    return zh if ZH else en


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("# 📊 CEX Analytics")
    st.caption(label("单页滚动 · 点击平滑跳转", "Single page · smooth anchor jump"))
    _stage = None
    for _sec in SECTIONS:
        if _sec["stage"] != _stage:
            _stage = _sec["stage"]
            st.markdown(f"**{T['stages'][_stage]}**")
        st.markdown(f"- [{_sec['module']} {_sec[LANG]['title']}](#sec-{_sec['id']})")
    st.divider()
    st.caption(f"Redis: {'✅ ' + T['redis_on'] if get_redis() is not None else '⚠ ' + T['redis_off']}")
    st.caption(f"DuckDB: {Path(settings.DUCKDB_PATH).name}")
    st.divider()
    st.markdown(f"**{T['docs']}**")
    for _name, _file in [("README", "README.md"), ("Development log", "docs/development_log.md"),
                         ("Data dictionary", "docs/data_dictionary.md"),
                         ("Scheduling", "docs/scheduling.md")]:
        st.markdown(f'<a href="{GITHUB}/{_file}" target="_blank">↗ {_name}</a>',
                    unsafe_allow_html=True)

kpi = load_json("kpi_summary.json")

st.markdown(f"""
<div class="hero">
  <h1>{T['app_title']}</h1>
  <p>{T['app_subtitle']}</p>
</div>
""", unsafe_allow_html=True)

if kpi:
    c = st.columns(4)
    c[0].metric(T["kpi_users"], f"{int(kpi['users']):,}")
    c[1].metric(T["kpi_deposit"], pct(kpi["deposit_rate"]))
    c[2].metric(T["kpi_traders"], f"{int(kpi['traders']):,}")
    c[3].metric(T["kpi_revenue"], f"${kpi['revenue']:,.2f}")
    c = st.columns(4)
    c[0].metric(T["kpi_gmv"], f"${kpi['gmv']/1e6:.2f}M")
    c[1].metric(T["kpi_ltv"], f"${kpi['avg_ltv_90d']:.2f}")
    c[2].metric(T["kpi_churn"], pct(kpi["churn_rate"]))
    c[3].metric(T["kpi_kyc"], pct(kpi["kyc_rate"]))
else:
    warn("KPI missing — run `python main.py` first.")


def render_section(sec: dict):
    copy = sec[LANG]
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(f'<span class="tag">{sec["module"]}</span>', unsafe_allow_html=True)
    st.header(f"{sec['module']} · {copy['title']}", anchor=f"sec-{sec['id']}")
    st.markdown(f"<div class='ctx'><b>{T['purpose']}</b><br>{copy['purpose']}</div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='ctx alt'><b>{T['analogy']}</b><br>{copy['analogy']}</div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='fields'><b>{T['fields']}</b>：{copy['fields']}</div>",
                unsafe_allow_html=True)
    renderer = CHARTS.get(sec["id"])
    if renderer:
        renderer()
    st.markdown(
        "<div class='insight'>"
        f"<div class='ins what'><span class='lbl'>{T['what']}</span><br>{copy['what']}</div>"
        f"<div class='ins why'><span class='lbl'>{T['why']}</span><br>{copy['why']}</div>"
        f"<div class='ins act'><span class='lbl'>{T['action']}</span><br>{copy['action']}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


CHARTS: dict = {}


def register(name: str):
    def deco(fn):
        CHARTS[name] = fn
        return fn
    return deco


@register("overview")
def _overview():
    manifest_path = ROOT / "data" / "raw" / "_manifest.json"
    c1, c2 = st.columns(2)
    with c1:
        if manifest_path.exists():
            counts = json.loads(manifest_path.read_text()).get("row_counts", {})
            m = pd.DataFrame(sorted(counts.items(), key=lambda x: -x[1]),
                             columns=[label("数据表", "Table"), "rows"])
            chart(px.bar(m, x="rows", y=label("数据表", "Table"), orientation="h",
                         title=label("各表行数（全部 ≥ 1,000 行）",
                                     "Rows per table (all ≥ 1,000)"),
                         color="rows", color_continuous_scale="Blues"), 430)
        else:
            warn(label("未找到 data/raw/_manifest.json", "data/raw/_manifest.json not found"))
    with c2:
        if kpi:
            rows = [
                [label("注册 → KYC", "Sign-up → KYC"), pct(kpi["kyc_rate"])],
                [label("注册 → 首充", "Sign-up → deposit"), pct(kpi["deposit_rate"])],
                [label("首充 → 首笔交易", "Deposit → first trade"), pct(kpi["deposit_to_trade_rate"])],
                ["ARPU", f"${kpi['arpu']:.2f}"],
                ["ARPPU", f"${kpi['arppu']:.2f}"],
                ["AOV", f"${kpi['aov']:,.2f}"],
                [label("90 天流失率", "90-day churn"), pct(kpi["churn_rate"])],
            ]
            st.dataframe(pd.DataFrame(rows, columns=[label("核心指标", "Metric"), label("数值", "Value")]),
                         use_container_width=True, hide_index=True, height=430)


@register("funnel")
def _funnel():
    daily = load_csv("funnel_daily.csv")
    last = load_csv("funnel_last_day.csv")
    if daily.empty or last.empty:
        return warn(label("缺少漏斗产物，请先运行 main.py", "Funnel artefact missing; run main.py"))
    last = last.copy()
    last["step"] = last["step"].map(lambda s: {
        "visit": label("访问", "visit"), "register": label("注册", "register"),
        "kyc": "KYC", "deposit": label("首充", "deposit"), "trade": label("交易", "trade")}.get(s, s))
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Funnel(y=last["step"], x=last["user_cnt"],
                                  textinfo="value+percent previous",
                                  marker=dict(color=["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"])))
        fig.update_layout(title=label("最后一天漏斗快照", "Last-day funnel snapshot"))
        chart(fig)
    with c2:
        piv = daily.pivot(index="period", columns="step", values="user_cnt").reset_index()
        chart(px.line(piv, x="period", y=[c for c in piv.columns if c != "period"],
                      title=label("每日漏斗趋势", "Daily funnel trend"),
                      labels={"value": label("人数", "users"), "variable": label("步骤", "step")}))
    st.dataframe(fmt_pct_df(last, ["step_cvr"]), use_container_width=True, hide_index=True)


@register("behaviour")
def _behaviour():
    beh = load_csv("behaviour_tests.csv")
    val = load_csv("behaviour_validation.csv")
    if beh.empty:
        return warn(label("缺少行为分析产物", "Behaviour artefact missing"))
    plot = beh.melt(id_vars="behaviour",
                    value_vars=["deposited_mean", "non_deposited_mean"],
                    var_name="group", value_name="rate")
    plot["group"] = plot["group"].map({"deposited_mean": label("已入金", "Deposited"),
                                       "non_deposited_mean": label("未入金", "Not deposited")})
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(plot, x="behaviour", y="rate", color="group", barmode="group",
                     title=label("注册后 1 小时关键动作", "Key actions in the first hour"),
                     labels={"rate": label("发生率", "incidence"), "behaviour": label("行为", "behaviour")}))
    with c2:
        if not val.empty:
            vp = val.melt(id_vars=["region_group", "behaviour"],
                          value_vars=["deposited_mean", "non_deposited_mean"],
                          var_name="group", value_name="rate")
            vp["group"] = vp["group"].map({"deposited_mean": label("已入金", "Deposited"),
                                           "non_deposited_mean": label("未入金", "Not deposited")})
            chart(px.bar(vp, x="behaviour", y="rate", color="group", facet_col="region_group",
                         barmode="group", title=label("分地区外部验证", "External validation by region"),
                         labels={"rate": label("发生率", "incidence")}))
        else:
            st.info(label("暂无外部验证数据", "No external-validation data"))
    st.dataframe(fmt_pct_df(beh, ["deposited_mean", "non_deposited_mean", "diff"]),
                 use_container_width=True, hide_index=True)


@register("flow")
def _flow():
    edges = load_csv("flow_edges.csv")
    paths = load_csv("flow_top_paths.csv")
    funnel_last = load_csv("funnel_last_day.csv")
    c1, c2 = st.columns(2)
    with c1:
        if edges.empty:
            warn(label("缺少路径数据", "Flow edges missing"))
        else:
            labels = list(pd.unique(pd.concat([edges["event_name"], edges["next_event"]],
                                             ignore_index=True)))
            idx = {lab: i for i, lab in enumerate(labels)}
            fig = go.Figure(go.Sankey(
                node=dict(label=labels, pad=22, thickness=16, color="#93c5fd"),
                link=dict(source=[idx[x] for x in edges["event_name"]],
                          target=[idx[x] for x in edges["next_event"]],
                          value=edges["weight"], color="rgba(37,99,235,0.26)")))
            fig.update_layout(title=label("事件跳转 Sankey 图", "Event transition Sankey"))
            chart(fig, 520)
    with c2:
        if not funnel_last.empty:
            order = ["visit", "register", "kyc", "deposit", "trade"]
            names = {"visit": label("访问", "visit"), "register": label("注册", "register"),
                     "kyc": "KYC", "deposit": label("首充", "deposit"),
                     "trade": label("交易", "trade")}
            d = funnel_last.set_index("step").reindex(order)
            vals = [float(d.loc["visit", "user_cnt"])]
            for i in range(1, len(order)):
                vals.append(float(d.loc[order[i], "user_cnt"] - d.loc[order[i - 1], "user_cnt"]))
            fig = go.Figure(go.Waterfall(
                x=[names[s] for s in order], y=vals, measure=["absolute"] + ["relative"] * 4,
                text=[f"{v:,.0f}" for v in vals], textposition="outside",
                decreasing={"marker": {"color": "#ef4444"}},
                increasing={"marker": {"color": "#10b981"}},
                totals={"marker": {"color": "#2563eb"}}))
            fig.update_layout(title=label("漏斗各步骤流失瀑布", "Funnel step drop waterfall"),
                              yaxis_title=label("人数", "users"))
            chart(fig, 520)
        else:
            warn(label("缺少漏斗快照", "Funnel snapshot missing"))
    if not paths.empty:
        st.dataframe(paths, use_container_width=True, hide_index=True)


@register("attribution")
def _attribution():
    attr = load_csv("attribution_comparison.csv")
    meta = load_json("attribution_meta.json")
    if attr.empty:
        return warn(label("缺少归因产物", "Attribution artefact missing"))
    models = ["first_touch", "last_touch", "position_based", "markov_chain"]
    names = {"first_touch": label("首次", "First"), "last_touch": label("末次", "Last"),
             "position_based": label("位置", "Position"), "markov_chain": "Markov"}
    long = attr.melt(id_vars="channel", value_vars=models, var_name="model", value_name="share")
    long["model"] = long["model"].map(names)
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(long, x="channel", y="share", color="model", barmode="group",
                     title=label("四归因模型渠道份额", "Channel share across four models"),
                     labels={"share": label("份额", "share"), "channel": label("渠道", "channel")}))
    with c2:
        tbl = attr.sort_values("markov_vs_last_pct")
        chart(px.bar(tbl, x="markov_vs_last_pct", y="channel", orientation="h",
                     color="markov_vs_last_pct", color_continuous_scale="RdBu",
                     title=label("Markov vs 末次（%）", "Markov vs last (%)"),
                     labels={"markov_vs_last_pct": label("差异（%）", "gap (%)"),
                             "channel": label("渠道", "channel")}))
    show = attr.copy()
    for c in ["first_touch", "last_touch", "position_based", "markov_chain"]:
        show[c] = show[c].map(pct)
    st.dataframe(show.round(4), use_container_width=True, hide_index=True)
    st.caption(label(f"转化基准率：{pct(meta.get('base_conversion_rate', 0))}",
                     f"Base conversion rate: {pct(meta.get('base_conversion_rate', 0))}"))


@register("shapley")
def _shapley():
    shap = load_csv("channel_shapley.csv")
    if shap.empty:
        return warn(label("缺少 Shapley 产物", "Shapley artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(shap.sort_values("shapley_share"), x="shapley_share", y="channel",
                     orientation="h", color="grade",
                     title=label("Shapley 渠道份额与分级", "Shapley share and grade"),
                     labels={"shapley_share": label("份额", "share"),
                             "channel": label("渠道", "channel")}))
    with c2:
        chart(px.scatter(shap, x="ad_spend", y="revenue", size="signups", color="roi",
                         hover_name="channel", size_max=45,
                         title=label("花费 vs 收入（气泡=注册数）", "Spend vs revenue (bubble = sign-ups)"),
                         labels={"ad_spend": label("广告花费", "ad spend"),
                                 "revenue": label("收入", "revenue"),
                                 "roi": "ROI", "signups": label("注册数", "sign-ups")}))
    show = shap.copy()
    show["shapley_share"] = show["shapley_share"].map(pct)
    st.dataframe(show.round(4), use_container_width=True, hide_index=True)


@register("ads_social")
def _ads_social():
    matrix = load_csv("ads_social_matrix.csv")
    lag = load_csv("ads_social_lag.csv")
    if matrix.empty:
        return warn(label("缺少相关分析产物", "Correlation artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        if not lag.empty:
            chart(px.line(lag, x="lag_days", y="corr", markers=True,
                          title=label("滞后相关：互动率领先 k 天 vs CPC",
                                      "Lag correlation: engagement leads CPC by k days"),
                          labels={"lag_days": label("领先天数", "lag (days)"),
                                  "corr": label("相关系数", "correlation")}))
    with c2:
        chart(px.bar(matrix, x="step", y="corr", color="segment",
                     title=label("四步相关结论矩阵", "Four-step correlation matrix"),
                     labels={"corr": label("相关系数", "correlation"),
                             "step": label("步骤", "step")}))
    st.dataframe(matrix.round(4), use_container_width=True, hide_index=True)


@register("roi")
def _roi():
    wf = load_csv("roi_waterfall.csv")
    if wf.empty:
        return warn(label("缺少 ROI 产物", "ROI artefact missing"))
    wf = wf.sort_values("contribution", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(wf, x="channel", y="contribution", color="contribution",
                     color_continuous_scale="RdYlGn",
                     title=label("ROI 贡献瀑布", "ROI contribution waterfall"),
                     labels={"contribution": label("贡献", "contribution"),
                             "channel": label("渠道", "channel")})
        fig.add_trace(go.Scatter(x=wf["channel"], y=wf["cumulative"], mode="lines+markers",
                                 name=label("累计贡献", "cumulative"), line=dict(color="#111827")))
        chart(fig)
    with c2:
        chart(px.bar(wf, x="channel", y="roi", color="spend_share",
                     title=label("各渠道 ROI（颜色=花费占比）", "Channel ROI (colour = spend share)"),
                     labels={"roi": "ROI", "channel": label("渠道", "channel"),
                             "spend_share": label("花费占比", "spend share")}))
    st.dataframe(wf.round(4), use_container_width=True, hide_index=True)
    with st.expander(label("统计检验：ANOVA / MANOVA", "Statistical tests: ANOVA / MANOVA")):
        anova = load_csv("roi_anova.csv")
        manova = load_csv("roi_manova.csv")
        if not anova.empty:
            st.dataframe(anova.round(4), use_container_width=True, hide_index=True)
        if not manova.empty:
            st.dataframe(manova.round(4), use_container_width=True, hide_index=True)


@register("rfm")
def _rfm():
    rfm = load_csv("rfm_assignments.csv")
    personas = load_csv("rfm_personas.csv")
    meta = load_json("rfm_metrics.json")
    if rfm.empty:
        return warn(label("缺少 RFM 产物", "RFM artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        sample = rfm.sample(min(len(rfm), 6000), random_state=42).copy()
        sample["cluster"] = sample["cluster"].astype(str)
        chart(px.scatter(sample, x="pc1", y="pc2", color="cluster",
                         hover_data=["rfm_segment", "monetary", "ltv_90d"], opacity=0.55,
                         title=label("行为分群（PCA 二维投影）", "Behavioural segments (PCA projection)"),
                         labels={"pc1": "PC1", "pc2": "PC2",
                                 "cluster": label("分群", "cluster")}))
    with c2:
        if not personas.empty:
            chart(px.bar(personas, x="cluster", y="users", color="avg_ltv_90d",
                         title=label("各分群人数与平均 LTV", "Segment size and average LTV"),
                         labels={"users": label("人数", "users"), "cluster": label("分群", "cluster"),
                                 "avg_ltv_90d": label("平均 LTV", "avg LTV")},
                         color_continuous_scale="Viridis"))
    st.dataframe(personas.round(2), use_container_width=True, hide_index=True)
    st.caption(label(f"k={meta.get('k','—')} · 轮廓系数 {meta.get('silhouette','—')} · PCA 解释 {pct(meta.get('explained_var',0))}",
                     f"k={meta.get('k','—')} · silhouette {meta.get('silhouette','—')} · PCA explained {pct(meta.get('explained_var',0))}"))


@register("ltv")
def _ltv():
    metrics = load_csv("ltv_metrics.csv")
    pred = load_csv("ltv_predictions.csv")
    imp = load_csv("ltv_feature_importance.csv")
    alive = load_csv("ltv_p_alive.csv")
    if metrics.empty:
        return warn(label("缺少 LTV 产物", "LTV artefact missing"))
    st.dataframe(metrics.round(2), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        if not pred.empty:
            s = pred.sample(min(len(pred), 3000), random_state=42)
            fig = px.scatter(s, x="ltv_90d", y="predicted_ltv_90d", opacity=0.45,
                             title=label("预测 vs 实际 LTV(90d)", "Predicted vs actual LTV (90d)"),
                             labels={"ltv_90d": label("实际 LTV", "actual LTV"),
                                     "predicted_ltv_90d": label("预测 LTV", "predicted LTV")})
            lim = float(max(s["ltv_90d"].max(), s["predicted_ltv_90d"].max()))
            fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines", name="y=x",
                                     line=dict(dash="dash", color="#ef4444")))
            chart(fig)
    with c2:
        if not imp.empty:
            chart(px.bar(imp.head(15), x="importance", y="feature", orientation="h",
                         title=label("LightGBM 特征重要性 Top15", "LightGBM feature importance (top 15)"),
                         labels={"importance": label("重要性", "importance"),
                                 "feature": label("特征", "feature")}))
    if not alive.empty:
        chart(px.histogram(alive, x="p_alive", nbins=40,
                           title=label("BG/NBD P(alive) 分布", "BG/NBD P(alive) distribution"),
                           labels={"p_alive": "P(alive)", "count": label("人数", "users")}), 360)


@register("survival")
def _survival():
    fa = load_csv("funnel_attribution.csv")
    cox = load_csv("cox_hazard_ratios.csv")
    km = load_csv("kaplan_meier_curves.csv")
    c1, c2 = st.columns(2)
    with c1:
        if not fa.empty:
            d = fa.dropna(subset=["contribution_pct"])
            chart(px.bar(d, x="step", y="contribution_pct", color="contribution_pct",
                         color_continuous_scale="RdBu",
                         title=label("各步骤对整体 CVR 变化的贡献（%）",
                                     "Step contribution to the overall CVR change (%)"),
                         labels={"contribution_pct": label("贡献（%）", "contribution (%)"),
                                 "step": label("步骤", "step")}))
    with c2:
        if not cox.empty:
            ycol = "feature" if "feature" in cox.columns else "covariate"
            top = cox.sort_values("hazard_ratio", ascending=False).head(10)
            chart(px.bar(top, x="hazard_ratio", y=ycol, orientation="h",
                         title=label("Cox 风险系数 Top10", "Cox hazard ratio (top 10)"),
                         labels={"hazard_ratio": "hazard ratio", ycol: label("变量", "covariate")}))
    if not km.empty:
        fig = go.Figure()
        palette = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                   "#06b6d4", "#ec4899", "#84cc16", "#64748b"]
        for i, (g, sub) in enumerate(km.groupby("group")):
            sub = sub.sort_values("time")
            color = palette[i % len(palette)]
            if {"lower", "upper"} <= set(sub.columns):
                fig.add_trace(go.Scatter(x=sub["time"], y=sub["upper"], mode="lines",
                                         line=dict(width=0), showlegend=False, hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=sub["time"], y=sub["lower"], mode="lines",
                                         line=dict(width=0), fill="tonexty",
                                         fillcolor="rgba(37,99,235,0.10)",
                                         showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=sub["time"], y=sub["survival"], mode="lines",
                                     name=g, line=dict(color=color, width=2)))
        fig.update_layout(title=label("Kaplan-Meier：未首充概率（含 95% CI）",
                                      "Kaplan-Meier: probability of not depositing (95% CI)"),
                          xaxis_title=label("注册后天数", "days since sign-up"),
                          yaxis_title=label("未首充概率", "P(not deposited)"))
        chart(fig, 460)
    if not fa.empty:
        st.dataframe(fmt_pct_df(fa, ["cvr_current", "cvr_previous", "contribution_pct"]),
                     use_container_width=True, hide_index=True)


@register("vip")
def _vip():
    vipd = load_csv("vip_distribution.csv")
    benefits = load_csv("vip_benefits.csv")
    stability = load_json("vip_stability.json")
    coverage = load_csv("tag_coverage.csv")
    personas = load_csv("tag_personas.csv")
    if vipd.empty:
        return warn(label("缺少 VIP 产物", "VIP artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(vipd, x="tier", y="users", color="avg_ltv_90d",
                     title=label("VIP 等级分布（颜色=平均 LTV）", "VIP tiers (colour = average LTV)"),
                     labels={"tier": "VIP", "users": label("人数", "users"),
                             "avg_ltv_90d": label("平均 LTV", "avg LTV")},
                     color_continuous_scale="Viridis"))
    with c2:
        if not coverage.empty:
            chart(px.bar(coverage, x="tag_type", y="users", color="distinct_tags",
                         title=label("标签体系覆盖（四类标签）", "Tag coverage (four types)"),
                         labels={"tag_type": label("标签类型", "tag type"),
                                 "users": label("覆盖用户", "users"),
                                 "distinct_tags": label("标签数", "distinct tags")}))
    if stability:
        m = st.columns(4)
        m[0].metric(label("等级不变率", "Tier stability"), pct(stability.get("stability_rate", 0)))
        m[1].metric(label("升级", "Upgrades"), f"{stability.get('upgrades', 0):,}")
        m[2].metric(label("降级", "Downgrades"), f"{stability.get('downgrades', 0):,}")
        m[3].metric(label("覆盖用户", "Users"), f"{stability.get('users', 0):,}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{label('VIP 权益设计', 'VIP benefits')}**")
        st.dataframe(benefits, use_container_width=True, hide_index=True)
    with c2:
        st.markdown(f"**{label('标签画像卡 Top 30', 'Tag persona cards (top 30)')}**")
        st.dataframe(fmt_pct_df(personas, ["deposit_rate"]), use_container_width=True, hide_index=True)


@register("campaign")
def _campaign():
    camp = load_csv("campaign_incremental_roi.csv")
    if camp.empty:
        return warn(label("缺少活动产物", "Campaign artefact missing"))
    camp = camp.sort_values("incremental_roi", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(camp, x="name", y="incremental_roi", color="incremental_roi",
                     color_continuous_scale="RdYlGn",
                     title=label("活动增量 ROI（正=跑赢基线）", "Campaign incremental ROI (positive = beats baseline)"),
                     labels={"incremental_roi": label("增量 ROI", "incremental ROI"),
                             "name": label("活动", "campaign")}))
    with c2:
        chart(px.bar(camp, x="name", y="incremental_revenue", color="channel",
                     title=label("活动增量收入", "Campaign incremental revenue"),
                     labels={"incremental_revenue": label("增量收入", "incremental revenue"),
                             "name": label("活动", "campaign"), "channel": label("渠道", "channel")}))
    st.dataframe(camp.round(2), use_container_width=True, hide_index=True)


@register("modules")
def _modules():
    mod = load_csv("module_efficiency.csv")
    if mod.empty:
        return warn(label("缺少模块效率产物", "Module efficiency artefact missing"))
    mod = mod.copy()
    mod["label"] = mod["page"] + " / " + mod["module_id"]
    c1, c2 = st.columns(2)
    with c1:
        top = mod.sort_values("relative_clickability", ascending=False).head(15)
        chart(px.bar(top, x="relative_clickability", y="label", orientation="h",
                     color="relative_clickability", color_continuous_scale="Teal",
                     title=label("相对可点击率 Top15", "Relative clickability (top 15)"),
                     labels={"relative_clickability": label("相对可点击率", "relative clickability"),
                             "label": label("页面 / 模块", "page / module")}))
    with c2:
        top2 = mod.sort_values("dea_efficiency", ascending=False).head(15)
        chart(px.bar(top2, x="dea_efficiency", y="label", orientation="h",
                     color="dea_efficiency", color_continuous_scale="Viridis",
                     title=label("DEA 综合效率 Top15", "DEA efficiency (top 15)"),
                     labels={"dea_efficiency": label("DEA 效率", "DEA efficiency"),
                             "label": label("页面 / 模块", "page / module")}))
    st.dataframe(mod.round(4), use_container_width=True, hide_index=True)


@register("cta")
def _cta():
    main = load_csv("cta_main_effects.csv")
    inter = load_csv("cta_interaction.csv")
    imp = load_csv("cta_feature_importance.csv")
    if main.empty:
        return warn(label("缺少 CTA 产物", "CTA artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(main, x="level", y="cvr", color="factor", barmode="group",
                     title=label("CTA 主效应：各水平转化率", "CTA main effects: CVR by level"),
                     labels={"cvr": label("转化率", "CVR"), "level": label("水平", "level"),
                             "factor": label("因子", "factor")}))
    with c2:
        if not inter.empty:
            piv = inter.pivot(index="cta_color", columns="cta_size", values="cvr")
            chart(px.imshow(piv, text_auto=".2%", color_continuous_scale="Blues",
                            title=label("交互效应：颜色 × 尺寸", "Interaction: colour × size"),
                            labels={"x": label("尺寸", "size"), "y": label("颜色", "colour"),
                                    "color": label("转化率", "CVR")}))
    if not imp.empty:
        chart(px.bar(imp.head(10), x="importance", y="feature", orientation="h",
                     title=label("随机森林特征重要性", "Random-forest feature importance"),
                     labels={"importance": label("重要性", "importance"),
                             "feature": label("特征", "feature")}), 360)


@register("churn")
def _churn():
    logi = load_csv("logistic_terms.csv")
    metrics = load_csv("churn_metrics.csv")
    roc = load_csv("churn_roc.csv")
    imp = load_csv("churn_importance.csv")
    if logi.empty:
        return warn(label("缺少流失模型产物", "Churn artefact missing"))
    sig = logi[logi["p_value"] < 0.05].copy()
    sig["abs_log"] = np.abs(np.log(sig["odds_ratio"].clip(lower=1e-6)))
    sig = sig.sort_values("abs_log", ascending=False).head(15)
    c1, c2 = st.columns(2)
    with c1:
        if sig.empty:
            st.info(label("没有 p<0.05 的显著项", "No significant terms at p<0.05"))
        else:
            chart(px.bar(sig.sort_values("odds_ratio"), x="odds_ratio", y="term",
                         orientation="h", color="odds_ratio", color_continuous_scale="RdBu",
                         title=label("Logistic 显著项 Odds Ratio", "Logistic odds ratios (significant)"),
                         labels={"odds_ratio": "odds ratio", "term": label("变量", "term")}))
    with c2:
        if not roc.empty:
            chart(px.line(roc, x="fpr", y="tpr", color="model",
                          title=label("流失模型 ROC 曲线", "Churn model ROC curves"),
                          labels={"fpr": "FPR", "tpr": "TPR", "model": label("模型", "model")}))
    if not metrics.empty:
        st.dataframe(metrics.round(2), use_container_width=True, hide_index=True)
    if not imp.empty:
        top = imp[imp["model"] == imp["model"].iloc[0]].head(12)
        chart(px.bar(top, x="importance", y="feature", orientation="h", color="model",
                     title=label("流失模型特征重要性 Top12", "Churn feature importance (top 12)"),
                     labels={"importance": label("重要性", "importance"),
                             "feature": label("特征", "feature")}), 360)


@register("ab")
def _ab():
    table = load_csv("ab_table.csv")
    meta = load_json("ab_meta.json")
    if table.empty:
        return warn(label("缺少 A/B 产物", "A/B artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(table, x="variant", y="cvr", color="variant", text_auto=".2%",
                     title=label("A/B 转化率对比", "A/B conversion rate"),
                     labels={"cvr": label("转化率", "CVR"), "variant": label("分组", "variant")}))
    with c2:
        if meta:
            m1, m2 = st.columns(2)
            m1.metric(label("绝对提升", "Absolute lift"), f"{meta['abs_lift']*100:.2f}pp")
            m2.metric(label("相对提升", "Relative lift"), f"{meta['rel_lift_pct']:.2f}%")
            m3, m4 = st.columns(2)
            m3.metric("p-value", f"{meta['p_value']:.2e}")
            m4.metric("MDE", f"{meta.get('mde_pp', 0)*100:.2f}pp")
            st.caption(label(f"95% CI：{meta['ci95']} · SRM p={meta['srm_p_value']:.2f}",
                             f"95% CI: {meta['ci95']} · SRM p={meta['srm_p_value']:.2f}"))
    st.dataframe(fmt_pct_df(table, ["cvr"]), use_container_width=True, hide_index=True)


@register("ops")
def _ops():
    ops = load_csv("ops_matrix.csv")
    if ops.empty:
        return warn(label("缺少运营矩阵产物", "Ops matrix artefact missing"))
    ops = ops.sort_values("priority_score", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(ops, x="priority_score", y="segment", orientation="h", color="strategy",
                     title=label("运营优先级", "Operations priority"),
                     labels={"priority_score": label("优先级分", "priority score"),
                             "segment": label("人群", "segment"), "strategy": label("策略", "strategy")}))
    with c2:
        chart(px.scatter(ops, x="users", y="avg_ltv_90d", size="priority_score",
                         color="segment", hover_name="strategy", size_max=50,
                         title=label("人群规模 vs 平均 LTV", "Segment size vs average LTV"),
                         labels={"users": label("人数", "users"),
                                 "avg_ltv_90d": label("平均 LTV", "avg LTV"),
                                 "segment": label("人群", "segment")}))
    show = fmt_pct_df(ops, ["deposit_rate"])
    st.dataframe(show.round(4), use_container_width=True, hide_index=True)


@register("budget")
def _budget():
    params = load_csv("budget_elasticity.csv")
    dec = load_csv("budget_decomposition.csv")
    if params.empty:
        return warn(label("缺少预算弹性产物", "Budget elasticity artefact missing"))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(params.sort_values("marginal_conv_per_dollar"),
                     x="marginal_conv_per_dollar", y="channel", orientation="h",
                     color="marginal_conv_per_dollar", color_continuous_scale="Teal",
                     title=label("每多花 1 美元的边际转化", "Marginal conversion per extra dollar"),
                     labels={"marginal_conv_per_dollar": label("边际转化/美元", "marginal conv/$"),
                             "channel": label("渠道", "channel")}))
    with c2:
        if not dec.empty:
            dec = dec.copy()
            dec["date"] = pd.to_datetime(dec["date"])
            chart(px.line(dec, x="date", y=["observed", "trend", "seasonal"],
                          title=label("STL 分解：趋势 + 季节性", "STL decomposition: trend + seasonality"),
                          labels={"value": label("转化", "conversions"),
                                  "variable": label("分量", "component")}))
    st.dataframe(params.round(4), use_container_width=True, hide_index=True)
    st.markdown(f"**{label('管理层假设模拟器', 'Management what-if simulator')}**")
    cols = st.columns(4)
    assumptions = {}
    for i, row in params.reset_index(drop=True).iterrows():
        assumptions[row["channel"]] = cols[i % 4].number_input(
            row["channel"], min_value=0.0,
            value=float(round(row["current_daily_spend"], 2)), step=50.0,
            key=f"budget_{row['channel']}")
    if st.button(label("运行预算模拟", "Run budget simulation"), type="primary"):
        rows = []
        for _, row in params.iterrows():
            spend = assumptions[row["channel"]]
            pred = max(row["intercept"] + row["log_spend_coef"] * np.log1p(spend), 0)
            rows.append({label("渠道", "channel"): row["channel"],
                         label("当前花费", "current spend"): row["current_daily_spend"],
                         label("假设花费", "assumed spend"): spend,
                         label("当前转化", "current conversions"): row["current_daily_conversions"],
                         label("预测转化", "predicted conversions"): round(pred, 2),
                         label("变化", "delta"): round(pred - row["current_daily_conversions"], 2)})
        res = pd.DataFrame(rows)
        st.dataframe(res, use_container_width=True, hide_index=True)
        st.metric(label("预计每日总转化变化", "Predicted daily conversion change"),
                  f"{res[label('变化', 'delta')].sum():+.1f}")


@register("okr")
def _okr():
    okr = load_csv("okr_attribution.csv")
    if okr.empty:
        return warn(label("缺少 OKR 归因产物", "OKR attribution artefact missing"))
    ch = "channel" if "channel" in okr.columns else okr.columns[0]
    long = okr.melt(id_vars=ch,
                    value_vars=["last_touch_share", "markov_share", "shapley_share"],
                    var_name="model", value_name="share")
    long["model"] = long["model"].map({"last_touch_share": label("末次", "Last"),
                                       "markov_share": "Markov",
                                       "shapley_share": "Shapley"})
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(long, x=ch, y="share", color="model", barmode="group",
                     title=label("末次 / Markov / Shapley 对比", "Last / Markov / Shapley comparison"),
                     labels={"share": label("份额", "share"), ch: label("渠道", "channel")}))
    with c2:
        d = okr.sort_values("markov_vs_last_pct", ascending=False)
        fig = go.Figure()
        fig.add_bar(x=d[ch], y=d["markov_vs_last_pct"], name=label("Markov vs 末次", "Markov vs last"))
        fig.add_bar(x=d[ch], y=d["shapley_vs_last_pct"], name=label("Shapley vs 末次", "Shapley vs last"))
        fig.update_layout(barmode="group", title=label("助攻价值差（%）", "Assist-value gap (%)"),
                          yaxis_title=label("差异（%）", "gap (%)"))
        chart(fig)
    show = okr.copy()
    for c in ["last_touch_share", "markov_share", "shapley_share"]:
        show[c] = show[c].map(pct)
    st.dataframe(show.round(2), use_container_width=True, hide_index=True)


st.divider()
st.markdown(f"### 📦 {label('交付物与文档', 'Deliverables & docs')}")
for _name, _file in [("README", "README.md"), ("README (EN)", "README_EN.md"),
                     ("Development log", "docs/development_log.md"),
                     ("Data dictionary", "docs/data_dictionary.md"),
                     ("Scheduling", "docs/scheduling.md")]:
    st.markdown(f'- <a href="{GITHUB}/{_file}" target="_blank">{_name}</a>', unsafe_allow_html=True)
st.caption(T["footer"])

for _sec in SECTIONS:
    render_section(_sec)
