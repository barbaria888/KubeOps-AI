import ActionButton from "./ActionButton";

export default function IssueCard({ data }) {
  return (
    <div className="issue-card">
      <div className="issue-header">
        <h3>
          <span className="issue-badge">Alert</span>
          Issue Detected
        </h3>
        <p className="issue-desc">{data.issue}</p>
      </div>

      <div className="issue-section">
        <h4>AI Diagnosis</h4>
        <div className="issue-explanation">
          {data.explanation}
        </div>
      </div>

      <div className="issue-section">
        <h4>Suggested Remediation</h4>
        <div className="code-block-wrapper">
          <code className="code-block">{data.suggested_action}</code>
        </div>
      </div>

      <div className="card-actions">
        <ActionButton command={data.suggested_action} safe={data.safe} issue={data.issue} />
      </div>
    </div>
  );
}
