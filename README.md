# OmniVigil

ระบบ Cloud-Native + Microservices สำหรับ Predictive Maintenance ในโรงงาน

## โครงภาพรวม 
- MS1 `services/ms1-auth`: login/JWT
- MS2 `services/ms2-ingestor`: ingest + clean telemetry + write InfluxDB
- MS3 `services/ms3-ai-engine`: ประเมิน anomaly/risk
- MS4 `services/ms4-alert`: แจ้งเตือน
- MS5 `services/ms5-maintenance`: work order
- Infra: Mosquitto, InfluxDB, Redis, RabbitMQ, PostgreSQL (2 ตัว)

flowchart LR
    User((Operator/Engineer)) --> FE[Frontend Dashboard]
    FE --> MS1[MS1 Auth Service]
    MS1 --> AuthDB[(PostgreSQL Auth)]

```mermaid
flowchart LR
    User((Operator/Engineer)) --> FE[Frontend Dashboard]
    FE --> MS1[MS1 Auth Service]
    MS1 --> AuthDB[(PostgreSQL Auth)]

    Sensors((Sensors)) --> MQTT[MQTT Broker]
    Simulator((Sensor Simulator)) --> MQTT
    MQTT --> MS2[MS2 IoT Ingestor]
    MS2 --> InfluxDB[(InfluxDB)]
    MS2 --> MS3[MS3 AI Engine]
    MS3 --> Redis[(Redis Cache)]
    MS3 --> RabbitMQ[(RabbitMQ Events)]
    RabbitMQ --> MS4[MS4 Alert]
    RabbitMQ --> MS5[MS5 Maintenance]
    MS4 --> LINE[LINE Notify]
    MS5 --> Postgres[(PostgreSQL)]
    FE --> MS2
    FE --> MS3
    FE --> MS4
    FE --> MS5
```
