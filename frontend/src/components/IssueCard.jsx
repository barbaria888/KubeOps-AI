import ActionButton from "./ActionButton";

export default function IssueCard({ data }) {
  return (
    <div style={{ border: "1px solid #ccc", padding: 15, marginBottom: 10 }}>
      <h3>Issue</h3>
      <p>{data.issue}</p>

      <h4>Explanation</h4>
      <p>{data.explanation}</p>

      <h4>Fix</h4>
      <code>{data.suggested_action}</code>

      <br /><br />

      <ActionButton command={data.suggested_action} safe={data.safe} issue={data.issue} />
    </div>
  );
}
