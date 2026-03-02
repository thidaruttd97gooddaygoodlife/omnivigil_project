export default function Topbar({ onSimulateBatch, onSimulateFail }) {
  return (
    <header className="topbar">
      <div className="factory-pill">FACTORY-01-PROD</div>
      <div className="topbar-actions">
        <button className="ghost" onClick={onSimulateBatch}>Simulate Batch</button>
        <button className="danger" onClick={onSimulateFail}>Simulate Fail</button>
      </div>
    </header>
  );
}
