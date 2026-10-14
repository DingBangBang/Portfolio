# 05 · 评论文本挖掘与主题聚类（Comments_NLP）

> English version → [README_EN.md](./README_EN.md)

**_从多源爬虫采集电商/社区评论，到中文分词、情感倾向、词云与 LDA 主题聚类的完整文本分析流程。_**

- 主要语言：`Python`
- 核心文件：[Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py](./Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py)
- 论文/项目核心：[thesis_project/SHU_comments_NLP.py](./thesis_project/SHU_comments_NLP.py)

## 1. 项目背景

我在做「线上社区用户口碑」相关分析时需要回答两个问题：**用户在夸什么、在骂什么？** 而这类数据大量散落在电商评论区、社区帖子里，没有现成结构化的数据集。因此这个项目覆盖了完整链路：先写爬虫把非结构化文本采下来，再做清洗与建模，最后用主题模型把「散点式吐槽」归纳成可运营的议题。

采集对象包括：

- 天猫商品评论（`Tmall_Review_Crawling_...py`）；
- 豆瓣电影 Top250（`douban_spider.py`）；
- 12306 车次信息（`rail_tickets_spider.py`）；
- 线上社区用户信息与文本（`online_community_userinfo_NLP.py`）。

## 2. 技术栈

| 环节 | 工具 |
| --- | --- |
| 采集 | `requests` `lxml` `BeautifulSoup` `Selenium` `Scrapy` `urllib` |
| 中文处理 | `jieba` `thulac` |
| 情感分析 | `snownlp`（SnowNLP） |
| 主题模型 | `gensim`（LDA / corpora / models） |
| 可视化 | `pyLDAvis`（交互式主题可视化）、`wordcloud`、`matplotlib` |
| 机器学习 | `scikit-learn`（`CountVectorizer` / `KMeans`） |

## 3. 核心发现 / 设计要点

- **文本去噪是前提**：先做去重、机械压缩去词、停用词过滤与无效词剔除，再进入建模，否则主题会大量被「好评」「宝贝」这类噪声占据；
- **正负面分开建模**：把评论按情感分正/负两组，分别做词频 TOP10、词云与 LDA（各 10 个主题），避免正负语义相互干扰；
- **主题粒度可控**：LDA 主题数设为 10，配合 `pyLDAvis` 交互面板判断主题是否重叠、是否需要调参；
- **多源采集铺路**：电商评论、电影榜单、车次、社区用户信息多源采集，验证了同一套「采集 → 清洗 → 分词 → 建模 → 可视化」流程的可迁移性。

## 4. 目录结构

```
05_Comments_NLP/
├── Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py  # 核心：采集 + LDA 主题聚类
├── douban_spider.py                       # 豆瓣电影 Top250 爬虫
├── rail_tickets_spider.py                 # 12306 车次爬虫
├── online_community_userinfo_NLP.py       # 社区用户文本分析（含 KMeans/LSTM 探索）
└── thesis_project/
    ├── SHU_comments_NLP.py                # 论文项目主流程
    ├── postopic.html                      # pyLDAvis 交互主题可视化结果
    ├── sentiment_analysis_mindmap.png     # 文本分析思维导图
    └── wordcloud_from_fre_pos.png         # 正面评论词云
    └── wordcloud_from_fre_neg.png         # 负面评论词云
```

## 5. 运行方式

1. 安装依赖：`pip install requests lxml beautifulsoup4 selenium scrapy jieba snownlp gensim pyLDAvis wordcloud matplotlib scikit-learn thulac tensorflow`；
2. 运行 `Tmall_Review_Crawling_and_LDA-Based_Topic_Clustering_Implementation.py`：依次采集 → 清洗 → 情感分组 → 词频/词云 → LDA → `pyLDAvis` 可视化；
3. 词云需要中文字体，请在代码中把 `font_path` 改成你本机的中文字体路径（当前为 Windows `msyh.ttc`）。

> ⚠️ 注意：脚本内的 Cookie、代理 IP 为历史示例值，早已失效，复现时请替换为你自己的合规凭据，并遵守目标站点的 robots 协议与使用条款。
