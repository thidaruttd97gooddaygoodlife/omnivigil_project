'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { hasPageAccess, Role } from '@/lib/mockData';
import {
    Activity, Heart, Brain, Bell, ClipboardList,
    Users, Server, Settings, LogOut, Eye, ChevronLeft,
    ChevronRight, Cpu
} from 'lucide-react';
import { useState } from 'react';

interface NavItem {
    id: string;
    label: string;
    href: string;
    icon: React.ReactNode;
}

const allNavItems: NavItem[] = [
    { id: 'monitoring', label: 'Real-time Monitoring', href: '/dashboard/monitoring', icon: <Activity size={20} /> },
    { id: 'health', label: 'Health Dashboard', href: '/dashboard/health', icon: <Heart size={20} /> },
    { id: 'anomaly', label: 'AI Anomaly Detection', href: '/dashboard/anomaly', icon: <Brain size={20} /> },
    { id: 'workorders', label: 'Work Orders', href: '/dashboard/workorders', icon: <ClipboardList size={20} /> },
    { id: 'users', label: 'User Management', href: '/dashboard/users', icon: <Users size={20} /> },
    { id: 'machines', label: 'Machine Registry', href: '/dashboard/machines', icon: <Cpu size={20} /> },
    { id: 'system', label: 'System Health', href: '/dashboard/system', icon: <Server size={20} /> },
];

const roleLabels: Record<Role, { label: string; color: string }> = {
    engineer: { label: 'Engineer', color: 'var(--accent-cyan)' },
    supervisor: { label: 'Supervisor', color: 'var(--accent-amber)' },
    it: { label: 'IT Admin', color: 'var(--accent-emerald)' },
    admin: { label: 'System Admin', color: 'var(--accent-primary)' },
};

export default function Sidebar() {
    const { user, logout } = useAuth();
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);

    if (!user) return null;

    const visibleItems = allNavItems.filter(item => hasPageAccess(user.role, item.id));
    const roleInfo = roleLabels[user.role];

    return (
        <aside style={{
            width: collapsed ? '72px' : '260px',
            minHeight: '100vh',
            background: 'var(--bg-sidebar)',
            borderRight: '1px solid var(--border-color)',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width var(--transition-slow)',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            zIndex: 50,
            overflow: 'hidden',
        }}>
            {/* Logo */}
            <div style={{
                padding: collapsed ? '20px 12px' : '20px 20px',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                minHeight: '72px',
            }}>
                <div style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '12px',
                    background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-cyan))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                }}>
                    <Eye size={22} color="white" />
                </div>
                {!collapsed && (
                    <div>
                        <div style={{ fontWeight: 800, fontSize: '1.05rem', letterSpacing: '-0.02em' }}>OmniVigil</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Predictive Maintenance</div>
                    </div>
                )}
            </div>

            {/* Navigation */}
            <nav style={{ flex: 1, padding: '12px 8px', overflowY: 'auto' }}>
                {visibleItems.map(item => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.id}
                            href={item.href}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '12px',
                                padding: collapsed ? '12px 16px' : '10px 16px',
                                borderRadius: 'var(--radius-md)',
                                marginBottom: '4px',
                                color: isActive ? 'var(--accent-primary)' : 'var(--text-secondary)',
                                background: isActive ? 'var(--accent-glow)' : 'transparent',
                                textDecoration: 'none',
                                fontSize: '0.875rem',
                                fontWeight: isActive ? 600 : 400,
                                transition: 'all var(--transition-fast)',
                                position: 'relative',
                                whiteSpace: 'nowrap',
                            }}
                            title={item.label}
                        >
                            {isActive && (
                                <div style={{
                                    position: 'absolute',
                                    left: 0,
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    width: '3px',
                                    height: '20px',
                                    borderRadius: '0 3px 3px 0',
                                    background: 'var(--accent-primary)',
                                }} />
                            )}
                            <span style={{ flexShrink: 0 }}>{item.icon}</span>
                            {!collapsed && <span>{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>

            {/* Collapse toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '12px',
                    margin: '4px 8px',
                    borderRadius: 'var(--radius-md)',
                    background: 'transparent',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                }}
            >
                {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>

            {/* User info */}
            <div style={{
                padding: collapsed ? '16px 8px' : '16px',
                borderTop: '1px solid var(--border-color)',
            }}>
                {!collapsed && (
                    <div style={{ marginBottom: '12px' }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                        }}>
                            <div style={{
                                width: '36px',
                                height: '36px',
                                borderRadius: '10px',
                                background: 'var(--bg-card)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                border: `1px solid ${roleInfo.color}30`,
                                flexShrink: 0,
                            }}>
                                <Users size={16} style={{ color: roleInfo.color }} />
                            </div>
                            <div style={{ minWidth: 0 }}>
                                <div style={{
                                    fontSize: '0.85rem',
                                    fontWeight: 600,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                }}>
                                    {user.name}
                                </div>
                                <div style={{
                                    fontSize: '0.72rem',
                                    color: roleInfo.color,
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                }}>
                                    {roleInfo.label}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                <button
                    onClick={() => { logout(); window.location.href = '/login'; }}
                    className="btn btn-ghost btn-sm"
                    style={{
                        width: '100%',
                        justifyContent: collapsed ? 'center' : 'flex-start',
                        color: 'var(--accent-red)',
                    }}
                >
                    <LogOut size={16} />
                    {!collapsed && <span>Sign Out</span>}
                </button>
            </div>
        </aside>
    );
}
