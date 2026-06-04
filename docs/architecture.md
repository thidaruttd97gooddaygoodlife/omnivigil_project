# OmniVigil Architecture

## High-Level Data Flow
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

## Service Responsibilities
- MS1 Auth: login + JWT + role-based authorization
- MS2 Ingestor: รับ/clean ข้อมูล telemetry และเก็บลง InfluxDB
- MS3 AI Engine: วิเคราะห์ anomaly score/risk และส่ง event ไป RabbitMQ
- MS4 Alert: subscribe event แล้วส่งแจ้งเตือนหลายช่องทาง
- MS5 Maintenance: subscribe event แล้วเปิด/ติดตามใบสั่งซ่อม

## Security Boundary
- Frontend และทุก backend service ต้องใช้ JWT จาก MS1
- service-to-service call ที่มีสิทธิ์สำคัญควรตรวจ token ผ่าน `/auth/verify`
- แยกฐานข้อมูล auth กับ maintenance ออกจากกันเพื่อลด coupling
