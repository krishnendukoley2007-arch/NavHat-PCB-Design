// ============================================================
//   NavHat PRO — Sensor Node Firmware
//   Board  : ESP32 Dev Module / ESP32-WROOM-32
//   Purpose: 3x HC-SR04 Ultrasonic + 2x Passive Buzzer + HTTP Server
//
//   mDNS hostname : navhat-sensor.local
//   Endpoint      : GET /distances  → JSON {front, left, right}
//   Endpoint      : GET /status     → "NAVHAT_SENSOR_OK"
//
//   BUZZER LOGIC:
//   < 30cm  → continuous tone (CRITICAL)  — BOTH buzzers
//   < 70cm  → fast beep                   — BOTH buzzers
//   >= 70cm → silent (no beep)
//   NOTE: Both buzzers always fire together (one unit damaged)
// ============================================================

#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>

// ── WiFi Configuration ───────────────────────────────────────
const char* ssid     = "iQOO Z6 kk";
const char* password = "bdfe1aa430eb";

// ── Ultrasonic Sensor Pins ───────────────────────────────────
#define TRIG_F  13
#define ECHO_F  18
#define TRIG_L  14
#define ECHO_L  33
#define TRIG_R  19
#define ECHO_R  23

// ── Buzzer Pins (PWM driven) ─────────────────────────────────
#define BUZZ_L  25
#define BUZZ_R  4

// ── Distance Thresholds (cm) ─────────────────────────────────
#define DIST_CRITICAL  30    // Continuous alarm threshold
#define DIST_CLOSE     70    // Proximity beep range (30-70cm)

// ── Buzzer Frequencies (Hz) ──────────────────────────────────
#define FREQ_CRITICAL  2500
#define FREQ_CLOSE     1800

WebServer server(80);

volatile float distF = 999.0;
volatile float distL = 999.0;
volatile float distR = 999.0;

// ─────────────────────────────────────────────────────────────
//  SINGLE ULTRASONIC READ — non-blocking with 25ms timeout (~4.3m max)
// ─────────────────────────────────────────────────────────────
float readDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 25000);
  if (duration == 0) return 999.0;
  return duration * 0.034f / 2.0f;
}

