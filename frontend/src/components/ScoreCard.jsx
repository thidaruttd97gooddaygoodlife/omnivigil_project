export default function ScoreCard({ healthScore, riskLevel }) {
  return (
    <div className="card score glass">
      <div className="card-label">CORE PREDICTIVE SCORE</div>
      <div className="score-row">
        <div>
          <div className="score-value">{healthScore}<span>%</span></div>
          <div className="score-sub">Bi-LSTM + PSO + Isolation Forest</div>
          <div className="score-meta">Isolation Forest drift: {riskLevel === "critical" ? "elevated" : "stable"}</div>
        </div>
        <div className="score-ring" style={{ "--score": `${healthScore}%` }}>
          <span>{riskLevel}</span>
        </div>
      </div>
    </div>
  );
}
