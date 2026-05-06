import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Topbar from "./components/Topbar.jsx";
import ScoreCard from "./components/ScoreCard.jsx";
import ServiceGrid from "./components/ServiceGrid.jsx";
import NotificationCard from "./components/NotificationCard.jsx";
import TelemetryChart from "./components/TelemetryChart.jsx";
import LogsCard from "./components/LogsCard.jsx";
import MobileSimulator from "./components/MobileSimulator.jsx";
import OrdersCard from "./components/OrdersCard.jsx";
import Toast from "./components/Toast.jsx";

const API = {
  auth: import.meta.env.VITE_MS1_URL || "http://localhost:8001",
  ingestor: import.meta.env.VITE_MS2_URL || "http://localhost:8002",
  ai: import.meta.env.VITE_MS3_URL || "http://localhost:8003",
  alert: import.meta.env.VITE_MS4_URL || "http://localhost:8004",
  maintenance: import.meta.env.VITE_MS5_URL || "http://localhost:8005"
};

const STATIC_ACCESS_TOKEN = import.meta.env.VITE_ACCESS_TOKEN || "";

const POLL_MS = 3000;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const SENSOR_DEFINITIONS = {
  temperature_c: { label: "Temperature", unit: "°C", icon: "🌡️" },
  vibration_rms: { label: "Vibration", unit: "rms", icon: "📳" },
  rpm: { label: "RPM", unit: "rpm", icon: "⚙️" },
  pressure_bar: { label: "Pressure", unit: "bar", icon: "🫧" },
  flow_lpm: { label: "Flow", unit: "L/min", icon: "💧" },
  current_a: { label: "Current", unit: "A", icon: "⚡" },
  oil_temp_c: { label: "Oil Temp", unit: "°C", icon: "🛢️" },
  humidity_pct: { label: "Humidity", unit: "%", icon: "💨" },
  power_kw: { label: "Power", unit: "kW", icon: "🔋" }
};

