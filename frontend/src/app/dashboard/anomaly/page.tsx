'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { generateSensorData, AnomalyEvent } from '@/lib/mockData';
import { aiApi } from '@/lib/api';
import { Brain, AlertTriangle, CheckCircle, Clock, Eye } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function AnomalyPage() {
    const { hasAccess, isDemoMode } = useAuth();
    const [selectedAnomaly, setSelectedAnomaly] = useState<string | null>(null);
    const [filter, setFilter] = useState<string>('all');
    const [anomalies, setAnomalies] = useState<AnomalyEvent[]>([]);

    useEffect(() => {
        const fetchEvents = async () => {
            if (isDemoMode) {
                 // Demo Mode: generate fake rich anomaly events
                 const fakeAnomalies: AnomalyEvent[] = [
                    { id: 'ea1', machineId: 'm1', machineName: 'CNC Mill - Alpha (m1)', timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), type: 'Vibration Spike', severity: 'critical', description: 'Extremely high vibration detected on spindle bearings. Immediate inspection required.', aiConfidence: 98, recommendedAction: 'Stop machine immediately. Inspect spindle bearings for wear or damage. Replace if necessary.', status: 'new', sensorType: 'vibration', actualValue: '12.4 mm/s', expectedRange: '< 4.0 mm/s' },
                    { id: 'ea2', machineId: 'm2', machineName: 'Lathe - Beta (m2)', timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(), type: 'Temperature Rise', severity: 'high', description: 'Coolant temperature steadily rising over the last 2 hours. AI predicts overheating in 45 mins.', aiConfidence: 85, recommendedAction: 'Check coolant level and pump operation. Top up coolant if low.', status: 'acknowledged', sensorType: 'temperature', actualValue: '85 °C', expectedRange: '< 65 °C' },
                    { id: 'ea3', machineId: 'm3', machineName: 'Hydraulic Press X (m3)', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), type: 'Pressure Drop', severity: 'medium', description: 'Slight systemic drop in hydraulic pressure during operation cycles.', aiConfidence: 72, recommendedAction: 'Schedule inspection of hydraulic lines and seals for minor leaks during next maintenance window.', status: 'resolved', sensorType: 'pressure', actualValue: '145 bar', expectedRange: '150-160 bar' }
                 ];
                 setAnomalies(fakeAnomalies);
                 return;
            }

            try {
                const res = await aiApi.get('/events');
                const apiEvents: AnomalyEvent[] = res.data.items.map((item: any) => ({
                    id: item.event_id,
                    machineId: 'm1', // MS3 does not return machine ID currently
                    machineName: 'System (AI Engine)',
                    timestamp: item.timestamp,
                    type: 'AI Anomaly Detected',
                    severity: item.risk_level === 'high' || item.risk_level === 'critical' ? item.risk_level : 'medium',
                    description: `AI Engine detected a pattern shift. Score: ${item.anomaly_score}. Auto-alert: ${item.alert_id || 'None'}. Auto-WO: ${item.work_order_id || 'None'}`,
                    aiConfidence: Math.round(item.anomaly_score * 100),
                    recommendedAction: 'Check MS5 Maintenance for generated work orders.',
                    status: 'new',
                    sensorType: 'Multiple',
                    actualValue: item.anomaly_score,
                    expectedRange: '< 0.5',
                }));
                setAnomalies([...apiEvents.reverse()]);
            } catch (err) {
                console.error('Failed to fetch MS3 AI events');
            }
        };
        fetchEvents();
        const interval = setInterval(fetchEvents, 10000);
        return () => clearInterval(interval);
    }, [isDemoMode]);

    if (!hasAccess('anomaly')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const filtered = filter === 'all' ? anomalies : anomalies.filter(a => a.severity === filter);
    const selected = anomalies.find(a => a.id === selectedAnomaly);

    const severityCounts = {
        critical: anomalies.filter(a => a.severity === 'critical').length,
        high: anomalies.filter(a => a.severity === 'high').length,
        medium: anomalies.filter(a => a.severity === 'medium').length,
        low: anomalies.filter(a => a.severity === 'low').length,
    };

    const severityColors: Record<string, string> = {
        critical: '#ef4444',
        high: '#f97316',
        medium: '#f59e0b',
        low: '#3b82f6',
    };

    const statusIcons: Record<string, React.ReactNode> = {
        new: <AlertTriangle size={14} />,
        acknowledged: <Eye size={14} />,
        resolved: <CheckCircle size={14} />,
    };

    return (
        <div className="fade-in">
            <div className="page-header">
                <h1>🧠 AI Anomaly Detection</h1>
                <p>AI-powered analysis detecting machine behavior anomalies before failures occur</p>
            </div>

            {/* Stats */}
            <div className="page-stats">
                {Object.entries(severityCounts).map(([sev, count]) => (
                    <div key={sev} className="stat-card glass-card">
                        <div className="stat-label" style={{ color: severityColors[sev] }}>
                            {sev.charAt(0).toUpperCase() + sev.slice(1)}
                        </div>
                        <div className="stat-value" style={{ color: severityColors[sev] }}>{count}</div>
                    </div>
                ))}
            </div>

            {/* Filter Tabs */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                {['all', 'critical', 'high', 'medium', 'low'].map(f => (
                    <button
                        key={f}
                        className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => setFilter(f)}
                    >
                        {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                        {f !== 'all' && ` (${severityCounts[f as keyof typeof severityCounts]})`}
                    </button>
                ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1fr' : '1fr', gap: '20px' }}>
                {/* Anomaly List */}
                <div>
                    {filtered.map(anomaly => (
                        <div
                            key={anomaly.id}
                            className="glass-card"
                            onClick={() => setSelectedAnomaly(selectedAnomaly === anomaly.id ? null : anomaly.id)}
                            style={{
                                padding: '16px 20px',
                                marginBottom: '12px',
                                cursor: 'pointer',
                                border: selectedAnomaly === anomaly.id ? `1px solid ${severityColors[anomaly.severity]}` : undefined,
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <span className={`badge badge-${anomaly.severity}`}>{anomaly.severity}</span>
                                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{anomaly.type}</span>
                                </div>
                                <span className={`badge badge-${anomaly.status === 'resolved' ? 'normal' : anomaly.status === 'acknowledged' ? 'info' : 'warning'}`}>
                                    {statusIcons[anomaly.status]} {anomaly.status}
                                </span>
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                                {anomaly.machineName}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} />
                                {new Date(anomaly.timestamp).toLocaleString('th-TH')}
                            </div>
                            {/* AI Confidence Bar */}
                            <div style={{ marginTop: '10px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                                    <span>AI Confidence</span>
                                    <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{anomaly.aiConfidence}%</span>
                                </div>
                                <div className="health-gauge">
                                    <div className="health-gauge-fill" style={{
                                        width: `${anomaly.aiConfidence}%`,
                                        background: `linear-gradient(90deg, var(--accent-primary), var(--accent-cyan))`,
                                    }} />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Detail Panel */}
                {selected && (
                    <div className="glass-card slide-in" style={{ padding: '24px', position: 'sticky', top: '20px', alignSelf: 'start' }}>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Brain size={20} style={{ color: 'var(--accent-primary)' }} />
                            AI Analysis Detail
                        </h3>

                        <div style={{ marginBottom: '16px' }}>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Machine</div>
                            <div style={{ fontWeight: 600 }}>{selected.machineName}</div>
                        </div>

                        <div style={{ marginBottom: '16px' }}>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Description</div>
                            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{selected.description}</div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Sensor</div>
                                <div style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{selected.sensorType}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Actual Value</div>
                                <div style={{ fontWeight: 600, color: severityColors[selected.severity] }}>{selected.actualValue}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Expected Range</div>
                                <div style={{ fontWeight: 600 }}>{selected.expectedRange}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>AI Confidence</div>
                                <div style={{ fontWeight: 700, color: 'var(--accent-primary)', fontSize: '1.1rem' }}>{selected.aiConfidence}%</div>
                            </div>
                        </div>

                        <div style={{
                            padding: '14px',
                            background: 'rgba(59, 130, 246, 0.08)',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid rgba(59, 130, 246, 0.2)',
                            marginBottom: '16px',
                        }}>
                            <div style={{ fontSize: '0.78rem', color: 'var(--accent-primary)', fontWeight: 600, marginBottom: '6px' }}>
                                💡 Recommended Action
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                {selected.recommendedAction}
                            </div>
                        </div>

                        {/* Mini Chart */}
                        <div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Sensor Trend (Last 4h)
                            </div>
                            <ResponsiveContainer width="100%" height={150}>
                                <AreaChart data={isDemoMode ? generateSensorData(selected.machineId, 4).slice(-24).map(d => ({
                                    time: new Date(d.timestamp).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
                                    value: selected.sensorType === 'temperature' ? d.temperature :
                                        selected.sensorType === 'vibration' ? d.vibration :
                                            selected.sensorType === 'pressure' ? d.pressure : d.rpm,
                                })) : []}>
                                    <defs>
                                        <linearGradient id="anomGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor={severityColors[selected.severity]} stopOpacity={0.3} />
                                            <stop offset="95%" stopColor={severityColors[selected.severity]} stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                    <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
                                    <YAxis stroke="#64748b" fontSize={10} />
                                    <Tooltip contentStyle={{ background: '#1a2136', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '0.8rem' }} />
                                    <Area type="monotone" dataKey="value" stroke={severityColors[selected.severity]} fill="url(#anomGrad)" strokeWidth={2} dot={false} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
