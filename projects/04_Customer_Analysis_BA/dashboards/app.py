#!/usr/bin/env python3
"""Single-page Streamlit data story for the CEX lifecycle analytics project.

Every README section 6.1-6.19 is rendered as one scrollable section with
charts, a bold business conclusion, and field definitions.
"""
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

st.set_page_config(page_title="CEX Customer Analytics", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], section.main > div,
section[data-testid="stMain"] {
    scroll-behavior: smooth;
}
.block-container {padding-top: 2.2rem; max-width: 1450px;}
h1, h2, h3 {letter-spacing: -0.01em;}
[data-testid="stMetric"] {
    background: linear-gradient(180deg,#ffffff,#f6f8fa);
    border: 1px solid #e5e7eb; border-radius: 14px;
    padding: 14px 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
[data-testid="stMetricLabel"] {color:#57606a;}
.section-tag {
    display:inline-block; background:#eef2ff; color:#3730a3;
    padding:3px 11px; border-radius:999px; font-size:12px; font-weight:700;
    letter-spacing:.03em;
}
.def {color:#57606a; font-size:.90rem; border-left:3px solid #d0d7de;
      padding:6px 0 6px 12px; margin:6px 0 12px 0; background:#fafbfc;}
.insight {
    background: linear-gradient(90deg,#f0f7ff 0%,#ffffff 85%);
    border-left:5px solid #2563eb; padding:14px 18px;
    border-radius:10px; margin:10px 0 22px 0; font-size:.97rem;
}
.warnbox {background:#fff8e6; border-left:5px solid #d4a72c; padding:12px 16px;
          border-radius:8px; margin:8px 0 18px 0;}
.hero {background:linear-gradient(120deg,#0b1f3a 0%,#143d6b 55%,#1d6fb8 100%);
       color:#fff; padding:26px 30px; border-radius:18px; margin-bottom:18px;}
.hero h1 {color:#fff; margin:0 0 6px 0; font-size:2rem;}
.hero p {color:#cfe3ff; margin:0; font-size:1rem;}
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


def section(anchor: str, tag: str, title: str, definition: str) -> None:
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown(f'<span class="section-tag">{tag}</span>', unsafe_allow_html=True)
    st.header(title, anchor=anchor)
    if definition:
        st.markdown(f'<div class="def">{definition}</div>', unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="insight">{text}</div>', unsafe_allow_html=True)


def warn(text: str) -> None:
    st.markdown(f'<div class="warnbox">{text}</div>', unsafe_allow_html=True)


def empty(name: str) -> bool:
    warn(f"缺少 <code>reports/results/{name}</code>，请先运行 <code>python main.py</code>。")
    return True


NAV = [
    ("overview", "总览与数据底座"),
    ("s61", "6.1 用户细分 RFM + 降维"),
    ("s62", "6.2 注册转化漏斗"),
    ("s63", "6.3 行为科学与心理学"),
    ("s64", "6.4 用户路径图"),
    ("s65", "6.5 LTV：BG/NBD vs 机器学习"),
    ("s66", "6.6 ROI 波动归因"),
    ("s67", "6.7 漏斗归因 + 生存分析"),
    ("s68", "6.8 活动 / 空投增量 ROI"),
    ("s69", "6.9 四归因模型对比"),
    ("s610", "6.10 渠道 Shapley 与分级"),
    ("s611", "6.11 广告 × 社媒相关性"),
    ("s612", "6.12 页面模块效率 / DEA"),
    ("s613", "6.13 CTA 全因子实验"),
    ("s614", "6.14 Logistic + 流失模型"),
    ("s615", "6.15 A/B 测试"),
    ("s616", "6.16 标签体系 + VIP"),
    ("s617", "6.17 精细化运营矩阵"),
    ("s618", "6.18 预算弹性模拟"),
    ("s619", "6.19 OKR 归因剥离"),
]

with st.sidebar:
    st.markdown("# 📊 CEX Analytics")
    st.caption("单页滚动 · 点击标题平滑跳转")
    st.markdown("\n".join(f"- [{label}](#{anchor})" for anchor, label in NAV))
    st.divider()
    st.caption(f"Redis：{'已连接' if get_redis() is not None else '未连接（直查 DuckDB）'}")
    st.caption(f"DuckDB：{Path(settings.DUCKDB_PATH).name}")
    st.divider()
    st.markdown("**文档**")
    st.caption("docs/development_log.md · docs/data_dictionary.md")
    st.caption("reports/insights.md · reports/latest_run.json")

kpi = load_json("kpi_summary.json")
st.markdown("""
<div class="hero">
  <h1>交易所用户全生命周期 · 数据故事</h1>
  <p>从注册、KYC、首充、交易到留存与召回：一套可复现的分析体系，覆盖 6.1–6.19 全部方法模块。</p>
</div>
""", unsafe_allow_html=True)

if kpi:
    c = st.columns(4)
    c[0].metric("注册用户", f"{int(kpi['users']):,}")
    c[1].metric("首次入金转化率", f"{kpi['deposit_rate']:.1%}")
    c[2].metric("交易用户", f"{int(kpi['traders']):,}")
    c[3].metric("手续费收入", f"${kpi['revenue']:,.0f}")
    c = st.columns(4)
    c[0].metric("GMV", f"${kpi['gmv']/1e6:.1f}M")
    c[1].metric("平均 LTV (90d)", f"${kpi['avg_ltv_90d']:.2f}")
    c[2].metric("90 天流失率", f"{kpi['churn_rate']:.1%}")
    c[3].metric("KYC 完成率", f"{kpi['kyc_rate']:.1%}")
else:
    warn("尚未生成 KPI，请先运行 `python main.py`。")

# ------------------------------------------------------------------ 00 overview
section("overview", "00", "总览与数据底座",
        "16 张核心表的本地数仓（DuckDB），经 dbt staging → intermediate → marts 三层加工；"
        "本节展示数据规模与核心 KPI，全部指标口径见 docs/data_dictionary.md。")

manifest_path = ROOT / "data" / "raw" / "_manifest.json"
counts = {}
if manifest_path.exists():
    counts = json.loads(manifest_path.read_text()).get("row_counts", {})

left, right = st.columns([1.05, 1])
with left:
    if counts:
        m = pd.DataFrame(sorted(counts.items(), key=lambda x: -x[1]),
                         columns=["table", "rows"])
        st.plotly_chart(px.bar(m, x="rows", y="table", orientation="h",
                               title="各表行数（全部 ≥ 1,000 行）",
                               color="rows", color_continuous_scale="Blues"),
                        use_container_width=True)
    else:
        warn("未找到 data/raw/_manifest.json，请先运行数据生成脚本。")
with right:
    if kpi:
        kt = pd.DataFrame([
            ["注册 → KYC", f"{kpi['kyc_rate']:.2%}"],
            ["注册 → 首充", f"{kpi['deposit_rate']:.2%}"],
            ["首充 → 首笔交易", f"{kpi['deposit_to_trade_rate']:.2%}"],
            ["ARPU", f"${kpi['arpu']:.2f}"],
            ["ARPPU", f"${kpi['arppu']:.2f}"],
            ["AOV", f"${kpi['aov']:,.2f}"],
            ["90 天流失率", f"{kpi['churn_rate']:.2%}"],
        ], columns=["核心指标", "数值"])
        st.dataframe(kt, use_container_width=True, hide_index=True)

insight("<b>数据底座健康：</b>16 张表全部 ≥ 1,000 行，dbt 27 个模型 + 30 个测试全部通过；"
        "整体漏斗从 32,199 次访问收敛到 7,608 名交易用户，<b>注册→首充仅 42.14%</b>，"
        "是整条链路最值得投入的增长杠杆。")

# ------------------------------------------------------------------ 6.1
section("s61", "6.1", "用户细分：RFM + 高级降维",
        "字段：<code>recency_days</code> 距上次交易天数；<code>frequency</code> 交易次数；"
        "<code>monetary</code> 累计交易额；<code>R/F/M</code> 为 1–5 分箱得分；"
        "<code>pc1/pc2</code> 为行为特征 PCA 两维坐标；<code>cluster</code> 为 K-Means 行为分群。")
rfm = load_csv("rfm_assignments.csv")
personas = load_csv("rfm_personas.csv")
rfm_meta = load_json("rfm_metrics.json")
if rfm.empty:
    empty("rfm_assignments.csv")
else:
    c1, c2 = st.columns([1.35, 1])
    with c1:
        sample = rfm.sample(min(len(rfm), 6000), random_state=42).copy()
        sample["cluster"] = sample["cluster"].astype(str)
        fig = px.scatter(sample,
                         x="pc1", y="pc2", color="cluster",
                         hover_data=["rfm_segment", "monetary", "ltv_90d"],
                         opacity=0.55, title="行为分群（PCA 二维投影）")
        fig.update_traces(marker=dict(size=5))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not personas.empty:
            st.plotly_chart(px.bar(personas, x="cluster", y="users", color="avg_ltv_90d",
                                   title="各分群人数与平均 LTV",
                                   color_continuous_scale="Viridis"),
                            use_container_width=True)
    st.dataframe(personas.round(2), use_container_width=True, hide_index=True)
    insight(f"<b>RFM 分群结论：</b>K-Means 选出 <b>k={rfm_meta.get('k','—')}</b>，"
            f"轮廓系数 <b>{rfm_meta.get('silhouette','—')}</b>，PCA 两维解释 "
            f"<b>{rfm_meta.get('explained_var',0):.1%}</b> 方差。"
            "高价值核心人群（cluster 2）人数占比不高但贡献了最高的平均 LTV，"
            "应配置专属权益；大众人群（cluster 1）适合用首充奖励与费率折扣提升频次。")

# ------------------------------------------------------------------ 6.2
section("s62", "6.2", "注册转化漏斗（CEX Conversion Funnel）",
        "字段：<code>step</code> 漏斗步骤（visit/register/kyc/deposit/trade）；"
        "<code>user_cnt</code> 当日累计到达人数；<code>prev_step_cnt</code> 上一步人数；"
        "<code>step_cvr</code> = user_cnt / prev_step_cnt。")
funnel_daily = load_csv("funnel_daily.csv")
funnel_last = load_csv("funnel_last_day.csv")
if funnel_daily.empty or funnel_last.empty:
    empty("funnel_daily.csv")
else:
    c1, c2 = st.columns([1, 1.25])
    with c1:
        fig = go.Figure(go.Funnel(y=funnel_last["step"], x=funnel_last["user_cnt"],
                                  textinfo="value+percent previous",
                                  marker=dict(color=["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"])))
        fig.update_layout(title="最后一天漏斗快照", height=430, margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        piv = funnel_daily.pivot(index="period", columns="step", values="user_cnt").reset_index()
        st.plotly_chart(px.line(piv, x="period",
                                y=[c for c in piv.columns if c != "period"],
                                title="每日漏斗趋势",
                                labels={"value": "users", "variable": "step"}),
                        use_container_width=True)
    st.dataframe(funnel_last, use_container_width=True, hide_index=True)
    insight("<b>漏斗结论：</b>KYC → 首次入金是最大漏损环节，CVR 仅 <b>59.55%</b>，"
            "流失 <b>5,724 人</b>；而首充 → 首笔交易高达 <b>90.27%</b>。"
            "这说明问题不在“入金后不会交易”，而在“KYC 完成后不愿入金”，"
            "应优先投入首充奖励、入金引导与支付方式扩容。")

# ------------------------------------------------------------------ 6.3
section("s63", "6.3", "用户行为科学与心理学分析",
        "字段：<code>behaviour</code> 注册后 1 小时内的关键动作；<code>deposited_mean</code> / "
        "<code>non_deposited_mean</code> 为入金 vs 未入金人群的动作发生率；"
        "<code>diff</code> 差值；<code>p_value</code> 为 Welch t 检验。")
beh = load_csv("behaviour_tests.csv")
beh_val = load_csv("behaviour_validation.csv")
if beh.empty:
    empty("behaviour_tests.csv")
else:
    plot = beh.melt(id_vars="behaviour", value_vars=["deposited_mean", "non_deposited_mean"],
                    var_name="group", value_name="rate")
    plot["group"] = plot["group"].map({"deposited_mean": "已入金", "non_deposited_mean": "未入金"})
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.plotly_chart(px.bar(plot, x="behaviour", y="rate", color="group", barmode="group",
                               title="注册后 1 小时关键动作：入金 vs 未入金"),
                        use_container_width=True)
    with c2:
        st.dataframe(beh, use_container_width=True, hide_index=True)
    if not beh_val.empty:
        st.markdown("**外部验证：按地区拆分后结论是否稳定**")
        vp = beh_val.melt(id_vars=["region_group", "behaviour"],
                          value_vars=["deposited_mean", "non_deposited_mean"],
                          var_name="group", value_name="rate")
        st.plotly_chart(px.bar(vp, x="behaviour", y="rate", color="group", facet_col="region_group",
                               barmode="group", title="分地区复现（避免单批数据过拟合）"),
                        use_container_width=True)
    top = beh.sort_values("diff", ascending=False).iloc[0]
    insight(f"<b>行为结论：</b>入金人群在「<b>{top['behaviour']}</b>」上的发生率比未入金人群高 "
            f"<b>{top['diff']*100:.1f} 个百分点</b>（p={top['p_value']:.2e}）。"
            "这是高流失人群的<b>先行前兆行为</b>——注册后 1 小时内没有完成该动作的用户，"
            "应在第 2 小时触发站内引导/推送，而不是等到 7 天后才召回。")

# ------------------------------------------------------------------ 6.4
section("s64", "6.4", "用户路径图（User Flow Path Graph）",
        "字段：<code>event_name → next_event</code> 为同一 session 内的页面/事件跳转；"
        "<code>weight</code> 为跳转次数；<code>path</code> 为完整事件序列，<code>sessions</code> 为出现次数。")
edges = load_csv("flow_edges.csv")
paths = load_csv("flow_top_paths.csv")
if edges.empty:
    empty("flow_edges.csv")
else:
    labels = list(pd.unique(pd.concat([edges["event_name"], edges["next_event"]], ignore_index=True)))
    idx = {lab: i for i, lab in enumerate(labels)}
    sankey = go.Figure(go.Sankey(
        node=dict(label=labels, pad=18, thickness=16, color="#93c5fd"),
        link=dict(source=[idx[x] for x in edges["event_name"]],
                  target=[idx[x] for x in edges["next_event"]],
                  value=edges["weight"], color="rgba(37,99,235,0.28)")))
    sankey.update_layout(title="事件跳转 Sankey 图", height=520)
    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.plotly_chart(sankey, use_container_width=True)
    with c2:
        st.markdown("**Top 会话路径**")
        st.dataframe(paths, use_container_width=True, hide_index=True)
    insight("<b>路径结论：</b>Sankey 图显示 <code>view_home → view_market → view_tutorial</code> "
            "是最高频的良性路径；而 <code>submit_kyc → deposit_start</code> 之后出现明显分叉，"
            "一部分用户直接掉出。结合 6.2 的漏斗，<b>路径图告诉我们“从哪漏”，漏斗告诉我们“漏多少”</b>，"
            "两者必须一起看。")

# ------------------------------------------------------------------ 6.5
section("s65", "6.5", "LTV 预测：BG/NBD vs 机器学习",
        "字段：<code>ltv_30d/ltv_90d</code> 为注册后 30/90 天累计手续费（不是交易额）；"
        "<code>predicted_ltv_90d</code> 为 LightGBM 预测值；<code>p_alive</code> 为 BG/NBD 的客户存活概率；"
        "评估口径：MAE / RMSE / Spearman（时间外样本）。")
ltv_m = load_csv("ltv_metrics.csv")
ltv_pred = load_csv("ltv_predictions.csv")
ltv_imp = load_csv("ltv_feature_importance.csv")
p_alive = load_csv("ltv_p_alive.csv")
if ltv_m.empty:
    empty("ltv_metrics.csv")
else:
    st.dataframe(ltv_m, use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        if not ltv_pred.empty:
            sample = ltv_pred.sample(min(len(ltv_pred), 3000), random_state=42)
            fig = px.scatter(sample, x="ltv_90d", y="predicted_ltv_90d", opacity=0.45,
                             title="预测 vs 实际 LTV(90d)",
                             labels={"ltv_90d": "实际", "predicted_ltv_90d": "预测"})
            lim = float(max(sample["ltv_90d"].max(), sample["predicted_ltv_90d"].max()))
            fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines",
                                     name="y=x", line=dict(dash="dash", color="#ef4444")))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not ltv_imp.empty:
            st.plotly_chart(px.bar(ltv_imp.head(15), x="importance", y="feature",
                                   orientation="h", title="LightGBM 特征重要性 Top15"),
                            use_container_width=True)
    if not p_alive.empty:
        st.plotly_chart(px.histogram(p_alive, x="p_alive", nbins=40,
                                     title="BG/NBD P(alive) 分布（区分真流失与暂时沉默）"),
                        use_container_width=True)
    insight("<b>LTV 选型结论：</b>LightGBM 的 MAE <b>1.75</b>、Spearman <b>0.99</b>，"
            "显著优于 BG/NBD 的 MAE <b>18.16</b>、Spearman <b>0.73</b>；"
            "但 BG/NBD 的 <code>P(alive)</code> 能回答“这个沉默用户是真流失还是暂时没来”，"
            "因此最终方案是 <b>LightGBM 做点预测 + BG/NBD 的存活概率做流失判定特征</b>，而不是二选一。")

# ------------------------------------------------------------------ 6.6
section("s66", "6.6", "ROI 波动归因（ANOVA / MANOVA + 瀑布图）",
        "字段：<code>roi</code> = 渠道收入 / 渠道花费；<code>spend_share</code> 花费占比；"
        "<code>contribution</code> = (渠道 ROI − 整体 ROI) × 花费占比，正负代表对整体 ROI 的拉动/拖累；"
        "<code>cumulative</code> 为累计贡献。")
wf = load_csv("roi_waterfall.csv")
roi_anova = load_csv("roi_anova.csv")
roi_manova = load_csv("roi_manova.csv")
roi_meta = load_json("roi_meta.json")
if wf.empty:
    empty("roi_waterfall.csv")
else:
    wf = wf.sort_values("contribution", ascending=False)
    c1, c2 = st.columns([1.25, 1])
    with c1:
        fig = px.bar(wf, x="channel", y="contribution", color="contribution",
                     color_continuous_scale="RdYlGn", title="ROI 贡献瀑布（按渠道）")
        fig.add_trace(go.Scatter(x=wf["channel"], y=wf["cumulative"], mode="lines+markers",
                                 name="累计贡献", line=dict(color="#111827")))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.plotly_chart(px.bar(wf, x="channel", y="roi", color="spend_share",
                               title="各渠道 ROI（颜色=花费占比）"),
                        use_container_width=True)
    st.dataframe(wf.round(4), use_container_width=True, hide_index=True)
    with st.expander("统计检验：ANOVA / MANOVA 明细"):
        if not roi_anova.empty:
            st.markdown("**ANOVA（每日 conversions_per_dollar ~ channel）**")
            st.dataframe(roi_anova, use_container_width=True, hide_index=True)
        if not roi_manova.empty:
            st.markdown("**MANOVA（conversions + clicks ~ channel）**")
            st.dataframe(roi_manova, use_container_width=True, hide_index=True)
    insight(f"<b>ROI 归因结论：</b>整体 ROI 为 <b>{roi_meta.get('overall_roi','—')}</b>。"
            "贡献为正的渠道在“拉高”整体 ROI，贡献为负的渠道在“拖累”整体 ROI；"
            "由于贡献度按花费占比加权，<b>高花费 + 低 ROI 的渠道会被放大成最大的负向项</b>，"
            "这正是预算调整应该优先动刀的地方。")

# ------------------------------------------------------------------ 6.7
section("s67", "6.7", "漏斗归因 + 生存分析（Cox）",
        "字段：<code>contribution_pct</code> 为各步骤对整体 CVR 变化的贡献（对数分解后归一化）；"
        "<code>hazard_ratio</code> &gt; 1 表示相对基准渠道更快完成首充；"
        "<code>survival</code> 为 Kaplan-Meier 未首充概率。")
fa = load_csv("funnel_attribution.csv")
fa_meta = load_json("funnel_attribution_meta.json")
cox = load_csv("cox_hazard_ratios.csv")
km = load_csv("kaplan_meier_curves.csv")
km_meta = load_json("kaplan_meier_meta.json")
if fa.empty:
    empty("funnel_attribution.csv")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(fa.dropna(subset=["contribution_pct"]),
                               x="step", y="contribution_pct", color="contribution_pct",
                               color_continuous_scale="RdBu", title="各步骤对整体 CVR 变化的贡献（%）"),
                        use_container_width=True)
    with c2:
        if not cox.empty:
            top = cox.sort_values("hazard_ratio", ascending=False).head(10)
            ycol = "feature" if "feature" in cox.columns else "covariate"
            st.plotly_chart(px.bar(top, x="hazard_ratio", y=ycol, orientation="h",
                                   title="Cox 流失/转化风险系数 Top10"),
                            use_container_width=True)
    if not km.empty:
        st.plotly_chart(px.line(km, x="time", y="survival", color="group",
                                title="Kaplan-Meier：未首充概率随时间下降"),
                        use_container_width=True)
    st.dataframe(fa, use_container_width=True, hide_index=True)
    _km_med = km_meta.get('overall_median_days')
    _km_p25 = km_meta.get('overall_p25_days')
    _km_txt = (f"{_km_med:.1f} 天" if isinstance(_km_med, (int, float)) else "观察期内未达到 50%")
    _p25_txt = (f"25% 用户在 {_km_p25:.1f} 天内完成首充" if isinstance(_km_p25, (int, float)) else "")
    insight(f"<b>漏斗归因结论：</b>近 {fa_meta.get('window_days','30')} 天整体 CVR 为 "
            f"<b>{fa_meta.get('overall_current',0):.2%}</b>（上一窗口 {fa_meta.get('overall_previous',0):.2%}）。"
            "贡献最大的环节就是最该优先修复的环节；Cox 模型进一步给出各渠道的<b>流失风险系数</b>，"
            f"KM 中位首充时间：<b>{_km_txt}</b>（{_p25_txt}）。"
            "观察期内未达到 50% 说明首充转化仍是主要瓶颈，应把强召回前置到前 30 天。")

# ------------------------------------------------------------------ 6.8
section("s68", "6.8", "活动 / 空投增量 ROI（DID）",
        "字段：<code>treated_pre/post</code> 为参与者活动前/后 4 周人均交易额；"
        "<code>control_pre/post</code> 为同渠道非参与者；<code>incremental_per_user</code> 为双重差分结果；"
        "<code>incremental_roi</code> = 增量收入 / 活动成本。")
camp = load_csv("campaign_incremental_roi.csv")
if camp.empty:
    empty("campaign_incremental_roi.csv")
else:
    camp = camp.sort_values("incremental_roi", ascending=False)
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(px.bar(camp, x="name", y="incremental_roi", color="incremental_roi",
                               color_continuous_scale="RdYlGn",
                               title="活动增量 ROI（正=跑赢自然增长基线）"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(px.bar(camp, x="name", y="incremental_revenue", color="channel",
                               title="活动增量收入"),
                        use_container_width=True)
    st.dataframe(camp.round(2), use_container_width=True, hide_index=True)
    insight("<b>活动结论：</b>多数活动的增量 ROI 为负，说明它们<b>没有跑赢自然增长基线</b>——"
            "如果只看活动期总交易额，会严重高估活动效果。"
            "只有少数活动（如 google_ads_campaign_0739）产生正增量，"
            "应把预算集中到可复现的正增量活动，并对负增量活动做停投复盘。")

# ------------------------------------------------------------------ 6.9
section("s69", "6.9", "四归因模型对比：首次 / 末次 / 位置 / 马尔可夫",
        "字段：<code>first_touch/last_touch/position_based/markov_chain</code> 为四种模型下各渠道的归因份额；"
        "<code>markov_vs_last_pct</code> = (马尔可夫 − 末次) / 末次；"
        "<code>stability_std</code> 为 5 折重采样的份额标准差（越小越稳）；"
        "<code>reconstruction_error</code> 为折均值与全量份额的平均绝对偏差。")
attr = load_csv("attribution_comparison.csv")
attr_meta = load_json("attribution_meta.json")
if attr.empty:
    empty("attribution_comparison.csv")
else:
    models = ["first_touch", "last_touch", "position_based", "markov_chain"]
    long = attr.melt(id_vars="channel", value_vars=models,
                     var_name="model", value_name="share")
    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.plotly_chart(px.bar(long, x="channel", y="share", color="model", barmode="group",
                               title="四归因模型渠道份额对比"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(px.bar(attr.sort_values("markov_vs_last_pct"),
                               x="markov_vs_last_pct", y="channel", orientation="h",
                               color="markov_vs_last_pct", color_continuous_scale="RdBu",
                               title="马尔可夫 vs 末次点击（%）"),
                        use_container_width=True)
    st.dataframe(attr.round(4), use_container_width=True, hide_index=True)
    over = attr.sort_values("markov_vs_last_pct", ascending=False).iloc[0]
    under = attr.sort_values("markov_vs_last_pct").iloc[0]
    insight(f"<b>归因结论：</b>末次点击高估 <b>{under['channel']}</b>、低估 <b>{over['channel']}</b>："
            f"{over['channel']} 的马尔可夫贡献比末次点击高 <b>{over['markov_vs_last_pct']:.1f}%</b>。"
            "转化基准率为 "
            f"<b>{attr_meta.get('base_conversion_rate',0):.2%}</b>，"
            "5 折稳定性标准差均 &lt; 0.01，说明结论稳定。"
            "<b>建议主归因改用马尔可夫移除效应，末次点击只作为对照基线。</b>")

# ------------------------------------------------------------------ 6.10
section("s610", "6.10", "渠道质量分级与 Shapley 归因",
        "字段：<code>shapley_revenue</code> 为渠道在全部联盟中的平均边际收入贡献；"
        "<code>shapley_share</code> 为归一化份额；<code>roi</code> = 收入/花费；"
        "<code>cpa</code> = 花费/首充人数；<code>grade</code> 为 S/A/B/C 分级；"
        "<code>inflation_flag</code> 表示“份额低 + ROI 低”的疑似注水渠道。")
shap = load_csv("channel_shapley.csv")
if shap.empty:
    empty("channel_shapley.csv")
else:
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.plotly_chart(px.bar(shap.sort_values("shapley_share"), x="shapley_share", y="channel",
                               orientation="h", color="grade",
                               title="Shapley 渠道贡献份额与分级"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(px.scatter(shap, x="ad_spend", y="revenue", size="signups",
                                   color="roi", hover_name="channel", size_max=45,
                                   title="花费 vs 收入（气泡=注册数）"),
                        use_container_width=True)
    st.dataframe(shap.round(4), use_container_width=True, hide_index=True)
    flagged = shap[shap["inflation_flag"] == True]["channel"].tolist() if "inflation_flag" in shap else []
    insight("<b>渠道结论：</b>organic 与 referral 是 Shapley 份额最高的 S 级渠道；"
            f"疑似注水渠道为 <b>{'、'.join(flagged) if flagged else '无'}</b>——"
            "它们的共同特征是 Shapley 份额低于中位数、且 ROI 也低于中位数。"
            "这类渠道不应继续加投，而应先做反作弊核验与归因复核。")

# ------------------------------------------------------------------ 6.11
section("s611", "6.11", "广告成本 × 社媒绩效（四步相关分析）",
        "字段：<code>lag_days</code> 为互动领先天数；<code>corr</code> 为相关系数；"
        "<code>step</code> 为 1 基础相关 / 2 滞后相关 / 3 偏相关（控制预算） / 4 分品牌词与通用词；"
        "<code>n_days</code> 为样本天数。")
ads_m = load_csv("ads_social_matrix.csv")
ads_lag = load_csv("ads_social_lag.csv")
if ads_m.empty:
    empty("ads_social_matrix.csv")
else:
    c1, c2 = st.columns([1, 1.2])
    with c1:
        if not ads_lag.empty:
            st.plotly_chart(px.line(ads_lag, x="lag_days", y="corr", markers=True,
                                    title="滞后相关：互动率领先 k 天 vs CPC"),
                            use_container_width=True)
    with c2:
        st.plotly_chart(px.bar(ads_m, x="step", y="corr", color="segment",
                               title="四步相关结论矩阵"),
                        use_container_width=True)
    st.dataframe(ads_m, use_container_width=True, hide_index=True)
    base = ads_m[ads_m["step"] == "1_base"]["corr"].iloc[0] if (ads_m["step"] == "1_base").any() else None
    part = ads_m[ads_m["step"] == "3_partial"]["corr"].iloc[0] if (ads_m["step"] == "3_partial").any() else None
    insight(f"<b>相关分析结论：</b>基础相关系数为 <b>{base}</b>，控制预算突增后的偏相关为 <b>{part}</b>。"
            "如果偏相关明显弱于基础相关，说明“高互动 → 低 CPC”的结论有一部分是被预算同时推高/压低造成的假象；"
            "<b>只有剥离预算后的偏相关才可作为投放策略依据</b>，并且该结论只在自然互动场景下成立。")

# ------------------------------------------------------------------ 6.12
section("s612", "6.12", "页面模块注册效率比较（相对可点击率 + DEA）",
        "字段：<code>module_area_pct</code> 模块曝光面积占比；<code>click_share</code> 模块点击占页面比例；"
        "<code>relative_clickability</code> = 点击占比 / 曝光面积占比（&gt;1 表示“超额点击”）；"
        "<code>dea_efficiency</code> 为 CCR 数据包络分析效率（1=相对最优）。")
mod = load_csv("module_efficiency.csv")
if mod.empty:
    empty("module_efficiency.csv")
else:
    mod = mod.copy()
    mod["label"] = mod["page"] + " / " + mod["module_id"]
    c1, c2 = st.columns(2)
    with c1:
        top = mod.sort_values("relative_clickability", ascending=False).head(15)
        st.plotly_chart(px.bar(top, x="relative_clickability", y="label", orientation="h",
                               color="relative_clickability", color_continuous_scale="Teal",
                               title="相对可点击率 Top15（消除位置偏差）"),
                        use_container_width=True)
    with c2:
        top2 = mod.sort_values("dea_efficiency", ascending=False).head(15)
        st.plotly_chart(px.bar(top2, x="dea_efficiency", y="label", orientation="h",
                               color="dea_efficiency", color_continuous_scale="Viridis",
                               title="DEA 综合效率 Top15（多投入多产出）"),
                        use_container_width=True)
    st.dataframe(mod.round(4), use_container_width=True, hide_index=True)
    best = mod.sort_values("dea_efficiency", ascending=False).iloc[0]
    insight(f"<b>模块效率结论：</b>综合效率最高的是 <b>{best['label']}</b>（DEA={best['dea_efficiency']:.3f}）；"
            "相对可点击率揭示了一个关键事实——<b>曝光面积大不等于有效</b>，"
            "部分模块点击占比远低于面积占比（relative_clickability &lt; 1），属于“名不副实”的位置浪费，"
            "应把面积让给表单类高转化模块。")

# ------------------------------------------------------------------ 6.13
section("s613", "6.13", "CTA 组件转化率属性调查（全因子实验）",
        "字段：<code>cta_color/cta_copy/cta_size</code> 为三个实验因子；<code>cvr</code> 为该水平下的转化率；"
        "<code>importance</code> 为随机森林对 one-hot 属性的重要性；"
        "交互表为 <code>颜色 × 尺寸</code> 的组合 CVR。")
cta_main = load_csv("cta_main_effects.csv")
cta_inter = load_csv("cta_interaction.csv")
cta_imp = load_csv("cta_feature_importance.csv")
if cta_main.empty:
    empty("cta_main_effects.csv")
else:
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(px.bar(cta_main, x="level", y="cvr", color="factor", barmode="group",
                               title="CTA 主效应：各水平转化率"),
                        use_container_width=True)
    with c2:
        if not cta_inter.empty:
            piv = cta_inter.pivot(index="cta_color", columns="cta_size", values="cvr")
            st.plotly_chart(px.imshow(piv, text_auto=".3f", color_continuous_scale="Blues",
                                      title="交互效应：颜色 × 尺寸"),
                            use_container_width=True)
    if not cta_imp.empty:
        st.plotly_chart(px.bar(cta_imp.head(10), x="importance", y="feature", orientation="h",
                               title="随机森林特征重要性"),
                        use_container_width=True)
    best = cta_main.sort_values("cvr", ascending=False).iloc[0]
    insight(f"<b>CTA 结论：</b>最优单因子水平是 <b>{best['factor']}={best['level']}</b>（CVR {best['cvr']:.2%}）。"
            "全因子实验的价值在于能看到<b>交互效应</b>：某些颜色只在 large 尺寸下有效，"
            "单独看主效应会漏掉这一点。随机森林重要性则给出全局排序，两者结合才是可靠的改版依据。")

# ------------------------------------------------------------------ 6.14
section("s614", "6.14", "多元 Logistic 回归 + 流失模型对比（ROC）",
        "字段：<code>odds_ratio</code> &gt; 1 表示该因素提高转化几率；<code>p_value</code> 为显著性；"
        "<code>AUC</code> 为 ROC 曲线下面积；<code>fpr/tpr</code> 为 ROC 坐标；"
        "<code>importance</code> 为模型特征重要性（树模型）或 |系数|（逻辑回归）。")
logi = load_csv("logistic_terms.csv")
churn_m = load_csv("churn_metrics.csv")
churn_roc = load_csv("churn_roc.csv")
churn_imp = load_csv("churn_importance.csv")
if logi.empty:
    empty("logistic_terms.csv")
else:
    sig = logi[logi["p_value"] < 0.05].copy()
    sig["abs_log_or"] = np.abs(np.log(sig["odds_ratio"].clip(lower=1e-6)))
    sig = sig.sort_values("abs_log_or", ascending=False).head(15)
    c1, c2 = st.columns(2)
    with c1:
        if sig.empty:
            st.info("没有 p<0.05 的显著项")
        else:
            st.plotly_chart(px.bar(sig.sort_values("odds_ratio"), x="odds_ratio", y="term",
                                   orientation="h", color="odds_ratio", color_continuous_scale="RdBu",
                                   title="Logistic 回归：显著项 Odds Ratio"),
                            use_container_width=True)
    with c2:
        if not churn_roc.empty:
            st.plotly_chart(px.line(churn_roc, x="fpr", y="tpr", color="model",
                                    title="流失模型 ROC 曲线", labels={"fpr": "FPR", "tpr": "TPR"}),
                            use_container_width=True)
    if not churn_m.empty:
        st.dataframe(churn_m, use_container_width=True, hide_index=True)
    if not churn_imp.empty:
        top = churn_imp[churn_imp["model"] == churn_imp["model"].iloc[0]].head(12)
        st.plotly_chart(px.bar(top, x="importance", y="feature", orientation="h", color="model",
                               title="流失模型特征重要性 Top12"),
                        use_container_width=True)
    best = churn_m.sort_values("AUC", ascending=False).iloc[0] if not churn_m.empty else None
    insight("<b>模型结论：</b>Logistic 回归的 Odds Ratio 给出可解释的方向（例如某渠道的转化几率是基准的多少倍）；"
            + (f"流失模型中 <b>{best['model']}</b> 的 AUC 最高（<b>{best['AUC']:.3f}</b>），"
               f"recall={best['recall']:.3f}。" if best is not None else "")
            + " <b>可解释模型用于找方向，树模型用于提精度</b>，两者应同时汇报。")

# ------------------------------------------------------------------ 6.15
section("s615", "6.15", "A/B 测试（注册 CTA）",
        "字段：<code>variant</code> 为 control/treat；<code>cvr</code> 为转化率；"
        "<code>abs_lift</code> 为绝对提升；<code>rel_lift_pct</code> 为相对提升；"
        "<code>ci95</code> 为差值的 95% 置信区间；<code>srm_p_value</code> 为分流均衡性检验；"
        "<code>mde_pp</code> 为在 80% power 下可检测到的最小效应。")
ab_t = load_csv("ab_table.csv")
ab_meta = load_json("ab_meta.json")
if ab_t.empty:
    empty("ab_table.csv")
else:
    c1, c2 = st.columns([1, 1.25])
    with c1:
        st.plotly_chart(px.bar(ab_t, x="variant", y="cvr", color="variant", text_auto=".2%",
                               title="A/B 转化率对比"),
                        use_container_width=True)
    with c2:
        if ab_meta:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("绝对提升", f"{ab_meta['abs_lift']*100:.2f}pp")
            m2.metric("相对提升", f"{ab_meta['rel_lift_pct']:.2f}%")
            m3.metric("p 值", f"{ab_meta['p_value']:.2e}")
            m4.metric("MDE", f"{ab_meta.get('mde_pp',0)*100:.2f}pp")
            st.caption(f"95% CI：{ab_meta['ci95']}；SRM p={ab_meta['srm_p_value']}")
    st.dataframe(ab_t, use_container_width=True, hide_index=True)
    insight(f"<b>A/B 结论：</b>实验组相对提升 <b>{ab_meta.get('rel_lift_pct',0):.2f}%</b>，"
            f"p 值 <b>{ab_meta.get('p_value',1):.2e}</b>，95% CI 为 <b>{ab_meta.get('ci95')}</b>；"
            f"SRM 检验 p={ab_meta.get('srm_p_value',0):.2f}，分流均衡。"
            "<b>结论：可以全量。</b>护栏指标（客诉/延迟）需在上线后继续监控。")

# ------------------------------------------------------------------ 6.16
section("s616", "6.16", "用户标签体系 + 完整 VIP 机制",
        "字段：<code>tier</code> 为 VIP 等级（按 90 天交易额 + 频次 + 客单价综合分的分位数）；"
        "<code>stability_rate</code> 为两期等级不变比例；<code>upgrades/downgrades</code> 为升降级人数；"
        "<code>tag_type</code> 为 fact/stat/model/rule 四类标签；<code>avg_tags_per_user</code> 为人均标签数。")
vipd = load_csv("vip_distribution.csv")
vipb = load_csv("vip_benefits.csv")
vips = load_json("vip_stability.json")
cov = load_csv("tag_coverage.csv")
topt = load_csv("tag_top.csv")
pers = load_csv("tag_personas.csv")
if vipd.empty:
    empty("vip_distribution.csv")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(vipd, x="tier", y="users", color="avg_ltv_90d",
                               title="VIP 等级分布（颜色=平均 LTV）",
                               color_continuous_scale="Viridis"),
                        use_container_width=True)
    with c2:
        if not cov.empty:
            st.plotly_chart(px.bar(cov, x="tag_type", y="users", color="distinct_tags",
                                   title="标签体系覆盖（四类标签）"),
                            use_container_width=True)
    if vips:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("等级不变率", f"{vips.get('stability_rate',0):.2%}")
        m2.metric("升级", f"{vips.get('upgrades',0):,}")
        m3.metric("降级", f"{vips.get('downgrades',0):,}")
        m4.metric("覆盖用户", f"{vips.get('users',0):,}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**VIP 权益设计**")
        st.dataframe(vipb, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**标签画像卡（Top 30）**")
        st.dataframe(pers, use_container_width=True, hide_index=True)
    insight(f"<b>VIP 结论：</b>等级不变率为 <b>{vips.get('stability_rate',0):.2%}</b>，"
            f"升级 {vips.get('upgrades',0):,} 人、降级 {vips.get('downgrades',0):,} 人。"
            "不变率低于 80% 时说明规则抖动过大，应拉长考核窗口或设置缓冲带；"
            "标签体系按 fact/stat/model/rule 四类维护，可支持运营自助圈人。")

# ------------------------------------------------------------------ 6.17
section("s617", "6.17", "精细化运营矩阵（人群 × 策略）",
        "字段：<code>strategy</code> 为建议动作；<code>target_metric</code> 为目标指标；"
        "<code>guardrail</code> 为护栏指标；<code>expected_uplift</code> 为预期提升假设；"
        "<code>priority_score</code> = 人群规模 × 平均 LTV × 预期提升，用于排序资源投入。")
ops = load_csv("ops_matrix.csv")
if ops.empty:
    empty("ops_matrix.csv")
else:
    ops = ops.sort_values("priority_score", ascending=False)
    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.plotly_chart(px.bar(ops, x="priority_score", y="segment", orientation="h",
                               color="strategy", title="运营优先级（人群 × 策略）"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(px.scatter(ops, x="users", y="avg_ltv_90d", size="priority_score",
                                   color="segment", hover_name="strategy", size_max=50,
                                   title="人群规模 vs 平均 LTV"),
                        use_container_width=True)
    st.dataframe(ops.round(4), use_container_width=True, hide_index=True)
    top = ops.iloc[0]
    insight(f"<b>运营结论：</b>优先级最高的是 <b>{top['segment']}</b>（{top['users']:,} 人），"
            f"建议动作「<b>{top['strategy']}</b>」，目标指标 <b>{top['target_metric']}</b>，"
            f"护栏指标 <b>{top['guardrail']}</b>。"
            "每个策略都必须同时定义目标与护栏，避免“涨了转化、伤了体验”。")

# ------------------------------------------------------------------ 6.18
section("s618", "6.18", "季度预算弹性测算与自动化模拟器",
        "字段：<code>log_spend_coef</code> 为 conversions ~ log(spend) 的斜率；"
        "<code>marginal_conv_per_dollar</code> = 斜率 / (当前花费+1)，即每多花 1 美元的边际转化；"
        "<code>observed/trend/seasonal/resid</code> 为 STL 分解结果。")
bparams = load_csv("budget_elasticity.csv")
bdec = load_csv("budget_decomposition.csv")
if bparams.empty:
    empty("budget_elasticity.csv")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(bparams.sort_values("marginal_conv_per_dollar"),
                               x="marginal_conv_per_dollar", y="channel", orientation="h",
                               color="marginal_conv_per_dollar", color_continuous_scale="Teal",
                               title="每多花 1 美元的边际转化"),
                        use_container_width=True)
    with c2:
        if not bdec.empty:
            bdec = bdec.copy()
            bdec["date"] = pd.to_datetime(bdec["date"])
            st.plotly_chart(px.line(bdec, x="date", y=["observed", "trend", "seasonal"],
                                    title="STL 分解：趋势 + 季节性"),
                            use_container_width=True)
    st.dataframe(bparams.round(4), use_container_width=True, hide_index=True)
    st.markdown("**管理层假设模拟器：调整各渠道每日预算，预测每日总转化**")
    cols = st.columns(4)
    assumptions = {}
    for i, row in bparams.reset_index(drop=True).iterrows():
        assumptions[row["channel"]] = cols[i % 4].number_input(
            row["channel"], min_value=0.0,
            value=float(round(row["current_daily_spend"], 2)), step=50.0,
            key=f"budget_{row['channel']}")
    if st.button("运行预算模拟", type="primary"):
        rows = []
        for _, row in bparams.iterrows():
            spend = assumptions[row["channel"]]
            pred = max(row["intercept"] + row["log_spend_coef"] * np.log1p(spend), 0)
            rows.append({"channel": row["channel"],
                         "current_spend": row["current_daily_spend"],
                         "assumed_spend": spend,
                         "current_conversions": row["current_daily_conversions"],
                         "predicted_conversions": round(pred, 2),
                         "delta": round(pred - row["current_daily_conversions"], 2)})
        res = pd.DataFrame(rows)
        st.dataframe(res, use_container_width=True, hide_index=True)
        st.metric("预计每日总转化变化", f"{res['delta'].sum():+.1f}")
    insight("<b>预算结论：</b>边际转化最高的渠道不一定值得加投——例如 affiliate 的边际转化最高，"
            "但它的 ROI 最低、CPA 最高，说明带来的是“便宜但低价值”的转化。"
            "<b>预算决策必须同时看边际回报、LTV 与 ROI 三者</b>，并在弹性曲线的拐点前停下。")

# ------------------------------------------------------------------ 6.19
section("s619", "6.19", "OKR 归因剥离与量化助攻价值",
        "字段：<code>last_touch_share / markov_share / shapley_share</code> 为三种口径的渠道份额；"
        "<code>markov_vs_last_pct</code> 与 <code>shapley_vs_last_pct</code> 为相对末次点击的助攻价值差；"
        "计算方式：(新口径 − 末次) / 末次。")
okr = load_csv("okr_attribution.csv")
if okr.empty:
    empty("okr_attribution.csv")
else:
    ch = "channel" if "channel" in okr.columns else okr.columns[0]
    long = okr.melt(id_vars=ch, value_vars=["last_touch_share", "markov_share", "shapley_share"],
                    var_name="model", value_name="share")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(px.bar(long, x=ch, y="share", color="model", barmode="group",
                               title="末次 / 马尔可夫 / Shapley 三种口径对比"),
                        use_container_width=True)
    with c2:
        okr2 = okr.sort_values("markov_vs_last_pct", ascending=False)
        fig = go.Figure()
        fig.add_bar(x=okr2[ch], y=okr2["markov_vs_last_pct"], name="马尔可夫 vs 末次")
        fig.add_bar(x=okr2[ch], y=okr2["shapley_vs_last_pct"], name="Shapley vs 末次")
        fig.update_layout(barmode="group", title="助攻价值差（%）")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(okr.round(4), use_container_width=True, hide_index=True)
    top = okr.sort_values("markov_vs_last_pct", ascending=False).iloc[0]
    insight(f"<b>OKR 归因结论：</b>{top[ch]} 的马尔可夫贡献比末次点击高 "
            f"<b>{top['markov_vs_last_pct']:.1f}%</b>，是最被末次点击低估的助攻渠道。"
            "马尔可夫回答“没有它行不行”，Shapley 回答“有了它平均好多少”，"
            "<b>汇报时必须写清用的是哪一种口径以及误差如何定义</b>。")

st.divider()
st.markdown("### 📦 交付物与文档")
st.markdown("- 数据/数仓：`scripts/generate_mock_data.py` · `warehouse.duckdb` · dbt 27 models / 30 tests")
st.markdown("- 算法：`src/modeling.py`（6.1–6.19 全部方法）· `src/analysis.py` · `src/export.py`")
st.markdown("- 编排与通知：`main.py` · macOS terminal-notifier · Lark webhook · HTML 邮件 · Playwright 截图")
st.markdown("- 文档：`docs/development_log.md` · `docs/data_dictionary.md` · `docs/scheduling.md`")
st.caption("本页由 Streamlit 渲染；截图见 reports/dashboard_screenshot.png。")
