FROM python:3.10-slim

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies (clean + minimal)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    tar \
    && rm -rf /var/lib/apt/lists/*

# -------------------------
# Install kubectl (stable)
# -------------------------
RUN curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" -o kubectl \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# -------------------------
# Install k8sgpt (robust)
# -------------------------
# -------------------------
# Install k8sgpt (robust)
# -------------------------
RUN set -eux; \
    K8SGPT_URL=$(curl -s https://api.github.com/repos/k8sgpt-ai/k8sgpt/releases/latest \
      | grep browser_download_url \
      | grep -iE "k8sgpt_Linux_x86_64\.tar\.gz" \
      | cut -d '"' -f 4); \
    echo "Downloading from: $K8SGPT_URL"; \
    test -n "$K8SGPT_URL"; \
    curl -fL "$K8SGPT_URL" -o k8sgpt.tar.gz; \
    tar -xzf k8sgpt.tar.gz; \
    chmod +x k8sgpt; \
    mv k8sgpt /usr/local/bin/k8sgpt; \
    rm k8sgpt.tar.gz# -------------------------
# App setup
# -------------------------
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# -------------------------
# Run app
# -------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
