# 🎨 React AI Dashboard (Frontend)

This directory contains the user interface for the K8s Agentic AI pipeline. Built with **Vite** and **React Native**, it provides a clean, single-pane-of-glass view into your cluster's health and the AI's deductions.

## 🧩 Components Overview

- **`App.jsx`**: The main container that fetches issues from the Backend immediately upon loading.
- **`IssueCard.jsx`**: A streamlined card displaying the exact Kubernetes fault, the AI's plain-English explanation, and the suggested `kubectl` fix.
- **`ActionButton.jsx`**: The critical "Approve & Run" interface. 
- **`api.js`**: Axios wrappers connecting to the backend's `/analyze` and `/execute` endpoints.

## 🛡️ "Approve & Run" Safety System

The dashboard is designed for **Human-in-the-Loop** (HITL) autonomy. 
The AI will *never* execute a command on its own. 

1. When the backend's guardrail marks a command as **Unsafe** (e.g. `delete pod`), the button will be **greyed out and disabled**.
2. When marked **Safe**, the button will turn **Green**.
3. Clicking "Approve & Run" triggers a browser confirmation prompt so administrators can double-check the raw `kubectl` command before it strikes the cluster.
4. Upon successful execution, the issue metric is silently passed back to the backend to be indexed into the incident memory vector database!

## 🚀 Running Locally

```bash
# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

Your app will be available at `http://localhost:5173`.

## ⚡ Event-Driven UI (New)

The dashboard is now part of a closed-loop event system. As Prometheus detects cluster faults and fires alerts through Alertmanager, the backend processes them and immediately surfaces the newly diagnosed issues onto the UI for approval, removing the need for manual discovery!
