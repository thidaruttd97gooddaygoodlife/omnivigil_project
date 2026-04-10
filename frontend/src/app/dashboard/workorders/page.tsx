'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { mockWorkOrders, mockMachines, WorkOrder, Machine } from '@/lib/mockData';
import { maintenanceApi, machineApi } from '@/lib/api';
import { ClipboardList, Plus, Clock, CheckCircle, AlertTriangle, Loader } from 'lucide-react';

export default function WorkOrdersPage() {
    const { hasAccess, user, isDemoMode } = useAuth();
    const [filter, setFilter] = useState<string>('all');
    const [showModal, setShowModal] = useState(false);
    const [orders, setOrders] = useState<WorkOrder[]>([]);
    const [machines, setMachines] = useState<Machine[]>([]);
    const [form, setForm] = useState({ machineId: '', title: '', description: '', priority: 'medium' as WorkOrder['priority'], assignedTo: '', estimatedHours: 2 });

    const loadMachines = async () => {
        if (isDemoMode) {
            setMachines(mockMachines);
            return;
        }
        try {
            const res = await machineApi.get('/machines');
            setMachines(res.data);
        } catch (err) {
            console.error('Failed to load MS6 machines');
            setMachines(mockMachines); // Fallback to mock if API fails
        }
    };

    const loadOrders = async () => {
        if (isDemoMode) {
             setOrders(mockWorkOrders);
             return;
        }

        try {
            const res = await maintenanceApi.get('/work-orders');
            // Use the machines loaded from API if possible (though we map below)
            const apiOrders: WorkOrder[] = res.data.items.map((item: any) => {
                // Ensure machines are loaded first or use mapping effectively
                return {
                    id: item.work_order_id,
                    machineId: item.machine_id || 'unknown',
                    machineName: 'Resolving...', // Will be resolved in the map below or in render
                    title: item.issue || 'No Title',
                    description: item.issue,
                    priority: item.priority || 'medium',
                    status: item.status === 'acknowledged' ? 'completed' : 'open',
                    assignedTo: 'Unassigned',
                    createdAt: item.created_at,
                    updatedAt: item.acknowledged_at || item.created_at,
                    estimatedHours: 2,
                };
            });
            setOrders([...apiOrders.reverse()]);
        } catch (err) {
            console.error('Failed to load live MS5 work orders');
        }
    };

    useEffect(() => { 
        loadMachines();
        loadOrders(); 
    }, [isDemoMode]);

    const isEngineer = user?.role === 'engineer';
    const isSupervisor = user?.role === 'supervisor';
    const isAdminOrIT = user?.role === 'admin' || user?.role === 'it';
    
    const canCreate = isEngineer || isAdminOrIT;
    const canEditStatus = isSupervisor || isAdminOrIT;

    if (!hasAccess('workorders')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const filtered = filter === 'all' ? orders : orders.filter(o => o.status === filter);
    const statusCounts = {
        open: orders.filter(o => o.status === 'open').length,
        in_progress: orders.filter(o => o.status === 'in_progress').length,
        completed: orders.filter(o => o.status === 'completed').length,
    };

    const statusIcons: Record<string, React.ReactNode> = {
        open: <AlertTriangle size={14} />,
        in_progress: <Loader size={14} />,
        completed: <CheckCircle size={14} />,
        cancelled: <Clock size={14} />,
    };

    const priorityOrder = { urgent: 0, high: 1, medium: 2, low: 3 };

    const handleCreate = async () => {
        try {
            await maintenanceApi.post('/work-orders', {
                machine_id: form.machineId,
                issue: form.title,
                priority: form.priority
            });
            await loadOrders();
            setShowModal(false);
            setForm({ machineId: '', title: '', description: '', priority: 'medium', assignedTo: '', estimatedHours: 2 });
        } catch (err) {
            console.error('Failed to create MS5 work order', err);
        }
    };

    const handleStatusChange = async (orderId: string, newStatus: string) => {
        if (newStatus === 'completed') {
            try {
                await maintenanceApi.patch(`/work-orders/${orderId}/ack`);
                await loadOrders();
            } catch (err) { console.error(err); }
        } else {
            setOrders(prev => prev.map(o => o.id === orderId ? { ...o, status: newStatus as WorkOrder['status'] } : o));
        }
    };

    return (
        <div className="fade-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1>📋 Work Orders</h1>
                    <p>Automated and manual maintenance work order management</p>
                </div>
                {canCreate && (
                    <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                        <Plus size={16} /> New Work Order
                    </button>
                )}
            </div>

            {/* Stats */}
            <div className="page-stats">
                <div className="stat-card glass-card">
                    <div className="stat-label">Open</div>
                    <div className="stat-value" style={{ color: 'var(--status-warning)' }}>{statusCounts.open}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">In Progress</div>
                    <div className="stat-value" style={{ color: 'var(--accent-primary)' }}>{statusCounts.in_progress}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Completed</div>
                    <div className="stat-value" style={{ color: 'var(--status-normal)' }}>{statusCounts.completed}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Total</div>
                    <div className="stat-value" style={{ color: 'var(--text-primary)' }}>{orders.length}</div>
                </div>
            </div>

            {/* Filters */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                {['all', 'open', 'in_progress', 'completed', 'cancelled'].map(f => (
                    <button key={f} className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setFilter(f)}>
                        {f === 'all' ? 'All' : f === 'in_progress' ? 'In Progress' : f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
            </div>

            {/* Table */}
            <div className="table-container glass-card">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Title</th>
                            <th>Machine</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>Assigned To</th>
                            <th>Est. Hours</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]).map(order => (
                            <tr key={order.id}>
                                <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent-cyan)', fontSize: '0.8rem' }}>{order.id}</td>
                                <td style={{ fontWeight: 500, color: 'var(--text-primary)', maxWidth: '200px' }}>
                                    {order.title}
                                    {order.anomalyId && <span style={{ fontSize: '0.7rem', color: 'var(--accent-purple)', marginLeft: '6px' }}>🤖 AI</span>}
                                </td>
                                <td>{machines.find(m => m.id === order.machineId)?.name || order.machineId}</td>
                                <td><span className={`badge badge-${order.priority}`}>{order.priority}</span></td>
                                <td>
                                    {canEditStatus ? (
                                        <select 
                                            className="input" 
                                            style={{ padding: '4px 8px', fontSize: '0.8rem', height: 'auto', background: 'var(--bg-card)' }}
                                            value={order.status}
                                            onChange={(e) => handleStatusChange(order.id, e.target.value)}
                                        >
                                            <option value="open">Open</option>
                                            <option value="in_progress">In Progress</option>
                                            <option value="completed">Completed</option>
                                            <option value="cancelled">Cancelled</option>
                                        </select>
                                    ) : (
                                        <span className={`badge ${order.status === 'completed' ? 'badge-normal' : order.status === 'in_progress' ? 'badge-info' : order.status === 'open' ? 'badge-warning' : 'badge-offline'}`}>
                                            {statusIcons[order.status]} {order.status === 'in_progress' ? 'In Progress' : order.status}
                                        </span>
                                    )}
                                </td>
                                <td style={{ fontSize: '0.85rem' }}>{order.assignedTo}</td>
                                <td style={{ textAlign: 'center' }}>{order.estimatedHours}h</td>
                                <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                                    {new Date(order.createdAt).toLocaleDateString('th-TH', { month: 'short', day: 'numeric' })}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Create Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h2>📋 Create New Work Order</h2>
                        <div className="form-group">
                            <label>Machine</label>
                            <select className="input" value={form.machineId} onChange={e => setForm({ ...form, machineId: e.target.value })}>
                                <option value="">Select machine...</option>
                                {machines.map(m => (
                                    <option key={m.id} value={m.id}>{m.name}</option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Title</label>
                            <input className="input" placeholder="Work order title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Description</label>
                            <textarea className="input" rows={3} placeholder="Describe the work needed..." value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} style={{ resize: 'vertical' }} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label>Priority</label>
                                <select className="input" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value as WorkOrder['priority'] })}>
                                    <option value="low">Low</option>
                                    <option value="medium">Medium</option>
                                    <option value="high">High</option>
                                    <option value="urgent">Urgent</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Est. Hours</label>
                                <input className="input" type="number" min={0.5} step={0.5} value={form.estimatedHours} onChange={e => setForm({ ...form, estimatedHours: Number(e.target.value) })} />
                            </div>
                        </div>
                        <div className="form-group">
                            <label>Assign To</label>
                            <input className="input" placeholder="Engineer name" value={form.assignedTo} onChange={e => setForm({ ...form, assignedTo: e.target.value })} />
                        </div>
                        <div className="form-actions">
                            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn btn-primary" onClick={handleCreate} disabled={!form.machineId || !form.title}>
                                <Plus size={16} /> Create
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
