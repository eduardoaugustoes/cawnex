# Pin Linux x86_64 explicitly so local builds on Apple Silicon don't produce
# an arm64 image that crashes on Fargate (Linux/amd64) with "exec format error".
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12
RUN dnf install -y git tar gzip && \
    curl -fsSL https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz | \
    tar xz -C /usr/local --strip-components=1 gh_2.62.0_linux_amd64/bin/gh && \
    dnf clean all && rm -rf /var/cache/dnf
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/worker/ ${LAMBDA_TASK_ROOT}/worker/
CMD ["worker.handler.lambda_handler"]
