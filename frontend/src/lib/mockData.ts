// ============================
// OmniVigil — Mock Data Layer
// ============================

export type Role = 'engineer' | 'supervisor' | 'it' | 'admin';

export interface User {
  id: string;
  username: string;
  password: string;
  name: string;
  role: Role;
  email: string;
  avatar?: string;
  createdAt: string;
}

export interface Machine {
  id: string;
  name: string;
  type: string;
  location: string;
  installDate: string;
  status: 'normal' | 'warning' | 'critical' | 'offline';
  healthScore: number;
  lastMaintenance: string;
  model: string;
  serialNumber: string;
}

export interface SensorReading {
  timestamp: string;
  machineId: string;
  temperature: number;
  vibration: number;
  pressure: number;
  rpm: number;
}

export interface AnomalyEvent {
  id: string;
  machineId: string;
  machineName: string;
  timestamp: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  aiConfidence: number;
  recommendedAction: string;
  status: 'new' | 'acknowledged' | 'resolved';
  sensorType: string;
  actualValue: number;
  expectedRange: string;
}

export interface WorkOrder {
  id: string;
  machineId: string;
  machineName: string;
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'completed' | 'cancelled';
  assignedTo: string;
  createdAt: string;
  updatedAt: string;
  estimatedHours: number;
  anomalyId?: string;
}

export interface Alert {
  id: string;
  machineId: string;
  machineName: string;
  timestamp: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  lineNotified: boolean;
  acknowledged: boolean;
  acknowledgedBy?: string;
}

export interface SystemService {
  name: string;
  status: 'running' | 'degraded' | 'down';
  uptime: string;
  cpu: number;
  memory: number;
  lastHealthCheck: string;
  version: string;
}

// ---- Mock Users ----
export const mockUsers: User[] = [
  {
    id: 'u1',
    username: 'engineer01',
    password: 'demo1234',
    name: 'สมชาย วิศวกร',
    role: 'engineer',
    email: 'somchai@omnivigil.io',
    createdAt: '2025-11-01T08:00:00Z',
  },
  {
    id: 'u2',
    username: 'supervisor01',
    password: 'demo1234',
    name: 'สุภาพร หัวหน้า',
    role: 'supervisor',
    email: 'supaporn@omnivigil.io',
    createdAt: '2025-10-15T08:00:00Z',
  },
  {
    id: 'u3',
    username: 'it01',
    password: 'demo1234',
    name: 'ธนกร ไอที',
    role: 'it',
    email: 'thanakorn@omnivigil.io',
    createdAt: '2025-09-01T08:00:00Z',
  },
  {
    id: 'u4',
    username: 'engineer02',
    password: 'demo1234',
    name: 'วิชัย ช่างเทค',
    role: 'engineer',
    email: 'wichai@omnivigil.io',
    createdAt: '2025-12-01T08:00:00Z',
  },
  {
    id: 'u5',
    username: 'supervisor02',
    password: 'demo1234',
    name: 'นภา ผู้ดูแล',
    role: 'supervisor',
    email: 'napa@omnivigil.io',
    createdAt: '2026-01-10T08:00:00Z',
  },
];

