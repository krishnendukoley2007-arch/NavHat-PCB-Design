# ⚡ NavHat PRO Firmware Architecture

This directory contains the embedded C++ firmware for the two microcontroller nodes comprising the NavHat PRO wearable hardware.

---

## 📂 Subdirectories

- **[`sensor_node/`](sensor_node/)**: ESP32 Dev Module firmware managing 3× HC-SR04 ultrasonic rangefinders, dual PWM piezo buzzers, non-blocking frequency modulation, and a local REST server (`/distances`, `/status`).
- **[`camera_node/`](camera_node/)**: AI-Thinker ESP32-CAM (OV7670) v18 firmware with software JPEG encoding on FreeRTOS Core 1, MJPEG streaming (`/stream`), real-time JSON metrics (`/debug`), and an embedded Cyberpunk Web HUD (`/`).
- **[`calibration/`](calibration/)**: Standalone calibration sketch for Arduino Serial Plotter noise profiling and distance verification.

---

## 🏗️ FreeRTOS & Core Execution Strategy

```text
┌────────────────────────────────────────────────────────────┐
│                    ESP32 Dual-Core CPU                     │
├─────────────────────────────┬──────────────────────────────┤
│          CORE 0             │            CORE 1            │
│  (System & Background)      │   (Real-Time Engine & Video) │
├─────────────────────────────┼──────────────────────────────┤
│  • WiFi Stack / LwIP        │  • Camera DMA Capture (DVP)  │
│  • mDNS Responder           │  • fmt2jpg Grayscale->JPEG   │
│  • WiFi Watchdog            │  • High-Speed HTTP Streaming │
│  • Brownout Protection      │  • Triple Framebuffer Queue  │
└─────────────────────────────┴──────────────────────────────┘
```

---

## 🛠 Flashing Instructions

### Prerequisites
1. Install [Arduino IDE v2.x](https://www.arduino.cc/en/software).
2. Install the **ESP32 Board Package** (`v3.0.0+` or `v2.0.14` by Espressif):
   - Add `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json` to Additional Board Manager URLs.

### Board Settings

| Parameter | Sensor Node | Camera Node |
| :--- | :--- | :--- |
| **Board** | `ESP32 Dev Module` | `AI Thinker ESP32-CAM` |
| **CPU Frequency** | `240 MHz` | `240 MHz (WiFi/BT)` |
| **Flash Frequency**| `80 MHz` | `80 MHz` |
| **Flash Mode** | `QIO` | `QIO` |
| **Partition Scheme** | `Default 4MB with SPIFFS` | `Huge APP (3MB No OTA / 1MB SPIFFS)` |
| **Upload Speed** | `921600` | `115200` |

> [!IMPORTANT]
> When programming the **ESP32-CAM**, short **GPIO 0 to GND** before pressing RESET to enter bootloader mode. Disconnect GPIO 0 from GND after flashing and press RESET to boot into normal operation.
