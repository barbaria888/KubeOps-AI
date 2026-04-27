# -------------------------
# Stage 1: Get k8sgpt binary
# -------------------------
FROM ghcr.io/k8sgpt-ai/k8sgpt:latest AS k8sgpt

# -------------------------
# Stage 2: Main app
# -------------------------
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install only what's needed
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl (optional but useful)
RUN curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" -o kubectl \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# 🔥 Copy k8sgpt binary directly (NO download needed)
COPY --from=k8sgpt /usr/local/bin/k8sgpt /usr/local/bin/k8sgpt

# App setup
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
