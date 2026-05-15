# Pin Linux x86_64 explicitly so local builds on Apple Silicon don't produce
# an arm64 image that crashes on Fargate (Linux/amd64) with "exec format error".
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/stream/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/stream/src/ ./src/

ENV PYTHONPATH="/app/src"
ENV PORT=8080

EXPOSE 8080

COPY apps/stream/main.py ./main.py

CMD ["python", "main.py"]
