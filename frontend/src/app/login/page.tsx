'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, getDefaultPage } from '@/context/AuthContext';
import type { Role } from '@/lib/mockData';
import { Shield, User, Wrench, Monitor, Eye } from 'lucide-react';

export default function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login, loginAsRole } = useAuth();
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        const result = await login(username, password);
        if (result.success && result.role) {
            router.push(getDefaultPage(result.role));
        } else {
            setError(result.error || 'Login failed');
        }
    };

    const handleQuickLogin = (role: Role) => {
        loginAsRole(role);
        router.push(getDefaultPage(role));
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'radial-gradient(ellipse at 30% 20%, rgba(59,130,246,0.08) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(6,182,212,0.06) 0%, transparent 50%), var(--bg-primary)',
            padding: '20px',
        }}>
            <div className="fade-in" style={{
                width: '100%',
                maxWidth: '440px',
            }}>
                {/* Logo */}
                <div style={{ textAlign: 'center', marginBottom: '40px' }}>
                    <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '72px',
                        height: '72px',
                        borderRadius: '20px',
                        background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-cyan))',
                        marginBottom: '20px',
                        boxShadow: '0 8px 32px rgba(59, 130, 246, 0.3)',
                    }}>
                        <Eye size={36} color="white" />
                    </div>
                    <h1 style={{
                        fontSize: '2rem',
                        fontWeight: 900,
                        letterSpacing: '-0.03em',
                        background: 'linear-gradient(135deg, #f1f5f9, #06b6d4)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                    }}>
                        OmniVigil
                    </h1>
                    <p style={{ color: 'var(--text-secondary)', marginTop: '6px', fontSize: '0.9rem' }}>
                        Smart Predictive Maintenance Platform
                    </p>
                </div>

                {/* Login Form */}
                <div className="glass-card" style={{ padding: '32px' }}>
                    <form onSubmit={handleLogin}>
                        <div className="form-group">
                            <label>Username</label>
                            <input
                                className="input"
                                type="text"
                                placeholder="Enter username"
                                value={username}
                                onChange={e => setUsername(e.target.value)}
                            />
                        </div>
                        <div className="form-group">
                            <label>Password</label>
                            <input
                                className="input"
                                type="password"
                                placeholder="Enter password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>
                        {error && (
                            <p style={{ color: 'var(--accent-red)', fontSize: '0.85rem', marginBottom: '12px' }}>{error}</p>
                        )}
                        <button className="btn btn-primary btn-lg" type="submit" style={{ width: '100%' }}>
                            <Shield size={18} />
                            Sign In
                        </button>
                    </form>

                    {/* Quick Login */}
                    <div style={{ marginTop: '28px' }}>
                        <p style={{
                            textAlign: 'center',
                            color: 'var(--text-muted)',
                            fontSize: '0.8rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            marginBottom: '16px',
                        }}>
                            Quick Demo Login
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            <button
                                className="btn btn-secondary"
                                onClick={() => handleQuickLogin('engineer')}
                                style={{ width: '100%', justifyContent: 'flex-start' }}
                            >
                                <Wrench size={16} style={{ color: 'var(--accent-cyan)' }} />
                                <span>Login as <strong>Engineer</strong></span>
                                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                    Monitoring • Health • AI
                                </span>
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={() => handleQuickLogin('supervisor')}
                                style={{ width: '100%', justifyContent: 'flex-start' }}
                            >
                                <User size={16} style={{ color: 'var(--accent-amber)' }} />
                                <span>Login as <strong>Supervisor</strong></span>
                                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                    Orders • Production • Machines
                                </span>
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={() => handleQuickLogin('admin')}
                                style={{ width: '100%', justifyContent: 'flex-start' }}
                            >
                                <Shield size={16} style={{ color: 'var(--accent-primary)' }} />
                                <span>Login as <strong>Admin</strong></span>
                                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                    Full Systems • Production
                                </span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Demo credentials */}
                <div style={{
                    marginTop: '20px',
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(59, 130, 246, 0.06)',
                    border: '1px solid rgba(59, 130, 246, 0.15)',
                }}>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                        Demo accounts: <code style={{ color: 'var(--accent-cyan)' }}>engineer01</code> / <code style={{ color: 'var(--accent-amber)' }}>supervisor01</code> / <code style={{ color: 'var(--accent-primary)' }}>security_admin</code>
                        <br />Password: <code style={{ color: 'var(--text-secondary)' }}>admin1234</code>
                    </p>
                </div>
            </div>
        </div>
    );
}