// ---- Mock Machines ----
export const mockMachines: Machine[] = [
  {
    id: 'm1',
    name: 'CNC Machine Alpha',
    type: 'CNC Milling',
    location: 'Building A - Zone 1',
    installDate: '2022-03-15',
    status: 'normal',
    healthScore: 92,
    lastMaintenance: '2026-02-15',
    model: 'Haas VF-2SS',
    serialNumber: 'CNC-2022-001',
  },
  {
    id: 'm2',
    name: 'Motor Drive Beta',
    type: 'Electric Motor',
    location: 'Building A - Zone 2',
    installDate: '2021-07-20',
    status: 'warning',
    healthScore: 68,
    lastMaintenance: '2026-01-28',
    model: 'Siemens 1LA7',
    serialNumber: 'MTR-2021-045',
  },
  {
    id: 'm3',
    name: 'Hydraulic Pump Gamma',
    type: 'Hydraulic Pump',
    location: 'Building B - Zone 1',
    installDate: '2023-01-10',
    status: 'critical',
    healthScore: 35,
    lastMaintenance: '2026-02-01',
    model: 'Parker PV270',
    serialNumber: 'HYD-2023-012',
  },
  {
    id: 'm4',
    name: 'Conveyor Line Delta',
    type: 'Conveyor Belt',
    location: 'Building B - Zone 2',
    installDate: '2020-11-05',
    status: 'normal',
    healthScore: 88,
    lastMaintenance: '2026-02-20',
    model: 'Dorner 3200',
    serialNumber: 'CNV-2020-089',
  },
  {
    id: 'm5',
    name: 'Robot Arm Epsilon',
    type: 'Industrial Robot',
    location: 'Building A - Zone 3',
    installDate: '2024-02-14',
    status: 'normal',
    healthScore: 95,
    lastMaintenance: '2026-02-25',
    model: 'FANUC M-20iD',
    serialNumber: 'ROB-2024-003',
  },
  {
    id: 'm6',
    name: 'Compressor Zeta',
    type: 'Air Compressor',
    location: 'Building C - Zone 1',
    installDate: '2021-05-30',
    status: 'warning',
    healthScore: 62,
    lastMaintenance: '2026-01-15',
    model: 'Atlas Copco GA45',
    serialNumber: 'CMP-2021-022',
  },
  {
    id: 'm7',
    name: 'Welding Station Eta',
    type: 'Welding Robot',
    location: 'Building C - Zone 2',
    installDate: '2023-08-22',
    status: 'normal',
    healthScore: 84,
    lastMaintenance: '2026-02-18',
    model: 'Lincoln Electric',
    serialNumber: 'WLD-2023-017',
  },
  {
    id: 'm8',
    name: 'Lathe Machine Theta',
    type: 'CNC Lathe',
    location: 'Building A - Zone 4',
    installDate: '2022-12-01',
    status: 'offline',
    healthScore: 0,
    lastMaintenance: '2026-02-28',
    model: 'Mazak QT-250',
    serialNumber: 'LTH-2022-008',
  },
];

// ---- Generate Time-Series Sensor Data (Monte Carlo) ----
export function generateSensorData(machineId: string, hours: number = 24): SensorReading[] {
  const data: SensorReading[] = [];
  const now = new Date();
  const machine = mockMachines.find(m => m.id === machineId);
  const isWarning = machine?.status === 'warning';
  const isCritical = machine?.status === 'critical';

  for (let i = hours * 6; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 10 * 60 * 1000);
    const baseTemp = isCritical ? 85 : isWarning ? 72 : 55;
    const baseVib = isCritical ? 12 : isWarning ? 8 : 3;
    const basePressure = isCritical ? 180 : isWarning ? 155 : 120;
    const baseRpm = 1500;

    // Monte Carlo: add random noise
    const noise = () => (Math.random() - 0.5) * 2;
    const spike = Math.random() > 0.95 ? (Math.random() * 10) : 0;

    data.push({
      timestamp: timestamp.toISOString(),
      machineId,
      temperature: Math.round((baseTemp + noise() * 5 + spike + Math.sin(i / 10) * 3) * 10) / 10,
      vibration: Math.round((baseVib + noise() * 2 + spike * 0.3 + Math.cos(i / 8) * 0.5) * 100) / 100,
      pressure: Math.round((basePressure + noise() * 10 + Math.sin(i / 12) * 5) * 10) / 10,
      rpm: Math.round(baseRpm + noise() * 50 + Math.sin(i / 15) * 20),
    });
  }
  return data;
}

