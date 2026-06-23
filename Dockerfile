# Stage 1
FROM ghcr.io/k8sgpt-ai/k8sgpt:latest AS k8sgpt

# Stage 2
FROM python:3.10-slim

# Install kubectl
RUN apt-get update && apt-get install -y curl \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/ \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# ✅ FIXED PATH
COPY --from=k8sgpt /k8sgpt /usr/local/bin/k8sgpt

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
