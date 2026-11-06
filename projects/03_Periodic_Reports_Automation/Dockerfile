# 纯脚本项目，不需要数据库，一个 python 镜像就够
FROM python:3.11-slim

WORKDIR /app

# openpyxl 处理中文不用字体，但导出 PDF 时要；先不装，保持镜像小
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 默认跑一次「取数 → 渲染 → 落 HTML/Excel」，不发邮件
CMD ["python", "src/report_pipeline.py", "--no-email"]
