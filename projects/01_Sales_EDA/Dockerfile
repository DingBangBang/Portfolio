# 纯脚本 + streamlit 的项目，一个镜像就够，不折腾多阶段构建
FROM python:3.11-slim

WORKDIR /app

# 中文字体没装的话 notebook 导出的图会变方块，这里顺手装上（镜像会大一点，值得）
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
# 默认起看板；想跑批处理就 docker run ... python src/eda_funnel.py
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
