export default function NotificationCard({ latestAlert }) {
  return (
    <div className="card notification glass">
      <div className="card-label">LINE NOTIFICATION</div>
      <div className="line-card">
        <div className="line-title">OmniVigil (Alert)</div>
        <div className="line-text">
          {latestAlert
            ? `[${latestAlert.risk_level}] ${latestAlert.message || "Vibration anomaly pattern matched"}`
            : "No alerts yet"}
        </div>
        <button className="line-btn">View Log</button>
      </div>
    </div>
  );
}
