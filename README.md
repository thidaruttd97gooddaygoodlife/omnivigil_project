# OmniVigil (ระบบตรวจจับและแจ้งเตือนการซ่อมบำรุงเชิงคาดการณ์อัจฉริยะ)

ระบบ **Predictive Maintenance** แบบ **Cloud-Native & Stateless Microservices** สำหรับโรงงานอัจฉริยะ (Smart Factory) ที่มาพร้อมระบบวิเคราะห์ซีรีส์เวลา (Time-series ML) ด้วยโมเดล Chronos, ระบบจัดการใบสั่งซ่อมบำรุง (Work Order), ระบบสังเกตการณ์ขั้นสูง (Observability) และระบบประสานงานแจ้งเตือนแบบริชการ์ดผ่านแอปพลิเคชัน LINE

---

## 🏗️ 1. สถาปัตยกรรมระบบ (System Architecture)

ระบบประกอบด้วย 5 เลเยอร์หลัก (เรียงลำดับจากหน้าบ้านถึงฐานข้อมูล) ออกแบบตามสถาปัตยกรรม Microservices ระดับโปรดักชั่น หลีกเลี่ยงเส้นเชื่อมพันกันด้วยโครงสร้างแบบ Sidecar และ Gateway Ingress:

```
[ Frontend Client (Next.js - Port 3000) ]
                   │
                   ▼ (ยิงเข้าพอร์ต 8000 เท่านั้น)
    [ Kong API Gateway (Port 8000) ]
                   │
  ┌────────────────┼────────────────┬────────────────┐
  ▼                ▼                ▼                ▼
[Auth (MS1)]  [Ingestor (MS2)]  [AI Engine (MS3)]  [Alert (MS4)] ... [Machine (MS6)]
  │                │                │                │
  ▼                ▼                ▼                ▼
[Postgres]     [InfluxDB]       [Redis/Worker]    [RabbitMQ]
```

### รายละเอียดส่วนประกอบ:
1. **Frontend Client (Next.js):** อินเตอร์เฟสหน้าบ้าน แสดงผลแผงควบคุมหลัก, ประวัติเครื่องจักร, รายการใบสั่งซ่อมบำรุง และ **แผนผังโครงสร้างการไหลข้อมูลแบบเรียลไทม์ (SVG Topology Map)**
2. **Central Ingress Gateway (Kong Gateway - Port 8000):** ตัวรับส่งสัญญาณและเราเตอร์กลาง (Ingress Point) ป้องกันไม่ให้หน้าบ้านคุยตรงกับหลังบ้าน จัดการ CORS และจำกัดอัตราการยิงเพื่อความปลอดภัย (Rate Limiting)
3. **Stateless Microservices (MS1 - MS6):**
   * **MS1 Auth (`8001`):** จัดการสิทธิ์ผู้ใช้งาน ตรวจสอบ Token JWT และอ่านข้อมูล Docker Socket
   * **MS2 Ingestor (`8002`):** รับข้อมูลดิบจากเซ็นเซอร์ผ่าน MQTT Broker คลีนข้อมูล และเก็บประวัติลง InfluxDB
   * **MS3 AI Engine (`8003`):** ทำงานร่วมกับ Celery Worker ทำนายโอกาสเสียล่วงหน้าโดยใช้โมเดล Chronos ML
   * **MS4 Alert (`8004`):** ควบคุมคิวแจ้งเตือนผ่าน RabbitMQ จัดส่ง Flex Message ไปยังผู้ใช้ผ่าน LINE API
   * **MS5 Maintenance (`8005`):** จัดการและติดตามสถานะใบสั่งซ่อมบำรุง (Work Orders) ลิงก์กับระบบ AI
   * **MS6 Machine (`8006`):** ทะเบียนควบคุมสเตตัสทางกายภาพของเครื่องจักรทุกตัวในโรงงาน
4. **Data & Message Broker Layer:**
   * **MQTT Broker (Mosquitto):** ตัวรับสัญญาณเทเลเมทรีจากเซ็นเซอร์เครื่องจักร
   * **InfluxDB 2.7:** เก็บข้อมูลซีรีส์เวลาของเซ็นเซอร์เพื่อวิเคราะห์ย้อนหลัง
   * **PostgreSQL:** จัดเก็บข้อมูลผู้ใช้ (Auth) และข้อมูลการซ่อมบำรุง (Maintenance) แยกฐานข้อมูลอิสระ
   * **Redis Cache & Stream:** เก็บผลลัพธ์การทำนาย ML และควบคุมคิวคำสั่ง Celery
   * **RabbitMQ:** จัดลำดับความสำคัญของระบบแจ้งเตือนเพื่อรับประกันการส่งข้อความ
5. **Observability Layer (ระบบตรวจสอบการทำงาน):**
   * **Prometheus (Port 9090):** เก็บสะสมตัวชี้วัดประสิทธิภาพ (Metrics) จาก Kong Gateway และแต่ละบริการ
   * **Grafana (Port 3001):** วาดกราฟวิเคราะห์แนวโน้มสุขภาพเซิร์ฟเวอร์แบบเรียลไทม์

