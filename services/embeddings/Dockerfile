FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/embeddings/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/embeddings/embedding_service.py services/agent/config.py ./

EXPOSE 8080

CMD ["uvicorn", "embedding_service:app", "--host", "0.0.0.0", "--port", "8080"]
