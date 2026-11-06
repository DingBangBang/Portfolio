# 05 主要是脚本 + 一个 streamlit 页面
FROM python:3.11-slim

WORKDIR /app

# 中文字体：词云不装字体会全变方框，这是必装的
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
# 默认起看板；爬虫和 LDA 用 docker run ... python crawler/tmall_crawler.py 这样跑
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
