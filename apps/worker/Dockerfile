# Pin Linux x86_64 explicitly so local builds on Apple Silicon don't produce
# an arm64 image that crashes on Fargate (Linux/amd64) with "exec format error".
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY lambdas/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY lambdas/worker/src/ ./worker_src/
COPY lambdas/murder/src/ ./murder_src/

ENV PYTHONPATH="/app/worker_src:/app/murder_src"

COPY apps/worker/main.py ./main.py

CMD ["python", "main.py"]
