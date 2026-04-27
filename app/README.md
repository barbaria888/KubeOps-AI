# 🧠 Fast AI Backend

This directory contains the core intelligence of the K8s Agentic AI system. Built with **FastAPI**, it orchestrates the interaction between K8sGPT, your local Kubernetes cluster, a Vector Database, and the Ollama LLM.

## 📁 Directory Structure
```text
app/
├── main.py            # FastAPI Entry Point (Routes)
├── agents/            # Autonomous AI Agents
│   ├── analyzer.py    # Extracts issues from K8sGPT
│   ├── reasoning.py   # Asks Ollama to explain the issue (with Vector Context)
│   ├── action.py      # Generates a safe kubectl command
│   └── guardrail.py   # Blocks destructive commands
├── tools/             # Integrations
│   ├── k8sgpt.py      # K8sGPT subprocess runner
│   ├── kubectl.py     # Kubectl subprocess runner
│   ├── ollama.py      # Local LLM API connector
│   └── vector_store.py# ChromaDB Incident Memory
```

## 🔄 How the Pipeline Works

1. **Discovery `GET /analyze`**: The backend triggers `k8sgpt analyze`. For every issue found, it passes the text to the **Reasoning Agent**.
2. **Context Retrieval**: The Reasoning Agent queries **ChromaDB** for similar historic incidents.
3. **LLM Generation**: Ollama (`gemma:2b`) is prompted with the issue + historic context to generate an explanation and a suggested fix.
4. **Validation**: The **Guardrail Agent** scans the suggested `kubectl` command. If it contains words like `delete`, `rm`, or `wipe`, it marks `safe: false`.
5. **Execution `POST /execute`**: If approved by the frontend, the command runs. If successful, the incident (Issue + Solution pair) is permanently saved into the Vector Database for future reference!

## 🚀 Running Locally

Create a virtual environment and start the server:
```bash
pip install -r ../requirements.txt
uvicorn app.main:app --reload --port 8000
```
*(The backend expects Ollama to be running on `http://localhost:11434` and `kubectl / k8sgpt` to be installed on your host).*
