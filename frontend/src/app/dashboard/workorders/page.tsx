'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/context/AuthContext';
import { mockWorkOrders, mockMachines, WorkOrder, Machine } from '@/lib/mockData';
import { maintenanceApi, machineApi } from '@/lib/api';
import { ClipboardList, Plus, Clock, CheckCircle, AlertTriangle, Loader } from 'lucide-react';

const DEMO_WORK_ORDERS_KEY = 'omnivigil_demo_workorders';
const PRIORITY_ORDER: Record<WorkOrder['priority'], number> = { urgent: 0, high: 1, medium: 2, low: 3 };
const DEMO_STATUS_TRANSITIONS: Record<WorkOrder['status'], WorkOrder['status'][]> = {
    open: ['open', 'in_progress', 'completed', 'cancelled'],
    in_progress: ['in_progress', 'completed', 'cancelled'],
    completed: ['completed'],
    cancelled: ['cancelled', 'open', 'in_progress'],
};

type ApiWorkOrder = {
    work_order_id: string;
    machine_id?: string;
    issue?: string;
    description?: string;
    priority?: WorkOrder['priority'];
    status?: string;
    assigned_to?: string;
    created_at: string;
    updated_at?: string;
    completed_at?: string;
    acknowledged_at?: string;
    estimated_hours?: number;
    source_alert_id?: string;
};

const persistDemoOrders = (items: WorkOrder[]) => {
    localStorage.setItem(DEMO_WORK_ORDERS_KEY, JSON.stringify(items));
};

const loadDemoOrders = (): WorkOrder[] => {
    const raw = localStorage.getItem(DEMO_WORK_ORDERS_KEY);
    if (!raw) {
        persistDemoOrders(mockWorkOrders);
        return mockWorkOrders;
    }
    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            persistDemoOrders(mockWorkOrders);
            return mockWorkOrders;
        }
        return parsed as WorkOrder[];
    } catch {
        persistDemoOrders(mockWorkOrders);
        return mockWorkOrders;
    }
};

const getCreatedAtTime = (order: WorkOrder) => {
    const timestamp = new Date(order.createdAt).getTime();
    return Number.isFinite(timestamp) ? timestamp : 0;
};

const sortWorkOrdersNewestFirst = (items: WorkOrder[]) => {
    return [...items].sort((a, b) => {
        const createdAtDiff = getCreatedAtTime(b) - getCreatedAtTime(a);
        if (createdAtDiff !== 0) return createdAtDiff;
        return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    });
};

