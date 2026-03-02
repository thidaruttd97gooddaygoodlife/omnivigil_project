export default function TelemetryChart({
  latestReading,
  machineIds,
  selectedMachine,
  onSelectMachine,
  machineInfo,
  selectedSensor,
  onSelectSensor,
  sensorOptions,
  sensorSnapshot,
  sensorSeries,
  selectedSensorSnapshot
}) {
  const chartWidth = 900;
  const chartHeight = 300;
  const margin = { top: 20, right: 24, bottom: 42, left: 68 };
  const plotWidth = chartWidth - margin.left - margin.right;
  const plotHeight = chartHeight - margin.top - margin.bottom;

  const threshold = selectedSensorSnapshot?.threshold || null;
  const yCandidates = [
    ...sensorSeries,
    threshold?.normalMin,
    threshold?.normalMax,
    threshold?.anomalyMin,
    threshold?.anomalyMax
  ].filter((value) => typeof value === "number" && Number.isFinite(value));

  const defaultMin = 0;
  const defaultMax = 100;
  const rawMin = yCandidates.length ? Math.min(...yCandidates) : defaultMin;
  const rawMax = yCandidates.length ? Math.max(...yCandidates) : defaultMax;
  const range = Math.max(rawMax - rawMin, 1);
  const paddedMin = rawMin - range * 0.15;
  const paddedMax = rawMax + range * 0.15;

  const yScale = (value) => {
    const normalized = (value - paddedMin) / (paddedMax - paddedMin);
    return margin.top + plotHeight - normalized * plotHeight;
  };

  const xScale = (index) => {
    if (sensorSeries.length <= 1) {
      return margin.left;
    }
    return margin.left + (index / (sensorSeries.length - 1)) * plotWidth;
  };

  const linePath = sensorSeries.length
    ? sensorSeries
      .map((value, index) => `${index === 0 ? "M" : "L"} ${xScale(index).toFixed(2)} ${yScale(value).toFixed(2)}`)
      .join(" ")
    : "";

  const yTicks = Array.from({ length: 6 }, (_, index) => {
    const ratio = index / 5;
    const value = paddedMax - ratio * (paddedMax - paddedMin);
    return {
      y: margin.top + ratio * plotHeight,
      label: value
    };
  });

  const xTicks = Array.from({ length: 6 }, (_, index) => {
    const ratio = index / 5;
    const sampleIndex = Math.round(ratio * Math.max(sensorSeries.length - 1, 0));
    return {
      x: margin.left + ratio * plotWidth,
      label: sensorSeries.length ? `t-${Math.max(sensorSeries.length - 1 - sampleIndex, 0)}` : "-"
    };
  });

  const latestPoint = sensorSeries.length
    ? {
      x: xScale(sensorSeries.length - 1),
      y: yScale(sensorSeries[sensorSeries.length - 1])
    }
    : null;

  const metricValue = selectedSensorSnapshot
    ? `${selectedSensorSnapshot.value.toFixed(2)} ${selectedSensorSnapshot.unit}`
    : "--";

  return (
    <section className="card chart glass">
      <div className="chart-header">
        <div>
          <div className="card-label">TELEMETRY REALTIME</div>
          <div className="chart-sub">Stream: MQTT / Ingress: MS2 / Machine: {selectedMachine || "--"}</div>
          <div className="chart-sub chart-machine-meta">
            {machineInfo ? `${machineInfo.machineType} • line ${machineInfo.line} • zone ${machineInfo.zone}` : "Awaiting metadata"}
          </div>
        </div>
        <div className="chart-metrics">
          <div>
            <div className="metric-label">Selected Sensor</div>
            <div className="metric-value">{selectedSensorSnapshot ? `${selectedSensorSnapshot.icon} ${selectedSensorSnapshot.label}` : "--"}</div>
          </div>
          <div>
            <div className="metric-label">Current Value</div>
            <div className="metric-value">{metricValue}</div>
          </div>
        </div>
      </div>

      <div className="machine-tabs">
        {machineIds.map((machineId) => (
          <button
            key={machineId}
            className={`machine-tab ${machineId === selectedMachine ? "active" : ""}`}
            onClick={() => onSelectMachine(machineId)}
          >
            {machineId}
          </button>
        ))}
      </div>

      <div className="sensor-selector">
        {sensorOptions.map((sensor) => (
          <button
            key={sensor.key}
            className={`sensor-chip ${sensor.key === selectedSensor ? "active" : ""}`}
            onClick={() => onSelectSensor(sensor.key)}
          >
            <span>{sensor.icon}</span>
            <span>{sensor.label}</span>
          </button>
        ))}
      </div>

      <div className="sensor-grid">
        {sensorSnapshot.map((sensor) => (
          <div key={sensor.key} className={`sensor-tile ${sensor.status}`}>
            <div className="sensor-label">{sensor.icon} {sensor.label}</div>
            <div className="sensor-value">{typeof sensor.value === "number" ? sensor.value.toFixed(2) : sensor.value}</div>
            <div className="sensor-unit">{sensor.unit}</div>
            <div className={`sensor-state ${sensor.status}`}>{sensor.status}</div>
          </div>
        ))}
      </div>

      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="chart-svg">
        <rect x={margin.left} y={margin.top} width={plotWidth} height={plotHeight} className="plot-area" />

        {yTicks.map((tick, index) => (
          <g key={`y-${index}`}>
            <line x1={margin.left} x2={margin.left + plotWidth} y1={tick.y} y2={tick.y} className="grid-line" />
            <text x={margin.left - 10} y={tick.y + 4} className="axis-label axis-y">{tick.label.toFixed(2)}</text>
          </g>
        ))}

        {xTicks.map((tick, index) => (
          <g key={`x-${index}`}>
            <line x1={tick.x} x2={tick.x} y1={margin.top} y2={margin.top + plotHeight} className="grid-line vertical" />
            <text x={tick.x} y={margin.top + plotHeight + 20} textAnchor="middle" className="axis-label">{tick.label}</text>
          </g>
        ))}

        {threshold && (
          <>
            <rect
              x={margin.left}
              y={Math.min(yScale(threshold.normalMax), yScale(threshold.normalMin))}
              width={plotWidth}
              height={Math.abs(yScale(threshold.normalMin) - yScale(threshold.normalMax))}
              className="normal-band"
            />
            <line
              x1={margin.left}
              x2={margin.left + plotWidth}
              y1={yScale(threshold.normalMin)}
              y2={yScale(threshold.normalMin)}
              className="threshold-line normal"
            />
            <line
              x1={margin.left}
              x2={margin.left + plotWidth}
              y1={yScale(threshold.normalMax)}
              y2={yScale(threshold.normalMax)}
              className="threshold-line normal"
            />
            <line
              x1={margin.left}
              x2={margin.left + plotWidth}
              y1={yScale(threshold.anomalyMin)}
              y2={yScale(threshold.anomalyMin)}
              className="threshold-line anomaly"
            />
            <line
              x1={margin.left}
              x2={margin.left + plotWidth}
              y1={yScale(threshold.anomalyMax)}
              y2={yScale(threshold.anomalyMax)}
              className="threshold-line anomaly"
            />
          </>
        )}

        <line x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + plotHeight} className="axis-line" />
        <line
          x1={margin.left}
          x2={margin.left + plotWidth}
          y1={margin.top + plotHeight}
          y2={margin.top + plotHeight}
          className="axis-line"
        />

        {linePath && <path d={linePath} className="line selected-sensor" />}
        {latestPoint && <circle cx={latestPoint.x} cy={latestPoint.y} r="4.5" className="latest-dot" />}
      </svg>

      <div className="chart-legend">
        <span><i className="legend-swatch data" /> Data line</span>
        <span><i className="legend-swatch normal" /> Normal range</span>
        <span><i className="legend-swatch anomaly" /> Anomaly limit</span>
      </div>

      <div className="chart-source">
        <div className="source-title">Reference source</div>
        <div className="source-text">{selectedSensorSnapshot?.threshold?.source || "No threshold reference available for this sensor yet."}</div>
      </div>
    </section>
  );
}
