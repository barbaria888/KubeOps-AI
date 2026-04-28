# Stage 1
FROM ghcr.io/k8sgpt-ai/k8sgpt:latest AS k8sgpt

# Stage 2
FROM python:3.10-slim




# ✅ FIXED PATH
COPY --from=k8sgpt /k8sgpt /usr/local/bin/k8sgpt

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
