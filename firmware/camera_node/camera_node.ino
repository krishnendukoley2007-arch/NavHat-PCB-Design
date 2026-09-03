// ============================================================
//   ESP32-CAM NavHat PRO — v18
//   Board  : AI Thinker ESP32-CAM
//   Sensor : OV7670 (NO hardware JPEG — grayscale only)
//
//   v18 fixes vs v17:
//   1. Back to PIXFORMAT_GRAYSCALE (OV7670 has no HW JPEG)
//   2. QQVGA (160x120) default — 4x fewer pixels = 4x faster
//      fmt2jpg + 4x smaller frame over WiFi = max FPS
//   3. fmt2jpg quality = 80 (smaller/faster than 63)
//   4. Resolution toggle in UI: QQVGA / QVGA
//   5. Keep: Core1, fb=3, soft retry, 16MHz, portYIELD
// ============================================================

#include "esp_camera.h"
#include <ESPmDNS.h>
#include <WiFi.h>
#include "img_converters.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "esp_http_server.h"
#include "freertos/task.h"

// ── WiFi Credentials ─────────────────────────────────────────
const char* ssid     = "iQOO Z6 kk";
const char* password = "bdfe1aa430eb";

// ── AI Thinker ESP32-CAM Pin Definitions ─────────────────────
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22

#define PART_BOUNDARY "gc0p4Jq0M2Yt08jU534c0p"

static const char* _STREAM_CONTENT_TYPE =
  "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY =
  "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART =
  "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd  = NULL;
volatile int   g_fps         = 0;
volatile int   g_frame_drops = 0;
int            fps_counter   = 0;
unsigned long  fps_timer     = 0;

// Current resolution — toggled via /res endpoint
volatile framesize_t g_framesize = FRAMESIZE_QQVGA; // 160x120 default

// ─────────────────────────────────────────────────────────────
//  STREAM HANDLER
// ─────────────────────────────────────────────────────────────
static esp_err_t stream_handler(httpd_req_t* req) {
  camera_fb_t* fb      = NULL;
  esp_err_t    res     = ESP_OK;
  uint8_t*     jpg_buf = NULL;
  size_t       jpg_len = 0;
  char         hdr[64];

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store, no-cache, must-revalidate");
  httpd_resp_set_hdr(req, "Pragma", "no-cache");
  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  int fail_count      = 0;
  int backoff_ms      = 5;
  const int MAX_BACK  = 500;

  while (true) {
    fb = esp_camera_fb_get();

    if (!fb) {
      fail_count++;
      g_frame_drops++;
      vTaskDelay(pdMS_TO_TICKS(backoff_ms));
      backoff_ms = min(backoff_ms * 2, MAX_BACK);
      if (fail_count > 500) {
        Serial.println("Camera dead — restarting");
        ESP.restart();
      }
      continue;
    }

    fail_count = 0;
    backoff_ms = 5;

    // Convert GRAYSCALE → JPEG
    // quality=80 → smaller file than q=63 (higher number = lower quality = faster transmission)
    bool ok = fmt2jpg(fb->buf, fb->len,
                      fb->width, fb->height,
                      PIXFORMAT_GRAYSCALE,
                      80, &jpg_buf, &jpg_len);
    esp_camera_fb_return(fb);
    fb = NULL;

    if (!ok || !jpg_buf || jpg_len == 0) {
      g_frame_drops++;
      portYIELD();
      continue;
    }

    size_t hlen = snprintf(hdr, sizeof(hdr), _STREAM_PART, jpg_len);
    res  = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    if (res == ESP_OK)
      res = httpd_resp_send_chunk(req, hdr, hlen);
    if (res == ESP_OK)
      res = httpd_resp_send_chunk(req, (const char*)jpg_buf, jpg_len);

    free(jpg_buf);
    jpg_buf = NULL;

    if (res != ESP_OK) {
      Serial.println("Client disconnected.");
      break;
    }

    portYIELD();

    fps_counter++;
    unsigned long now = millis();
    if (now - fps_timer >= 1000) {
      g_fps       = fps_counter;
      fps_counter = 0;
      fps_timer   = now;
      Serial.printf("FPS:%d | Drops:%d | Heap:%dKB | RSSI:%ddBm\n",
        g_fps, g_frame_drops,
        ESP.getFreeHeap() / 1024, WiFi.RSSI());
    }
  }
  return res;
}