// ---- Mock Anomaly Events ----
export const mockAnomalies: AnomalyEvent[] = [
  {
    id: 'a1',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    timestamp: '2026-03-02T14:23:00Z',
    type: 'Vibration Spike',
    severity: 'critical',
    description: 'Vibration exceeded 15mm/s threshold — bearing may be failing. Immediate inspection recommended.',
    aiConfidence: 94.2,
    recommendedAction: 'Stop machine immediately. Inspect main bearing assembly. Schedule emergency replacement.',
    status: 'new',
    sensorType: 'vibration',
    actualValue: 16.8,
    expectedRange: '2-8 mm/s',
  },
  {
    id: 'a2',
    machineId: 'm2',
    machineName: 'Motor Drive Beta',
    timestamp: '2026-03-02T12:45:00Z',
    type: 'Temperature Rise',
    severity: 'high',
    description: 'Motor winding temperature increasing steadily over 6 hours. Overheating risk within 48 hours.',
    aiConfidence: 87.5,
    recommendedAction: 'Schedule coolant system inspection within 24 hours. Check ventilation fans.',
    status: 'acknowledged',
    sensorType: 'temperature',
    actualValue: 78.3,
    expectedRange: '45-65°C',
  },
  {
    id: 'a3',
    machineId: 'm6',
    machineName: 'Compressor Zeta',
    timestamp: '2026-03-02T10:15:00Z',
    type: 'Pressure Anomaly',
    severity: 'medium',
    description: 'Output pressure dropping below optimal range. Possible valve or seal degradation.',
    aiConfidence: 76.8,
    recommendedAction: 'Check discharge valves and seals during next scheduled maintenance.',
    status: 'new',
    sensorType: 'pressure',
    actualValue: 98.5,
    expectedRange: '110-140 PSI',
  },
  {
    id: 'a4',
    machineId: 'm4',
    machineName: 'Conveyor Line Delta',
    timestamp: '2026-03-01T22:30:00Z',
    type: 'RPM Fluctuation',
    severity: 'low',
    description: 'Minor RPM fluctuation detected in drive motor. Belt tension may need adjustment.',
    aiConfidence: 65.3,
    recommendedAction: 'Check belt tension and alignment during routine maintenance.',
    status: 'resolved',
    sensorType: 'rpm',
    actualValue: 1380,
    expectedRange: '1450-1550 RPM',
  },
  {
    id: 'a5',
    machineId: 'm1',
    machineName: 'CNC Machine Alpha',
    timestamp: '2026-03-01T18:10:00Z',
    type: 'Vibration Pattern Change',
    severity: 'medium',
    description: 'Spindle vibration signature changed — potential tool wear or imbalance.',
    aiConfidence: 72.1,
    recommendedAction: 'Inspect spindle and tool holder. Replace cutting tool if worn.',
    status: 'acknowledged',
    sensorType: 'vibration',
    actualValue: 6.2,
    expectedRange: '1-4 mm/s',
  },
  {
    id: 'a6',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    timestamp: '2026-03-01T09:45:00Z',
    type: 'Oil Temperature High',
    severity: 'high',
    description: 'Hydraulic oil temperature exceeding safe operating range. Risk of seal failure.',
    aiConfidence: 91.0,
    recommendedAction: 'Replace hydraulic oil and inspect heat exchanger. Check for internal leaks.',
    status: 'new',
    sensorType: 'temperature',
    actualValue: 92.7,
    expectedRange: '40-70°C',
  },
  {
    id: 'a7',
    machineId: 'm7',
    machineName: 'Welding Station Eta',
    timestamp: '2026-02-28T16:20:00Z',
    type: 'Current Draw Anomaly',
    severity: 'low',
    description: 'Slight increase in welding current draw. Contact tips may be wearing.',
    aiConfidence: 58.9,
    recommendedAction: 'Replace contact tips at next shift change.',
    status: 'resolved',
    sensorType: 'temperature',
    actualValue: 67.5,
    expectedRange: '50-62°C',
  },
];

