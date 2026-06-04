# MS5 Maintenance

Stub service for maintenance work orders.

## Endpoints
- GET /health
- POST /work-orders
- GET /work-orders
- GET /work-orders/{work_order_id}
- PATCH /work-orders/{work_order_id} (admin/supervisor JWT)
- PATCH /work-orders/{work_order_id}/ack (admin/supervisor JWT)
- PATCH /work-orders/{work_order_id}/status (admin/supervisor JWT)
- PATCH /work-orders/{work_order_id}/accept (admin/supervisor JWT)
- PATCH /work-orders/{work_order_id}/complete (admin/supervisor JWT)
