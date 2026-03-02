# OmniVigil Architecture (Stub)

## High-Level Data Flow
```mermaid
flowchart LR
    Sensors((Sensors)) --> MQTT[MQTT Broker]
    Simulator((Sensor Simulator)) --> MQTT
    MQTT --> MS1[MS1 IoT Ingestor]
    MS1 --> InfluxDB[(InfluxDB)]
    MS1 --> MS2[MS2 AI Engine]
    MS2 --> Redis[(Redis Cache)]
    MS2 --> RabbitMQ[(RabbitMQ Events)]
    RabbitMQ --> MS3[MS3 Alert]
    RabbitMQ --> MS4[MS4 Maintenance]
    MS3 --> LINE[LINE Notify]
    MS4 --> Postgres[(PostgreSQL)]
```

## Service Responsibilities
- MS1: Clean telemetry, ingest, and forward for analysis.
- MS2: Score anomalies, trigger alert/work-order pipeline.
- MS3: Simulate multichannel alert delivery.
- MS4: Simulate maintenance work orders and history.