export default function WorkOrdersPage() {
    const { hasAccess, user, isDemoMode } = useAuth();
    const [filter, setFilter] = useState<string>('all');
    const [showModal, setShowModal] = useState(false);
    const [orders, setOrders] = useState<WorkOrder[]>([]);
    const [machines, setMachines] = useState<Machine[]>([]);
    const [form, setForm] = useState({ machineId: '', title: '', description: '', priority: 'medium' as WorkOrder['priority'], assignedTo: '', estimatedHours: 2 });
    const [editingOrderId, setEditingOrderId] = useState<string | null>(null);
    const [editForm, setEditForm] = useState({ assignedTo: '', estimatedHours: '2' });
    const statusOptionsByState = DEMO_STATUS_TRANSITIONS;

    const loadMachines = useCallback(async () => {
        if (isDemoMode) {
            setMachines(mockMachines);
            return;
        }
        try {
            const res = await machineApi.get('/machines');
            setMachines(res.data);
        } catch {
            console.error('Failed to load MS6 machines');
            setMachines(mockMachines); // Fallback to mock if API fails
        }
    }, [isDemoMode]);

    const loadOrders = useCallback(async () => {
        if (isDemoMode) {
            setOrders(loadDemoOrders());
            return;
        }

        try {
            const res = await maintenanceApi.get('/work-orders');
            const apiOrders: WorkOrder[] = (res.data.items as ApiWorkOrder[]).map((item) => {
                // Map DB status to Frontend status
                let mappedStatus: WorkOrder['status'] = 'open';
                if (item.status === 'completed') mappedStatus = 'completed';
                else if (item.status === 'acknowledged') mappedStatus = 'in_progress';
                else if (item.status === 'in_progress') mappedStatus = 'in_progress';
                else if (item.status === 'cancelled') mappedStatus = 'cancelled';
                
                return {
                    id: item.work_order_id,
                    machineId: item.machine_id || 'unknown',
                    machineName: 'Resolving...',
                    title: item.issue || 'No Title',
                    description: item.description || item.issue || '',
                    priority: item.priority || 'medium',
                    status: mappedStatus,
                    assignedTo: item.assigned_to || 'Unassigned',
                    createdAt: item.created_at,
                    updatedAt: item.updated_at || item.completed_at || item.acknowledged_at || item.created_at,
                    estimatedHours: Number(item.estimated_hours ?? 2),
                    anomalyId: item.source_alert_id || undefined,
                };
            });
            setOrders(apiOrders);
        } catch {
            console.error('Failed to load live MS5 work orders');
        }
    }, [isDemoMode]);

    useEffect(() => { 
        loadMachines();
        loadOrders(); 
    }, [loadMachines, loadOrders]);

    const [showConfirm, setShowConfirm] = useState<{ id: string, status: string } | null>(null);

    const isSupervisor = user?.role === 'supervisor';
    const isAdmin = user?.role === 'admin';
    
    const canManageWorkOrders = isSupervisor || isAdmin;
    const canCreate = canManageWorkOrders;
    const canEditStatus = canManageWorkOrders;
    const canEditAssignment = canManageWorkOrders;

    const sortedFilteredOrders = useMemo(() => {
        const filtered = filter === 'all' ? orders : orders.filter(o => o.status === filter);
        return sortWorkOrdersNewestFirst(filtered);
    }, [filter, orders]);
    if (!hasAccess('workorders') && user?.role !== 'admin') {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }


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

    const handleCreate = async () => {
        const selectedMachine = machines.find((m) => m.id === form.machineId);
        const now = new Date().toISOString();
        try {
            if (isDemoMode) {
                const newOrder: WorkOrder = {
                    id: `WO-DEMO-${Date.now()}`,
                    machineId: form.machineId,
                    machineName: selectedMachine?.name || form.machineId,
                    title: form.title.trim(),
                    description: (form.description || form.title).trim(),
                    priority: form.priority,
                    status: 'open',
                    assignedTo: form.assignedTo.trim() || 'Unassigned',
                    createdAt: now,
                    updatedAt: now,
                    estimatedHours: Number(form.estimatedHours) || 0,
                };

                setOrders((prev) => {
                    const updated = [newOrder, ...prev];
                    persistDemoOrders(updated);
                    return updated;
                });
                setShowModal(false);
                setForm({ machineId: '', title: '', description: '', priority: 'medium', assignedTo: '', estimatedHours: 2 });
                return;
            }

            await maintenanceApi.post('/work-orders', {
                machine_id: form.machineId,
                issue: form.title,
                description: form.description,
                priority: form.priority,
                assigned_to: form.assignedTo || null,
                estimated_hours: form.estimatedHours,
            });
            await loadOrders();
            setShowModal(false);
            setForm({ machineId: '', title: '', description: '', priority: 'medium', assignedTo: '', estimatedHours: 2 });
        } catch (err) {
            console.error('Failed to create MS5 work order', err);
        }
    };

    const executeStatusChange = async () => {
        if (!showConfirm) return;
        const { id: orderId, status: newStatus } = showConfirm;

        try {
            if (isDemoMode) {
                setOrders((prev) => {
                    const updated = prev.map((order) => {
                        if (order.id !== orderId) return order;

                        const next = newStatus as WorkOrder['status'];
                        const allowed = DEMO_STATUS_TRANSITIONS[order.status];
                        if (!allowed.includes(next)) return order;

                        return {
                            ...order,
                            status: next,
                            updatedAt: new Date().toISOString(),
                        };
                    });
                    persistDemoOrders(updated);
                    return updated;
                });
            } else {
                if (newStatus === 'completed') {
                    await maintenanceApi.patch(`/work-orders/${orderId}/complete`, {
                        action_taken: 'Completed from dashboard',
                    });
                } else if (newStatus === 'in_progress') {
                    await maintenanceApi.patch(`/work-orders/${orderId}/accept`);
                } else {
                    await maintenanceApi.patch(`/work-orders/${orderId}/status`, { status: newStatus });
                }
                await loadOrders();
            }
        } catch (err) { 
            console.error('Failed to update status', err); 
        } finally {
            setShowConfirm(null);
        }
    };

    const handleStatusChange = (orderId: string, newStatus: string) => {
        setShowConfirm({ id: orderId, status: newStatus });
    };

    const startAssignmentEdit = (order: WorkOrder) => {
        setEditingOrderId(order.id);
        setEditForm({
            assignedTo: order.assignedTo === 'Unassigned' ? '' : order.assignedTo,
            estimatedHours: String(order.estimatedHours ?? 2),
        });
    };

    const cancelAssignmentEdit = () => {
        setEditingOrderId(null);
        setEditForm({ assignedTo: '', estimatedHours: '2' });
    };

    const saveAssignmentEdit = async (orderId: string) => {
        const estimatedHours = Number(editForm.estimatedHours);
        if (!Number.isFinite(estimatedHours) || estimatedHours < 0) {
            alert('Est. Hours must be a number greater than or equal to 0.');
            return;
        }

        const assignedTo = editForm.assignedTo.trim();

        try {
            if (isDemoMode) {
                setOrders((prev) => {
                    const updated = prev.map((order) => (
                        order.id === orderId
                            ? {
                                ...order,
                                assignedTo: assignedTo || 'Unassigned',
                                estimatedHours,
                                updatedAt: new Date().toISOString(),
                            }
                            : order
                    ));
                    persistDemoOrders(updated);
                    return updated;
                });
            } else {
                await maintenanceApi.patch(`/work-orders/${orderId}`, {
                    assigned_to: assignedTo || null,
                    estimated_hours: estimatedHours,
                });
                await loadOrders();
            }
            cancelAssignmentEdit();
        } catch (err) {
            console.error('Failed to update work order assignment', err);
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
                            {canEditAssignment && <th>Actions</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {sortedFilteredOrders.map(order => (
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
                                            {statusOptionsByState[order.status].map((statusOption) => (
                                                <option key={statusOption} value={statusOption}>
                                                    {statusOption === 'in_progress'
                                                        ? 'In Progress'
                                                        : statusOption.charAt(0).toUpperCase() + statusOption.slice(1)}
                                                </option>
                                            ))}
                                        </select>
                                    ) : (
                                        <span className={`badge ${order.status === 'completed' ? 'badge-normal' : order.status === 'in_progress' ? 'badge-info' : order.status === 'open' ? 'badge-warning' : 'badge-offline'}`}>
                                            {statusIcons[order.status]} {order.status === 'in_progress' ? 'In Progress' : order.status}
                                        </span>
                                    )}
                                </td>
                                <td style={{ fontSize: '0.85rem', minWidth: '160px' }}>
                                    {editingOrderId === order.id ? (
                                        <input
                                            className="input"
                                            placeholder="Engineer name"
                                            value={editForm.assignedTo}
                                            onChange={(e) => setEditForm({ ...editForm, assignedTo: e.target.value })}
                                            style={{ padding: '6px 8px', fontSize: '0.8rem', height: 'auto' }}
                                        />
                                    ) : (
                                        order.assignedTo
                                    )}
                                </td>
                                <td style={{ textAlign: 'center', minWidth: '110px' }}>
                                    {editingOrderId === order.id ? (
                                        <input
                                            className="input"
                                            type="number"
                                            min={0}
                                            step={0.5}
                                            value={editForm.estimatedHours}
                                            onChange={(e) => setEditForm({ ...editForm, estimatedHours: e.target.value })}
                                            style={{ padding: '6px 8px', fontSize: '0.8rem', height: 'auto', textAlign: 'center' }}
                                        />
                                    ) : (
                                        `${order.estimatedHours}h`
                                    )}
                                </td>
                                <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                                    {new Date(order.createdAt).toLocaleDateString('th-TH', { month: 'short', day: 'numeric' })}
                                </td>
                                {canEditAssignment && (
                                    <td style={{ whiteSpace: 'nowrap' }}>
                                        {editingOrderId === order.id ? (
                                            <div style={{ display: 'flex', gap: '8px' }}>
                                                <button className="btn btn-sm btn-primary" onClick={() => saveAssignmentEdit(order.id)}>
                                                    Save
                                                </button>
                                                <button className="btn btn-sm btn-secondary" onClick={cancelAssignmentEdit}>
                                                    Cancel
                                                </button>
                                            </div>
                                        ) : (
                                            <button className="btn btn-sm btn-ghost" onClick={() => startAssignmentEdit(order)}>
                                                Edit
                                            </button>
                                        )}
                                    </td>
                                )}
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

            {/* Confirm Status Change Modal */}
            {showConfirm && (
                <div className="modal-overlay" onClick={() => setShowConfirm(null)}>
                    <div className="modal-content" style={{ maxWidth: '400px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                        <div style={{ 
                            width: '60px', 
                            height: '60px', 
                            borderRadius: '50%', 
                            background: 'rgba(59, 130, 246, 0.1)', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            margin: '0 auto 20px',
                            color: 'var(--accent-primary)'
                        }}>
                            <ClipboardList size={30} />
                        </div>
                        <h2 style={{ marginBottom: '10px' }}>Confirm Status Change</h2>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
                            Are you sure you want to change the status of this work order to <strong>&quot;{showConfirm.status.replace('_', ' ')}&quot;</strong>?
                        </p>
                        <div className="form-actions" style={{ justifyContent: 'center', gap: '12px' }}>
                            <button className="btn btn-secondary" onClick={() => setShowConfirm(null)}>Cancel</button>
                            <button className="btn btn-primary" onClick={executeStatusChange}>
                                Confirm Change
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
