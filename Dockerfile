FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY services/tournament-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/tournament-service/ .
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/healthz || exit 1
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8003", "--workers", "4", "app:app"]