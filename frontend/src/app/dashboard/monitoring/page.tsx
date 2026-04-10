'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { mockMachines, generateSensorData, SensorReading } from '@/lib/mockData';
import { ingestorApi, machineApi } from '@/lib/api';
import { Activity, Thermometer, BarChart3, Gauge, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';

export default function MonitoringPage() {
    const { hasAccess, isDemoMode } = useAuth();
    const [machines, setMachines] = useState<any[]>([]);
    const [selectedMachine, setSelectedMachine] = useState('');
    const [sensorData, setSensorData] = useState<SensorReading[]>([]);
    const [isLive, setIsLive] = useState(true);

    useEffect(() => {
        const fetchMachines = async () => {
            if (isDemoMode) {
                setMachines(mockMachines);
                if (mockMachines.length > 0) setSelectedMachine(mockMachines[0].id);
                return;
            }
            try {
                const res = await machineApi.get('/machines');
                setMachines(res.data);
                if (res.data.length > 0) setSelectedMachine(res.data[0].id);
            } catch (err) {
                console.error("Failed to fetch machines", err);
            }
        };
        fetchMachines();
    }, [isDemoMode]);

    const loadData = useCallback(async () => {
        if (isDemoMode) {
             setSensorData(prev => {
                const machine = machines.find(m => m.id === selectedMachine);
                const isWarn = machine?.status === 'warning';
                const isCrit = machine?.status === 'critical';
                const baseTemp = isCrit ? 85 : isWarn ? 72 : 55;
                const baseVib = isCrit ? 12 : isWarn ? 8 : 3;
                
                const newReading: SensorReading = {
                    timestamp: new Date().toISOString(),
                    machineId: selectedMachine,
                    temperature: Math.round((baseTemp + (Math.random() - 0.5) * 8) * 10) / 10,
                    vibration: Math.round((baseVib + (Math.random() - 0.5) * 3) * 100) / 100,
                    pressure: Math.round((120 + (Math.random() - 0.5) * 20) * 10) / 10,
                    rpm: Math.round(1500 + (Math.random() - 0.5) * 80),
                };
                
                if (prev.length === 0) return generateSensorData(selectedMachine, 30);
                return [...prev.slice(Math.max(0, prev.length - 29)), newReading];
            });
            return;
        }

        try {
            if (!selectedMachine) return;
            
            // For the first load, get history from InfluxDB
            // For subsequent live updates, we can keep using standard readings or stick to history
            const res = await ingestorApi.get(`/history/${selectedMachine}?days=1`);
            const data = res.data;
            
            const machineData = data.map((d: any) => ({
                timestamp: d.timestamp,
                machineId: selectedMachine,
                temperature: d.temperature_c,
                vibration: d.vibration_rms,
                pressure: d.pressure_bar || 0,
                rpm: d.rpm || 0
            }));

            setSensorData(machineData.slice(-30));
        } catch (err) {
            console.error('Failed to load live sensor data', err);
        }
    }, [selectedMachine, isDemoMode]);

    useEffect(() => { loadData(); }, [loadData]);

    useEffect(() => {
        if (!isLive) return;
        const interval = setInterval(() => {
            loadData();
        }, 3000); // Polling every 3s since API isn't WebSockets
        return () => clearInterval(interval);
    }, [isLive, loadData]);

    if (!hasAccess('monitoring')) {
        return <div className="no-access"><h2>🔒 Access Denied</h2><p>You do not have permission to view this page.</p></div>;
    }

    const machine = machines.find(m => m.id === selectedMachine);
    const latest = sensorData[sensorData.length - 1];
    const chartData = sensorData.slice(-30).map(d => ({
        time: new Date(d.timestamp).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
        temperature: d.temperature,
        vibration: d.vibration,
        pressure: d.pressure,
        rpm: d.rpm,
    }));

    const statusColors: Record<string, string> = {
        normal: 'var(--status-normal)',
        warning: 'var(--status-warning)',
        critical: 'var(--status-critical)',
        offline: 'var(--status-offline)',
    };

    const machinesByStatus = {
        normal: machines.filter(m => m.status === 'normal').length,
        warning: machines.filter(m => m.status === 'warning').length,
        critical: machines.filter(m => m.status === 'critical').length,
        offline: machines.filter(m => m.status === 'offline').length,
    };

    return (
        <div className="fade-in">
            <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                    <h1>⚡ Real-time Monitoring</h1>
                    <p>Live sensor data from all machines across the factory floor</p>
                </div>
                <button
                    className={`btn ${isLive ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    onClick={() => setIsLive(!isLive)}
                >
                    <RefreshCw size={14} style={{ animation: isLive ? 'spin 2s linear infinite' : 'none' }} />
                    {isLive ? 'LIVE' : 'PAUSED'}
                </button>
            </div>

            {/* Status Summary */}
            <div className="page-stats">
                {Object.entries(machinesByStatus).map(([status, count]) => (
                    <div key={status} className="stat-card glass-card">
                        <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className={`status-dot ${status}`} />
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </div>
                        <div className="stat-value" style={{ color: statusColors[status] }}>{count}</div>
                    </div>
                ))}
            </div>

            {/* Machine Grid */}
            <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                    Select Machine
                </h3>
                <div className="grid-4">
                    {machines.map(m => (
                        <div
                            key={m.id}
                            className="glass-card"
                            onClick={() => setSelectedMachine(m.id)}
                            style={{
                                padding: '16px',
                                cursor: 'pointer',
                                border: selectedMachine === m.id ? '1px solid var(--accent-primary)' : undefined,
                                boxShadow: selectedMachine === m.id ? 'var(--shadow-glow)' : undefined,
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{m.name}</span>
                                <span className={`status-dot ${m.status}`} />
                            </div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{m.type}</div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{m.location}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Live Sensor Readings */}
            {latest && (
                <div className="page-stats" style={{ marginBottom: '24px' }}>
                    <div className="stat-card glass-card">
                        <div className="stat-label"><Thermometer size={14} style={{ display: 'inline', marginRight: '6px' }} />Temperature</div>
                        <div className="stat-value" style={{ color: latest.temperature > 75 ? 'var(--status-critical)' : latest.temperature > 65 ? 'var(--status-warning)' : 'var(--status-normal)' }}>
                            {latest.temperature}°C
                        </div>
                    </div>
                    <div className="stat-card glass-card">
                        <div className="stat-label"><Activity size={14} style={{ display: 'inline', marginRight: '6px' }} />Vibration</div>
                        <div className="stat-value" style={{ color: latest.vibration > 10 ? 'var(--status-critical)' : latest.vibration > 6 ? 'var(--status-warning)' : 'var(--status-normal)' }}>
                            {latest.vibration} mm/s
                        </div>
                    </div>
                    <div className="stat-card glass-card">
                        <div className="stat-label"><Gauge size={14} style={{ display: 'inline', marginRight: '6px' }} />Pressure</div>
                        <div className="stat-value" style={{ color: 'var(--accent-cyan)' }}>{latest.pressure} PSI</div>
                    </div>
                    <div className="stat-card glass-card">
                        <div className="stat-label"><BarChart3 size={14} style={{ display: 'inline', marginRight: '6px' }} />RPM</div>
                        <div className="stat-value" style={{ color: 'var(--accent-purple)' }}>{latest.rpm}</div>
                    </div>
                </div>
            )}

            {/* Charts */}
            <div className="grid-2">
                <div className="glass-card" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '0.95rem', marginBottom: '16px', fontWeight: 600 }}>🌡️ Temperature Trend</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <AreaChart data={chartData}>
                            <defs>
                                <linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                            <YAxis stroke="#64748b" fontSize={11} />
                            <Tooltip contentStyle={{ background: '#1a2136', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '0.85rem' }} />
                            <Area type="monotone" dataKey="temperature" stroke="#ef4444" fill="url(#tempGrad)" strokeWidth={2} dot={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
                <div className="glass-card" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '0.95rem', marginBottom: '16px', fontWeight: 600 }}>📳 Vibration Trend</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <AreaChart data={chartData}>
                            <defs>
                                <linearGradient id="vibGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                            <YAxis stroke="#64748b" fontSize={11} />
                            <Tooltip contentStyle={{ background: '#1a2136', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '0.85rem' }} />
                            <Area type="monotone" dataKey="vibration" stroke="#3b82f6" fill="url(#vibGrad)" strokeWidth={2} dot={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
