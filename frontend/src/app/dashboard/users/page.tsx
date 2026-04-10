'use client';

import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Role } from '@/lib/mockData';
import { Users, Plus, Trash2, Shield } from 'lucide-react';

export default function UsersPage() {
    const { hasAccess, user: currentUser, allUsers, addUser, editUser, deleteUser } = useAuth();
    const [showModal, setShowModal] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [targetDeleteId, setTargetDeleteId] = useState<string | null>(null);
    const [editId, setEditId] = useState<string | null>(null);
    const [form, setForm] = useState({ username: '', password: 'demo1234', name: '', email: '', role: 'engineer' as Role });

    if (!hasAccess('users')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const isIT = currentUser?.role === 'it' || currentUser?.role === 'admin';
    const isSupervisor = currentUser?.role === 'supervisor';

    // Supervisor/Admin can manage users
    const canManageUsers = isIT || isSupervisor;

    // Filter users based on role (Supervisor should NOT see Admin/IT)
    const visibleUsers = allUsers.filter(u => {
        if (isIT) return true;
        if (isSupervisor) return u.role !== 'admin' && u.role !== 'it';
        return false;
    });

    // Supervisor cannot assign Admin/IT role
    const availableRoles: { value: Role; label: string }[] = [
        { value: 'engineer' as Role, label: 'Engineer' },
        { value: 'supervisor', label: 'Supervisor' },
        ...(isIT ? [
            { value: 'it' as Role, label: 'IT User' },
            { value: 'admin' as Role, label: 'System Admin' }
        ] : []),
    ];

    const roleColors: Record<Role, string> = {
        engineer: 'var(--accent-cyan)',
        supervisor: 'var(--accent-amber)',
        it: 'var(--accent-emerald)',
        admin: 'var(--accent-primary)',
    };

    const roleCounts = {
        engineer: visibleUsers.filter(u => u.role === 'engineer').length,
        supervisor: visibleUsers.filter(u => u.role === 'supervisor').length,
    };

    const openCreate = () => {
        setEditId(null);
        setForm({ username: '', password: 'demo1234', name: '', email: '', role: 'engineer' });
        setShowModal(true);
    };

    const openEdit = (u: any) => {
        setEditId(u.id);
        setForm({ username: u.username, password: u.password, name: u.name, email: u.email, role: u.role });
        setShowModal(true);
    };

    const handleCreate = () => {
        if (!form.username || !form.name || !form.email) return;
        if (editId) {
            editUser(editId, {
                username: form.username,
                password: form.password,
                name: form.name,
                email: form.email,
                role: form.role,
            });
        } else {
            addUser({
                username: form.username,
                password: form.password,
                name: form.name,
                email: form.email,
                role: form.role,
            });
        }
        setShowModal(false);
    };

    const handleDelete = (id: string) => {
        const target = allUsers.find(u => u.id === id);
        if (target?.id === currentUser?.id) return;
        if (isSupervisor && target?.role === 'it') return;
        
        setTargetDeleteId(id);
        setShowDeleteModal(true);
    };

    const confirmDelete = () => {
        if (targetDeleteId) {
            deleteUser(targetDeleteId);
            setShowDeleteModal(false);
            setTargetDeleteId(null);
        }
    };

    return (
        <div className="fade-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1>👥 User Management</h1>
                    <p>Manage user accounts and role assignments</p>
                </div>
                <button className="btn btn-primary" onClick={openCreate}>
                    <Plus size={16} /> Add User
                </button>
            </div>

            {/* Role Stats */}
            <div className="page-stats">
                <div className="stat-card glass-card">
                    <div className="stat-label">Total Users</div>
                    <div className="stat-value" style={{ color: 'var(--accent-primary)' }}>{visibleUsers.length}</div>
                </div>
                {Object.entries(roleCounts).map(([role, count]) => (
                    <div key={role} className="stat-card glass-card">
                        <div className="stat-label">{role === 'it' ? 'IT Admin' : role.charAt(0).toUpperCase() + role.slice(1)}</div>
                        <div className="stat-value" style={{ color: roleColors[role as Role] }}>{count}</div>
                    </div>
                ))}
            </div>

            {/* Permission Info */}
            {isSupervisor && (
                <div style={{
                    padding: '12px 16px',
                    background: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.2)',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: '20px',
                    fontSize: '0.85rem',
                    color: 'var(--accent-amber)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                }}>
                    <Shield size={16} />
                    As Supervisor, you can create Engineer and Supervisor accounts. IT Admin role requires IT permissions.
                </div>
            )}

            {/* Users Table */}
            <div className="table-container glass-card">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {visibleUsers.sort((a, b) => b.createdAt.localeCompare(a.createdAt)).map(u => (
                            <tr key={u.id}>
                                <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                        <div style={{
                                            width: '32px',
                                            height: '32px',
                                            borderRadius: '8px',
                                            background: `${roleColors[u.role]}20`,
                                            border: `1px solid ${roleColors[u.role]}40`,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            fontSize: '0.8rem',
                                            fontWeight: 700,
                                            color: roleColors[u.role],
                                        }}>
                                            {u.name.charAt(0)}
                                        </div>
                                        {u.name}
                                        {u.id === currentUser?.id && (
                                            <span style={{ fontSize: '0.7rem', color: 'var(--accent-primary)', fontWeight: 600 }}>(You)</span>
                                        )}
                                    </div>
                                </td>
                                <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{u.username}</td>
                                <td>{u.email}</td>
                                <td>
                                    <span style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        padding: '4px 12px',
                                        borderRadius: '20px',
                                        background: `${roleColors[u.role]}15`,
                                        color: roleColors[u.role],
                                        fontSize: '0.78rem',
                                        fontWeight: 600,
                                        border: `1px solid ${roleColors[u.role]}30`,
                                    }}>
                                        <Shield size={12} />
                                        {u.role === 'it' ? 'IT Admin' : u.role.charAt(0).toUpperCase() + u.role.slice(1)}
                                    </span>
                                </td>
                                <td style={{ fontSize: '0.8rem' }}>
                                    {new Date(u.createdAt).toLocaleDateString('th-TH', { year: 'numeric', month: 'short', day: 'numeric' })}
                                </td>
                                <td>
                                    {u.id !== currentUser?.id && !(isSupervisor && (u.role === 'it' || u.role === 'admin')) ? (
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <button className="btn btn-secondary btn-sm" onClick={() => openEdit(u)}>
                                                Edit
                                            </button>
                                            <button className="btn btn-danger btn-sm" onClick={() => handleDelete(u.id)}>
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    ) : (
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>—</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Create User Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h2>{editId ? '✏️ Edit User' : '➕ Add New User'}</h2>
                        <div className="form-group">
                            <label>Full Name</label>
                            <input className="input" placeholder="Enter full name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Username</label>
                            <input className="input" placeholder="Enter username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Email</label>
                            <input className="input" type="email" placeholder="user@omnivigil.io" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Password</label>
                            <input className="input" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Role</label>
                            <select className="input" value={form.role} onChange={e => setForm({ ...form, role: e.target.value as Role })}>
                                {availableRoles.map(r => (
                                    <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                            </select>
                            {isSupervisor && (
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                                    IT Admin role is not available for Supervisor
                                </p>
                            )}
                        </div>
                        <div className="form-actions">
                            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn btn-primary" onClick={handleCreate} disabled={!form.username || !form.name || !form.email}>
                                {editId ? '💾 Save Changes' : <><Plus size={16} /> Create User</>}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Custom Delete Confirmation Modal */}
            {showDeleteModal && (
                <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
                    <div className="modal-content" style={{ maxWidth: '400px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                        <div style={{ 
                            width: '60px', 
                            height: '60px', 
                            borderRadius: '50%', 
                            background: 'rgba(239, 68, 68, 0.1)', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            margin: '0 auto 20px',
                            color: 'var(--accent-red)'
                        }}>
                            <Trash2 size={30} />
                        </div>
                        <h2 style={{ marginBottom: '10px' }}>Confirm Deletion</h2>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
                            Are you sure you want to delete user <strong>"{allUsers.find(u => u.id === targetDeleteId)?.name}"</strong>? This action cannot be undone.
                        </p>
                        <div className="form-actions" style={{ justifyContent: 'center', gap: '12px' }}>
                            <button className="btn btn-secondary" onClick={() => setShowDeleteModal(false)}>Cancel</button>
                            <button className="btn btn-danger" onClick={confirmDelete}>
                                Yes, Delete User
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
