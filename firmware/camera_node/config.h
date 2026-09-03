#pragma once
// ============================================================
//   NavHat PRO — Camera Node Hardware Configuration
// ============================================================

// ── WiFi Settings ────────────────────────────────────────────
#define WIFI_SSID_DEFAULT     "iQOO Z6 kk"
#define WIFI_PASS_DEFAULT     "bdfe1aa430eb"
#define MDNS_HOSTNAME         "navhat-cam"
#define HTTP_PORT             80

// ── Camera Clock & Frame Configuration ───────────────────────
#define CAM_XCLK_FREQ_HZ      16000000  // 16MHz for stable OV7670 clock
#define CAM_PIXEL_FORMAT      PIXFORMAT_GRAYSCALE
#define CAM_DEFAULT_FRAMESIZE FRAMESIZE_QQVGA // 160x120 for low-latency WiFi
#define CAM_JPEG_QUALITY      80        // Higher number = faster transmission
#define CAM_FRAME_BUFFERS     3         // Triple frame buffering for Core 1

// ── Server Task Core Affinity ────────────────────────────────
#define HTTP_SERVER_CORE_ID   1         // Pin web streaming server to CPU Core 1
#define HTTP_SERVER_STACK_SZ  8192      // Stack size in bytes

// ── AI Thinker ESP32-CAM Pin Mapping ─────────────────────────
#define CAM_PIN_PWDN          32
#define CAM_PIN_RESET         -1
#define CAM_PIN_XCLK          0
#define CAM_PIN_SIOD          26
#define CAM_PIN_SIOC          27
#define CAM_PIN_D7            35
#define CAM_PIN_D6            34
#define CAM_PIN_D5            39
#define CAM_PIN_D4            36
#define CAM_PIN_D3            21
#define CAM_PIN_D2            19
#define CAM_PIN_D1            18
#define CAM_PIN_D0            5
#define CAM_PIN_VSYNC         25
#define CAM_PIN_HREF          23
#define CAM_PIN_PCLK          22
