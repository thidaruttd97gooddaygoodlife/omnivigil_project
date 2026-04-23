export default function MobileSimulator({ latestAlert }) {
  return (
    <div className="card mobile glass">
      <div className="card-label">MOBILE UI SIMULATOR</div>
      <div className="mobile-screen">
        <div className="mobile-header">LINE Notify</div>
        <div className="mobile-message">
          <div className="mobile-title">OmniVigil Agent</div>
          <div className="mobile-text">
            {latestAlert
              ? `Risk ${latestAlert.risk_level} on ${latestAlert.machine_id}`
              : "Awaiting alerts"}
          </div>
          <div className="mobile-actions">
            <button>View Detail</button>
            <button className="ghost">Acknowledge</button>
          </div>
        </div>
      </div>
    </div>
  );
}
