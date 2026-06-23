# 🎨 React AI Dashboard (Frontend)

This directory contains the user interface for the K8s Agentic AI pipeline. Built with **Vite** and **React**, it provides a clean, single-pane-of-glass view into your cluster's health and the AI's deductions.

## 🧩 Components Overview

- **`App.jsx`**: The main container that fetches issues from the Backend. It implements the automated **Remediation Verification Loop**:
  - Sets an interval every 5 seconds (up to 12 attempts) upon execution success.
  - Compares subsequent fetched issues to the resolved issue text.
  - Automatically updates the UI status and clears the interval when the issue is resolved or max attempts are reached.
  - Provides a **manual Refresh button** and displays a **Last refreshed** timestamp in the header.
  - Displays a **Verifying badge** with an animated pulsing dot and count (`Verifying fix… poll N/12`).
- **`components/IssueCard.jsx`**: Displays the exact Kubernetes fault, the AI's explanation, and the suggested `kubectl` fix. Forwards the `onExecuteSuccess` callback to the ActionButton.
- **`components/ActionButton.jsx`**: The "Approve & Run" interface. 
  - Triggers the `onExecuteSuccess(issueText)` callback immediately upon successful execution.
  - Replaces blocking `window.alert()` dialogs with an **inline result panel** containing:
    - A `✅ Executed` status badge.
    - A scrollable terminal code block with raw `kubectl` command execution output.
    - A `🔄 Verifying fix — dashboard will update automatically…` helper message.
- **`api.js`**: Axios wrappers connecting to the backend endpoints, including the new `/webhook/results` polling helper (`fetchWebhookResults()`).
- **`index.css`**: Scorpio-themed styling, featuring styling for the new `.verifying-badge`, `.pulse-dot`, `.btn-refresh`, and inline `.execution-result` panels.

## 🛡️ "Approve & Run" Safety & Verification Loop

The dashboard is designed for **Human-in-the-Loop** (HITL) autonomy:

1. **Guardrails**: When the backend's guardrail marks a command as **Unsafe** (e.g. `delete pod`), the execution button is disabled.
2. **Approval**: When marked **Safe**, the button glows green, requiring explicit administrator approval to trigger execution.
3. **Execution & Inline Feedback**: Clicking the button runs the command and prints the output inline in the card (no intrusive browser alert dialogs).
4. **Autonomous Verification**: Upon execution, the frontend starts a polling verification loop to automatically check the cluster state. It monitors the dashboard issues list and transitions the UI back to a clean state once the issue disappears from the backend scans.

## 🚀 Running Locally

```bash
# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

Your app will be available at `http://localhost:5173`.
