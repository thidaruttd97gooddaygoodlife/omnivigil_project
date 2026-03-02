export default function ServiceGrid({ serviceStatus, services }) {
  return (
    <div className="card services glass">
      <div className="card-label">EDGE SERVICE GRID</div>
      <div className="service-row">
        <span>API Gateway</span>
        <span className="pill up">UP</span>
      </div>
      {serviceStatus.map((svc) => (
        <div key={svc.name} className="service-row">
          <span>{svc.name}</span>
          <span className={`pill ${svc.status}`}>{svc.status.toUpperCase()}</span>
        </div>
      ))}
      <div className="service-row">
        <span>Line Gateway</span>
        <span className={`pill ${services.alert === "UP" ? "busy" : "down"}`}>{services.alert === "UP" ? "BUSY" : "DOWN"}</span>
      </div>
    </div>
  );
}
