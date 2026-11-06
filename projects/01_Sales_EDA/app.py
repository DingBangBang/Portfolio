"""01 的极简展示页。

不是 BI 看板，就是跑完 pipeline 之后想快速看一眼漏斗长什么样。
界面没做美化，一个漏斗图 + 一张分层表，够用。

启动：
    streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.eda_funnel import funnel_stats, read_events, repurchase_stats, rfm_tiers  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent


@st.cache_data(show_spinner="跑数据中...")
def analyze(path, chunk_size):
    """读一次算三样，别重复读文件 —— 大文件重复读是真的慢。"""
    data = read_events(path, chunk_size)
    return funnel_stats(data), repurchase_stats(data), rfm_tiers(data)


st.set_page_config(page_title="Sales EDA 速览", layout="centered")
st.title("电商行为日志 · 漏斗速览")

with st.sidebar:
    st.caption("数据文件")
    default_path = BASE_DIR / "sample_data" / "events_sample.csv"
    path = st.text_input("CSV 路径", value=str(default_path))
    chunk_size = st.number_input("chunk_size", min_value=10000, value=500000, step=10000)

if not Path(path).exists():
    st.error("文件不存在：%s" % path)
    st.stop()

stats, rebuy, rfm = analyze(path, int(chunk_size))

c1, c2, c3, c4 = st.columns(4)
c1.metric("UV", format(stats["uv"], ","))
c2.metric("订单数", format(stats["orders"], ","))
c3.metric("GMV", "$%s" % format(stats["gmv"], ",.0f"))
c4.metric("复购率", "%.1f%%" % (rebuy["repurchase_rate"] * 100))

st.subheader("转化漏斗")
funnel_df = pd.DataFrame(stats["steps"])
funnel_df["step"] = funnel_df["step"].map({"view": "浏览", "cart": "加购", "purchase": "成交"})
fig = px.funnel(funnel_df, x="users", y="step")
fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# 文字结论直接写在图上，省得每次都要自己再看一眼数字
for d in stats["drop_off"]:
    st.caption("%s → %s 流失 %.1f%%" % (d["from"], d["to"], d["lost_rate"] * 100))

st.subheader("粗分层（RFM 拍脑袋版）")
if rfm.empty:
    st.info("这个文件里没有 purchase 事件")
else:
    summary = (
        rfm.groupby("tier")
        .agg(users=("user_id", "nunique"), avg_monetary=("monetary", "mean"))
        .round(2)
        .reset_index()
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.bar_chart(summary.set_index("tier")["users"])