// ─────────────────────────────────────────────────────────────
//  MEDIAN FILTER — takes 3 readings, returns the middle value
//  Eliminates single-shot ghost echoes from HC-SR04
// ─────────────────────────────────────────────────────────────
float readDistanceFiltered(int trigPin, int echoPin) {
  float a = readDistance(trigPin, echoPin);
  delayMicroseconds(500);
  float b = readDistance(trigPin, echoPin);
  delayMicroseconds(500);
  float c = readDistance(trigPin, echoPin);

  // Return median of 3
  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

// ─────────────────────────────────────────────────────────────
//  BUZZER LOGIC — fully non-blocking, runs every loop()
//  Both buzzers always fire together (one unit may be damaged)
// ─────────────────────────────────────────────────────────────
void updateBuzzers() {
  static unsigned long lastToggle = 0;
  static bool          beepOn     = false;
  unsigned long now = millis();

  // ── CRITICAL: < 30cm — both buzzers, any direction ───────
  if (distF < DIST_CRITICAL || distL < DIST_CRITICAL || distR < DIST_CRITICAL) {
    ledcWriteTone(BUZZ_L, FREQ_CRITICAL);
    ledcWriteTone(BUZZ_R, FREQ_CRITICAL);
    beepOn = true;
    return;
  }

  // ── CLOSE: 30cm–70cm → fast beep, both buzzers ───────────
  float closest = min(distF, min(distL, distR));

  if (closest < DIST_CLOSE) {
    // Interval: 100ms (very close to 30) → 600ms (approaching 70)
    int interval = (int)map((long)constrain((int)closest, DIST_CRITICAL, DIST_CLOSE),
                            DIST_CRITICAL, DIST_CLOSE, 100, 600);

    if (now - lastToggle > (unsigned long)interval) {
      lastToggle = now;
      beepOn     = !beepOn;

      if (beepOn) {
        // Both buzzers always — one may be damaged
        ledcWriteTone(BUZZ_L, FREQ_CLOSE);
        ledcWriteTone(BUZZ_R, FREQ_CLOSE);
      } else {
        ledcWriteTone(BUZZ_L, 0);
        ledcWriteTone(BUZZ_R, 0);
      }
    }
    return;
  }

  // ── ALL CLEAR: >= 70cm → completely silent ────────────────
  ledcWriteTone(BUZZ_L, 0);
  ledcWriteTone(BUZZ_R, 0);
  beepOn = false;
}

// ─────────────────────────────────────────────────────────────
//  HTTP HANDLERS
// ─────────────────────────────────────────────────────────────
void handleDistances() {
  String json = "{";
  json += "\"front\":" + String(distF, 1) + ",";
  json += "\"left\":"  + String(distL, 1) + ",";
  json += "\"right\":" + String(distR, 1);
  json += "}";
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleStatus() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "NAVHAT_SENSOR_OK");
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
}

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nNavHat Sensor Node — Starting...");

  // ── Pin setup ──────────────────────────────────────────────
  pinMode(TRIG_F, OUTPUT); pinMode(ECHO_F, INPUT);
  pinMode(TRIG_L, OUTPUT); pinMode(ECHO_L, INPUT);
  pinMode(TRIG_R, OUTPUT); pinMode(ECHO_R, INPUT);

  // ── Buzzers (LEDC Setup for ESP32 Core 3.x / 2.x) ──────────
  ledcAttach(BUZZ_L, 2000, 8);
  ledcAttach(BUZZ_R, 2000, 8);
  ledcWriteTone(BUZZ_L, 0);
  ledcWriteTone(BUZZ_R, 0);

  // ── WiFi ───────────────────────────────────────────────────
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  WiFi.begin(ssid, password);
  Serial.print("WiFi connecting");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts++ < 40) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi FAILED — restarting");
    ESP.restart();
  }
  WiFi.setSleep(false);
  Serial.printf("\nConnected — IP: %s\n", WiFi.localIP().toString().c_str());

  // ── mDNS ───────────────────────────────────────────────────
  if (MDNS.begin("navhat-sensor")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("mDNS ready: navhat-sensor.local");
  } else {
    Serial.println("mDNS FAILED — IP fallback only");
  }

  // ── HTTP server ────────────────────────────────────────────
  server.on("/distances", HTTP_GET, handleDistances);
  server.on("/status",    HTTP_GET, handleStatus);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("HTTP server ready on port 80");
  Serial.println("Endpoint: http://navhat-sensor.local/distances");

  // ── Startup beep — two short beeps = ready ─────────────────
  ledcWriteTone(BUZZ_L, 1500); ledcWriteTone(BUZZ_R, 1500);
  delay(100);
  ledcWriteTone(BUZZ_L, 0);   ledcWriteTone(BUZZ_R, 0);
  delay(150);
  ledcWriteTone(BUZZ_L, 1500); ledcWriteTone(BUZZ_R, 1500);
  delay(100);
  ledcWriteTone(BUZZ_L, 0);   ledcWriteTone(BUZZ_R, 0);
}

// ─────────────────────────────────────────────────────────────
//  LOOP — sensor read + buzzer + HTTP server
// ─────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  static unsigned long lastRead = 0;
  unsigned long now = millis();

  if (now - lastRead >= 80) {
    lastRead = now;
    distF = readDistanceFiltered(TRIG_F, ECHO_F);
    distL = readDistanceFiltered(TRIG_L, ECHO_L);
    distR = readDistanceFiltered(TRIG_R, ECHO_R);

    Serial.printf("F:%.0fcm  L:%.0fcm  R:%.0fcm\n", distF, distL, distR);
  }

  updateBuzzers();

  // WiFi watchdog
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost — reconnecting...");
    WiFi.reconnect();
    delay(3000);
  }
}
