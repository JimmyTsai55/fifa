FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8887
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run 注入 $PORT；SQLite 寫到容器可寫路徑即可（單實例、ephemeral 可接受）
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8887}"]
