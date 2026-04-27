FROM python:3.10

# Fix: Install kubectl and k8sgpt so that the subprocess commands work
RUN apt-get update && apt-get install -y curl tar
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    
RUN curl -fL -o k8sgpt.tar.gz https://github.com/k8sgpt-ai/k8sgpt/releases/download/v0.3.43/k8sgpt_Linux_x86_64.tar.gz && \
    tar -xzf k8sgpt.tar.gz && \
    mv k8sgpt /usr/local/bin/k8sgpt

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