// ─────────────────────────────────────────────────────────────
//  RESOLUTION TOGGLE  /res?v=qqvga|qvga
// ─────────────────────────────────────────────────────────────
static esp_err_t res_handler(httpd_req_t* req) {
  char query[32] = {0};
  httpd_req_get_url_query_str(req, query, sizeof(query));

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    if (strstr(query, "v=qvga")) {
      s->set_framesize(s, FRAMESIZE_QVGA);
      g_framesize = FRAMESIZE_QVGA;
      Serial.println("Resolution → QVGA 320x240");
    } else {
      s->set_framesize(s, FRAMESIZE_QQVGA);
      g_framesize = FRAMESIZE_QQVGA;
      Serial.println("Resolution → QQVGA 160x120");
    }
  }
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, "OK", 2);
}

// ─────────────────────────────────────────────────────────────
//  DEBUG JSON  /debug
// ─────────────────────────────────────────────────────────────
static esp_err_t debug_handler(httpd_req_t* req) {
  char buf[300];
  snprintf(buf, sizeof(buf),
    "{\"fps\":%d,\"drops\":%d,\"heap\":%d,\"rssi\":%d,\"uptime\":%lu,\"res\":\"%s\"}",
    g_fps, g_frame_drops, ESP.getFreeHeap(), WiFi.RSSI(), millis(),
    g_framesize == FRAMESIZE_QVGA ? "QVGA" : "QQVGA");
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, buf, strlen(buf));
}

