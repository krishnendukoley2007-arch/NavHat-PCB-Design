# 📡 NavHat PRO — REST API & Network Interface Reference

Complete API specification for the ESP32 Sensor Node, ESP32-CAM Video Node, and Host Vision System telemetry.

---

## 1. ESP32 Sensor Node API (`http://navhat-sensor.local`)

### `GET /distances`
Returns filtered ultrasonic distance readings across all 3 sensors in centimeters.

* **Response Code**: `200 OK`
* **Content-Type**: `application/json`
* **CORS**: `Access-Control-Allow-Origin: *`

```json
{
  "front": 45.2,
  "left": 110.0,
  "right": 85.4
}
```

---

### `GET /status`
Health check endpoint returning device readiness.

* **Response Code**: `200 OK`
* **Content-Type**: `text/plain`
* **Response Body**: `NAVHAT_SENSOR_OK`

---

## 2. ESP32-CAM Video Node API (`http://navhat-cam.local`)

### `GET /`
Serves the embedded Cyberpunk Web HUD HTML5 client.

* **Response Code**: `200 OK`
* **Content-Type**: `text/html`

---

### `GET /stream`
Multipart MJPEG video stream.

* **Response Code**: `200 OK`
* **Content-Type**: `multipart/x-mixed-replace;boundary=gc0p4Jq0M2Yt08jU534c0p`

---

### `GET /debug`
Real-time hardware performance metrics from FreeRTOS runtime.

* **Response Code**: `200 OK`
* **Content-Type**: `application/json`

```json
{
  "fps": 28,
  "drops": 0,
  "heap": 184320,
  "rssi": -52,
  "uptime": 145200,
  "res": "QQVGA"
}
```

---

### `GET /res?v=qqvga|qvga`
Dynamically switches sensor resolution on the fly.

* **Query Parameters**:
  - `v`: `qqvga` ($160\times 120$) or `qvga` ($320\times 240$)
* **Response Code**: `200 OK`
* **Response Body**: `OK`
