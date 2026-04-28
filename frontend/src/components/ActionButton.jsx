import { runAction } from "../api";
import { useState } from "react";

export default function ActionButton({ command, safe, issue }) {
  const [running, setRunning] = useState(false);

  const handleRun = async () => {
    if (!window.confirm(`Execute the following command on the cluster?\n\n${command}`)) return;
    
    setRunning(true);
    try {
      const res = await runAction(command, issue);
      alert(`Success:\n${res.data.output}`);
    } catch (err) {
      alert(`Error:\n${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <button
      onClick={handleRun}
      disabled={!safe || running}
      className={`btn ${safe ? 'btn-safe' : 'btn-unsafe'}`}
    >
      {running ? (
        <>
          <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⚙️</span> 
          Executing...
        </>
      ) : safe ? (
        <>
          ⚡ Approve & Run
        </>
      ) : (
        <>
          ⚠️ Unsafe Action
        </>
      )}
    </button>
  );
}
