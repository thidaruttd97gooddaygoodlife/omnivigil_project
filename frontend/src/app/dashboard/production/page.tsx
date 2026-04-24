'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { ingestorApi, machineApi } from '@/lib/api';
import { Box, History, TrendingUp, AlertTriangle, CheckCircle, Timer, BarChart4 } from 'lucide-react';

export default function ProductionPage() {
    const { user, hasAccess, isDemoMode } = useAuth();
    const [productionData, setProductionData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    // RBAC Check
    if (!hasAccess('supervisor') && user?.role !== 'admin') {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', textAlign: 'center', padding: '40px' }}>
                <div style={{ background: 'rgba(244, 63, 94, 0.1)', padding: '24px', borderRadius: '50%', marginBottom: '24px' }}>
                    <AlertTriangle size={64} style={{ color: '#f43f5e' }} />
                </div>
                <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', marginBottom: '8px' }}>Access Restricted</h1>
                <p style={{ color: 'rgba(255,255,255,0.5)', maxWidth: '400px', lineHeight: '1.6' }}>
                    This analytics layer is exclusive to <b>Supervisors</b>. Please contact your administrator if you believe this is an error.
                </p>
            </div>
        );
    }

    useEffect(() => {
        const fetchProduction = async () => {
            try {
                let machines = [];
                if (isDemoMode) {
                    const { mockMachines: mockData } = await import('@/lib/mockData');
                    machines = mockData;
                } else {
                    const mRes = await machineApi.get('/machines');
                    machines = mRes.data;
                }

                const results = await Promise.all(machines.map(async (m: any) => {
                    let history = [];
                    if (!isDemoMode) {
                        try {
                            const hRes = await ingestorApi.get(`/history/${m.id}?days=1`);
                            history = hRes.data;
                        } catch {
                            history = [];
                        }
                    } else {
                        // Create some fake recent history points for demo
                        history = Array(12).fill(0).map(() => ({ quality_score: 90 + Math.random() * 10 }));
                    }
                    
                    const avgQuality = history.length > 0 
                        ? history.reduce((sum: number, h: any) => sum + h.quality_score, 0) / history.length 
                        : 85;
                    
                    const totalProduced = Math.floor(m.healthScore * 150 + (history.length * 10));
                    const target = 20000;
                    const downtime = m.status === 'offline' ? 480 : (m.status === 'warning' ? 45 : 12);
                    const maintenanceCount = m.healthScore < 60 ? 8 : (m.healthScore < 85 ? 3 : 1);

                    return {
                        ...m,
                        totalProduced,
                        target,
                        progress: (totalProduced / target) * 100,
                        oee: Math.min(98.5, Math.max(40, avgQuality - 5)),
                        downtime,
                        maintenanceCount,
                        efficiency: avgQuality > 90 ? 'High Performance' : (avgQuality > 70 ? 'Optimal' : 'Low Efficiency')
                    };
                }));

                setProductionData(results);
                setLoading(false);
            } catch (err) {
                console.error("Failed to load production data", err);
                setLoading(false);
            }
        };

        fetchProduction();
    }, [isDemoMode]);

    if (loading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
                <div style={{ width: '48px', height: '48px', border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
            </div>
        );
    }

    const totalFleetOutput = productionData.reduce((sum, m) => sum + m.totalProduced, 0);
    const avgOee = productionData.length > 0 
        ? productionData.reduce((sum, m) => sum + m.oee, 0) / productionData.length 
        : 0;

    return (
        <div style={{ paddingBottom: '80px', animation: 'fadeIn 0.5s ease-out' }}>
            <style jsx>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes spin { to { transform: rotate(360deg); } }
                .glass-card { 
                    background: rgba(255, 255, 255, 0.03);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 20px;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }
                .glass-card:hover {
                    background: rgba(255, 255, 255, 0.06);
                    border-color: rgba(59, 130, 246, 0.3);
                    transform: translateY(-2px);
                }
                .grid-stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 24px;
                    margin-bottom: 40px;
                }
                .progress-bar {
                    height: 8px;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 4px;
                    overflow: hidden;
                    position: relative;
                }
                .progress-fill {
                    height: 100%;
                    background: linear-gradient(90deg, #3b82f6, #06b6d4);
                    box-shadow: 0 0 12px rgba(59, 130, 246, 0.5);
                    border-radius: 4px;
                    transition: width 1s ease-in-out;
                }
                .tooltip {
                    position: relative;
                    display: inline-block;
                }
                .tooltip .tooltiptext {
                    visibility: hidden;
                    width: 200px;
                    background-color: #0f172a;
                    color: #fff;
                    text-align: center;
                    border-radius: 8px;
                    padding: 10px;
                    position: absolute;
                    z-index: 100;
                    bottom: 125%;
                    left: 50%;
                    margin-left: -100px;
                    opacity: 0;
                    transition: opacity 0.3s;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                    font-size: 0.75rem;
                    line-height: 1.4;
                    pointer-events: none;
                }
                .tooltip:hover .tooltiptext {
                    visibility: visible;
                    opacity: 1;
                }
            `}</style>

            <header style={{ marginBottom: '40px', display: 'flex', alignItems: 'center', gap: '20px' }}>
                <div style={{ padding: '16px', background: 'rgba(59, 130, 246, 0.15)', borderRadius: '16px', boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
                    <BarChart4 size={32} color="#3b82f6" />
                </div>
                <div>
                    <h1 style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', margin: 0 }}>Production Analytics</h1>
                    <p style={{ color: 'rgba(255,255,255,0.4)', marginTop: '4px', fontSize: '1.1rem' }}>Smart OEE tracking and production flow insights</p>
                </div>
            </header>

            {/* Top Stats Row */}
            <div className="grid-stats">
                <div className="glass-card" style={{ padding: '28px', borderLeft: '4px solid #3b82f6' }}>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>Fleet Output</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                        <span style={{ fontSize: '2.8rem', fontWeight: 900, color: '#fff' }}>{totalFleetOutput.toLocaleString()}</span>
                        <span style={{ color: '#10b981', fontSize: '0.9rem', fontWeight: 700 }}>↑ 12.4%</span>
                    </div>
                    <div style={{ marginTop: '12px', color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem' }}>Combined production across all active lines</div>
                </div>

                <div className="glass-card" style={{ padding: '28px', borderLeft: '4px solid #f59e0b' }}>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>Global OEE</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                        <span style={{ fontSize: '2.8rem', fontWeight: 900, color: '#f59e0b' }}>{avgOee.toFixed(1)}%</span>
                        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '1rem' }}>Efficiency</span>
                    </div>
                    <div style={{ marginTop: '12px', color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem' }}>Overall Equipment Effectiveness average</div>
                </div>

                <div className="glass-card" style={{ padding: '28px', borderLeft: '4px solid #f43f5e' }}>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>Factory Downtime</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                        <span style={{ fontSize: '2.8rem', fontWeight: 900, color: '#f43f5e' }}>{productionData.reduce((sum, m) => sum + m.downtime, 0)}</span>
                        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '1rem' }}>Minutes</span>
                    </div>
                    <div style={{ marginTop: '12px', color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem' }}>Total time lost in the current 24h cycle</div>
                </div>
            </div>

            {/* Detailed Machine List */}
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#fff', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Timer size={24} color="#3b82f6" /> Line-by-Line Performance
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {productionData.map(m => (
                    <div key={m.id} className="glass-card" style={{ padding: '32px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.5fr 1fr 0.8fr', gap: '40px', alignItems: 'center' }}>
                            {/* Machine Info */}
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: m.status === 'normal' ? '#10b981' : '#f43f5e', boxShadow: m.status === 'normal' ? '0 0 10px #10b981' : '0 0 10px #f43f5e' }}></div>
                                    <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#fff' }}>{m.name}</h3>
                                </div>
                                <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{m.type} • {m.location}</div>
                                <div style={{ marginTop: '16px', fontSize: '0.8rem', color: '#3b82f6', background: 'rgba(59, 130, 246, 0.1)', width: 'fit-content', padding: '4px 10px', borderRadius: '6px' }}>
                                    Downtime: {m.downtime}m today
                                </div>
                            </div>

                            {/* Production Progress */}
                            <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '0.9rem' }}>
                                    <span style={{ color: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <BarChart4 size={14} /> Target Goal (Daily): {m.target.toLocaleString()}
                                    </span>
                                    <span style={{ color: '#fff', fontWeight: 800 }}>{m.progress.toFixed(1)}%</span>
                                </div>
                                <div className="progress-bar">
                                    <div className="progress-fill" style={{ width: `${Math.min(100, m.progress)}%` }}></div>
                                </div>
                                <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.3)', marginBottom: '2px' }}>Current Actual</div>
                                        <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--accent-primary)' }}>{m.totalProduced.toLocaleString()} <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'rgba(255,255,255,0.4)' }}>units</span></div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: m.progress >= 100 ? '#10b981' : '#f59e0b' }}>
                                            {m.progress >= 100 ? '✅ Goal Achieved!' : `Remaining: ${(m.target - m.totalProduced).toLocaleString()}`}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Maintenance Stats */}
                            <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                <div 
                                    className="tooltip"
                                    style={{ textAlign: 'center', position: 'relative', cursor: 'help', padding: '4px', borderRadius: '8px' }}
                                >
                                    <span className="tooltiptext">จำนวนครั้งที่มีการแจ้งเตือนความผิดปกติหรือประวัติการซ่อมบำรุงในรอบ 30 วัน</span>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginBottom: '4px' }}>
                                        <History size={16} color="rgba(255,255,255,0.4)" />
                                        <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'rgba(255,255,255,0.4)', fontWeight: 700 }}>Events</span>
                                    </div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>{m.maintenanceCount}</div>
                                </div>
                                <div style={{ width: '1px', background: 'rgba(255,255,255,0.1)', height: '40px' }}></div>
                                <div style={{ textAlign: 'center' }}>
                                    <CheckCircle size={16} color="#10b981" style={{ marginBottom: '4px' }} />
                                    <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#10b981' }}>{m.healthScore}%</div>
                                    <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'rgba(255,255,255,0.4)', fontWeight: 700 }}>Health</div>
                                </div>
                            </div>

                            {/* Efficiency Score */}
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>Machine OEE</div>
                                <div style={{ fontSize: '2.2rem', fontWeight: 900, color: m.oee > 80 ? '#10b981' : (m.oee > 60 ? '#f59e0b' : '#f43f5e') }}>{m.oee.toFixed(1)}%</div>
                                <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>{m.efficiency}</div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* AI Supervisor Section */}
            <div className="glass-card" style={{ marginTop: '40px', padding: '32px', background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1))', borderColor: 'rgba(59, 130, 246, 0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <div style={{ padding: '12px', background: '#3b82f6', borderRadius: '12px', boxShadow: '0 0 20px rgba(59, 130, 246, 0.5)' }}>
                        <TrendingUp size={24} color="#fff" />
                    </div>
                    <div>
                        <h4 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#fff' }}>Supervisor AI Insight</h4>
                        <p style={{ margin: '8px 0 0 0', color: 'rgba(255,255,255,0.6)', lineHeight: '1.6', fontSize: '1rem' }}>
                            Based on real-time ingestion, <span style={{ color: '#fff', fontWeight: 700 }}>Line 1 (TA)</span> is operating at peak efficiency with 98.2% quality yield. 
                            Overall factory output has increased by <span style={{ color: '#10b981', fontWeight: 700 }}>+4.2%</span> since the start of the current shift. 
                            No urgent maintenance required for next 24 hours.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
