import { useEffect, useState } from "react";
import { fetchIssues } from "./api";
import IssueCard from "./components/IssueCard";

export default function App() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchIssues()
      .then((res) => {
        setIssues(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch issues", err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1 className="dashboard-title">K8s AI Diagnostics</h1>
        <p className="dashboard-subtitle">Agentic analysis and automated remediation</p>
      </header>

      {loading ? (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Analyzing cluster state...</p>
        </div>
      ) : issues.length > 0 ? (
        <div className="issues-grid">
          {issues.map((i, idx) => (
            <IssueCard key={idx} data={i} />
          ))}
        </div>
      ) : (
        <div className="no-issues">
          <h3>No issues detected</h3>
          <p>Your cluster is running optimally.</p>
        </div>
      )}
    </div>
  );
}
