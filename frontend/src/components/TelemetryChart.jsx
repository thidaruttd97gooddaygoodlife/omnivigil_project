export default function TelemetryChart({ latestReading, telemetryPath, vibrationPath }) {
  return (
    <section className="card chart glass">
      <div className="chart-header">
        <div>
          <div className="card-label">TELEMETRY REALTIME</div>
          <div className="chart-sub">Stream: MQTT / Ingress: NGINX Controller</div>
        </div>
        <div className="chart-metrics">
          <div>
            <div className="metric-label">Temperature</div>
            <div className="metric-value">{latestReading ? `${latestReading.temperature_c.toFixed(1)}°C` : "--"}</div>
          </div>
          <div>
            <div className="metric-label">Vibration</div>
            <div className="metric-value">{latestReading ? latestReading.vibration_rms.toFixed(2) : "--"}</div>
          </div>
        </div>
      </div>
      <svg viewBox="0 0 820 200" className="chart-svg">
        <defs>
          <linearGradient id="tempGlow" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#ff7a1a" />
            <stop offset="100%" stopColor="#f6b26b" />
          </linearGradient>
          <linearGradient id="vibGlow" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#6b6eff" />
            <stop offset="100%" stopColor="#a3a6ff" />
          </linearGradient>
        </defs>
        <path d={telemetryPath} className="line temperature" />
        <path d={vibrationPath} className="line vibration" />
      </svg>
    </section>
  );
}