---

## ✨ 2. ฟีเจอร์เด่นที่เพิ่มเข้ามาล่าสุด (New Enhancements)

* **Strict Gateway Routing:** Frontend วิ่งเข้าหาพอร์ต `8000` (Kong Gateway) เท่านั้น ห้ามคุยกับบริการหลังบ้านตรง ๆ เพื่อความปลอดภัยสูงสุดตามหลักสถาปัตยกรรมระดับ Production
* **SVG Interactive Topology Map:** หน้าตรวจสอบระบบมีแผนผังแบบ Grid แบ่งเลเยอร์สวยงาม พร้อมแอนิเมชันเส้นเชื่อมข้อมูลไหลกะพริบตามอัตราการทำงานจริง (Green = ปกติ, Orange = ชะลอตัว, Red = ออฟไลน์) คลิกที่ Node ใดก็ได้เพื่อดึงข้อมูล RAM/CPU/Latency มาแสดงฝั่งขวา
* **Rich Anomaly LINE Alerts (Flex Card):** ข้อความไลน์ไม่ใช่แค่แจ้งเตือนเปล่า ๆ อีกต่อไป แต่จะวิเคราะห์เซ็นเซอร์ที่เสีย (เช่น อุณหภูมิสูง, แรงสั่นมากผิดปกติ), แสดงค่าสถิติจริง, และให้คำแนะนำการซ่อมบำรุงเชิงเทคนิคเบื้องต้นทันที (เช่น ให้ไปเปลี่ยนฟิลเตอร์, เช็คน้ำมันหล่อลื่น, ขันน็อตฐานยึด) พร้อมปุ่มกดลิงก์กลับมาตรวจสอบระบบ
* **Standardized Logging (console / JSON):** ทุกตัวแอปพลิเคชันจะพิมพ์ Log แบบมีโครงสร้างระบุเวลาและเลเวลชัดเจน และเมื่อตั้งค่า `LOG_FORMAT=JSON` จะเปลี่ยนไปพิมพ์ JSON Log ทั้งหมดเพื่อส่งต่อให้ซอฟต์แวร์วิเคราะห์ข้อมูล (Loki, Fluentd) ประมวลผลต่อได้ทันที

---

## 🛠️ 3. สิ่งที่ต้องมีในเครื่องคอมพิวเตอร์ (Prerequisites)

1. **Docker Desktop** (ต้องรันโปรแกรมทิ้งไว้ก่อนเริ่มคำสั่ง)
2. **Node.js 18 ขึ้นไป** (สำหรับทดลองรันหน้าเว็บในเครื่องพัฒนา)
3. **LINE OA Developer Account** (เลือกทำหรือไม่ทำก็ได้ หากต้องการเห็นข้อความเด้งเข้าแอปพลิเคชันจริง)

---

## 🚀 4. ขั้นตอนการติดตั้งและรันระบบ (Step-by-step Setup)

### ขั้นตอนที่ 1: ตั้งค่าตัวแปรสภาพแวดล้อม (Environment Variables)
เปิด Terminal ในโฟลเดอร์โปรเจกต์ `OmniVigil` และคัดลอกไฟล์เทมเพลตสภาพแวดล้อม:

```powershell
# บน Windows PowerShell
Copy-Item .env.example .env
```

