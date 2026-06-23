import { useEffect, useState, useCallback, useRef } from "react";
import { fetchIssues } from "./api";
import IssueCard from "./components/IssueCard";

// How often (ms) to re-poll after a remediation is applied
const POLL_INTERVAL_MS = 5_000;
// Max number of re-poll attempts before giving up
const MAX_POLL_ATTEMPTS = 12;

export default function App() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [pollCount, setPollCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const pollRef = useRef(null);

  // ── Core data fetch ────────────────────────────────────────────────────────
  const loadIssues = useCallback(async () => {
    try {
      const res = await fetchIssues();
      setIssues(res.data);
      setLastUpdated(new Date());
      return res.data;
    } catch (err) {
      console.error("Failed to fetch issues", err);
      return null;
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadIssues().finally(() => setLoading(false));
  }, [loadIssues]);

  // ── Verification loop ──────────────────────────────────────────────────────
  // Called by ActionButton when "Approve & Run" succeeds.
  // Polls /analyze every POLL_INTERVAL_MS until:
  //   • issues list is empty  → all clear
  //   • the resolved issue no longer appears → partial clear
  //   • MAX_POLL_ATTEMPTS reached → give up to avoid infinite polling
  const startVerificationLoop = useCallback((resolvedIssueText) => {
    // Cancel any running loop first
    if (pollRef.current) clearInterval(pollRef.current);

    let attempts = 0;
    setVerifying(true);
    setPollCount(0);

    pollRef.current = setInterval(async () => {
      attempts += 1;
      setPollCount(attempts);

      const freshIssues = await loadIssues();

      // Determine if the specific issue we just fixed is gone
      const issueGone =
        !freshIssues ||
        freshIssues.length === 0 ||
        !freshIssues.some((i) =>
          (i.issue || "").toLowerCase().includes(
            (resolvedIssueText || "").toLowerCase().slice(0, 40)
          )
        );

      if (issueGone || attempts >= MAX_POLL_ATTEMPTS) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setVerifying(false);
        setPollCount(0);

        if (issueGone && freshIssues !== null) {
          console.info("✅ Verification loop: issue resolved, dashboard updated.");
        } else {
          console.warn(
            "⚠️ Verification loop ended after max attempts. Manual check may be needed."
          );
        }
      }
    }, POLL_INTERVAL_MS);
  }, [loadIssues]);

  // Clean up interval on unmount
  useEffect(() => () => pollRef.current && clearInterval(pollRef.current), []);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1 className="dashboard-title">K8s AI Diagnostics</h1>
        <p className="dashboard-subtitle">Agentic analysis and automated remediation</p>

        {lastUpdated && (
          <p className="dashboard-meta">
            Last refreshed: {lastUpdated.toLocaleTimeString()}
            {verifying && (
              <span className="verifying-badge">
                <span className="pulse-dot" />
                Verifying fix… poll {pollCount}/{MAX_POLL_ATTEMPTS}
              </span>
            )}
          </p>
        )}

        <button
          className="btn btn-refresh"
          onClick={() => { setLoading(true); loadIssues().finally(() => setLoading(false)); }}
          title="Manually refresh cluster analysis"
        >
          🔄 Refresh
        </button>
      </header>

      {loading ? (
        <div className="loading-container">
          <div className="spinner" />
          <p>Analyzing cluster state…</p>
        </div>
      ) : issues.length > 0 ? (
        <div className="issues-grid">
          {issues.map((issue, idx) => (
            <IssueCard
              key={`${issue.issue}-${idx}`}
              data={issue}
              onExecuteSuccess={startVerificationLoop}
            />
          ))}
        </div>
      ) : (
        <div className="no-issues">
          <h3>✅ No issues detected</h3>
          <p>Your cluster is running optimally.</p>
        </div>
      )}
    </div>
  );
}