const SENSOR_GUARDRAILS = {
  temperature_c: { min: -20, max: 200, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  vibration_rms: { min: 0, max: 50, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  rpm: { min: 0, max: 20000, source: "MS2 ingest non-negative enforcement from services/ms2-ingestor/app/main.py" },
  pressure_bar: { min: 0, max: 25, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  flow_lpm: { min: 0, max: 5000, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  current_a: { min: 0, max: 1200, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  oil_temp_c: { min: -20, max: 220, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  humidity_pct: { min: 0, max: 100, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" },
  power_kw: { min: 0, max: 2500, source: "MS2 ingest clamp from services/ms2-ingestor/app/main.py" }
};

const MACHINE_PROFILE_REFERENCE = {
  "mix-pump-101": {
    temperature_c: { base: 61.5, amp: 4.5 },
    vibration_rms: { base: 1.8, amp: 0.55 },
    rpm: { base: 1480.0, amp: 35.0 },
    pressure_bar: { base: 4.2 },
    flow_lpm: { base: 285.0 },
    current_a: { base: 28.0 },
    power_kw: { base: 11.0 }
  },
  "filling-comp-201": {
    temperature_c: { base: 74.0, amp: 5.0 },
    vibration_rms: { base: 2.2, amp: 0.65 },
    rpm: { base: 2960.0, amp: 70.0 },
    pressure_bar: { base: 7.6 },
    current_a: { base: 33.5 },
    oil_temp_c: { base: 69.0 },
    power_kw: { base: 18.5 }
  },
  "cnc-spindle-301": {
    temperature_c: { base: 67.0, amp: 6.5 },
    vibration_rms: { base: 1.5, amp: 0.45 },
    rpm: { base: 10800.0, amp: 850.0 },
    current_a: { base: 24.0 },
    oil_temp_c: { base: 62.0 },
    power_kw: { base: 7.5 }
  },
  "boiler-feed-401": {
    temperature_c: { base: 83.0, amp: 4.0 },
    vibration_rms: { base: 2.6, amp: 0.8 },
    rpm: { base: 3520.0, amp: 85.0 },
    pressure_bar: { base: 9.8 },
    flow_lpm: { base: 118.0 },
    current_a: { base: 40.5 },
    power_kw: { base: 22.0 }
  },
  "pack-conveyor-501": {
    temperature_c: { base: 49.0, amp: 3.8 },
    vibration_rms: { base: 1.2, amp: 0.35 },
    rpm: { base: 92.0, amp: 6.0 },
    current_a: { base: 11.5 },
    humidity_pct: { base: 58.0 },
    power_kw: { base: 2.2 }
  }
};

const buildThreshold = (deviceId, sensorKey) => {
  const profile = MACHINE_PROFILE_REFERENCE[deviceId]?.[sensorKey];
  const guardrail = SENSOR_GUARDRAILS[sensorKey];

  if (!profile) {
    if (!guardrail) {
      return null;
    }
    return {
      normalMin: guardrail.min,
      normalMax: guardrail.max,
      anomalyMin: guardrail.min,
      anomalyMax: guardrail.max,
      source: guardrail.source
    };
  }

  let normalMin;
  let normalMax;
  let anomalyMin;
  let anomalyMax;
  let source;

  if (typeof profile.amp === "number") {
    normalMin = profile.base - profile.amp;
    normalMax = profile.base + profile.amp;
    anomalyMin = profile.base - profile.amp * 2;
    anomalyMax = profile.base + profile.amp * 2;
    source = "Simulator baseline from services/sim-sensor/app/machine_profiles.py (normal=base±amp, anomaly=base±2×amp)";
  } else {
    const normalSpan = Math.max(Math.abs(profile.base) * 0.08, 1);
    const anomalySpan = Math.max(Math.abs(profile.base) * 0.16, 2);
    normalMin = profile.base - normalSpan;
    normalMax = profile.base + normalSpan;
    anomalyMin = profile.base - anomalySpan;
    anomalyMax = profile.base + anomalySpan;
    source = "Simulator baseline from services/sim-sensor/app/machine_profiles.py (derived ±8% normal, ±16% anomaly for sensors without amplitude)";
  }

  if (guardrail) {
    normalMin = clamp(normalMin, guardrail.min, guardrail.max);
    normalMax = clamp(normalMax, guardrail.min, guardrail.max);
    anomalyMin = clamp(anomalyMin, guardrail.min, guardrail.max);
    anomalyMax = clamp(anomalyMax, guardrail.min, guardrail.max);
    source = `${source}; bounded by ${guardrail.source}`;
  }

  return {
    normalMin,
    normalMax,
    anomalyMin,
    anomalyMax,
    source
  };
};

const getAccessToken = () => {
  // Runtime override: localStorage token has priority for developer testing.
  return window.localStorage.getItem("omnivigil_access_token") || STATIC_ACCESS_TOKEN;
};

const fetchJson = async (url, options = {}) => {
  const token = getAccessToken();
  const headers = {
    ...(options.headers || {})
  };

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
};

const playBeep = () => {
  const context = new (window.AudioContext || window.webkitAudioContext)();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = 880;
  gain.gain.value = 0.08;
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.25);
};

export default function App() {
  const [telemetry, setTelemetry] = useState([]);
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [workOrders, setWorkOrders] = useState([]);
  const [services, setServices] = useState({});
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [selectedSensor, setSelectedSensor] = useState("temperature_c");
  const [toast, setToast] = useState(null);
  const [soundOn, setSoundOn] = useState(true);
  const lastAlertId = useRef(null);
  const lastEventId = useRef(null);

  const telemetryByMachine = useMemo(() => {
    const grouped = telemetry.reduce((acc, item) => {
      if (!acc[item.device_id]) {
        acc[item.device_id] = [];
      }
      acc[item.device_id].push(item);
      return acc;
    }, {});
    return grouped;
  }, [telemetry]);

  const machineIds = useMemo(() => Object.keys(telemetryByMachine), [telemetryByMachine]);

  useEffect(() => {
    if (!machineIds.length) {
      return;
    }
    if (!selectedMachine || !machineIds.includes(selectedMachine)) {
      setSelectedMachine(machineIds[0]);
    }
  }, [machineIds, selectedMachine]);

  const selectedMachineTelemetry = selectedMachine ? telemetryByMachine[selectedMachine] || [] : telemetry;
  const latestReading = selectedMachineTelemetry[selectedMachineTelemetry.length - 1] || telemetry[telemetry.length - 1];
  const selectedMachineInfo = latestReading
    ? {
      machineType: latestReading.machine_type,
      line: latestReading.line,
      zone: latestReading.zone
    }
    : null;
  const latestEvent = events[events.length - 1];
  const latestAlert = alerts[alerts.length - 1];

  const healthScore = useMemo(() => {
    if (!latestReading) {
      return 72;
    }
    const tempPenalty = (latestReading.temperature_c - 60) * 0.8;
    const vibPenalty = latestReading.vibration_rms * 4.2;
    const score = 100 - tempPenalty - vibPenalty;
    return Math.round(clamp(score, 0, 100));
  }, [latestReading]);

  const riskLevel = latestEvent?.risk_level || (healthScore < 45 ? "critical" : healthScore < 65 ? "warning" : "healthy");

  const nodeStatus = useMemo(() => ([
    { name: "edge-node-01", status: services.ingestor === "UP" ? "ready" : "degraded" },
    { name: "edge-node-02", status: services.ai === "UP" ? "ready" : "degraded" },
    { name: "edge-node-03", status: services.alert === "UP" ? "busy" : "degraded" },
    { name: "edge-node-04", status: services.maintenance === "UP" ? "ready" : "degraded" }
  ]), [services]);

  const serviceStatus = useMemo(() => ([
    { name: "MS1 Auth", status: services.auth === "UP" ? "up" : "down" },
    { name: "MS2 Ingestor", status: services.ingestor === "UP" ? "up" : "down" },
    { name: "MS3 AI Engine", status: services.ai === "UP" ? "up" : "down" },
    { name: "MS4 Alert", status: services.alert === "UP" ? "busy" : "down" },
    { name: "MS5 Maintenance", status: services.maintenance === "UP" ? "up" : "down" }
  ]), [services]);

  const sensorSnapshot = useMemo(() => {
    if (!latestReading) {
      return [];
    }

    return Object.entries(SENSOR_DEFINITIONS)
      .filter(([sensorKey]) => latestReading[sensorKey] !== null && latestReading[sensorKey] !== undefined)
      .map(([sensorKey, meta]) => {
        const threshold = buildThreshold(latestReading.device_id, sensorKey);
        const value = latestReading[sensorKey];
        let status = "normal";

        if (threshold) {
          if (value < threshold.anomalyMin || value > threshold.anomalyMax) {
            status = "abnormal";
          } else if (value < threshold.normalMin || value > threshold.normalMax) {
            status = "warning";
          }
        }

        return {
          key: sensorKey,
          label: meta.label,
          unit: meta.unit,
          icon: meta.icon,
          value,
          status,
          threshold
        };
      });
  }, [latestReading]);

  useEffect(() => {
    if (!sensorSnapshot.length) {
      return;
    }
    if (!sensorSnapshot.some((sensor) => sensor.key === selectedSensor)) {
      setSelectedSensor(sensorSnapshot[0].key);
    }
  }, [sensorSnapshot, selectedSensor]);

  const selectedSensorSeries = useMemo(() => {
    return selectedMachineTelemetry
      .map((item) => item[selectedSensor])
      .filter((value) => typeof value === "number" && Number.isFinite(value));
  }, [selectedMachineTelemetry, selectedSensor]);

  const selectedSensorSnapshot = sensorSnapshot.find((sensor) => sensor.key === selectedSensor) || null;

  const logEntries = useMemo(() => {
    const time = new Date().toLocaleTimeString();
    return [
      `[${time}] gRPC stream linked to edge gateway`,
      `[${time}] Scheduler: balancing microservice replicas`,
      selectedMachine
        ? `[${time}] Selected machine: ${selectedMachine}`
        : `[${time}] Waiting machine telemetry`,
      latestAlert
        ? `[${time}] Alert dispatched: ${latestAlert.risk_level} ${latestAlert.machine_id}`
        : `[${time}] Alert dispatch queued via internal API/event flow`
    ];
  }, [latestAlert, selectedMachine]);

  const poll = async () => {
    try {
      const [readings, eventData, alertData, workOrderData] = await Promise.all([
        fetchJson(`${API.ingestor}/readings?limit=40`).catch(() => []),
        fetchJson(`${API.ai}/events?limit=20`).catch(() => ({ items: [] })),
        fetchJson(`${API.alert}/alerts?limit=20`).catch(() => ({ items: [] })),
        fetchJson(`${API.maintenance}/work-orders?limit=20`).catch(() => ({ items: [] }))
      ]);

      const nextTelemetry = Array.isArray(readings) ? readings : [];
      const nextEvents = eventData.items || [];
      const nextAlerts = alertData.items || [];
      const nextWorkOrders = workOrderData.items || [];

      setTelemetry(nextTelemetry);
      setEvents(nextEvents);
      setAlerts(nextAlerts);
      setWorkOrders(nextWorkOrders);

      const recentAlert = nextAlerts[nextAlerts.length - 1];
      const recentEvent = nextEvents[nextEvents.length - 1];

      if (recentAlert?.alert_id && recentAlert.alert_id !== lastAlertId.current) {
        lastAlertId.current = recentAlert.alert_id;
        setToast({
          title: "OMNIVIGIL AGENT",
          message: `System anomaly detected on ${recentAlert.machine_id}`,
          time: new Date().toLocaleTimeString()
        });
        if (soundOn) {
          playBeep();
        }
      } else if (recentEvent?.event_id && recentEvent.event_id !== lastEventId.current) {
        lastEventId.current = recentEvent.event_id;
        setToast({
          title: "OMNIVIGIL AGENT",
          message: `Predictive anomaly event ${recentEvent.risk_level}`,
          time: new Date().toLocaleTimeString()
        });
        if (soundOn) {
          playBeep();
        }
      }
    } catch (error) {
      console.error(error);
    }

    const statusChecks = await Promise.all([
      fetchJson(`${API.auth}/health`).catch(() => null),
      fetchJson(`${API.ingestor}/health`).catch(() => null),
      fetchJson(`${API.ai}/health`).catch(() => null),
      fetchJson(`${API.alert}/health`).catch(() => null),
      fetchJson(`${API.maintenance}/health`).catch(() => null)
    ]);

    setServices({
      auth: statusChecks[0]?.status === "ok" ? "UP" : "DOWN",
      ingestor: statusChecks[1]?.status === "ok" ? "UP" : "DOWN",
      ai: statusChecks[2]?.status === "ok" ? "UP" : "DOWN",
      alert: statusChecks[3]?.status === "ok" ? "UP" : "DOWN",
      maintenance: statusChecks[4]?.status === "ok" ? "UP" : "DOWN"
    });
  };

  useEffect(() => {
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className={`app ${riskLevel === "critical" ? "critical" : ""}`}>
      <Sidebar
        healthScore={healthScore}
        riskLevel={riskLevel}
        nodeStatus={nodeStatus}
        serviceStatus={serviceStatus}
        soundOn={soundOn}
        onToggleSound={() => setSoundOn((value) => !value)}
      />
      <main className="main">
        <Topbar />
        <section className="grid">
          <ScoreCard healthScore={healthScore} riskLevel={riskLevel} />
          <ServiceGrid serviceStatus={serviceStatus} services={services} />
          <NotificationCard latestAlert={latestAlert} />
        </section>
        <TelemetryChart
          latestReading={latestReading}
          machineIds={machineIds}
          selectedMachine={selectedMachine}
          onSelectMachine={setSelectedMachine}
          machineInfo={selectedMachineInfo}
          selectedSensor={selectedSensor}
          onSelectSensor={setSelectedSensor}
          sensorOptions={sensorSnapshot}
          sensorSnapshot={sensorSnapshot}
          sensorSeries={selectedSensorSeries}
          selectedSensorSnapshot={selectedSensorSnapshot}
        />
        <section className="grid bottom">
          <LogsCard logEntries={logEntries} />
          <MobileSimulator latestAlert={latestAlert} />
          <OrdersCard workOrders={workOrders} />
        </section>
      </main>
      {toast && <Toast toast={toast} onDone={() => setToast(null)} />}
    </div>
  );
}
