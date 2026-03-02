export default function LogsCard({ logEntries }) {
  return (
    <div className="card logs glass">
      <div className="card-label">LIVE POD ORCHESTRATION</div>
      {logEntries.map((entry) => (
        <div key={entry} className="log-row">{entry}</div>
      ))}
    </div>
  );
}
