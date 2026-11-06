"""评论速览页：丢一批评论进来，先看情感分布和高频词。

起因很实际：新采回来两万多条评论，我要先确认「是不是真的在骂运费」，
开 notebook 太慢，写个页面点两下更快。界面没美化，能用就行。

启动：
    streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.text_clean import sentiment_score, split_by_sentiment, word_freq  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="评论速览", layout="centered")
st.title("评论速览")

source = st.radio("数据来源", ["样例数据", "上传 CSV"], horizontal=True)
texts = []

if source == "样例数据":
    df = pd.read_csv(BASE_DIR / "sample_data" / "comments_sample.csv")
    texts = df["评论内容"].dropna().astype(str).tolist()
else:
    uploaded = st.file_uploader("CSV 需要有「评论内容」这一列", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        if "评论内容" not in df.columns:
            st.error("没有找到「评论内容」列，表头是：%s" % list(df.columns))
            st.stop()
        texts = df["评论内容"].dropna().astype(str).tolist()

pasted = st.text_area("也可以直接粘几条评论（一行一条）", height=100)
if pasted.strip():
    texts = texts + [t.strip() for t in pasted.splitlines() if t.strip()]

if not texts:
    st.info("先选数据或粘几句话")
    st.stop()

scores = [sentiment_score(t) for t in texts]
pos_ratio = sum(s >= 0.6 for s in scores) / len(scores)
neg_ratio = sum(s <= 0.4 for s in scores) / len(scores)

c1, c2, c3 = st.columns(3)
c1.metric("条数", len(texts))
c2.metric("偏正面", "%.1f%%" % (pos_ratio * 100))
c3.metric("偏负面", "%.1f%%" % (neg_ratio * 100))
st.caption("阈值 0.6 / 0.4 是粗略划的，SnowNLP 在这类短评论上只能当参考")

pos_texts, neg_texts = split_by_sentiment(texts)

t1, t2 = st.tabs(["正面高频词", "负面高频词"])
with t1:
    freq = word_freq(pos_texts, topn=15)
    st.bar_chart(pd.Series(dict(freq)))
with t2:
    freq = word_freq(neg_texts, topn=15)
    st.bar_chart(pd.Series(dict(freq)))

with st.expander("看明细"):
    st.dataframe(
        pd.DataFrame({"评论内容": texts, "情感分": [round(s, 3) for s in scores]}).sort_values(
            "情感分", ascending=False
        ),
        use_container_width=True,
        hide_index=True,
    )