// ─────────────────────────────────────────────────────────────
//  WEB UI
// ─────────────────────────────────────────────────────────────
static esp_err_t index_handler(httpd_req_t* req) {
  const char* html = R"rawhtml(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NavHat PRO v18</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Bebas+Neue&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --ink:#e8e4dc;--ink2:#8a8880;--ink3:#4a4845;
  --bg:#0b0b0b;--surface:#131313;--panel:#161616;--line:#222;
  --accent:#d4ff5a;--accent2:#ff6b35;--danger:#ff3b3b;
  --ok:#4dff91;--warn:#ffb800;
  --font:'IBM Plex Mono',monospace;--panel-w:300px;--hdr-h:48px;
}
html,body{height:100%;width:100%;overflow:hidden;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:12px}
#topbar{
  position:fixed;top:0;left:0;right:0;height:var(--hdr-h);
  background:var(--surface);border-bottom:1px solid var(--line);
  display:flex;align-items:center;padding:0 16px;gap:12px;z-index:100;
}
#logo{font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:4px;color:var(--ink);white-space:nowrap}
#logo em{color:var(--accent);font-style:normal}
.top-pill{padding:3px 10px;border:1px solid var(--line);border-radius:2px;font-size:10px;letter-spacing:1.5px;color:var(--ink2);white-space:nowrap}
.top-pill.live{color:var(--ok);border-color:var(--ok);animation:blink 1.4s ease infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
#top-fps{margin-left:auto;font-size:20px;font-family:'Bebas Neue',sans-serif;letter-spacing:2px;color:var(--accent);min-width:80px;text-align:right}
#toggle-panel{background:none;border:1px solid var(--line);color:var(--ink2);padding:6px 12px;border-radius:2px;cursor:pointer;font-family:var(--font);font-size:10px;letter-spacing:1px;transition:border-color .2s,color .2s}
#toggle-panel:hover{border-color:var(--accent);color:var(--accent)}
#layout{position:fixed;top:var(--hdr-h);left:0;right:0;bottom:0;display:flex}
#feed{flex:1;position:relative;background:#000;display:flex;align-items:center;justify-content:center;overflow:hidden;min-width:0}
#stream{
  width:80%;
  height:80%;
  object-fit:contain;
  image-rendering:pixelated;
  transition:filter .15s;
}
.corner{position:absolute;width:20px;height:20px;border-color:var(--accent);border-style:solid;opacity:.25;pointer-events:none}
.c-tl{top:10px;left:10px;border-width:2px 0 0 2px}
.c-tr{top:10px;right:10px;border-width:2px 2px 0 0}
.c-bl{bottom:10px;left:10px;border-width:0 0 2px 2px}
.c-br{bottom:10px;right:10px;border-width:0 2px 2px 0}
#crosshair{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;opacity:.15}
#crosshair::before,#crosshair::after{content:'';position:absolute;background:var(--accent)}
#crosshair::before{width:24px;height:1px;top:0;left:-12px}
#crosshair::after{width:1px;height:24px;left:0;top:-12px}
#feed-info{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);font-size:9px;letter-spacing:2px;color:var(--ink3);pointer-events:none;white-space:nowrap}
#res-label{position:absolute;top:10px;right:12px;font-size:9px;letter-spacing:1.5px;color:var(--ink3);pointer-events:none}
#reconnect-overlay{position:absolute;inset:0;background:#000a;display:none;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:var(--warn);font-size:11px;letter-spacing:3px}
#reconnect-overlay.show{display:flex}
.spinner{width:24px;height:24px;border:2px solid var(--line);border-top-color:var(--warn);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
#panel{width:var(--panel-w);background:var(--panel);border-left:1px solid var(--line);display:flex;flex-direction:column;overflow:hidden;transition:width .25s,opacity .25s;overflow-y:auto}
#panel.collapsed{width:0;opacity:0;pointer-events:none}
.pane-section{border-bottom:1px solid var(--line);padding:14px 16px}
.sec-title{font-size:9px;letter-spacing:2.5px;color:var(--ink3);text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.sec-title::before{content:'';width:3px;height:10px;background:var(--accent);border-radius:1px}
.trow{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #1a1a1a}
.trow:last-child{border-bottom:none}
.tlabel{font-size:10px;color:var(--ink2);letter-spacing:.5px}
.tval{font-size:12px;font-weight:500;color:var(--ink);letter-spacing:.5px}
.tval.ok{color:var(--ok)}.tval.warn{color:var(--warn)}.tval.err{color:var(--danger)}
.fps-bar-wrap{margin:8px 0 4px;height:3px;background:#1e1e1e;border-radius:2px;overflow:hidden}
.fps-bar{height:100%;border-radius:2px;transition:width .4s,background .4s;width:0}
.filter-row{margin-bottom:12px}
.filter-label{display:flex;justify-content:space-between;font-size:10px;color:var(--ink2);margin-bottom:5px;letter-spacing:.5px}
.filter-label span{color:var(--ink);font-weight:500}
input[type=range]{width:100%;height:3px;-webkit-appearance:none;appearance:none;background:#2a2a2a;border-radius:2px;outline:none;cursor:pointer}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--accent)}
input[type=range]::-moz-range-thumb{width:14px;height:14px;border-radius:50%;background:var(--accent);border:none;cursor:pointer}
.toggle-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tog{flex:1;min-width:60px;padding:6px 0;background:#1a1a1a;border:1px solid var(--line);color:var(--ink2);font-family:var(--font);font-size:9px;letter-spacing:1.5px;cursor:pointer;border-radius:2px;text-align:center;transition:all .15s}
.tog:hover{border-color:var(--ink3);color:var(--ink)}
.tog.active{background:var(--accent);border-color:var(--accent);color:#000;font-weight:600}
.action-row{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}
.btn{flex:1;padding:8px;background:none;border:1px solid var(--line);color:var(--ink2);font-family:var(--font);font-size:10px;letter-spacing:1px;cursor:pointer;border-radius:2px;transition:all .15s;white-space:nowrap}
.btn:hover{border-color:var(--ink);color:var(--ink)}
.btn.primary{border-color:var(--accent2);color:var(--accent2)}
.btn.primary:hover{background:var(--accent2);color:#000}
.btn.active{border-color:var(--accent);color:var(--accent)}
.preset-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px}
.preset-btn{padding:7px 4px;background:#111;border:1px solid var(--line);color:var(--ink2);font-family:var(--font);font-size:9px;letter-spacing:1px;cursor:pointer;border-radius:2px;text-align:center;transition:all .15s}
.preset-btn:hover{border-color:var(--accent);color:var(--accent)}
.preset-btn.active{border-color:var(--accent);color:#000;background:var(--accent)}
#log-wrap{flex:1;overflow:hidden;display:flex;flex-direction:column;min-height:120px}
#log{flex:1;overflow-y:auto;padding:10px 12px;font-size:10px;line-height:1.8;color:var(--ink3);white-space:pre-wrap;scrollbar-width:thin;scrollbar-color:var(--line) transparent}
#log::-webkit-scrollbar{width:4px}
#log::-webkit-scrollbar-thumb{background:var(--line);border-radius:2px}
@media(max-width:600px){
  :root{--panel-w:100%}
  #layout{flex-direction:column-reverse}
  #panel{width:100%!important;max-height:55vh;border-left:none;border-top:1px solid var(--line)}
  #panel.collapsed{height:0!important;max-height:0;opacity:0;pointer-events:none}
}
</style>
</head>
<body>
<div id="topbar">
  <div id="logo">NAV<em>HAT</em> PRO</div>
  <div class="top-pill live" id="live-pill">● LIVE</div>
  <div class="top-pill" id="res-pill">QQVGA</div>
  <div class="top-pill">GRAYSCALE</div>
  <div class="top-pill" id="rssi-pill">RSSI --</div>
  <div id="top-fps">-- FPS</div>
  <button id="toggle-panel" onclick="togglePanel()">[ PANEL ]</button>
</div>

<div id="layout">
  <div id="feed">
    <img id="stream" src="/stream" alt="camera feed">
    <div class="corner c-tl"></div>
    <div class="corner c-tr"></div>
    <div class="corner c-bl"></div>
    <div class="corner c-br"></div>
    <div id="crosshair"></div>
    <div id="res-label">160×120</div>
    <div id="feed-info">OV7670 · QQVGA · GRAYSCALE · q=80 · fb=3 · Core1</div>
    <div id="reconnect-overlay">
      <div class="spinner"></div>
      <span>RECONNECTING</span>
    </div>
  </div>

  <div id="panel">
    <div class="pane-section">
      <div class="sec-title">Telemetry</div>
      <div class="trow"><span class="tlabel">FPS</span><span class="tval ok" id="p-fps">--</span></div>
      <div class="fps-bar-wrap"><div class="fps-bar" id="fps-bar"></div></div>
      <div class="trow"><span class="tlabel">Frame Drops</span><span class="tval" id="p-drops">--</span></div>
      <div class="trow"><span class="tlabel">Free Heap</span><span class="tval" id="p-heap">--</span></div>
      <div class="trow"><span class="tlabel">RSSI</span><span class="tval" id="p-rssi">--</span></div>
      <div class="trow"><span class="tlabel">Poll Latency</span><span class="tval" id="p-lag">--</span></div>
      <div class="trow"><span class="tlabel">Uptime</span><span class="tval" id="p-up">--</span></div>
      <div class="trow"><span class="tlabel">Reconnects</span><span class="tval warn" id="p-rc">0</span></div>
    </div>

    <div class="pane-section">
      <div class="sec-title">Resolution</div>
      <div class="action-row">
        <button class="btn active" id="btn-qqvga" onclick="setRes('qqvga')">QQVGA 160×120</button>
        <button class="btn"        id="btn-qvga"  onclick="setRes('qvga')">QVGA 320×240</button>
      </div>
    </div>

    <div class="pane-section">
      <div class="sec-title">Image Filters</div>
      <div class="filter-row">
        <div class="filter-label">Brightness <span id="lbl-br">100%</span></div>
        <input type="range" min="0" max="300" value="100" id="sl-br">
      </div>
      <div class="filter-row">
        <div class="filter-label">Contrast <span id="lbl-ct">100%</span></div>
        <input type="range" min="0" max="400" value="100" id="sl-ct">
      </div>
      <div class="filter-row">
        <div class="filter-label">Sharpness <span id="lbl-sh">0</span></div>
        <input type="range" min="0" max="5" step="0.1" value="0" id="sl-sh">
      </div>
      <div class="filter-row">
        <div class="filter-label">Blur <span id="lbl-bl">0px</span></div>
        <input type="range" min="0" max="5" step="0.1" value="0" id="sl-bl">
      </div>
      <div class="toggle-row">
        <button class="tog" id="tog-inv" onclick="toggleFlag('inv')">INVERT</button>
        <button class="tog active" id="tog-xh" onclick="toggleFlag('xh')">CROSSHAIR</button>
        <button class="tog active" id="tog-hud" onclick="toggleFlag('hud')">CORNERS</button>
      </div>
    </div>

    <div class="pane-section">
      <div class="sec-title">Presets</div>
      <div class="preset-grid">
        <button class="preset-btn active" id="pre-raw"   onclick="applyPreset('raw')">RAW</button>
        <button class="preset-btn"        id="pre-boost" onclick="applyPreset('boost')">BOOST</button>
        <button class="preset-btn"        id="pre-night" onclick="applyPreset('night')">NIGHT</button>
        <button class="preset-btn"        id="pre-edge"  onclick="applyPreset('edge')">EDGE</button>
        <button class="preset-btn"        id="pre-ghost" onclick="applyPreset('ghost')">GHOST</button>
        <button class="preset-btn"        id="pre-sharp" onclick="applyPreset('sharp')">SHARP</button>
      </div>
    </div>

    <div class="pane-section">
      <div class="sec-title">Controls</div>
      <div class="action-row">
        <button class="btn primary" onclick="reconnect()">↺ RECONNECT</button>
        <button class="btn" onclick="poll()">⟳ REFRESH</button>
      </div>
      <div class="action-row" style="margin-top:6px">
        <button class="btn" onclick="applyPreset('raw')">RESET FILTERS</button>
      </div>
    </div>

    <div id="log-wrap">
      <div class="pane-section" style="border-bottom:none;padding-bottom:4px">
        <div class="sec-title">Event Log</div>
      </div>
      <div id="log"></div>
    </div>
  </div>
</div>

<script>
const img     = document.getElementById('stream');
const logEl   = document.getElementById('log');
const overlay = document.getElementById('reconnect-overlay');

let reconnects   = 0;
let stalling     = false;
let lastFrame    = Date.now();
let panelOpen    = true;
let activePreset = 'raw';
let currentRes   = 'qqvga';
let flags = { inv:false, xh:true, hud:true };
let F     = { br:100, ct:100, sh:0, bl:0 };

function log(msg, cls='') {
  const t = new Date().toLocaleTimeString('en-GB',{hour12:false});
  const d = document.createElement('div');
  const c = cls==='ok'?'#4dff91':cls==='warn'?'#ffb800':cls==='err'?'#ff3b3b':'#8a8880';
  d.innerHTML = `<span style="color:#4a4845">[${t}]</span> <span style="color:${c}">${msg}</span>`;
  logEl.appendChild(d);
  if (logEl.children.length > 100) logEl.removeChild(logEl.firstChild);
  logEl.scrollTop = logEl.scrollHeight;
}

function togglePanel() {
  panelOpen = !panelOpen;
  document.getElementById('panel').classList.toggle('collapsed', !panelOpen);
}

function applyFilter() {
  let sc = F.sh > 0 ? F.sh * 20 : 0;
  let f = `brightness(${F.br}%) contrast(${F.ct+sc}%) blur(${F.bl}px)`;
  if (flags.inv) f += ' invert(1)';
  img.style.filter = f;
}

function wireSlider(slId, lbId, key, unit) {
  const sl = document.getElementById(slId);
  const lb = document.getElementById(lbId);
  sl.addEventListener('input', () => {
    F[key] = parseFloat(sl.value);
    lb.textContent = Math.round(F[key]) + unit;
    activePreset = null; syncPresetBtns(); applyFilter();
  });
}
wireSlider('sl-br','lbl-br','br','%');
wireSlider('sl-ct','lbl-ct','ct','%');
wireSlider('sl-sh','lbl-sh','sh','');
wireSlider('sl-bl','lbl-bl','bl','px');

function toggleFlag(k) {
  flags[k] = !flags[k];
  document.getElementById('tog-'+k).classList.toggle('active', flags[k]);
  if (k==='xh')  document.getElementById('crosshair').style.display = flags.xh?'':'none';
  if (k==='hud') document.querySelectorAll('.corner').forEach(c=>c.style.display=flags.hud?'':'none');
  if (k==='inv') applyFilter();
}

const PRESETS = {
  raw:   { br:100, ct:100, sh:0, bl:0, inv:false },
  boost: { br:130, ct:180, sh:0, bl:0, inv:false },
  night: { br:220, ct:160, sh:0, bl:0, inv:false },
  edge:  { br:100, ct:400, sh:0, bl:0, inv:false },
  ghost: { br:80,  ct:120, sh:0, bl:0, inv:true  },
  sharp: { br:110, ct:150, sh:3, bl:0, inv:false },
};

function applyPreset(name) {
  const p = PRESETS[name]; if (!p) return;
  F.br=p.br; F.ct=p.ct; F.sh=p.sh; F.bl=p.bl;
  flags.inv = p.inv;
  activePreset = name;
  const units={br:'%',ct:'%',sh:'',bl:'px'};
  const sls={br:'sl-br',ct:'sl-ct',sh:'sl-sh',bl:'sl-bl'};
  const lbs={br:'lbl-br',ct:'lbl-ct',sh:'lbl-sh',bl:'lbl-bl'};
  Object.keys(F).forEach(k=>{
    document.getElementById(sls[k]).value = F[k];
    document.getElementById(lbs[k]).textContent = Math.round(F[k]) + units[k];
  });
  document.getElementById('tog-inv').classList.toggle('active', flags.inv);
  applyFilter(); syncPresetBtns();
  log('Preset: ' + name.toUpperCase(), 'ok');
}

function syncPresetBtns() {
  document.querySelectorAll('.preset-btn').forEach(b=>b.classList.remove('active'));
  if (activePreset) {
    const el = document.getElementById('pre-'+activePreset);
    if (el) el.classList.add('active');
  }
}

// Resolution toggle
async function setRes(r) {
  currentRes = r;
  document.getElementById('btn-qqvga').classList.toggle('active', r==='qqvga');
  document.getElementById('btn-qvga').classList.toggle('active',  r==='qvga');
  document.getElementById('res-pill').textContent = r==='qvga' ? 'QVGA' : 'QQVGA';
  document.getElementById('res-label').textContent = r==='qvga' ? '320×240' : '160×120';
  document.getElementById('feed-info').textContent =
    'OV7670 · ' + (r==='qvga'?'QVGA':'QQVGA') + ' · GRAYSCALE · q=80 · fb=3 · Core1';
  try {
    await fetch('/res?v=' + r);
    log('Resolution → ' + (r==='qvga'?'QVGA 320×240':'QQVGA 160×120'), 'ok');
    setTimeout(reconnect, 300); // reconnect stream after res change
  } catch(e) {
    log('Res change failed: ' + e.message, 'err');
  }
}

// Stream health
img.addEventListener('load', () => {
  lastFrame = Date.now();
  if (stalling) {
    stalling = false;
    overlay.classList.remove('show');
    document.getElementById('live-pill').textContent = '● LIVE';
    log('Stream restored', 'ok');
  }
});
img.addEventListener('error', () => {
  log('Stream error — retrying 1.5s', 'err');
  setTimeout(reconnect, 1500);
});
setInterval(() => {
  if (Date.now() - lastFrame > 4500 && !stalling) {
    stalling = true;
    overlay.classList.add('show');
    document.getElementById('live-pill').textContent = '● STALLED';
    log('Stalled — auto-reconnect', 'warn');
    reconnect();
  }
}, 2000);

function reconnect() {
  reconnects++;
  document.getElementById('p-rc').textContent = reconnects;
  overlay.classList.add('show');
  document.getElementById('live-pill').textContent = '● RECONNECT';
  img.src = '/stream?r=' + Date.now();
  log('Reconnect #' + reconnects, 'warn');
}

async function poll() {
  const t0 = performance.now();
  try {
    const r   = await fetch('/debug?r=' + Date.now());
    const lag = Math.round(performance.now() - t0);
    const d   = await r.json();
    const fps = d.fps;

    const bar = document.getElementById('fps-bar');
    bar.style.width      = Math.min(100, fps/30*100) + '%';
    bar.style.background = fps<5?'#ff3b3b':fps<12?'#ffb800':'#4dff91';
    document.getElementById('top-fps').textContent = fps + ' FPS';
    const fpsEl = document.getElementById('p-fps');
    fpsEl.textContent = fps + ' fps';
    fpsEl.className   = 'tval ' + (fps<5?'err':fps<12?'warn':'ok');
    document.getElementById('p-drops').textContent = d.drops;
    document.getElementById('p-heap').textContent  = (d.heap/1024).toFixed(0) + ' KB';
    const rssiEl = document.getElementById('p-rssi');
    rssiEl.textContent = d.rssi + ' dBm';
    rssiEl.className   = 'tval ' + (d.rssi<-75?'err':d.rssi<-60?'warn':'ok');
    document.getElementById('rssi-pill').textContent = 'RSSI ' + d.rssi;
    const lagEl = document.getElementById('p-lag');
    lagEl.textContent = lag + ' ms';
    lagEl.className   = 'tval ' + (lag>300?'err':lag>150?'warn':'');
    const s=Math.floor(d.uptime/1000);
    const hh=Math.floor(s/3600), mm=Math.floor((s%3600)/60);
    document.getElementById('p-up').textContent =
      (hh?hh+'h ':'')+( mm?mm+'m ':'')+( s%60)+'s';
    if (fps>0) log(`FPS:${fps} Lag:${lag}ms RSSI:${d.rssi} Heap:${(d.heap/1024).toFixed(0)}KB`);
  } catch(e) {
    log('Poll failed: '+e.message,'err');
  }
}

log('NavHat PRO v18 — QQVGA default · GRAYSCALE · Core1 · fb=3', 'ok');
poll();
setInterval(poll, 1500);
</script>
</body>
</html>
)rawhtml";
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html, strlen(html));
}

// ─────────────────────────────────────────────────────────────
//  HTTP SERVER
// ─────────────────────────────────────────────────────────────
void startCameraServer() {
  httpd_config_t cfg    = HTTPD_DEFAULT_CONFIG();
  cfg.server_port       = 80;
  cfg.stack_size        = 8192;
  cfg.recv_wait_timeout = 30;
  cfg.send_wait_timeout = 30;
  cfg.lru_purge_enable  = true;
  cfg.max_open_sockets  = 8;
  cfg.core_id           = 1;

  httpd_uri_t u1 = {"/",       HTTP_GET, index_handler,  NULL};
  httpd_uri_t u2 = {"/stream", HTTP_GET, stream_handler, NULL};
  httpd_uri_t u3 = {"/debug",  HTTP_GET, debug_handler,  NULL};
  httpd_uri_t u4 = {"/res",    HTTP_GET, res_handler,    NULL};

  if (httpd_start(&stream_httpd, &cfg) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &u1);
    httpd_register_uri_handler(stream_httpd, &u2);
    httpd_register_uri_handler(stream_httpd, &u3);
    httpd_register_uri_handler(stream_httpd, &u4);
    Serial.println("HTTP server OK — Core 1");
  } else {
    Serial.println("HTTP server FAILED");
    delay(1000);
    ESP.restart();
  }
}

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  setCpuFrequencyMhz(240);
  Serial.begin(115200);
  delay(100);
  Serial.println("\nNavHat PRO v18 — QQVGA | GRAYSCALE | Core1 | fb=3 | 16MHz");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0=Y2_GPIO_NUM; config.pin_d1=Y3_GPIO_NUM;
  config.pin_d2=Y4_GPIO_NUM; config.pin_d3=Y5_GPIO_NUM;
  config.pin_d4=Y6_GPIO_NUM; config.pin_d5=Y7_GPIO_NUM;
  config.pin_d6=Y8_GPIO_NUM; config.pin_d7=Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 16000000;
  config.pixel_format = PIXFORMAT_GRAYSCALE;
  config.frame_size   = FRAMESIZE_QQVGA;  // 160x120 — 4x faster than QVGA
  config.jpeg_quality = 12;               // unused for grayscale, set anyway
  config.fb_count     = 3;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera INIT FAILED");
    delay(3000);
    ESP.restart();
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_framesize(s, FRAMESIZE_QQVGA);
    // Uncomment if image is flipped:
    // s->set_vflip(s, 1);
    // s->set_hmirror(s, 1);
  }

  Serial.println("Camera OK — QQVGA 160x120 | GRAYSCALE | fb=3 | 16MHz");

  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  WiFi.begin(ssid, password);
  Serial.print("WiFi");
  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t++ < 40) { delay(500); Serial.print("."); }
  if (WiFi.status() != WL_CONNECTED) { Serial.println("\nFAIL"); ESP.restart(); }

  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  Serial.printf("\nReady — http://%s\n", WiFi.localIP().toString().c_str());

  if (MDNS.begin("navhat-cam")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("mDNS: navhat-cam.local");
  }

  fps_timer = millis();
  startCameraServer();
}

// ─────────────────────────────────────────────────────────────
//  LOOP — WiFi watchdog only
// ─────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost...");
    int t = 0;
    while (WiFi.status() != WL_CONNECTED && t++ < 40) delay(500);
    if (WiFi.status() != WL_CONNECTED) { Serial.println("Restart"); ESP.restart(); }
    Serial.println("WiFi back.");
  }
  delay(5000);
}
