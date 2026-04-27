import { useEffect, useState } from "react";
import { fetchIssues } from "./api";
import IssueCard from "./components/IssueCard";

export default function App() {
  const [issues, setIssues] = useState([]);

  useEffect(() => {
    fetchIssues().then((res) => setIssues(res.data));
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>K8s AI Dashboard</h1>
      {issues.map((i, idx) => (
        <IssueCard key={idx} data={i} />
      ))}
    </div>
  );
}
