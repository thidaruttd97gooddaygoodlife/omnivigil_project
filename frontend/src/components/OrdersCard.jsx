export default function OrdersCard({ workOrders }) {
  return (
    <div className="card orders glass">
      <div className="card-label">MAINTENANCE QUEUE</div>
      {workOrders.slice(-3).map((order) => (
        <div key={order.work_order_id} className="order-row">
          <span>{order.machine_id}</span>
          <span className="pill">{order.status}</span>
        </div>
      ))}
      {!workOrders.length && <div className="order-row">No work orders yet</div>}
    </div>
  );
}
