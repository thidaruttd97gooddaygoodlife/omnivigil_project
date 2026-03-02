export default function Sidebar({
  healthScore,
  riskLevel,
  nodeStatus,
  serviceStatus,
  soundOn,
  onToggleSound
}) {
  return (
    <aside className="sidebar">
      <div className="brand glass">
        <div className="logo">OV</div>
        <div>
          <div className="brand-title">OMNIVIGIL</div>
          <div className="brand-sub">Cloud Command</div>
        </div>
      </div>
      <nav className="nav">
        <button className="nav-item active">Overview</button>
        <button className="nav-item">Telemetry</button>
        <button className="nav-item">Alerts</button>
        <button className="nav-item">Maintenance</button>
        <button className="nav-item">Infrastructure</button>
      </nav>
      <div className="sidebar-block glass">
        <div className="block-title">CLUSTER HEALTH</div>
        <div className="block-metric">
          <span className="metric-big">{healthScore}</span>
          <span className={`status-pill ${riskLevel}`}>{riskLevel}</span>
        </div>
        <div className="block-sub">K8s Scheduler latency 18ms</div>
      </div>
      <div className="sidebar-block glass">
        <div className="block-title">K8S NODES</div>
        {nodeStatus.map((node) => (
          <div key={node.name} className="infra-row">
            <span>{node.name}</span>
            <span className={`dot ${node.status}`} />
          </div>
        ))}
      </div>
      <div className="sound-toggle" onClick={onToggleSound}>
        <span className={`sound-dot ${soundOn ? "on" : "off"}`} />
        {soundOn ? "Sound On" : "Sound Off"}
      </div>
    </aside>
  );
}
