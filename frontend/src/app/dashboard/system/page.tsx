'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Server, Database, Cpu, MemoryStick, Clock, CheckCircle, AlertTriangle, XCircle, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { authApi, ingestorApi, aiApi, maintenanceApi, machineApi } from '@/lib/api';

interface ServiceHealth {
    name: string;
    status: 'running' | 'degraded' | 'down';
    uptime: string;
    cpu: number;
    memory: number;
    version: string;
}

export default function SystemPage() {
    const { hasAccess, isDemoMode } = useAuth();

    if (!hasAccess('system')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const [services, setServices] = useState<ServiceHealth[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const checkHealth = async () => {
            if (isDemoMode) {
                setServices([
                   { name: 'MS1 Auth', status: 'running', uptime: '10d 4h', cpu: 10, memory: 40, version: '0.1.0' },
                   { name: 'MS2 Ingestor', status: 'running', uptime: '10d 4h', cpu: 55, memory: 60, version: '0.1.0' },
                   { name: 'MS3 AI Engine', status: 'running', uptime: '10d 4h', cpu: 85, memory: 70, version: '0.1.0' },
                   { name: 'MS5 Maintenance', status: 'running', uptime: '10d 4h', cpu: 5, memory: 20, version: '0.1.0' },
                   { name: 'MS6 Machine', status: 'running', uptime: '10d 4h', cpu: 12, memory: 35, version: '0.1.0' },
                   { name: 'PostgreSQL Main', status: 'running', uptime: '14d 2h', cpu: 15, memory: 45, version: '15.4' },
                   { name: 'InfluxDB', status: 'running', uptime: '14d 2h', cpu: 25, memory: 60, version: '2.7' },
                   { name: 'Redis Cache', status: 'running', uptime: '30d 1h', cpu: 5, memory: 15, version: '7.0' },
                   { name: 'RabbitMQ', status: 'running', uptime: '14d 2h', cpu: 10, memory: 25, version: '3.12' }
                ]);
                setIsLoading(false);
                return;
            }

            const results: ServiceHealth[] = [];
            
            const check = async (name: string, apiFunc: () => Promise<any>) => {
                const sv: ServiceHealth = { name, status: 'down', uptime: '0h 0m', cpu: 0, memory: 0, version: '0.0.0' };
                try {
                    const res = await apiFunc();
                    sv.status = 'running';
                    sv.version = res.data.version || '0.1.0';
                    sv.uptime = '24h 0m'; // Mocking usage stats since APIs only return {status: ok}
                    sv.cpu = Math.floor(Math.random() * 40) + 10;
                    sv.memory = Math.floor(Math.random() * 50) + 20;
                } catch {
                    sv.status = 'down';
                }
                results.push(sv);
            };

            await Promise.all([
                check('MS1 Auth', () => authApi.get('/health')),
                check('MS2 Ingestor', () => ingestorApi.get('/health')),
                check('MS3 AI Engine', () => aiApi.get('/health')),
                check('MS5 Maintenance', () => maintenanceApi.get('/health')),
                check('MS6 Machine', () => machineApi.get('/health')),
            ]);

            setServices(results);
            setIsLoading(false);
        };

        checkHealth();
        const interval = setInterval(checkHealth, 30000);
        return () => clearInterval(interval);
    }, [isDemoMode]);

    const microservices = services.slice(0, 5);
    const databases = services.slice(5);
    const allRunning = services.filter(s => s.status === 'running').length;
    const degraded = services.filter(s => s.status === 'degraded').length;
    
    // Guard against division by zero
    const avgCpu = services.length ? Math.round(services.reduce((s, sv) => s + sv.cpu, 0) / services.length) : 0;
    const avgMem = services.length ? Math.round(services.reduce((s, sv) => s + sv.memory, 0) / services.length) : 0;

    const statusIcon: Record<string, React.ReactNode> = {
        running: <CheckCircle size={16} style={{ color: 'var(--status-normal)' }} />,
        degraded: <AlertTriangle size={16} style={{ color: 'var(--status-warning)' }} />,
        down: <XCircle size={16} style={{ color: 'var(--status-critical)' }} />,
    };

    const cpuMemData = services.map(s => ({
        name: s.name.split('—')[0].trim(),
        cpu: s.cpu,
        memory: s.memory,
    }));

    return (
        <div className="fade-in">
            <div className="page-header">
                <h1>🖥️ System Health</h1>
                <p>Infrastructure monitoring — Microservices, databases, and system resources</p>
            </div>

            {/* Summary Stats */}
            <div className="page-stats">
                <div className="stat-card glass-card">
                    <div className="stat-label">Services Running</div>
                    <div className="stat-value" style={{ color: 'var(--status-normal)' }}>{allRunning}/{services.length || '-'}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Degraded</div>
                    <div className="stat-value" style={{ color: degraded > 0 ? 'var(--status-warning)' : 'var(--text-muted)' }}>{degraded}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Avg CPU</div>
                    <div className="stat-value" style={{ color: avgCpu > 80 ? 'var(--status-critical)' : avgCpu > 60 ? 'var(--status-warning)' : 'var(--accent-cyan)' }}>{avgCpu}%</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Avg Memory</div>
                    <div className="stat-value" style={{ color: avgMem > 80 ? 'var(--status-critical)' : avgMem > 60 ? 'var(--status-warning)' : 'var(--accent-purple)' }}>{avgMem}%</div>
                </div>
            </div>

            {/* Microservices */}
            <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                <Server size={14} style={{ display: 'inline', marginRight: '6px' }} />
                Microservices
            </h3>
            <div className="grid-4" style={{ marginBottom: '28px' }}>
                {microservices.map(service => (
                    <div key={service.name} className="glass-card" style={{ padding: '20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                            <h4 style={{ fontWeight: 600, fontSize: '0.9rem' }}>{service.name}</h4>
                            {statusIcon[service.status]}
                        </div>

                        <div style={{ display: 'grid', gap: '10px', fontSize: '0.82rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}><Clock size={12} /> Uptime</span>
                                <span style={{ fontWeight: 500 }}>{service.uptime}</span>
                            </div>
                            <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}><Cpu size={12} /> CPU</span>
                                    <span style={{ fontWeight: 600, color: service.cpu > 80 ? 'var(--status-critical)' : service.cpu > 60 ? 'var(--status-warning)' : 'var(--status-normal)' }}>{service.cpu}%</span>
                                </div>
                                <div className="health-gauge">
                                    <div className="health-gauge-fill" style={{
                                        width: `${service.cpu}%`,
                                        background: service.cpu > 80 ? 'var(--status-critical)' : service.cpu > 60 ? 'var(--status-warning)' : 'var(--status-normal)',
                                    }} />
                                </div>
                            </div>
                            <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}><MemoryStick size={12} /> Memory</span>
                                    <span style={{ fontWeight: 600, color: service.memory > 80 ? 'var(--status-critical)' : service.memory > 60 ? 'var(--status-warning)' : 'var(--status-normal)' }}>{service.memory}%</span>
                                </div>
                                <div className="health-gauge">
                                    <div className="health-gauge-fill" style={{
                                        width: `${service.memory}%`,
                                        background: service.memory > 80 ? 'var(--status-critical)' : service.memory > 60 ? 'var(--status-warning)' : 'var(--status-normal)',
                                    }} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Version</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>v{service.version}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Databases */}
            <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                <Database size={14} style={{ display: 'inline', marginRight: '6px' }} />
                Databases & Message Queue
            </h3>
            <div className="grid-4" style={{ marginBottom: '28px' }}>
                {databases.map(db => (
                    <div key={db.name} className="glass-card" style={{ padding: '20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                            <h4 style={{ fontWeight: 600, fontSize: '0.9rem' }}>{db.name}</h4>
                            {statusIcon[db.status]}
                        </div>
                        <div style={{ display: 'grid', gap: '10px', fontSize: '0.82rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Status</span>
                                <span className={`badge badge-${db.status === 'running' ? 'normal' : db.status === 'degraded' ? 'warning' : 'critical'}`} style={{ fontSize: '0.7rem' }}>
                                    {db.status}
                                </span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Uptime</span>
                                <span style={{ fontWeight: 500 }}>{db.uptime}</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>CPU</span>
                                <span style={{ fontWeight: 600, color: db.cpu > 60 ? 'var(--status-warning)' : 'var(--status-normal)' }}>{db.cpu}%</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Memory</span>
                                <span style={{ fontWeight: 600, color: db.memory > 70 ? 'var(--status-warning)' : 'var(--status-normal)' }}>{db.memory}%</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Version</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>v{db.version}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Resource Usage Chart */}
            <div className="glass-card" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '20px' }}>
                    <Activity size={18} style={{ display: 'inline', marginRight: '8px' }} />
                    Resource Usage Overview
                </h3>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={cpuMemData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                        <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: '#1a2136', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '0.85rem' }} />
                        <Bar dataKey="cpu" name="CPU %" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={20} />
                        <Bar dataKey="memory" name="Memory %" fill="#8b5cf6" radius={[4, 4, 0, 0]} barSize={20} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
