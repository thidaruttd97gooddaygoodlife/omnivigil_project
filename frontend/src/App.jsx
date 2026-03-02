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
  ms1: import.meta.env.VITE_MS1_URL || "http://localhost:8001",
  ms2: import.meta.env.VITE_MS2_URL || "http://localhost:8002",
  ms3: import.meta.env.VITE_MS3_URL || "http://localhost:8003",
  ms4: import.meta.env.VITE_MS4_URL || "http://localhost:8004"
};

const POLL_MS = 3000;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const fetchJson = async (url, options) => {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
};

const buildPath = (values, width, height, min, max) => {
  if (!values.length) {
    return "";
  }
  const step = width / (values.length - 1 || 1);
  return values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / (max - min)) * height;
      const clamped = clamp(y, 6, height - 6);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${clamped.toFixed(1)}`;
    })
    .join(" ");
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
  const [toast, setToast] = useState(null);
  const [soundOn, setSoundOn] = useState(true);
  const lastAlertId = useRef(null);
  const lastEventId = useRef(null);

  const latestReading = telemetry[telemetry.length - 1];
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
    { name: "edge-node-01", status: services.ms1 === "UP" ? "ready" : "degraded" },
    { name: "edge-node-02", status: services.ms2 === "UP" ? "ready" : "degraded" },
    { name: "edge-node-03", status: services.ms3 === "UP" ? "busy" : "degraded" },
    { name: "edge-node-04", status: services.ms4 === "UP" ? "ready" : "degraded" }
  ]), [services]);

  const serviceStatus = useMemo(() => ([
    { name: "IoT Ingestor", status: services.ms1 === "UP" ? "up" : "down" },
    { name: "AI Engine", status: services.ms2 === "UP" ? "up" : "down" },
    { name: "Alert Hub", status: services.ms3 === "UP" ? "busy" : "down" },
    { name: "Maintenance", status: services.ms4 === "UP" ? "up" : "down" }
  ]), [services]);

  const temperatureSeries = telemetry.map((item) => item.temperature_c);
  const vibrationSeries = telemetry.map((item) => item.vibration_rms);

  const telemetryPath = buildPath(temperatureSeries, 820, 200, 40, 120);
  const vibrationPath = buildPath(vibrationSeries, 820, 200, 0, 12);

  const logEntries = useMemo(() => {
    const time = new Date().toLocaleTimeString();
    return [
      `[${time}] gRPC stream linked to edge gateway`,
      `[${time}] Scheduler: balancing microservice replicas`,
      latestAlert
        ? `[${time}] Alert dispatched: ${latestAlert.risk_level} ${latestAlert.machine_id}`
        : `[${time}] Alert dispatch queued via RabbitMQ`
    ];
  }, [latestAlert]);

  const poll = async () => {
    try {
      const [readings, eventData, alertData, workOrderData] = await Promise.all([
        fetchJson(`${API.ms1}/readings?limit=40`).catch(() => []),
        fetchJson(`${API.ms2}/events?limit=20`).catch(() => ({ items: [] })),
        fetchJson(`${API.ms3}/alerts?limit=20`).catch(() => ({ items: [] })),
        fetchJson(`${API.ms4}/work-orders?limit=20`).catch(() => ({ items: [] }))
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
      fetchJson(`${API.ms1}/health`).catch(() => null),
      fetchJson(`${API.ms2}/health`).catch(() => null),
      fetchJson(`${API.ms3}/health`).catch(() => null),
      fetchJson(`${API.ms4}/health`).catch(() => null)
    ]);

    setServices({
      ms1: statusChecks[0]?.status === "ok" ? "UP" : "DOWN",
      ms2: statusChecks[1]?.status === "ok" ? "UP" : "DOWN",
      ms3: statusChecks[2]?.status === "ok" ? "UP" : "DOWN",
      ms4: statusChecks[3]?.status === "ok" ? "UP" : "DOWN"
    });
  };

  useEffect(() => {
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, []);

  const simulateFail = async () => {
    await fetchJson(`${API.ms1}/simulate/fail?device_id=motor-001`, { method: "POST" }).catch(() => null);
    poll();
  };

  const simulateBatch = async () => {
    await fetchJson(`${API.ms1}/simulate/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: "motor-001", count: 30 })
    }).catch(() => null);
    poll();
  };

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
        <Topbar onSimulateBatch={simulateBatch} onSimulateFail={simulateFail} />
        <section className="grid">
          <ScoreCard healthScore={healthScore} riskLevel={riskLevel} />
          <ServiceGrid serviceStatus={serviceStatus} services={services} />
          <NotificationCard latestAlert={latestAlert} />
        </section>
        <TelemetryChart latestReading={latestReading} telemetryPath={telemetryPath} vibrationPath={vibrationPath} />
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
