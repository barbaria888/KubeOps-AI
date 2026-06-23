import { runAction } from "../api";
import { useState } from "react";

export default function ActionButton({ command, safe, issue, onExecuteSuccess }) {
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [output, setOutput] = useState("");

  const handleRun = async () => {
    if (!window.confirm(`Execute the following command on the cluster?\n\n${command}`)) return;

    setRunning(true);
    try {
      const res = await runAction(command, issue);
      const result = res.data?.output ?? "Command executed.";
      setOutput(result);
      setDone(true);

      // Kick off the verification polling loop in App.jsx
      if (typeof onExecuteSuccess === "function") {
        onExecuteSuccess(issue);
      }
    } catch (err) {
      alert(`Error:\n${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  // ── Already ran — show output inline instead of blocking alert ─────────────
  if (done) {
    return (
      <div className="execution-result">
        <span className="execution-badge">✅ Executed</span>
        <code className="execution-output">{output}</code>
        <p className="verifying-text">🔄 Verifying fix — dashboard will update automatically…</p>
      </div>
    );
  }

  return (
    <button
      onClick={handleRun}
      disabled={!safe || running}
      className={`btn ${safe ? "btn-safe" : "btn-unsafe"}`}
    >
      {running ? (
        <>
          <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⚙️</span>{" "}
          Executing…
        </>
      ) : safe ? (
        <>⚡ Approve &amp; Run</>
      ) : (
        <>⚠️ Unsafe Action</>
      )}
    </button>
  );
}
