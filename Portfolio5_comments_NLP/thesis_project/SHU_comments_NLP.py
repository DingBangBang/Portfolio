import pandas as pd
import requests
import re
import time
from snownlp import SnowNLP
import io
import sys
from collections import Counter
import jieba
from matplotlib import pyplot as plt
import wordcloud
import warnings
from gensim import corpora, models
import pyLDAvis.gensim
import pyLDAvis



# =================获取数据==================
nick = []
quality = []
date = []
comment = []
page = 3  # 【每页20条，输入需要翻页的页数+1在page处】
for i in range(1, page, 1):
    print("正在爬取第" + str(i) + "页")
    first = 'https://rate.tmall.com/list_detail_rate.htm?itemId=557510761368&spuId=1067672569&sellerId=2820842454&order=3&currentPage='
    last = '&append=0&content=1&tagId=&posi=&picture=&groupId=&ua=098#E1hvCpvUvbpvUpCkvvvvvjiWPLFW1jDnRLqvtjnEPmPpljimRLLhgjtbRFMhzjEVRTOCvvpvvUmmRvhvCvvvvvvRvpvhMMGvvvvCvvOvCvvvphmgvpvIMMGv/qYvvnGvvUjUphvUNQvvvACvpvQovvv2UhCv2CUvvvWiphvWQO9CvvOWvvVvJhTIvpvUvvmvKtQXQv9UvpCWh81Fvva4YExrs8TrEcqvac7Q+ulQbNotlfh0yj6Ofa1l+boJEcqvaNshVBrQpKFZARp7RAYVyO2vqbVQWl4vAWFIRfU6pwet9E7rjv==&needFold=0&_ksTS=1614312455436_436&callback=jsonp437'
    url = first + str(i) + last
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0',
        'referer': 'https://list.tmall.com/search_product.htm?q=%D6%B2%B4%E5%D0%E3&type=p&spm=a220m.1000858.a2227oh.d100&from=.list.pc_1_searchbutton',
        'cookie': 'cna=MQY3F16TIiUCAXj0KLkDrCSr; isg=BAMDf6e9Z11oDhSkH8Y_-OInkceteJe68MstDTXgvWKY9CAWvElzCjQibgS6z--y; tfstk=c7UCBAb24pvCQyTywW1w8hf5io3CZHLI_HMLOkoQGawNk-V1i0YqhJasqdmKSf1..; l=eBPYPbzmOInY98vFKO5Cnurza779fIRV1kPzaNbMiInca1WdNeRHzNCIr97HldtfgtfU-eKzpOD6ydnM-q4LRE_ceTwhKXIpBqp9-; lid=t_1498050231982_0133; enc=pI1QRFc21Y3%2BeedHEHCwaPQQxxXEGuvHw%2BQPROnTlxuv7WPkm%2FsDxEl8DD1HVRvPSq%2BUF6522Tj3eWc3Oe%2BxqQ%3D%3D; sgcookie=E100yGUBtKmZPVt1SUzKwzJN5TgRxYduHpqQ6LEOTNjgevd9Llmpw%2BiCkCNIEFIKzep26emR9fxKMYiZeNBDsRAMnhFLBsy08lT4W%2Fd1g3G%2FCK0cS; lgc=t_1498050231982_0133; _tb_token_=e76dbbf173ee4; cookie2=18ca72ed93207c71af40832a44f69dfd; xlly_s=1; dnk=t_1498050231982_0133; uc1=existShop=false&cookie16=UtASsssmPlP%2Ff1IHDsDaPRu%2BPw%3D%3D&cookie21=U%2BGCWk%2F7p4mBoUyS4E9C&cookie15=Vq8l%2BKCLz3%2F65A%3D%3D&cookie14=Uoe1hgR2h5poXQ%3D%3D&pas=0; csg=c34b003f; _l_g_=Ug%3D%3D; unb=3334488617; cookie1=B0OtIf8tUpGpFggiRbxP9Rqge9vJMacTRJkR2cf0lYg%3D; login=true; cookie17=UNN%2BwsEaojiS1g%3D%3D; _nk_=t_1498050231982_0133; sg=37e'
    }
    try:
        proxy = {'http': '108.49.237.244:80'}
        data = requests.get(url, headers=headers, proxies=proxy).text
        print(data)
        time.sleep(10)
        nickname = re.findall('"displayUserNick":"(.*?)"', data)
        nick.extend(nickname)
        auctionSku = re.findall('"auctionSku":"(.*?)"', data)
        quality.extend(auctionSku)
        rateDate = re.findall('"rateDate":"(.*?)"', data)
        date.extend(rateDate)
        rateContent = re.findall('"rateContent":"(.*?)"', data)
        comment.extend(rateContent)
    except Exception as e:
        print(str(e))
        print("本页爬取失败")
