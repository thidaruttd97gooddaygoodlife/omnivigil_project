import React from 'react';
import { Info, Thermometer, Activity, Gauge, TrendingUp, RotateCcw } from 'lucide-react';

interface SensorGuideProps {
  mode?: 'monitoring' | 'health' | 'all';
}

export const SensorGuide: React.FC<SensorGuideProps> = ({ mode = 'all' }) => {
  const isMonitoring = mode === 'monitoring' || mode === 'all';
  const isHealth = mode === 'health' || mode === 'all';

  return (
    <div className="glass-card" style={{ padding: '28px', marginTop: '32px', borderLeft: '4px solid var(--accent-primary)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <div style={{ padding: '10px', background: 'rgba(59, 130, 246, 0.15)', borderRadius: '10px' }}>
          <Info size={24} color="var(--accent-primary)" />
        </div>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
            คู่มือเกณฑ์มาตรฐานเครื่องจักร (Technical Guide)
          </h3>
          <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            มาตรฐานการตรวจสอบตามข้อกำหนดวิศวกรรม (Engineering Standards)
          </p>
        </div>
      </div>

      <div className="grid-3" style={{ gap: '24px' }}>
        {isMonitoring && (
          <>
            {/* Temperature & Vibration */}
            <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                <Thermometer size={18} />
                <span style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>Temp & Vibration</span>
              </div>
              <div style={{ display: 'grid', gap: '14px' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                    <span style={{ color: 'var(--status-normal)' }}>● Temp ปกติ: 45-85°C</span>
                    <span style={{ color: 'var(--status-critical)' }}>⚠️ &gt;105°C</span>
                  </div>
                  <div style={{ height: '8px', width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                    <div style={{ width: '60%', background: 'var(--status-normal)' }}></div>
                    <div style={{ width: '20%', background: 'var(--status-warning)' }}></div>
                    <div style={{ width: '20%', background: 'var(--status-critical)' }}></div>
                  </div>
                </div>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                    <span style={{ color: 'var(--status-normal)' }}>● Vib ปกติ: 0-4.5</span>
                    <span style={{ color: 'var(--status-critical)' }}>⚠️ &gt;7.1</span>
                  </div>
                  <div style={{ height: '8px', width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                    <div style={{ width: '50%', background: 'var(--status-normal)' }}></div>
                    <div style={{ width: '20%', background: 'var(--status-warning)' }}></div>
                    <div style={{ width: '30%', background: 'var(--status-critical)' }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Pressure & RPM Guide */}
            <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                <RotateCcw size={18} />
                <span style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>Pressure & RPM</span>
              </div>
              <div style={{ display: 'grid', gap: '16px' }}>
                <ul style={{ padding: 0, margin: 0, listStyle: 'none', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <li style={{ marginBottom: '10px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>🔹 <b>Pressure:</b> 100-140 PSI</span>
                    <span style={{ color: 'var(--status-normal)' }}>Optimal</span>
                  </li>
                  <li style={{ marginBottom: '10px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>🔹 <b>Idle RPM:</b> 800-1000</span>
                    <span style={{ color: 'var(--text-muted)' }}>Standby</span>
                  </li>
                  <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>🔹 <b>Load RPM:</b> 1400-1800</span>
                    <span style={{ color: 'var(--accent-purple)' }}>Operation</span>
                  </li>
                </ul>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '8px' }}>
                  การสวิงของรอบเครื่อง (RPM Surge) เกิน 15% บ่งบอกถึงปัญหาในระบบควบคุมไฟฟ้า
                </p>
              </div>
            </div>
          </>
        )}

        {isHealth && (
          <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              <TrendingUp size={18} />
              <span style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>Health & Trends</span>
            </div>
            <div style={{ display: 'grid', gap: '12px' }}>
              <ul style={{ padding: 0, margin: 0, listStyle: 'none', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                <li style={{ marginBottom: '8px' }}>🏆 <b style={{ color: '#10b981' }}>85-100:</b> สภาพสมบูรณ์ (Excellent)</li>
                <li style={{ marginBottom: '8px' }}>⚠️ <b style={{ color: '#f59e0b' }}>50-85:</b> พบความผิดปกติเล็กน้อย (Warning)</li>
                <li style={{ marginBottom: '12px' }}>❌ <b style={{ color: '#ef4444' }}>ต่ำกว่า 50:</b> อันตราย (Critical)</li>
              </ul>
              <div style={{ paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                <p style={{ fontSize: '0.8rem', color: '#fff', fontWeight: 600, marginBottom: '6px' }}>การอ่าน 7-Day Trend:</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                  หากกราฟมีแนวโน้มดิ่งลงต่อเนื่องเกิน 3 วัน แม้จะยังอยู่ในโซนสีเขียว ให้รีบแจ้งวิศวกรเพื่อเข้าตรวจสอบก่อนเครื่องจักรหยุดทำงาน
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
