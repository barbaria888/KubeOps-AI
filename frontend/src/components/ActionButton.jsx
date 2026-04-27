import { runAction } from "../api";

export default function ActionButton({ command, safe, issue }) {

  const handleRun = async () => {
    if (!window.confirm(`Run?\n${command}`)) return;

    const res = await runAction(command, issue);
    alert(res.data.output);
  };

  return (
    <button
      onClick={handleRun}
      disabled={!safe}
      style={{
        background: safe ? "green" : "gray",
        color: "white",
        padding: "10px"
      }}
    >
      {safe ? "Approve & Run" : "Unsafe"}
    </button>
  );
}
