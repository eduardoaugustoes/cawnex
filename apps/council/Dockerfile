FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/council/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY lambdas/council/src/council /app/council
COPY apps/council/main.py /app/main.py

ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import council" || exit 1

CMD ["python", "/app/main.py"]
