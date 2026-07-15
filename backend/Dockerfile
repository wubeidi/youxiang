FROM python:3.12-slim

WORKDIR /app

# 系统依赖（bcrypt/cryptography 已有 wheel，通常无需编译；保留 curl 便于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# 生产用多 worker；轮询调度器只应在单进程内运行，故这里用单 worker + 内部 asyncio 并发
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
