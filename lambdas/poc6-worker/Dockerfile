FROM public.ecr.aws/lambda/python:3.12

# Install git + gh CLI
RUN dnf install -y git tar gzip && \
    curl -fsSL https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz | \
    tar xz -C /usr/local --strip-components=1 gh_2.62.0_linux_amd64/bin/gh && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Handler
COPY handler.py .

CMD ["handler.lambda_handler"]
