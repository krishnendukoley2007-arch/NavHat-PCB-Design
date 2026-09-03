# 📋 NavHat PRO — Bill of Materials (BOM)

Comprehensive component listing for fabricating the NavHat PRO sensor node PCB, camera rig, and power supply.

---

## 🔩 Electronics & Active Components

| Item | Component | Designator | Footprint / Package | Description / Specs | Recommended Part / Source | Est. Qty | Unit Price (USD) |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| 1 | **ESP32 Dev Module** | U1 | DIP-30 (ESP-WROOM-32) | Dual-core 240MHz, 4MB Flash, WiFi+BT | ESP32-WROOM-32D | 1 | $3.50 |
| 2 | **ESP32-CAM Board** | CAM1 | AI-Thinker Module | Dual-core ESP32 + OV7670 / OV2640 DVP | AI-Thinker ESP32-CAM | 1 | $4.80 |
| 3 | **Ultrasonic Sensor** | US_F, US_L, US_R | 4-Pin Header (2.54mm) | $40\text{kHz}$ Sonar, $2\text{cm}-400\text{cm}$ Range | HC-SR04 / RCWL-1601 | 3 | $0.90 |
| 4 | **Piezo Buzzer** | BUZZ_L, BUZZ_R | 2-Pin Through-Hole | Passive Piezo Transducer ($2-4\text{kHz}$) | TDK PS1240 / Generic | 2 | $0.40 |
| 5 | **Linear Regulator** | VR1 | SOT-223 | $3.3\text{V}$ LDO, $800\text{mA}-1\text{A}$ Output | STMicroelectronics LD1117S33TR | 1 | $0.35 |
| 6 | **Resistor (Divider)**| R1, R2, R3 | 0805 SMD / 0.25W Axial | $1\text{ k}\Omega \pm 1\%$ Metal Film | Yageo RC0805FR-071KL | 3 | $0.02 |
| 7 | **Resistor (Divider)**| R4, R5, R6 | 0805 SMD / 0.25W Axial | $2\text{ k}\Omega \pm 1\%$ Metal Film | Yageo RC0805FR-072KL | 3 | $0.02 |
| 8 | **Capacitor (Filter)**| C1, C2 | 0805 SMD / Radial | $10\mu\text{F}$ 16V Ceramic / Tantalum | Murata GRM21BR61C106KE15L | 2 | $0.08 |
| 9 | **Power Jack / Header**| JP1 | 2-Pin Terminal / 2.54mm | $5\text{V}$ DC Power In | JST-XH 2.54mm 2-Pin | 1 | $0.15 |

---

## 🔋 Power Management & Wearable Rig

| Item | Component | Description / Function | Recommended Model | Est. Qty | Unit Price (USD) |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 10 | **LiPo Charging Module** | TP4056 with Battery Protection (Over-discharge/Overcurrent) | Micro-USB / Type-C TP4056 | 1 | $0.60 |
| 11 | **5V Step-Up Converter** | DC-DC Boost Converter ($3.7\text{V} \rightarrow 5.0\text{V} \ge 2\text{A}$) | MT3608 or XL6009 Boost Module | 1 | $0.80 |
| 12 | **Rechargeable Battery** | 3.7V 18650 Li-ion Cell ($2600\text{mAh}$) or Flat 1200mAh LiPo | Samsung 26J 18650 / 103450 LiPo | 1 | $3.50 |
| 13 | **SPST Power Switch** | Slide / Rocker Switch for Main Power On/Off | SS12D00 Slide Switch | 1 | $0.20 |
| 14 | **Wiring & Connectors** | 24 AWG Silicone Jumper Wires & JST-XH Connectors | Premium Stranded Copper | 1 set | $1.50 |
| 15 | **Headwear Mount** | Lightweight Cap, Headband, or Chest Rig | Standard Cotton Baseball Cap | 1 | $4.00 |

<br/>

**Total Estimated Hardware Cost**: **~$21.00 USD**