// ---- Mock Work Orders ----
export const mockWorkOrders: WorkOrder[] = [
  {
    id: 'WO-2026-001',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    title: 'Emergency Bearing Replacement',
    description: 'Critical vibration detected. Main bearing assembly needs immediate replacement.',
    priority: 'urgent',
    status: 'open',
    assignedTo: 'สมชาย วิศวกร',
    createdAt: '2026-03-02T14:25:00Z',
    updatedAt: '2026-03-02T14:25:00Z',
    estimatedHours: 8,
    anomalyId: 'a1',
  },
  {
    id: 'WO-2026-002',
    machineId: 'm2',
    machineName: 'Motor Drive Beta',
    title: 'Coolant System Inspection',
    description: 'Motor temperature trending upward. Inspect cooling system and ventilation.',
    priority: 'high',
    status: 'in_progress',
    assignedTo: 'วิชัย ช่างเทค',
    createdAt: '2026-03-02T13:00:00Z',
    updatedAt: '2026-03-02T15:30:00Z',
    estimatedHours: 4,
    anomalyId: 'a2',
  },
  {
    id: 'WO-2026-003',
    machineId: 'm6',
    machineName: 'Compressor Zeta',
    title: 'Valve & Seal Inspection',
    description: 'Pressure dropping below optimal range. Check discharge valves and replace seals.',
    priority: 'medium',
    status: 'open',
    assignedTo: 'สมชาย วิศวกร',
    createdAt: '2026-03-02T10:30:00Z',
    updatedAt: '2026-03-02T10:30:00Z',
    estimatedHours: 3,
    anomalyId: 'a3',
  },
  {
    id: 'WO-2026-004',
    machineId: 'm1',
    machineName: 'CNC Machine Alpha',
    title: 'Spindle & Tool Inspection',
    description: 'Vibration pattern changed. Inspect spindle assembly and replace cutting tool.',
    priority: 'medium',
    status: 'in_progress',
    assignedTo: 'วิชัย ช่างเทค',
    createdAt: '2026-03-01T18:30:00Z',
    updatedAt: '2026-03-02T09:00:00Z',
    estimatedHours: 2,
    anomalyId: 'a5',
  },
  {
    id: 'WO-2026-005',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    title: 'Hydraulic Oil Replacement',
    description: 'Oil temperature too high. Replace oil and inspect heat exchanger.',
    priority: 'high',
    status: 'open',
    assignedTo: 'สมชาย วิศวกร',
    createdAt: '2026-03-01T10:00:00Z',
    updatedAt: '2026-03-01T10:00:00Z',
    estimatedHours: 5,
    anomalyId: 'a6',
  },
  {
    id: 'WO-2026-006',
    machineId: 'm4',
    machineName: 'Conveyor Line Delta',
    title: 'Belt Tension Adjustment',
    description: 'Minor RPM fluctuation. Adjust belt tension and check alignment.',
    priority: 'low',
    status: 'completed',
    assignedTo: 'วิชัย ช่างเทค',
    createdAt: '2026-03-01T08:00:00Z',
    updatedAt: '2026-03-02T11:00:00Z',
    estimatedHours: 1,
    anomalyId: 'a4',
  },
  {
    id: 'WO-2026-007',
    machineId: 'm7',
    machineName: 'Welding Station Eta',
    title: 'Contact Tips Replacement',
    description: 'Slight current draw increase. Replace worn contact tips.',
    priority: 'low',
    status: 'completed',
    assignedTo: 'สมชาย วิศวกร',
    createdAt: '2026-02-28T17:00:00Z',
    updatedAt: '2026-03-01T09:00:00Z',
    estimatedHours: 0.5,
    anomalyId: 'a7',
  },
  {
    id: 'WO-2026-008',
    machineId: 'm8',
    machineName: 'Lathe Machine Theta',
    title: 'Scheduled Overhaul',
    description: 'Annual maintenance overhaul. Machine taken offline for comprehensive service.',
    priority: 'medium',
    status: 'in_progress',
    assignedTo: 'วิชัย ช่างเทค',
    createdAt: '2026-02-28T08:00:00Z',
    updatedAt: '2026-03-02T08:00:00Z',
    estimatedHours: 40,
  },
  {
    id: 'WO-2026-009',
    machineId: 'm5',
    machineName: 'Robot Arm Epsilon',
    title: 'Routine Calibration',
    description: 'Quarterly calibration of robot arm axes and end-effector.',
    priority: 'low',
    status: 'completed',
    assignedTo: 'สมชาย วิศวกร',
    createdAt: '2026-02-25T08:00:00Z',
    updatedAt: '2026-02-25T14:00:00Z',
    estimatedHours: 3,
  },
  {
    id: 'WO-2026-010',
    machineId: 'm5',
    machineName: 'Robot Arm Epsilon',
    title: 'Servo Motor Lubrication',
    description: 'Preventive lubrication of all servo motors in the robot arm.',
    priority: 'low',
    status: 'completed',
    assignedTo: 'วิชัย ช่างเทค',
    createdAt: '2026-02-20T08:00:00Z',
    updatedAt: '2026-02-20T12:00:00Z',
    estimatedHours: 2,
  },
];

