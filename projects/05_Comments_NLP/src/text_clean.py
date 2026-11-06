# -*- coding: utf-8 -*-
"""文本清洗 / 分词 / 情感打分的公共函数。

为什么单独抽出来：
原来这套逻辑在 Tmall_Review_Crawling...py 里跟爬虫、LDA 混着写，
后来想在 app.py 里复用，只能整段复制，改一次要改两个地方，很蠢。
"""

import re
import warnings
from collections import Counter

warnings.filterwarnings("ignore")  # jieba 首次加载会刷一堆日志

# 手写的停用词，就三十来个 —— 电商评论里真正的噪声其实很集中，
# 用通用停用词表反而会把「也就那样」「不值」这类有效表达过滤掉
STOPWORDS = {
    "的", "了", "是", "我", "也", "就", "都", "和", "在", "有", "很", "还",
    "这个", "那个", "一个", "什么", "因为", "所以", "但是", "而且", "然后",
    "感觉", "觉得", "真的", "非常", "比较", "一点", "有点", "东西", "宝贝",
    "卖家", "客服", "物流", "包装", "收到", "买", "用", "说", "没", "不",
}

# SnowNLP 没用上的兜底词典。朴素得有点丢人，但 snowNLP 装不上时能跑
POS_WORDS = {"好", "喜欢", "满意", "舒服", "划算", "快", "赞", "推荐", "精致", "惊喜", "值得"}
NEG_WORDS = {"差", "垃圾", "失望", "慢", "贵", "假", "破", "退货", "难用", "臭", "漏"}

EMOJI_RE = re.compile("[\U00010000-\U0010ffff]", flags=re.UNICODE)


def clean(text):
    """去表情、去多余空白、去纯符号。数字保留，价格类的评论里数字有意义。"""
    if not isinstance(text, str):
        return ""
    text = EMOJI_RE.sub("", text)
    text = re.sub(r"[^\w\u4e00-\u9fa5]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_words(text):
    """分词 + 过滤。单字基本没信息量，直接扔掉。"""
    import jieba

    words = []
    for w in jieba.cut(clean(text)):
        w = w.strip()
        if len(w) < 2 or w in STOPWORDS or w.isdigit():
            continue
        words.append(w)
    return words


def sentiment_score(text):
    """情感分：0 最负面，1 最正面。

    优先用 SnowNLP；装不上（或者它在这个领域不准）就用词典兜底。
    说实话 SnowNLP 在电商短评论上只能当参考，所以 app 里我把它当「大概看看」用。
    """
    try:
        from snownlp import SnowNLP

        return float(SnowNLP(text).sentiments)
    except Exception:
        words = set(split_words(text))
        pos, neg = len(words & POS_WORDS), len(words & NEG_WORDS)
        if pos + neg == 0:
            return 0.5
        return round(pos / (pos + neg), 4)


def word_freq(texts, topn=20):
    counter = Counter()
    for t in texts:
        counter.update(split_words(t))
    return counter.most_common(topn)


def split_by_sentiment(texts, threshold=0.5):
    """按情感分正负两组，后面做词云和 LDA 都是分开做的。"""
    pos, neg = [], []
    for t in texts:
        (pos if sentiment_score(t) >= threshold else neg).append(t)
    return pos, neg
