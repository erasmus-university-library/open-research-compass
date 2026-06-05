FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/agent/agent.py services/agent/backend_agent.py services/agent/config.py __init__.py ./

EXPOSE 8000

CMD ["python", "backend_agent.py"]
