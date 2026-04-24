'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Machine } from '@/lib/mockData';
import { machineApi } from '@/lib/api';
import { Cpu, Plus, Edit, Trash2, MapPin, Calendar } from 'lucide-react';

export default function MachinesPage() {
    const { hasAccess } = useAuth();
    const [machines, setMachines] = useState<Machine[]>([]);
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<string | null>(null);
    const [form, setForm] = useState({
        name: '', type: '', location: '', model: '', serialNumber: '',
        installDate: '', status: 'normal' as Machine['status'], healthScore: 100,
    });

    if (!hasAccess('machines')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const loadMachines = async () => {
        try {
            const res = await machineApi.get('/machines');
            setMachines(res.data);
        } catch (err) {
            console.error('Failed to load MS6 machines');
        }
    };

    useEffect(() => { loadMachines(); }, []);

    const statusColors: Record<string, string> = {
        normal: 'var(--status-normal)',
        warning: 'var(--status-warning)',
        critical: 'var(--status-critical)',
        offline: 'var(--status-offline)',
    };

    const openCreate = () => {
        setEditId(null);
        setForm({ name: '', type: '', location: '', model: '', serialNumber: '', installDate: '', status: 'normal', healthScore: 100 });
        setShowModal(true);
    };

    const openEdit = (m: Machine) => {
        setEditId(m.id);
        setForm({ name: m.name, type: m.type, location: m.location, model: m.model, serialNumber: m.serialNumber, installDate: m.installDate, status: m.status, healthScore: m.healthScore });
        setShowModal(true);
    };

    const handleSave = async () => {
        try {
            if (editId) {
                await machineApi.put(`/machines/${editId}`, form);
            } else {
                await machineApi.post('/machines', form);
            }
            await loadMachines();
            setShowModal(false);
        } catch (err) {
            console.error('Failed to save machine');
        }
    };

    const handleDelete = async (id: string) => {
        if (confirm('Delete this machine?')) {
            try {
                await machineApi.delete(`/machines/${id}`);
                await loadMachines();
            } catch (err) {
                console.error('Failed to delete machine');
            }
        }
    };

    return (
        <div className="fade-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1>⚙️ Machine Registry</h1>
                    <p>Register, edit, and manage all factory machines</p>
                </div>
                <button className="btn btn-primary" onClick={openCreate}>
                    <Plus size={16} /> Register Machine
                </button>
            </div>

            {/* Stats */}
            <div className="page-stats">
                <div className="stat-card glass-card">
                    <div className="stat-label">Total Machines</div>
                    <div className="stat-value" style={{ color: 'var(--accent-primary)' }}>{machines.length}</div>
                </div>
                {['normal', 'warning', 'critical', 'offline'].map(s => (
                    <div key={s} className="stat-card glass-card">
                        <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className={`status-dot ${s}`} style={{ width: '8px', height: '8px' }} />
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                        </div>
                        <div className="stat-value" style={{ color: statusColors[s] }}>
                            {machines.filter(m => m.status === s).length}
                        </div>
                    </div>
                ))}
            </div>

            {/* Machine Cards Grid */}
            <div className="grid-3">
                {machines.map(m => (
                    <div key={m.id} className="glass-card" style={{ padding: '20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                            <div>
                                <h4 style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '2px' }}>{m.name}</h4>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{m.type}</span>
                            </div>
                            <span className={`badge badge-${m.status}`}>
                                <span className={`status-dot ${m.status}`} style={{ width: '8px', height: '8px' }} />
                                {m.status}
                            </span>
                        </div>

                        <div style={{ display: 'grid', gap: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <MapPin size={13} style={{ color: 'var(--text-muted)' }} />
                                {m.location}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Cpu size={13} style={{ color: 'var(--text-muted)' }} />
                                {m.model} — <span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{m.serialNumber}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Calendar size={13} style={{ color: 'var(--text-muted)' }} />
                                Installed: {m.installDate}
                            </div>
                        </div>

                        {/* Health */}
                        <div style={{ marginBottom: '14px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '4px' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Health</span>
                                <span style={{ fontWeight: 700, color: m.healthScore >= 80 ? 'var(--status-normal)' : m.healthScore >= 50 ? 'var(--status-warning)' : 'var(--status-critical)' }}>
                                    {m.healthScore}%
                                </span>
                            </div>
                            <div className="health-gauge">
                                <div className="health-gauge-fill" style={{
                                    width: `${m.healthScore}%`,
                                    background: m.healthScore >= 80 ? 'var(--status-normal)' : m.healthScore >= 50 ? 'var(--status-warning)' : 'var(--status-critical)',
                                }} />
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }} onClick={() => openEdit(m)}>
                                <Edit size={14} /> Edit
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDelete(m.id)}>
                                <Trash2 size={14} />
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h2>{editId ? '✏️ Edit Machine' : '➕ Register New Machine'}</h2>
                        <div className="form-group">
                            <label>Machine Name</label>
                            <input className="input" placeholder="e.g. CNC Machine Alpha" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label>Type</label>
                                <input className="input" placeholder="e.g. CNC Milling" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label>Model</label>
                                <input className="input" placeholder="e.g. Haas VF-2SS" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} />
                            </div>
                        </div>
                        <div className="form-group">
                            <label>Location</label>
                            <input className="input" placeholder="e.g. Building A - Zone 1" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label>Serial Number</label>
                                <input className="input" placeholder="e.g. CNC-2022-001" value={form.serialNumber} onChange={e => setForm({ ...form, serialNumber: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label>Install Date</label>
                                <input className="input" type="date" value={form.installDate} onChange={e => setForm({ ...form, installDate: e.target.value })} />
                            </div>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div className="form-group">
                                <label>Status</label>
                                <select className="input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value as Machine['status'] })}>
                                    <option value="normal">Normal</option>
                                    <option value="warning">Warning</option>
                                    <option value="critical">Critical</option>
                                    <option value="offline">Offline</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Health Score</label>
                                <input className="input" type="number" min={0} max={100} value={form.healthScore} onChange={e => setForm({ ...form, healthScore: Number(e.target.value) })} />
                            </div>
                        </div>
                        <div className="form-actions">
                            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn btn-primary" onClick={handleSave} disabled={!form.name || !form.type}>
                                {editId ? '💾 Save Changes' : '➕ Register'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
