'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { ingestorApi, machineApi } from '@/lib/api';
import { generateHealthHistory, Machine } from '@/lib/mockData';
import { Heart, TrendingUp, TrendingDown, Shield } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Cell } from 'recharts';
import { SensorGuide } from '@/components/SensorGuide';

export default function HealthPage() {
    const { hasAccess, isDemoMode } = useAuth();

    if (!hasAccess('health')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const [machines, setMachines] = useState<Machine[]>([]);
    const [machineHistory, setMachineHistory] = useState<Record<string, any[]>>({});

    useEffect(() => {
        const fetchMachines = async () => {
             if (isDemoMode) {
                 const { mockMachines } = await import('@/lib/mockData');
                 setMachines(mockMachines);
                 return;
             }

            try {
                const res = await machineApi.get('/machines');
                setMachines(res.data);
                
                // Fetch history for each machine
                const historyMap: Record<string, any[]> = {};
                await Promise.all(res.data.map(async (m: Machine) => {
                    try {
                        const hRes = await ingestorApi.get(`/history/${m.id}?days=7`);
                        historyMap[m.id] = hRes.data.map((h: any) => ({
                            day: new Date(h.timestamp).toLocaleDateString('th-TH', { weekday: 'short' }),
                            score: h.quality_score
                        }));
                    } catch {
                        historyMap[m.id] = [];
                    }
                }));
                setMachineHistory(historyMap);
            } catch (err) {
                console.error("Failed to fetch machines for HealthPage");
            }
        };
        fetchMachines();
    }, [isDemoMode]);

    const activeMachines = machines.filter(m => m.status !== 'offline');
    const avgHealth = Math.round(activeMachines.reduce((sum, m) => sum + m.healthScore, 0) / (activeMachines.length || 1));
    const criticalCount = machines.filter(m => m.healthScore < 50).length;
    const healthyCount = machines.filter(m => m.healthScore >= 80).length;

    const barData = machines.map(m => ({
        name: m.name.split(' ').slice(0, 2).join(' '),
        score: m.healthScore,
        status: m.status,
    }));

    const getBarColor = (score: number) => {
        if (score >= 80) return '#10b981';
        if (score >= 50) return '#f59e0b';
        if (score > 0) return '#ef4444';
        return '#64748b';
    };

    return (
        <div className="fade-in">
            <div className="page-header">
                <h1>💚 Health Dashboard</h1>
                <p>Machine health scores and maintenance readiness overview</p>
            </div>

            {/* Summary Stats */}
            <div className="page-stats">
                <div className="stat-card glass-card">
                    <div className="stat-label">Fleet Avg Health</div>
                    <div className="stat-value" style={{ color: avgHealth >= 70 ? 'var(--status-normal)' : 'var(--status-warning)' }}>{avgHealth}%</div>
                    <div className="stat-change" style={{ color: 'var(--status-normal)' }}>
                        <TrendingUp size={14} style={{ display: 'inline', marginRight: '4px' }} />+2.3% vs last week
                    </div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Healthy ({'>'}80%)</div>
                    <div className="stat-value" style={{ color: 'var(--status-normal)' }}>{healthyCount}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Critical ({'<'}50%)</div>
                    <div className="stat-value" style={{ color: 'var(--status-critical)' }}>{criticalCount}</div>
                </div>
                <div className="stat-card glass-card">
                    <div className="stat-label">Total Machines</div>
                    <div className="stat-value" style={{ color: 'var(--accent-primary)' }}>{machines.length}</div>
                </div>
            </div>

            {/* Health Bar Chart */}
            <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '20px' }}>📊 Machine Health Scores</h3>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={barData} layout="vertical" margin={{ left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                        <XAxis type="number" domain={[0, 100]} stroke="#64748b" fontSize={11} />
                        <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={11} width={120} />
                        <Tooltip contentStyle={{ background: '#1a2136', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '0.85rem' }} />
                        <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={20}>
                            {barData.map((entry, index) => (
                                <Cell key={index} fill={getBarColor(entry.score)} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Machine Health Cards + Trend */}
            <div className="grid-2">
                {machines.map(m => {
                    const history = isDemoMode 
                        ? generateHealthHistory(m.id).map(h => ({ day: h.date, score: h.score }))
                        : (machineHistory[m.id] && machineHistory[m.id].length > 0)
                            ? machineHistory[m.id]
                            : Array(7).fill({}).map((_, i) => ({ day: `D-${6-i}`, score: m.healthScore }));
                    
                    const trend = history.length > 1 ? history[history.length - 1].score - history[0].score : 0;
                    return (
                        <div key={m.id} className="glass-card" style={{ padding: '20px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                                <div>
                                    <h4 style={{ fontWeight: 600, fontSize: '0.95rem' }}>{m.name}</h4>
                                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{m.type} • {m.location}</p>
                                </div>
                                <span className={`badge badge-${m.status}`}>
                                    <span className={`status-dot ${m.status}`} style={{ width: '8px', height: '8px' }} />
                                    {m.status}
                                </span>
                            </div>

                            {/* Health Gauge */}
                            <div style={{ marginBottom: '12px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Health Score</span>
                                    <span style={{ fontSize: '0.9rem', fontWeight: 700, color: getBarColor(m.healthScore) }}>{m.healthScore}%</span>
                                </div>
                                <div className="health-gauge">
                                    <div className="health-gauge-fill" style={{
                                        width: `${m.healthScore}%`,
                                        background: `linear-gradient(90deg, ${getBarColor(m.healthScore)}88, ${getBarColor(m.healthScore)})`,
                                    }} />
                                </div>
                            </div>

                            {/* 7-day Trend */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>7-day trend:</span>
                                {trend >= 0 ? (
                                    <span style={{ fontSize: '0.78rem', color: 'var(--status-normal)', display: 'flex', alignItems: 'center', gap: '2px' }}>
                                        <TrendingUp size={12} /> +{trend}%
                                    </span>
                                ) : (
                                    <span style={{ fontSize: '0.78rem', color: 'var(--status-critical)', display: 'flex', alignItems: 'center', gap: '2px' }}>
                                        <TrendingDown size={12} /> {trend}%
                                    </span>
                                )}
                            </div>
                            <ResponsiveContainer width="100%" height={60}>
                                <LineChart data={history}>
                                    <Line type="monotone" dataKey="score" stroke={getBarColor(m.healthScore)} strokeWidth={2} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>

                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                                Last maintenance: {m.lastMaintenance}
                            </div>
                        </div>
                    );
                })}
            </div>

            <SensorGuide mode="health" />
        </div>
    );
}