*(ทางเลือก)* หากต้องการให้ระบบแจ้งเตือน LINE เด้งเข้าโทรศัพท์จริง ๆ:
1. สมัครสร้างแชนเนลบอทที่ [LINE Developers Console](https://developers.line.biz/)
2. เปิดไฟล์ `.env` ที่สร้างขึ้นมา และใส่รหัสแชนเนลในส่วนท้ายไฟล์:
   ```env
   LINE_CHANNEL_SECRET=ระบุรหัส_Secret_ที่นี่
   LINE_CHANNEL_ACCESS_TOKEN=ระบุรหัส_Token_ที่นี่
   # LINE_TARGET_USER_ID=ระบุไอดีของคุณ (หรือ Group ID) ที่ต้องการให้ยิงข้อความหา
   ```

### ขั้นตอนที่ 2: รันบริการทั้งหมดผ่าน Docker Compose
เริ่มระบบพร้อมโปรไฟล์เครื่องจำลองเซ็นเซอร์ (Simulator Profile) เพื่อป้อนข้อมูลเสมือนเข้าสู่ระบบอัตโนมัติ:

```powershell
# รันโปรเจกต์แบบรีบิลด์และรันเบื้องหลัง (Background/Daemon)
docker compose --profile simulator up -d --build
```

ตรวจสอบว่าบริการทั้ง 18 ตัวขึ้นทำงานและขึ้นสถานะทำงานปกติ:

```powershell
docker compose ps
```
*(ทุกตัวต้องขึ้นสถานะ **healthy** หรือ **running**)*

### ขั้นตอนที่ 3: เปิดใช้งาน Frontend (หน้าบ้าน)
เปิดโฟลเดอร์หน้าบ้าน ติดตั้งแพ็คเกจ และเริ่มเซิร์ฟเวอร์พัฒนา:

```powershell
cd frontend
npm install
npm run dev
```

เมื่อติดตั้งเสร็จ หน้าเว็บหน้าบ้านจะพร้อมใช้งานที่: **[http://localhost:3000](http://localhost:3000)**

---

## 🔗 5. ลิงก์แดชบอร์ดหลักและพอร์ตที่ใช้งาน (Endpoints & Dashboards)

| บริการ / หน้าเพจ | ลิงก์ภายนอกที่เปิดใช้งาน | รายละเอียด |
| :--- | :--- | :--- |
| **Frontend Web App** | [http://localhost:3000](http://localhost:3000) | หน้าต่างใช้งานหลักของพนักงานโรงงาน |
| **System Topology Page** | [http://localhost:3000/dashboard/system](http://localhost:3000/dashboard/system) | แผนผังระบบเรียลไทม์ + ปุ่มตรวจสอบ RAM/CPU |
| **Kong API Gateway** | [http://localhost:8000](http://localhost:8000) | ทางผ่านเราเตอร์หลักสำหรับ API หน้าบ้าน |
| **Prometheus Monitor** | [http://localhost:9090](http://localhost:9090) | หน้าตรวจสอบสุขภาพ Scrape targets และ Metrics |
| **Grafana Analytics** | [http://localhost:3001](http://localhost:3001) | ตัวช่วยวาดกราฟสุขภาพระบบ (ID: `admin` / PW: `admin`) |
| **InfluxDB Admin UI** | [http://localhost:8086](http://localhost:8086) | ตารางเช็กพูลข้อมูลเซ็นเซอร์ย้อนหลังในเทเลเมทรี |

*ตัวอย่างการเรียกดู API Docs (Swagger) ของ Microservices ผ่าน Kong Gateway:*
* **Auth Service Docs:** `http://localhost:8000/auth-service/docs`
* **AI Engine Docs:** `http://localhost:8000/ai-service/docs`
* **Alert Docs:** `http://localhost:8000/alert-service/docs`

---

## 🧪 6. วิธีการยืนยันและการทดสอบระบบ (Verification)

อาจารย์หรือนักพัฒนาสามารถทดสอบกลไกตรวจจับและแจ้งเตือนความเสียหายล่วงหน้าได้ด้วยตนเองดังนี้:

### ทดสอบที่ 1: บังคับให้เกิดภาวะผิดปกติในเครื่องจักร (Force Anomaly)
จำลองสถานการณ์ที่มีความร้อนหรือการสั่นสะเทือนทะลุพิกัดความปลอดภัย โดยส่งคำสั่งเข้าไฟล์สั่งการของเซ็นเซอร์จำลอง:

```powershell
docker compose exec sim-sensor sh -c "echo all > /tmp/force_anomaly"
```

### สิ่งที่จะเกิดขึ้นในระบบทันที (หลังพิมพ์คำสั่ง):
1. **MS2 Ingestor** จะรับค่าที่สูงเกินเกณฑ์ ส่งต่อประวัติข้อมูลเข้า InfluxDB
2. **MS3 AI Engine** จะเริ่มคำนวณประเมินความเสี่ยงล่วงหน้า ผลลัพธ์แสดงระดับความเสี่ยงเป็นระดับ `critical`
3. ระบบจะสั่งลบสุขภาพ (Health Score) ของเครื่องจักรที่ได้รับผลกระทบลงใน **MS6 Machine Registry**
4. **MS5 Maintenance** จะรับคำร้องขอ และสั่งสร้างใบสั่งซ่อมบำรุง (Work Order) โดยอัตโนมัติ
5. **MS4 Alert** จะได้รับแจ้งเตือน นำข้อมูลไปสร้างเป็น Flex Card ข้อความพร้อมปุ่มลิงก์ และยิงส่งแจ้งเตือนเข้าสู่แอปพลิเคชัน LINE ที่เชื่อมต่อไว้
6. หน้าบ้าน **[http://localhost:3000/dashboard/system](http://localhost:3000/dashboard/system)** จะแสดงจุดเชื่อมต่อของบริการที่มีปัญหาเป็นเส้นสีส้ม/แดง ทันทีในเสี้ยววินาที

---

## 🛠️ 7. คำสั่งการดูแลรักษาระบบ (Troubleshooting Commands)

* **ดูประวัติ Log ของตัวเซ็นเซอร์ตัวเดียว:**
  ```powershell
  docker compose logs -f ms3-ai-engine
  ```
* **รีเซ็ตระบบและล้างฐานข้อมูลใหม่ทั้งหมด (ใช้เมื่อระบบเพี้ยน):**
  ```powershell
  docker compose down -v
  docker compose --profile simulator up -d --build
  ```