// ---- Mock Alerts ----
export const mockAlerts: Alert[] = [
  {
    id: 'alt1',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    timestamp: '2026-03-02T14:23:00Z',
    severity: 'critical',
    message: '🚨 CRITICAL: Hydraulic Pump Gamma — vibration exceeded 15mm/s. Bearing failure imminent. Work order WO-2026-001 auto-created.',
    lineNotified: true,
    acknowledged: false,
  },
  {
    id: 'alt2',
    machineId: 'm2',
    machineName: 'Motor Drive Beta',
    timestamp: '2026-03-02T12:45:00Z',
    severity: 'critical',
    message: '⚠️ HIGH: Motor Drive Beta — winding temperature 78.3°C (limit 65°C). Overheating risk in 48h.',
    lineNotified: true,
    acknowledged: true,
    acknowledgedBy: 'สุภาพร หัวหน้า',
  },
  {
    id: 'alt3',
    machineId: 'm6',
    machineName: 'Compressor Zeta',
    timestamp: '2026-03-02T10:15:00Z',
    severity: 'warning',
    message: '⚡ WARNING: Compressor Zeta — output pressure dropped to 98.5 PSI (min 110 PSI). Check valves.',
    lineNotified: true,
    acknowledged: false,
  },
  {
    id: 'alt4',
    machineId: 'm1',
    machineName: 'CNC Machine Alpha',
    timestamp: '2026-03-01T18:10:00Z',
    severity: 'warning',
    message: '⚡ WARNING: CNC Machine Alpha — spindle vibration signature changed. Tool wear suspected.',
    lineNotified: true,
    acknowledged: true,
    acknowledgedBy: 'สุภาพร หัวหน้า',
  },
  {
    id: 'alt5',
    machineId: 'm3',
    machineName: 'Hydraulic Pump Gamma',
    timestamp: '2026-03-01T09:45:00Z',
    severity: 'critical',
    message: '🚨 HIGH: Hydraulic Pump Gamma — oil temperature 92.7°C (limit 70°C). Seal failure risk.',
    lineNotified: true,
    acknowledged: true,
    acknowledgedBy: 'นภา ผู้ดูแล',
  },
  {
    id: 'alt6',
    machineId: 'm4',
    machineName: 'Conveyor Line Delta',
    timestamp: '2026-03-01T22:30:00Z',
    severity: 'info',
    message: 'ℹ️ INFO: Conveyor Line Delta — minor RPM fluctuation at 1380 RPM. Belt tension check suggested.',
    lineNotified: false,
    acknowledged: true,
    acknowledgedBy: 'สุภาพร หัวหน้า',
  },
  {
    id: 'alt7',
    machineId: 'm7',
    machineName: 'Welding Station Eta',
    timestamp: '2026-02-28T16:20:00Z',
    severity: 'info',
    message: 'ℹ️ INFO: Welding Station Eta — slight current draw increase. Contact tip replacement recommended.',
    lineNotified: false,
    acknowledged: true,
    acknowledgedBy: 'สุภาพร หัวหน้า',
  },
];

// ---- Mock System Services ----
export const mockSystemServices: SystemService[] = [
  {
    name: 'MS1 — IoT Ingestor',
    status: 'running',
    uptime: '15d 7h 23m',
    cpu: 23,
    memory: 45,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '1.4.2',
  },
  {
    name: 'MS2 — AI Engine',
    status: 'running',
    uptime: '15d 7h 23m',
    cpu: 67,
    memory: 78,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '2.1.0',
  },
  {
    name: 'MS3 — Alert Service',
    status: 'running',
    uptime: '12d 3h 10m',
    cpu: 12,
    memory: 32,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '1.2.1',
  },
  {
    name: 'MS4 — Maintenance Service',
    status: 'running',
    uptime: '15d 7h 23m',
    cpu: 18,
    memory: 41,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '1.3.0',
  },
  {
    name: 'InfluxDB',
    status: 'running',
    uptime: '30d 2h 15m',
    cpu: 34,
    memory: 62,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '2.7.1',
  },
  {
    name: 'Redis',
    status: 'running',
    uptime: '30d 2h 15m',
    cpu: 8,
    memory: 25,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '7.2.4',
  },
  {
    name: 'PostgreSQL',
    status: 'running',
    uptime: '30d 2h 15m',
    cpu: 22,
    memory: 55,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '16.1',
  },
  {
    name: 'RabbitMQ',
    status: 'degraded',
    uptime: '5d 18h 42m',
    cpu: 45,
    memory: 71,
    lastHealthCheck: '2026-03-02T20:00:00Z',
    version: '3.13.0',
  },
];

// ---- Health Score History (7 days) ----
export function generateHealthHistory(machineId: string): { date: string; score: number }[] {
  const machine = mockMachines.find(m => m.id === machineId);
  const currentScore = machine?.healthScore ?? 80;
  const history: { date: string; score: number }[] = [];

  for (let i = 6; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    const dayStr = date.toISOString().split('T')[0];
    const variation = (Math.random() - 0.3) * 10;
    const score = Math.min(100, Math.max(0, Math.round(currentScore + variation + i * 1.5)));
    history.push({ date: dayStr, score });
  }
  return history;
}

// ---- Role Access Control ----
export const rolePermissions: Record<Role, string[]> = {
  engineer: ['health', 'anomaly', 'workorders'],
  supervisor: ['monitoring', 'workorders', 'users', 'machines'],
  it: ['monitoring', 'health', 'anomaly', 'workorders', 'users', 'machines', 'system'],
  admin: ['monitoring', 'health', 'anomaly', 'workorders', 'users', 'machines', 'system'],
};

export function hasPageAccess(role: Role, page: string): boolean {
  return rolePermissions[role]?.includes(page) ?? false;
}

export function getDefaultPage(role: Role): string {
  switch (role) {
    case 'engineer': return '/dashboard/health';
    case 'supervisor': return '/dashboard/monitoring';
    case 'it': 
    case 'admin': return '/dashboard/monitoring';
    default: return '/login';
  }
}
