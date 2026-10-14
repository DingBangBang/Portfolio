# -*- coding=utf-8 -*-
# __author = 'bonnieting'__

import pandas as pd
from collections import Counter
import re
from wordcloud import WordCloud
import jieba
import thulac
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

import numpy as np
from gensim.models import KeyedVectors
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense
from sklearn.preprocessing import LabelEncoder


# 1.import rawdata
df_raw = pd.read_csv('rawdata_treated.csv', encoding='utf-8', usecols=range(8))
pd.set_option('display.max_columns', None)
print(df_raw.head(10))
print(df_raw.shape)


# 2.start cleaning
unique_professions = df_raw.iloc[:, 3].drop_duplicates()
unique_professions = pd.DataFrame(unique_professions.apply(reverse=True))  # 再次生成DataFrame；
print(profession_uni.head(10))
print(profession_uni.shape)


# 3. delete invalid words
short_judge = unique_professions[:].str.len() < 3
unique_professions.insert(1, 'short_judge', short_judge)
result = unique_professions[unique_professions['short_judge'] == 'TRUE']['职业']
print(unique_professions[:])
print(unique_professions[:])
invalid_words = ['无业', '空白', '待业', '求职中']
cleaned_professions = unique_professions.apply(lambda x: re.sub('|'.join(invalid_words), '', str(x)))
thu1 = thulac.thulac()
processed_professions_dup = [list(thu1.cut(description)) for description in cleaned_professions]
print(processed_professions_dup)
flat_list_pp_dup = [word for sublist in processed_professions_dup for word in sublist]
print(flat_list_pp_dup)
processed_professions_dup = pd.DataFrame(flat_list_pp_dup)
# processed_professions_dup = processed_professions_dup.drop(columns=1)
print(processed_professions_dup)
print(processed_professions_dup.shape)


# 4. word counts
processed_professions_dup = processed_professions_dup.iloc[:,0]
print(type(processed_professions_dup))
word_counts = Counter(processed_professions_dup)
print(word_counts)
duplicate_words = [word for word, count in word_counts.items() if count > 1]
duplicates_dict = {word: [] for word in duplicate_words}
print(duplicate_words)
print(duplicates_dict)

print("===================================================")

print(list(cleaned_professions))
cleaned_professions = cleaned_professions.drop_duplicates()
cleaned_professions = list(cleaned_professions)
print(cleaned_professions)


# 5. do Chinese segment with thu
jieba.load_userdict("userdict.txt")
segmented_text = jieba.cut("主理人")
processed_professions = [list(jieba.cut(description)) for description in cleaned_professions]
thu = thulac.thulac()
processed_professions = [list(thu.cut(description)) for description in cleaned_professions]
processed_professions = [thu.cut(description, text=True) for description in cleaned_professions]
print(processed_professions)
flat_list_pp = [word for sublist in processed_professions for word in sublist]
flat_list_pp = [word for sublist in flat_list_pp for word in sublist]
flat_list_pp = [wo for word in sublist for sublist in processed_professions for word in sublist for wo in word]
print(flat_list_pp)


# 6. remove stopwords
stopword = pd.read_csv('stopword.csv', encoding='utf-8', header=None, usecols=range(1), error_bad_lines=False)
# , engine='python',squeeze=True,
# stopword = stopword.tolist()
print(stopword.tail(20))
# stopword = [' ', ''] + list(stopword[0])
stopword = stopword.values.tolist()
flat_list_sw = [word for sublist in stopword if pd.notnull(sublist) for word in sublist]
print(flat_list_sw)
processed_professions = pd.DataFrame(flat_list_pp)
processed_professions = processed_professions.drop(columns=1)
print(processed_professions)
print(processed_professions.shape)

# [word for word in text if word not in flat_list_sw]
def remove_stopwords(text):
    # for word in text:
    if text in flat_list_sw:
        text = ''
    else:
        text = text
    return text

valid_professions = processed_professions.applymap(remove_stopwords)  # lambda x: [i for i in x if i not in stopword]
print(valid_professions.shape)


# 7. extract text features with CountVectorizer
vectorizer = CountVectorizer()
valid_professions = valid_professions.values.tolist()
print(valid_professions)
feature_matrix = vectorizer.fit_transform([' '.join(description) for description in valid_professions])


# 8. cluster with KMeans
kmeans = KMeans(n_clusters=20)  # suppose there are 2 categories of occupation
kmeans.fit(feature_matrix)


# 9. print cluster results
for i, description in enumerate(valid_professions): # cleaned_profession
    print(description, "=> Cluster:", kmeans.labels_[i])
data = {'词汇': valid_professions, '聚类编号': kmeans.labels_[i]}
data = pd.DataFrame(data)


# 10. count samples in each cluster
cluster_counts = {i: len([1 for label in kmeans.labels_ if label == i]) for i in set(kmeans.labels_)}
print("Cluster counts:", cluster_counts)

# print details of each cluster
for cluster_label in set(kmeans.labels_):
    samples = [label for label, cluster in zip(kmeans.labels_, data) if cluster == cluster_label]
    print(f"Cluster {cluster_label}: {samples}")

# 11. illustrate cluster bubblechart
# extract cluster labels and sample_cnt
labels = list(cluster_counts.keys())
sizes = list(cluster_counts.values())

# bubbleplot
plt.scatter(kmeans.cluster_centers_[:, 0], kmeans.cluster_centers_[:, 1], s=sizes, c=labels, cmap='viridis')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
plt.title('Cluster Bubble Plot')
plt.colorbar(label='Cluster Label')
plt.show()

for profession in cleaned_professions:
    for word in duplicate_words:
        if word in profession:
            duplicates_dict[word].append(profession)
for word, duplicates in duplicates_dict.items():
    print(f"Duplicates for '{word}':")
    for duplicate in duplicates:
        print(duplicate)
    print(f"Count: {len(duplicates)}\n")


# 12. produce wordcloud
wordcloud = WordCloud(width=800, height=400).generate_from_frequencies(word_counts)
plt.figure(figsize=(10, 5))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis('off')
plt.show()

