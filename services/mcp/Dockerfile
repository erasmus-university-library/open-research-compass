FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mcp/mcp_server.py services/agent/config.py __init__.py ./

EXPOSE 9000

CMD ["python", "mcp_server.py"]