print('总共成功爬取 ' + str(len(comment)) + ' 条评论如下！')
print(comment)
df = pd.DataFrame()
df["用户名"] = nick
df["购买规格"] = quality
df["评论时间"] = date
df["评论内容"] = comment
df.to_excel("评论_汇总_brush.xlsx")
print('成功保存到Excel！')
# 保存数据到csv文件
df.to_csv("comments_summary_brush.csv", encoding="utf-8")
print('成功保存到CSV文件！')



# =================数据清洗==================
print('\n========该文档共有%s条评论如下：========' % len(df))
print(df.head())
print(type(df))
# 1文本去重
a1 = len(df)
df1 = pd.DataFrame(df.iloc[:, 4].unique())
a2 = len(df1)
print('========文本去重共删除了%s条评论如下：=========' % (a1 - a2))
print(df1.head())
# 2【重点】机械压缩去词（不改变评论条数）
注释掉是因为没什么意义，去掉了一句中的所有大于1次出现的字
ser1 = df1.iloc[:, 0].apply(str_unique)  # 这时，因为索引了第一列，所以结果成了Series；
print(type(ser1))  # 输出<class 'pandas.core.series.Series'>
df2 = pd.DataFrame(ser1.apply(str_unique, reverse=True))  # 再次生成DataFrame；
print('========机械压缩去词已完成如下：========')
print(df2.head())
# 4清除无意义文本：（1）”此用户没有填写评论“（2）”到货神速，双十一力度太给力了“
df2 = df1.replace('此用户没有填写评论!', '')
df2 = df1.replace('到货神速 双十一力度太给力了', '')
print('========清除无意义文本已完成如下：========')
print(df2.head())
# 3短句过滤
c1 = len(df2)
df3 = df2[df2.iloc[:, 0].apply(len) >= 4]
c2 = len(df3)
print('短句过滤共删除了%s条评论如下：' % (c1 - c2))
print(df3[:5])
df3.to_csv('temp_after_filter3_lipstick.txt', index=False, header=True, encoding='utf-8')
print('========预处理完成后还剩%s条评论========' % len(df3))
print('评论预处理过程结束！')



# =================情感分类==================
comments = pd.DataFrame(df3.copy())
print(comments.head())
coms = []
for i in comments['comment']:
    ss = SnowNLP(i)
    coms.append(ss.sentiments)
comments['score'] = coms
print(comments.head())
pos_data = comments[comments['score'] > 0.6]
neg_data = comments[comments['score'] < 0.4]
neutral_data = comments[(comments['score'] >= 0.4) & (comments['score'] <= 0.6)]
print(len(pos_data), 'pos_data\n', pos_data[:5])
print(len(neg_data), 'neg_data\n', neg_data[:5])
print(len(neutral_data), 'neutral_data\n', neutral_data[:5])
pos_data.to_csv('pos_data.csv')
neg_data.to_csv('neg_data.csv')
neutral_data.to_csv('neutral_data.csv')



# =================数据预处理==================
def mycut(str1):
    str1 = ' '.join(jieba.cut(str1))
    return str1


# 4SnowNLP模块做正负情感分析
df1 = pos_data['comment']
df2 = neg_data['comment']
print('pos:\n', df1.head(), 'neg\n', df2.head())


# 5jieba模块做中文分词处理，采用apply()广播形式加快分词速度
df11 = pd.DataFrame(df1.apply(mycut))
df22 = pd.DataFrame(df2.apply(mycut))
print('分词处理后正面：\n')
print(df11.head())
print('分词处理后负面：\n')
print(df22.head())


# 6去除停用词
stopfilepath = './stoplist_utf8.txt'
stop = pd.read_csv(stopfilepath, encoding='utf-8', header=None, sep='dingbangchu', engine='python')
stop = [' ', ''] + list(stop[0])
pos = pd.DataFrame(df11.copy())
neg = pd.DataFrame(df22.copy())
pos = pos['comment'].apply(lambda s: s.split(' '))
pos = pos.apply(lambda x: [i for i in x if i not in stop])
neg = neg['comment'].apply(lambda s: s.split(' '))
neg = neg.apply(lambda x: [i for i in x if i not in stop])
print('去除停用词后正面：\n')
print(pos.head())
print('去除停用词后负面：\n')
print(neg.head())
pos.to_csv('foundation_output/正面情感分词有效版.txt', index=False, header=False, encoding='utf-8')
neg.to_csv('foundation_output/负面情感分词有效版.txt', index=False, header=False, encoding='utf-8')


