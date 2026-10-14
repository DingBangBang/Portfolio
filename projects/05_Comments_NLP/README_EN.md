# 05 · Review Text Mining & Topic Clustering (Comments_NLP)

> 中文版 → [README.md](./README.md)

**_An end-to-end pipeline from multi-source crawling of e-commerce/community reviews to Chinese tokenisation, sentiment, word clouds and LDA topic clustering._**

- Language: `Python`
- Core file: [Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py](./Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py)
- Thesis project: [thesis_project/SHU_comments_NLP.py](./thesis_project/SHU_comments_NLP.py)

## 1. Background

While analysing online-community word-of-mouth, I needed to answer two questions: **what are users praising, and what are they complaining about?** Such data sits in review sections and community posts with no ready-made structured dataset, so this project covers the whole chain: crawl the unstructured text, clean it, model it, and use a topic model to turn scattered complaints into actionable themes.

Sources include:

- Tmall product reviews (`Tmall_Review_Crawling_...py`);
- Douban Movie Top250 (`douban_spider.py`);
- 12306 train schedule data (`rail_tickets_spider.py`);
- Online-community user info and text (`online_community_userinfo_NLP.py`).

## 2. Stack

| Stage | Tools |
| --- | --- |
| Crawling | `requests` `lxml` `BeautifulSoup` `Selenium` `Scrapy` `urllib` |
| Chinese NLP | `jieba` `thulac` |
| Sentiment | `snownlp` (SnowNLP) |
| Topic model | `gensim` (LDA / corpora / models) |
| Visualisation | `pyLDAvis`, `wordcloud`, `matplotlib` |
| Machine learning | `scikit-learn` (`CountVectorizer` / `KMeans`) |

## 3. Key findings / design notes

- **Denoising first**: dedupe, mechanical compression, stop-word filtering and invalid-word removal before modelling — otherwise topics get dominated by noise words;
- **Model positive and negative separately**: split reviews by sentiment, then run word frequency TOP10, word clouds and LDA (10 topics each) on each group to avoid cross-contamination;
- **Controllable granularity**: LDA uses 10 topics with `pyLDAvis` to judge overlap and whether to re-tune;
- **Transferable pipeline**: crawling reviews, a movie chart, train schedules and community user info validated that the same crawl → clean → tokenise → model → visualise flow transfers across sources.

## 4. Layout

```
05_Comments_NLP/
├── Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py  # Core: crawl + LDA clustering
├── douban_spider.py                       # Douban Movie Top250 spider
├── rail_tickets_spider.py                 # 12306 train spider
├── online_community_userinfo_NLP.py       # Community user text analysis (KMeans/LSTM exploration)
└── thesis_project/
    ├── SHU_comments_NLP.py                # Thesis main pipeline
    ├── postopic.html                      # pyLDAvis interactive topic visualisation
    ├── sentiment_analysis_mindmap.png     # Text-analysis mindmap
    ├── wordcloud_from_fre_pos.png         # Positive word cloud
    └── wordcloud_from_fre_neg.png         # Negative word cloud
```

## 5. How to run

1. `pip install requests lxml beautifulsoup4 selenium scrapy jieba snownlp gensim pyLDAvis wordcloud matplotlib scikit-learn thulac tensorflow`;
2. Run `Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py`: crawl → clean → sentiment split → frequency/word cloud → LDA → `pyLDAvis`;
3. Word clouds need a Chinese font — set `font_path` to a font on your machine (currently Windows `msyh.ttc`).

> ⚠️ Note: the cookies and proxy IPs in the scripts are historical examples and long expired. Replace them with your own compliant credentials and respect the target sites' robots policy and terms of use.
