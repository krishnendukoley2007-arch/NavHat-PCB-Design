#pragma once
// ============================================================
//   NavHat PRO — Sensor Node Hardware Configuration
// ============================================================

// ── WiFi Settings ────────────────────────────────────────────
#define WIFI_SSID_DEFAULT     "iQOO Z6 kk"
#define WIFI_PASS_DEFAULT     "bdfe1aa430eb"
#define MDNS_HOSTNAME         "navhat-sensor"
#define HTTP_PORT             80

// ── Ultrasonic Sensor GPIO Assignments ───────────────────────
// Front Sensor (Center Arc: -15° to +15°)
#define PIN_TRIG_FRONT        13
#define PIN_ECHO_FRONT        18

// Left Sensor (Lateral Arc: -65° to -15°)
#define PIN_TRIG_LEFT         14
#define PIN_ECHO_LEFT         33

// Right Sensor (Lateral Arc: +15° to +65°)
#define PIN_TRIG_RIGHT        19
#define PIN_ECHO_RIGHT        23

// ── Piezo Buzzer GPIO Assignments (LEDC PWM) ─────────────────
#define PIN_BUZZER_LEFT       25
#define PIN_BUZZER_RIGHT      4

// ── Proximity Thresholds (Centimeters) ───────────────────────
#define THRESHOLD_CRITICAL_CM 30.0f   // Continuous emergency alarm
#define THRESHOLD_CLOSE_CM    70.0f   // Dynamic proportional beep range
#define THRESHOLD_MAX_CM      400.0f  // Max valid ultrasonic range

// ── Audio Frequency Profiles (Hertz) ─────────────────────────
#define FREQ_CRITICAL_HZ      2500    // High piercing alarm tone
#define FREQ_PROXIMITY_HZ     1800    // Proximity alert tone
#define FREQ_STARTUP_HZ       1500    // Boot chime tone

// ── Timing Parameters ────────────────────────────────────────
#define SENSOR_SAMPLE_INTERVAL_MS  80   // Main loop poll rate
#define PULSE_TIMEOUT_US           25000 // pulseIn timeout (~4.3 meters)
#define MEDIAN_BLANKING_DELAY_US   500  // Delay between 3 median samples