# 7词频统计

# (1)pos_wordcount
all_words = []
for n in range(0, len(pos)):
    for i in pos[n]:
        all_words.append(i)
word_count = pd.Series(all_words)
top_10 = word_count.value_counts(sort=True, ascending=False, dropna=True)
print('正面词频统计TOP10关键词：')
print(top_10[:10])
counts_result = dict(Counter(all_words))
counts_result = dict(sorted(counts_result.items(), key=lambda d: d[1], reverse=True))
with open('foundation_output/正面词频统计.txt', 'w', errors='ignore') as f:
    [f.write(str('{0},{1}\n'.format(key, value))) for key, value in counts_result.items()]
    
# (2)neg_wordcount
all_words = []
for n in range(0, len(neg)):
    for i in neg[n]:
        all_words.append(i)
word_count = pd.Series(all_words)
top_10 = word_count.value_counts(sort=True, ascending=False, dropna=True)
print('负面词频统计TOP10关键词：')
print(top_10[:10])
counts_result = dict(Counter(all_words))
counts_result = dict(sorted(counts_result.items(), key=lambda d: d[1], reverse=True))
with open('foundation_output/负面词频统计.txt', 'w', errors='ignore') as f:
    [f.write(str('{0},{1}\n'.format(key, value))) for key, value in counts_result.items()]


# 8词云图绘制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
warnings.filterwarnings("ignore")
# (1)pos_wordcloud
font = r'C:\Windows\Fonts\msyh.ttc'
wc = wordcloud.WordCloud(
    background_color="white",
    height=800,
    width=1000,
    font_path=font,
    prefer_horizontal=0.2,
    max_words=2000,
    relative_scaling=0.3,
    max_font_size=200).generate(str(pos.tolist()))
plt.imshow(wc, interpolation="nearest")
plt.axis("off")
plt.show()
wc.to_file("ciyun_foundaiton_pos.png")
print('词云图_正面已生成！')
# (2)neg_wordcloud
font = r'C:\Windows\Fonts\msyh.ttc'
wc = wordcloud.WordCloud(
    background_color="white",
    height=800,
    width=1000,
    font_path=font,
    prefer_horizontal=0.2,
    max_words=2000,
    relative_scaling=0.3,
    max_font_size=200).generate(str(neg.tolist()))
plt.imshow(wc, interpolation="nearest")
plt.axis("off")
plt.show()
wc.to_file("ciyun_foundation_neg.png")
print('词云图_负面已生成！')



# =================LDA模型聚类==================
# 正面主题分析
pos_dict = corpora.Dictionary(pos)
pos_corpus = [pos_dict.doc2bow(i) for i in pos]  # 建立语料库，bag of word
pos_lda = models.LdaModel(pos_corpus, num_topics=10, id2word=pos_dict, passes=10)  # LDA模型训练
print('\n以下是gensim实现的LDA模型训练结果：\n')
for i in range(10):
    print('pos_topic' + ' ' + str(i + 1) + ' : ')
    print(pos_lda.print_topic(i))
LDA_result_pos = pos_lda.print_topics(num_topics=10, num_words=10)
df_pos = pd.DataFrame(data=LDA_result_pos)
df_pos.to_excel('LDA_result_pos.xlsx', sheet_name='LDA_result_pos', startcol=0, startrow=0)
print('LDA_result_pos 成功输出!\n')
# 负面主题分析
neg_dict = corpora.Dictionary(neg)
neg_corpus = [neg_dict.doc2bow(i) for i in neg]
neg_lda = models.LdaModel(neg_corpus, num_topics=10, id2word=neg_dict, passes=10)
for i in range(10):
    print('neg_topic' + ' ' + str(i + 1) + ' : ')
    print(neg_lda.print_topic(i))
LDA_result_neg = neg_lda.print_topics(num_topics=10, num_words=10)
df_neg = pd.DataFrame(data=LDA_result_neg)
df_neg.to_excel('LDA_result_neg.xlsx')
print('LDA_result_neg 成功输出!\n')



# =================主题聚类可视化==================
data2 = pyLDAvis.gensim.prepare(pos_lda, pos_corpus, pos_dict)
print('以下是正面可视化参数\n')
print(data2)
pyLDAvis.save_html(data2, 'postopic.html')
pyLDAvis.display(data2)
pyLDAvis.show(data2, open_browser=True)

data1 = pyLDAvis.gensim.prepare(neg_lda, neg_corpus, neg_dict)
print('以下是负面可视化参数\n')
print(data1)
pyLDAvis.save_html(data1, 'negtopic.html')
pyLDAvis.display(data1)
pyLDAvis.show(data1, open_browser=True)