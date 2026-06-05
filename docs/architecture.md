# OmniVigil Architecture

## High-Level Data Flow

```mermaid
flowchart TD
    User((Operator/Engineer)) --> FE[Frontend Dashboard]
    FE -->|HTTP Port 8000| Kong[Kong API Gateway]

    subgraph Routing Layer
        Kong
    end

    subgraph Microservices Layer
        MS1[MS1 Auth]
        MS2[MS2 Ingestor]
        MS3[MS3 AI Engine]
        MS4[MS4 Alert]
        MS5[MS5 Maintenance]
        MS6[MS6 Machine]
    end

    subgraph Messaging & Data Flow
        MQTT[MQTT Broker]
        Redis[(Redis Cache & Celery)]
        RabbitMQ[(RabbitMQ Queue)]
    end

    subgraph Storage Layer
        AuthDB[(PostgreSQL Auth)]
        MaintDB[(PostgreSQL Main)]
        InfluxDB[(InfluxDB Telemetry)]
    end

    subgraph Observability Layer (Sidecar)
        Prometheus[Prometheus Metrics]
        Grafana[Grafana Dashboard]
    end

    %% Routing Ingress
    Kong -->|/auth-service| MS1
    Kong -->|/ingestor-service| MS2
    Kong -->|/ai-service| MS3
    Kong -->|/alert-service| MS4
    Kong -->|/maintenance-service| MS5
    Kong -->|/machine-service| MS6

    %% Ingestion Flow
    MQTT --> MS2
    MS2 --> InfluxDB
    MS2 -->|POST /analyze| MS3

    %% AI Pipeline
    MS3 --> Redis
    MS3 -->|Celery Workers| Redis
    MS3 -->|RabbitMQ queue| MS4
    MS3 -->|RabbitMQ queue| MS5

    %% Database connections
    MS1 --> AuthDB
    MS5 --> MaintDB

    %% External Notifications
    MS4 -->|Flex Message Card| LINE[LINE Messaging API]

    %% Observability Scrapes
    Prometheus -->|Pull Scrape| Kong
    Prometheus -->|Pull Scrape| Prometheus
    Grafana -->|Query| Prometheus
```

## Service Responsibilities

- **Kong API Gateway (พอร์ต 8000):** ด่านหน้ารับคำขอ (Central Ingress) จาก Frontend จัดการการจำกัดสิทธิ์ CORS และจำกัดความถี่การยิง (Rate Limiting) ของพอร์ตเข้าสู่ระบบหลังบ้านทั้งหมด
- **MS1 Auth (พอร์ต 8001):** จัดการสิทธิ์การใช้งาน การสร้าง Token JWT และเชื่อมต่ออ่านสถานะ Resource ผ่าน Docker Socket (`docker.sock`)
- **MS2 Ingestor (พอร์ต 8002):** ดึงข้อมูลเทเลเมทรีจากเซ็นเซอร์ (MQTT) ตรวจสอบความถูกต้องคลีนข้อมูล (Sanitization) และบันทึกลงใน InfluxDB
- **MS3 AI Engine (พอร์ต 8003):** ประมวลผลความเสี่ยงเครื่องจักร (Anomaly Detection) ทั้งแบบ immediate threshold และแบบ Celery Asynchronous ML (ด้วยโมเดล Chronos Forecaster)
- **MS4 Alert (พอร์ต 8004):** นำเข้าข้อมูล Anomaly ประมวลผลสร้าง Flex Message และส่งการแจ้งเตือนไปยังผู้ใช้ทาง LINE Messaging API
- **MS5 Maintenance (พอร์ต 8005):** สร้างใบสั่งซ่อมบำรุง (Work Orders) อัตโนมัติเมื่อเกิดการพังล่วงหน้า และติดตามการแก้ไขของเจ้าหน้าที่เทคนิค
- **MS6 Machine (พอร์ต 8006):** ระบบทะเบียนเครื่องจักรและ Zone ต่างๆ ในโรงงาน คอยรับการบันทึกระดับสุขภาพ (Health Score)

## Security Boundary

- **Gateway Ingress Isolation:** หน้าบ้านคุยผ่านพอร์ต `8000` เท่านั้น ห้ามมิให้เรียกใช้บริการตรงไปยังพอร์ตแยก (`8001`-`8006`) ของแต่ละไมโครเซอร์วิส เพื่อสร้างความมั่นใจในเรื่องสิทธิ์การเข้าถึง
- **Token Verification:** ทุกบริการย่อยจะตรวจสอบสิทธิ์ผู้ใช้งานผ่าน JWT Token ที่ออกโดย MS1 Auth
- **Database Coupling Avoidance:** ฐานข้อมูลของระบบแบ่งแยกอิสระ (Database-per-service pattern) ทั้งฐานข้อมูลระบบล็อกอิน และฐานข้อมูลการซ่อมบำรุง เพื่อให้เกิด Low Coupling
