FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8003
EXPOSE 8003

# Healthcheck mirrors the /healthz endpoint used by the other services
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8003/healthz').status==200 else sys.exit(1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8003", "--workers", "2", "app:app"]
