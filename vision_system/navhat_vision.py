"""
╔══════════════════════════════════════════════════════════════════════╗
║                   N A V H A T   P R O   v6.0                        ║
║          Advanced AI Vision System for Blind Navigation              ║
║                                                                      ║
║  MODE 1 → Navigation    (YOLO + Tracker + TTC + Grouped Counting)   ║
║  MODE 2 → Environment   (LLaVA + Scene Memory + Change Detect)      ║
║  MODE 3 → Hazard Guard  (Threat Scoring + Collision Warn)           ║
║  MODE 4 → Text Reader   (OCR — reads signs, labels, text)           ║
║  MODE 5 → Walking Assist (5-Zone Path Guidance + Instructions)      ║
║                                                                      ║
║  CAMERA  → ESP32-CAM (MJPEG Stream) | Fallback: Webcam             ║
║  AUDIO   → Neural Voice (edge-tts) | 3D Stereo Pan | Emotion Tones ║
║                                                                      ║
║  Keys: [1]Nav [2]Env [3]Hazard [4]OCR [5]Walk [F]Flow [S]Snap [Q]  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import cv2
import base64
import requests
import time
import threading
import asyncio
import tempfile
import os
import collections
import sys
import math
import json
import datetime
import numpy as np
import urllib.request
import queue as _queue
from typing import TypedDict

# ── Attempt imports with clear error messages ────────────────────────
try:
    from ultralytics import YOLO
except ImportError:
    sys.exit("[FATAL] ultralytics not installed. Run setup.bat or 'pip install ultralytics' first.")

try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False
    print("[WARN] pygame failed — spatial audio disabled.")

try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False
    print("[WARN] edge-tts not found — falling back to pyttsx3.")

try:
    import pyttsx3
    _PYTTSX_ENGINE = pyttsx3.init()
    _PYTTSX_ENGINE.setProperty('rate', 200)
    PYTTSX_OK = True
except Exception:
    PYTTSX_OK = False
    print("[WARN] pyttsx3 also unavailable — running silent.")


# ═══════════════════════════════════════════════════════════════════
#  ESP32-CAM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

ESP32_IP              = "10.154.74.40"      # Change to your ESP32-CAM IP (or "navhat-cam.local")
ESP32_STREAM_URL      = f"http://{ESP32_IP}:80/stream"   # MJPEG stream endpoint
ESP32_CONTROL_URL     = f"http://{ESP32_IP}/control"     # Camera control endpoint (optional)
ESP32_CAPTURE_URL     = f"http://{ESP32_IP}/capture"     # Single JPEG capture endpoint
ESP32_CONNECT_TIMEOUT = 6                  # seconds to wait when connecting
ESP32_READ_TIMEOUT    = 10                 # seconds before stream read times out
ESP32_MAX_RETRIES     = 10                 # reconnect attempts before falling back to webcam
ESP32_RETRY_DELAY     = 2.0                # seconds between reconnect attempts
USE_WEBCAM_FALLBACK   = True               # fall back to webcam if ESP32 unreachable


# ═══════════════════════════════════════════════════════════════════
#  GLOBAL SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

def _detect_yolo_model():
    if os.path.exists("model.cfg"):
        with open("model.cfg", encoding="utf-8") as f:
            for line in f:
                if line.startswith("YOLO_MODEL="):
                    m = line.strip().split("=")[1]
                    if os.path.exists(m):
                        return m
    for candidate in ["yolo11n.pt", "yolov8n.pt"]:
        if os.path.exists(candidate):
            return candidate
    return "yolo11n.pt"

YOLO_MODEL_PATH  = _detect_yolo_model()

OLLAMA_URL       = "http://localhost:11434/api/generate"
YOLO_CONF        = 0.42
NAV_INTERVAL     = 4.0
ENV_INTERVAL     = 12.0
HAZARD_INTERVAL  = 3.0
OCR_INTERVAL     = 4.0
WALK_INTERVAL    = 2.5
FRAME_W          = 640
FRAME_H          = 480
LLAVA_IMG_SIZE   = 336
MOTION_THRESHOLD = 25
FPS_WINDOW       = 30

SCENE_CHANGE_THRESH    = 0.72
TTC_WARN_SECS          = 3.5
HAZARD_SPEAK_THRESHOLD = 35
SNAPSHOT_DIR           = "navhat_snapshots"

WALK_ZONE_NAMES  = ["far left", "left", "center", "right", "far right"]
WALK_BLOCK_AF    = 0.08
WALK_CRITICAL_AF = 0.18

HAZARD_LABELS = {
    "person": 10, "car": 25, "truck": 25, "motorcycle": 20,
    "bicycle": 15, "bus": 25, "traffic light": 10, "stop sign": 8,
    "knife": 30, "scissors": 20, "dog": 15, "cat": 5,
    "fire hydrant": 8, "bench": 5, "chair": 5,
}

PROX_CLOSE  = 0.18
PROX_MEDIUM = 0.07

PROX_COLORS = {
    "CRITICAL": (0,   0, 255),
    "CLOSE"   : (0,  80, 255),
    "NEARBY"  : (0, 165, 255),
    "AHEAD"   : (0, 255,   0),
}

MODE_META = {
    1: {"name": "NAV",   "label": "NAVIGATION",    "color": (0, 255, 120)},
    2: {"name": "ENV",   "label": "ENVIRONMENT",   "color": (0, 200, 255)},
    3: {"name": "HAZARD","label": "HAZARD GUARD",  "color": (0,  60, 255)},
    4: {"name": "OCR",   "label": "TEXT READER",   "color": (255,180,  0)},
    5: {"name": "WALK",  "label": "WALKING ASSIST","color": (180, 0, 255)},
}

NUMBER_WORDS = {
    1:"one", 2:"two", 3:"three", 4:"four", 5:"five",
    6:"six", 7:"seven", 8:"eight", 9:"nine", 10:"ten",
}

def num_word(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))

FLOW_ARROW_COLOR     = (0, 180, 180)
FLOW_STEP            = 24
HAZARD_OVERLAY_ALPHA = 0.35
COLLISION_PULSE_HZ   = 6
SPOKEN_PURGE_SECS    = 60.0
MAX_CAM_FAILURES     = 30


# ═══════════════════════════════════════════════════════════════════
#  TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

class TrackState(TypedDict):
    box:       tuple
    age:       int
    cx:        float
    cy:        float
    vx:        float
    vy:        float
    label:     str
    af_hist:   collections.deque
    conf_hist: collections.deque


class Detection(TypedDict):
    id:         int
    label:      str
    box:        tuple
    af:         float
    cx:         float
    cy:         float
    vx:         float
    vy:         float
    conf:       float
    approaching: bool
    ttc:        "float | None"


# ═══════════════════════════════════════════════════════════════════
#  ESP32-CAM STREAM READER WITH FAILOVER
# ═══════════════════════════════════════════════════════════════════

class ESP32CamStream:
    """
    Reads MJPEG stream from ESP32-CAM in a background thread.
    Falls back to webcam if ESP32 is unreachable.
    Stream URL format: http://<ESP32_IP>:80/stream
    """

    def __init__(self):
        self._frame       = None
        self._lock        = threading.Lock()
        self._running     = False
        self._thread      = None
        self._use_webcam  = False
        self._webcam_cap  = None
        self._cam_source  = "ESP32-CAM"
        self._connected   = False
        self._fail_count  = 0
        self._status      = "Initializing..."

    @property
    def source(self) -> str:
        return self._cam_source

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> str:
        return self._status

    def _probe_esp32(self) -> bool:
        """Quick check: can we reach the ESP32 at all?"""
        try:
            r = requests.get(f"http://{ESP32_IP}/", timeout=ESP32_CONNECT_TIMEOUT)
            return r.status_code < 500
        except Exception:
            try:
                r = requests.get(ESP32_STREAM_URL, timeout=ESP32_CONNECT_TIMEOUT, stream=True)
                r.close()
                return True
            except Exception:
                return False

    def _read_mjpeg_stream(self):
        """
        Parse multipart/x-mixed-replace MJPEG stream.
        Each frame is a JPEG delimited by boundary markers.
        """
        print(f"[CAM] Connecting to ESP32-CAM: {ESP32_STREAM_URL}")
        self._status = f"Connecting to {ESP32_IP}..."
        retries = 0

        while self._running and not self._use_webcam:
            try:
                response = requests.get(
                    ESP32_STREAM_URL,
                    stream=True,
                    timeout=(ESP32_CONNECT_TIMEOUT, ESP32_READ_TIMEOUT)
                )
                if response.status_code != 200:
                    raise ConnectionError(f"HTTP {response.status_code}")

                print(f"[CAM] ✓ ESP32-CAM stream connected!")
                self._connected = True
                self._status    = f"ESP32-CAM @ {ESP32_IP}"
                retries = 0
                buf = bytes()

                for chunk in response.iter_content(chunk_size=4096):
                    if not self._running:
                        break
                    buf += chunk

                    # JPEG starts with FF D8, ends with FF D9
                    start = buf.find(b'\xff\xd8')
                    end   = buf.find(b'\xff\xd9')

                    if start != -1 and end != -1 and end > start:
                        jpg_bytes = buf[start:end + 2]
                        buf = buf[end + 2:]

                        arr   = np.frombuffer(jpg_bytes, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                        if frame is not None:
                            frame = cv2.resize(frame, (FRAME_W, FRAME_H))
                            with self._lock:
                                self._frame = frame
                            self._fail_count = 0

                self._connected = False
                raise ConnectionError("Stream ended unexpectedly")

            except Exception as e:
                self._connected = False
                retries += 1
                self._status = f"ESP32 disconnected (retry {retries}/{ESP32_MAX_RETRIES})"
                print(f"[CAM] ESP32 stream error: {e} — retry {retries}/{ESP32_MAX_RETRIES}")

                if retries >= ESP32_MAX_RETRIES:
                    if USE_WEBCAM_FALLBACK:
                        print("[CAM] Falling back to webcam...")
                        self._use_webcam = True
                        self._start_webcam()
                        return
                    else:
                        print("[CAM] Max retries reached. No fallback. Exiting stream thread.")
                        self._running = False
                        return

                time.sleep(ESP32_RETRY_DELAY)

    def _start_webcam(self):
        """Initialize OpenCV webcam as fallback."""
        self._webcam_cap = cv2.VideoCapture(0)
        self._webcam_cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
        self._webcam_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        self._cam_source = "WEBCAM (fallback)"
        self._status     = "Webcam fallback active"
        self._connected  = True
        print("[CAM] Webcam fallback started.")

        fail_count = 0
        while self._running:
            ret, frame = self._webcam_cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
                fail_count = 0
            else:
                fail_count += 1
                if fail_count > MAX_CAM_FAILURES:
                    print("[CAM] Webcam read failed too many times. Stopping.")
                    self._running = False
                    break
            time.sleep(0.01)

        if self._webcam_cap:
            self._webcam_cap.release()

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._read_mjpeg_stream, daemon=True)
        self._thread.start()

    def read(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if self._frame is not None:
                return True, self._frame.copy()
        return False, None

    def stop(self):
        self._running = False
        if self._webcam_cap:
            self._webcam_cap.release()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# ═══════════════════════════════════════════════════════════════════
#  EMOTION TONE PROFILES
# ═══════════════════════════════════════════════════════════════════

TONE_CALM   = {"rate": "+60%",  "pitch": "+0Hz",  "volume": "+0%"}
TONE_ALERT  = {"rate": "+80%",  "pitch": "+5Hz",  "volume": "+10%"}
TONE_URGENT = {"rate": "+100%", "pitch": "+15Hz", "volume": "+20%"}

def _tone_for_threat(score: float) -> dict:
    if score >= 60:
        return TONE_URGENT
    if score >= 35:
        return TONE_ALERT
    return TONE_CALM


# ═══════════════════════════════════════════════════════════════════
#  AUDIO ENGINE (Neural TTS + 3D Stereo Panning + Interruptible)
# ═══════════════════════════════════════════════════════════════════

_audio_queue   = _queue.PriorityQueue()
_audio_thread  = None
_audio_running = False
_current_sound = None
_audio_lock    = threading.Lock()

_speak_seq      = 0
_speak_seq_lock = threading.Lock()

def _get_seq() -> int:
    with _speak_seq_lock:
        return _speak_seq

def _flush_queue():
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except Exception:
            break

EDGE_VOICE = "en-IN-NeerjaNeural"


def _pan_value(zone_name: str):
    pan_map = {
        "far left":  (1.0, 0.1),
        "left":      (1.0, 0.4),
        "center":    (1.0, 1.0),
        "right":     (0.4, 1.0),
        "far right": (0.1, 1.0),
    }
    return pan_map.get(zone_name, (1.0, 1.0))


def _stop_current():
    global _current_sound
    if PYGAME_OK:
        pygame.mixer.stop()
    with _audio_lock:
        _current_sound = None


async def _edge_tts_generate(text: str, tone: dict, tmp_path: str):
    communicate = edge_tts.Communicate(
        text,
        voice=EDGE_VOICE,
        rate=tone["rate"],
        pitch=tone["pitch"],
        volume=tone["volume"],
    )
    await communicate.save(tmp_path)


def _speak_worker():
    global _current_sound
    while True:
        try:
            priority, text, tone, zone, my_seq = _audio_queue.get(timeout=1.0)
        except _queue.Empty:
            continue

        if my_seq >= 0 and _get_seq() != my_seq:
            _audio_queue.task_done()
            continue

        pan = _pan_value(zone)

        if EDGE_TTS_OK and PYGAME_OK:
            try:
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".mp3", dir=tempfile.gettempdir()
                )
                tmp_path = tmp.name
                tmp.close()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_edge_tts_generate(text, tone, tmp_path))
                loop.close()

                if my_seq >= 0 and _get_seq() != my_seq:
                    try: os.unlink(tmp_path)
                    except Exception: pass
                    _audio_queue.task_done()
                    continue

                sound = pygame.mixer.Sound(tmp_path)
                ch = pygame.mixer.find_channel(True)
                if ch:
                    ch.set_volume(pan[0], pan[1])
                    with _audio_lock:
                        _current_sound = sound
                    ch.play(sound)
                    while ch.get_busy():
                        time.sleep(0.05)
                        if my_seq >= 0 and _get_seq() != my_seq:
                            ch.stop()
                            break
                    with _audio_lock:
                        _current_sound = None

                try: os.unlink(tmp_path)
                except Exception: pass

            except Exception as e:
                print(f"[AUDIO] edge-tts error: {e} — falling back")
                _fallback_speak(text)

        elif PYTTSX_OK:
            _fallback_speak(text)

        _audio_queue.task_done()


def _fallback_speak(text: str):
    if PYTTSX_OK:
        try:
            _PYTTSX_ENGINE.say(text)
            _PYTTSX_ENGINE.runAndWait()
        except Exception as e:
            print(f"[AUDIO] pyttsx3 error: {e}")


def _ensure_audio_thread():
    global _audio_thread
    if _audio_thread and _audio_thread.is_alive():
        return
    _audio_thread = threading.Thread(target=_speak_worker, daemon=True)
    _audio_thread.start()


def _cap_words(text: str, n: int = 8) -> str:
    words = text.split()
    return " ".join(words[:n]) if len(words) > n else text


def speak(text: str, urgent: bool = False, zone: str = "center",
          threat_score: float = 0.0, env: bool = False):
    global _speak_seq
    _ensure_audio_thread()
    if not env:
        text = _cap_words(text)
        with _speak_seq_lock:
            _speak_seq += 1
            my_seq = _speak_seq
        _flush_queue()
        if urgent:
            _stop_current()
    else:
        my_seq = -1
    tone     = _tone_for_threat(threat_score)
    priority = 0 if urgent else 1
    try:
        _audio_queue.put_nowait((priority, text, tone, zone, my_seq))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  SMART PRIORITY VOICE FILTER
# ═══════════════════════════════════════════════════════════════════

_last_spoken: dict[str, tuple[float, str]] = {}
_last_purge_t: float = 0.0


def _purge_stale_spoken() -> None:
    global _last_purge_t
    now = time.time()
    if now - _last_purge_t < SPOKEN_PURGE_SECS:
        return
    _last_purge_t = now
    cutoff = now - SPOKEN_PURGE_SECS
    stale = [k for k, (t, _) in _last_spoken.items() if t < cutoff]
    for k in stale:
        del _last_spoken[k]


def should_speak_object(det: Detection, prox: str, cooldown: float = 4.0) -> bool:
    _purge_stale_spoken()
    key       = f"{det['label']}_{det['id']}"
    now       = time.time()
    prox_rank = {"AHEAD": 0, "NEARBY": 1, "CLOSE": 2, "CRITICAL": 3}

    if key not in _last_spoken:
        _last_spoken[key] = (now, prox)
        return True

    last_time, last_prox = _last_spoken[key]
    escalated = prox_rank.get(prox, 0) > prox_rank.get(last_prox, 0)

    if escalated:
        _last_spoken[key] = (now, prox)
        return True

    if now - last_time >= cooldown:
        _last_spoken[key] = (now, prox)
        return True

    return False


# ═══════════════════════════════════════════════════════════════════
#  SPATIAL HELPERS
# ═══════════════════════════════════════════════════════════════════

def zone_label(cx: float, fw: float) -> str:
    f   = fw / 5
    idx = int(cx // f)
    return WALK_ZONE_NAMES[min(idx, 4)]

def proximity_label(af: float) -> str:
    if af >= 0.28:        return "CRITICAL"
    if af >= PROX_CLOSE:  return "CLOSE"
    if af >= PROX_MEDIUM: return "NEARBY"
    return "AHEAD"

def estimate_ttc(af_history: collections.deque, interval: float):
    if len(af_history) < 4:
        return None
    areas      = list(af_history)
    diffs      = [areas[i+1] - areas[i] for i in range(len(areas)-1)]
    avg_growth = sum(diffs) / len(diffs)
    if avg_growth <= 0:
        return None
    current = areas[-1]
    if current <= 0:
        return None
    ttc = (current / avg_growth) * interval
    return ttc if ttc < 60 else None


# ═══════════════════════════════════════════════════════════════════
#  PLURALISER
# ═══════════════════════════════════════════════════════════════════

def _pluralise(label: str, count: int) -> str:
    if count == 1:
        return label
    irregular = {"person": "people", "knife": "knives", "leaf": "leaves"}
    if label in irregular:
        return irregular[label]
    if label.endswith(("s", "x", "ch")):
        return label + "es"
    return label + "s"


# ═══════════════════════════════════════════════════════════════════
#  THREAT SCORER ALGORITHM
# ═══════════════════════════════════════════════════════════════════

def threat_score(det: dict) -> float:
    base  = HAZARD_LABELS.get(det["label"].lower(), 3)
    prox  = det["af"]
    speed = math.hypot(det["vx"], det["vy"])
    score = base
    score += prox * 120
    score += 15 if det["approaching"] else 0
    score += min(speed / 50, 20)
    if det["ttc"] is not None and det["ttc"] < TTC_WARN_SECS:
        score += 25
    return min(score, 100.0)


# ═══════════════════════════════════════════════════════════════════
#  GROUPED NAV SPEECH GENERATOR
# ═══════════════════════════════════════════════════════════════════

def build_grouped_nav_speech(tracked: list) -> tuple[str | None, str, float]:
    if not tracked:
        return None, "center", 0.0

    groups: dict[str, list] = {}
    for d in tracked:
        groups.setdefault(d["label"].lower(), []).append(d)

    sorted_groups = sorted(
        groups.items(),
        key=lambda kv: max(threat_score(d) for d in kv[1]),
        reverse=True
    )

    parts        = []
    imminent_ttc = None
    max_ts       = 0.0
    dom_zone     = "center"

    for label, dets in sorted_groups[:4]:
        rep   = max(dets, key=threat_score)
        ts    = threat_score(rep)
        count = len(dets)
        prox  = proximity_label(rep["af"])
        zone  = zone_label(rep["cx"], FRAME_W)

        if ts > max_ts:
            max_ts   = ts
            dom_zone = zone

        if not should_speak_object(rep, prox):
            continue

        display_label = _pluralise(label, count)
        count_str     = f"{num_word(count)} " if count > 1 else ""

        if prox in ("CRITICAL", "CLOSE"):
            loc_str = f"very close on your {zone}"
        elif prox == "NEARBY":
            loc_str = f"nearby on your {zone}"
        else:
            loc_str = f"ahead on your {zone}"

        approach_str = ", coming toward you" if rep["approaching"] else ""

        if rep["ttc"] and rep["ttc"] < TTC_WARN_SECS:
            if imminent_ttc is None or rep["ttc"] < imminent_ttc:
                imminent_ttc = rep["ttc"]

        parts.append(f"{count_str}{display_label} {loc_str}{approach_str}")

    if not parts:
        return None, dom_zone, max_ts

    msg = ", ".join(parts)
    if imminent_ttc is not None:
        msg = f"Watch out! Impact in {imminent_ttc:.1f} seconds. {msg}"

    return msg, dom_zone, max_ts


# ═══════════════════════════════════════════════════════════════════
#  HAZARD SPEECH GENERATOR
# ═══════════════════════════════════════════════════════════════════

def build_hazard_speech(tracked: list) -> tuple[str | None, str, float]:
    scored = [(threat_score(d), d) for d in tracked
              if d["label"].lower() in HAZARD_LABELS]
    if not scored:
        return None, "center", 0.0
    scored.sort(key=lambda x: x[0], reverse=True)
    score, d = scored[0]
    if score < HAZARD_SPEAK_THRESHOLD:
        return None, "center", score

    same      = [x for _, x in scored if x["label"] == d["label"]]
    count     = len(same)
    prox      = proximity_label(d["af"])
    zone      = zone_label(d["cx"], FRAME_W)
    label_str = _pluralise(d["label"].lower(), count)
    count_str = f"{num_word(count)} " if count > 1 else ""

    ttc_s  = (f", impact in {d['ttc']:.1f} seconds"
              if d["ttc"] and d["ttc"] < TTC_WARN_SECS else "")
    suffix = ", moving closer" if d["approaching"] else ""

    msg = (f"DANGER! {count_str}{label_str}, {prox.lower()} on your "
           f"{zone}{suffix}{ttc_s}. Threat level {int(score)}.")
    return msg, zone, score


# ═══════════════════════════════════════════════════════════════════
#  WALKING ASSIST ENGINE — MODE 5
# ═══════════════════════════════════════════════════════════════════

class WalkingAssist:
    def __init__(self):
        self._last_instruction = ""
        self._last_time        = 0.0
        self._zone_blocked:  list[bool] = [False] * 5
        self._zone_critical: list[bool] = [False] * 5

    def analyse(self, tracked: list, fw: int, fh: int) -> tuple[str | None, str]:
        zone_width = fw / 5
        self._zone_blocked  = [False] * 5
        self._zone_critical = [False] * 5

        for d in tracked:
            z_idx = min(int(d["cx"] // zone_width), 4)
            if d["af"] >= WALK_CRITICAL_AF:
                self._zone_critical[z_idx] = True
                self._zone_blocked[z_idx]  = True
            elif d["af"] >= WALK_BLOCK_AF:
                self._zone_blocked[z_idx] = True

        center_blocked  = self._zone_blocked[2]
        center_critical = self._zone_critical[2]

        instruction = self._decide_instruction(
            self._zone_blocked, self._zone_critical, center_blocked, center_critical
        )

        if not instruction:
            return None, "center"

        if center_critical:
            dom_zone = "center"
        elif center_blocked:
            dom_zone = self._find_open_corridor(self._zone_blocked)
        else:
            dom_zone = "center"

        now = time.time()
        if (instruction == self._last_instruction and
                now - self._last_time < WALK_INTERVAL * 2):
            return None, dom_zone

        self._last_instruction = instruction
        self._last_time        = now
        return instruction, dom_zone

    def _decide_instruction(self, blocked, critical, center_blocked, center_critical):
        crit_count = sum(critical)
        if center_critical or crit_count >= 3:
            return "Stop. Obstacle directly ahead, very close."

        if not any(blocked):
            return "Path clear. Move forward."

        if center_blocked:
            if not blocked[0] and not blocked[1]:
                return "Move left. Path clearer on your left."
            if not blocked[3] and not blocked[4]:
                return "Move right. Path clearer on your right."
            left_clear  = not blocked[1]
            right_clear = not blocked[3]
            if left_clear:
                return "Slight left. Obstacle ahead."
            if right_clear:
                return "Slight right. Obstacle ahead."
            return "Stop. Path blocked. Wait for clear."

        left_danger  = blocked[0] or blocked[1]
        right_danger = blocked[3] or blocked[4]

        if left_danger and not right_danger:
            return "Keep right. Objects on your left."
        if right_danger and not left_danger:
            return "Keep left. Objects on your right."
        if left_danger and right_danger:
            return "Move through center carefully."

        return "Path clear. Move forward."

    def _find_open_corridor(self, blocked):
        if not blocked[0] and not blocked[1]:
            return "left"
        if not blocked[3] and not blocked[4]:
            return "right"
        return "center"

    def draw_overlay(self, frame, tracked, instruction):
        fw, fh = frame.shape[1], frame.shape[0]
        zone_w = fw // 5
        zone_blocked  = self._zone_blocked
        zone_critical = self._zone_critical

        for i in range(5):
            x1 = i * zone_w
            x2 = x1 + zone_w
            if zone_critical[i]:
                color = (0, 0, 180); alpha = 0.45
            elif zone_blocked[i]:
                color = (0, 80, 200); alpha = 0.28
            else:
                color = (0, 180, 50); alpha = 0.15
            ov = frame.copy()
            cv2.rectangle(ov, (x1, 60), (x2, fh - 50), color, -1)
            cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)
            cv2.line(frame, (x2, 60), (x2, fh - 50), (60, 60, 60), 1)
            lbl = "BLOCK" if zone_blocked[i] else "CLEAR"
            col = (0, 0, 255) if zone_critical[i] else \
                  (0, 165, 255) if zone_blocked[i] else (0, 220, 60)
            cv2.putText(frame, lbl, (x1 + 5, fh // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)

        if instruction:
            arrow_cx = fw // 2
            arrow_cy = fh - 80
            if "left" in instruction.lower():
                pts = np.array([[arrow_cx-60, arrow_cy],[arrow_cx-20, arrow_cy-30],[arrow_cx-20, arrow_cy+30]], np.int32)
                cv2.fillPoly(frame, [pts], (0, 220, 255))
            elif "right" in instruction.lower():
                pts = np.array([[arrow_cx+60, arrow_cy],[arrow_cx+20, arrow_cy-30],[arrow_cx+20, arrow_cy+30]], np.int32)
                cv2.fillPoly(frame, [pts], (0, 220, 255))
            elif "forward" in instruction.lower() or "clear" in instruction.lower():
                pts = np.array([[arrow_cx, arrow_cy-40],[arrow_cx-25, arrow_cy+10],[arrow_cx+25, arrow_cy+10]], np.int32)
                cv2.fillPoly(frame, [pts], (0, 220, 60))
            elif "stop" in instruction.lower():
                cv2.rectangle(frame, (arrow_cx-25, arrow_cy-25),(arrow_cx+25, arrow_cy+25), (0, 0, 255), -1)

        return frame


# ═══════════════════════════════════════════════════════════════════
#  ADVANCED IoU TRACKER
# ═══════════════════════════════════════════════════════════════════

class AdvancedTracker:
    def __init__(self, max_age=10, iou_thresh=0.25):
        self.tracks     = {}
        self._next_id   = 0
        self.max_age    = max_age
        self.iou_thresh = iou_thresh

    def _iou(self, a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
        iw  = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
        inter = iw * ih
        union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
        return inter / union if union > 0 else 0.0

    def update(self, detections, dt: float):
        for tid in list(self.tracks):
            self.tracks[tid]["age"] += 1
            if self.tracks[tid]["age"] > self.max_age:
                del self.tracks[tid]

        used    = set()
        results = []

        for label, box, af, cx, cy, conf in detections:
            best_tid, best_iou = None, self.iou_thresh
            for tid, t in self.tracks.items():
                if tid in used: continue
                iou = self._iou(box, t["box"])
                if iou > best_iou:
                    best_iou, best_tid = iou, tid

            if best_tid is not None:
                used.add(best_tid)
                t  = self.tracks[best_tid]
                vx = (cx - t["cx"]) / max(dt, 0.001)
                vy = (cy - t["cy"]) / max(dt, 0.001)
                t.update({"box": box, "age": 0, "cx": cx, "cy": cy,
                          "vx": vx, "vy": vy, "label": label})
                t["af_hist"].append(af)
                t["conf_hist"].append(conf)
                approaching = (len(t["af_hist"]) >= 3 and
                               t["af_hist"][-1] > t["af_hist"][-3] * 1.05)
                ttc      = estimate_ttc(t["af_hist"], NAV_INTERVAL)
                avg_conf = sum(t["conf_hist"]) / len(t["conf_hist"])
            else:
                best_tid = self._next_id
                self._next_id += 1
                ah = collections.deque(maxlen=8)
                ch = collections.deque(maxlen=8)
                ah.append(af); ch.append(conf)
                self.tracks[best_tid] = {
                    "box": box, "age": 0, "cx": cx, "cy": cy,
                    "vx": 0.0, "vy": 0.0, "label": label,
                    "af_hist": ah, "conf_hist": ch
                }
                approaching = False
                ttc         = None
                avg_conf    = conf

            t = self.tracks[best_tid]
            results.append({
                "id": best_tid, "label": label, "box": box,
                "af": af, "cx": cx, "cy": cy,
                "vx": t["vx"], "vy": t["vy"], "conf": avg_conf,
                "approaching": approaching, "ttc": ttc,
            })
        return results


# ═══════════════════════════════════════════════════════════════════
#  MOTION DETECTOR
# ═══════════════════════════════════════════════════════════════════

class MotionDetector:
    def __init__(self):
        self._prev      = None
        self._flow_prev = None

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (15, 15), 0)
        if self._prev is None:
            self._prev = blur; self._flow_prev = gray
            return 0.0, np.zeros((FRAME_H, FRAME_W, 2), dtype=np.float32)
        diff       = cv2.absdiff(self._prev, blur)
        self._prev = blur
        score      = float(cv2.countNonZero(
            cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]))
        motion     = min(100.0, score / (FRAME_H * FRAME_W) * 1000)
        flow = cv2.calcOpticalFlowFarneback(
            self._flow_prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        self._flow_prev = gray
        return motion, flow


# ═══════════════════════════════════════════════════════════════════
#  SCENE MEMORY (Bag-of-Words Cosine Similarity)
# ═══════════════════════════════════════════════════════════════════

class SceneMemory:
    def __init__(self, maxlen: int = 3):
        self._maxlen  = maxlen
        self._history: list[tuple[str, dict]] = []

    def _bow(self, text: str) -> dict:
        freq: dict[str, int] = {}
        for w in text.lower().split():
            freq[w] = freq.get(w, 0) + 1
        return freq

    def _cosine(self, a: dict, b: dict) -> float:
        keys = set(a) | set(b)
        dot  = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        na   = math.sqrt(sum(v * v for v in a.values()))
        nb   = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na * nb > 0 else 0.0

    def is_new_scene(self, text: str) -> bool:
        bow_new = self._bow(text)
        if not self._history:
            self._history.append((text, bow_new))
            return True
        sims = [self._cosine(bow_new, bow) for _, bow in self._history]
        if sum(sims) / len(sims) < SCENE_CHANGE_THRESH:
            if len(self._history) >= self._maxlen:
                self._history.pop(0)
            self._history.append((text, bow_new))
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
#  LLaVA MULTIMODAL ENGINE
# ═══════════════════════════════════════════════════════════════════

class LLaVAEngine:
    def __init__(self):
        self._lock    = threading.Lock()
        self._result  = {"text": "", "ready": False}
        self._running = False
        self.memory   = SceneMemory(maxlen=3)

    def trigger(self, frame):
        if self._running: return
        self._running = True
        threading.Thread(target=self._run, args=(frame.copy(),), daemon=True).start()

    def _run(self, frame):
        small   = cv2.resize(frame, (LLAVA_IMG_SIZE, LLAVA_IMG_SIZE))
        _, buf  = cv2.imencode('.jpg', small, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
        img_b64 = base64.b64encode(buf).decode('utf-8')
        payload = {
            "model": "llava:7b",
            "prompt": ("Bro, describe picture and vibe for a blind man in under 15 words. "
                       "Be direct, casual, and literal."),
            "images": [img_b64], "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.1, "num_predict": 50},
        }
        try:
            res  = requests.post(OLLAMA_URL, json=payload, timeout=60)
            text = res.json().get("response", "").strip()
            with self._lock:
                self._result = {"text": text, "ready": True}
        except Exception as e:
            print(f"[LLaVA] {e}")
        finally:
            self._running = False

    def pop(self):
        with self._lock:
            if self._result["ready"]:
                text = self._result["text"]
                self._result["ready"] = False
                if text and self.memory.is_new_scene(text):
                    return text
        return None

    @property
    def is_running(self): return self._running


# ═══════════════════════════════════════════════════════════════════
#  OCR ENGINE (Enhanced Preprocessing + LLaVA Vision)
# ═══════════════════════════════════════════════════════════════════

class OCREngine:
    def __init__(self):
        self._lock    = threading.Lock()
        self._result  = {"text": "", "ready": False}
        self._running = False

    def trigger(self, frame):
        if self._running: return
        self._running = True
        threading.Thread(target=self._run, args=(frame.copy(),), daemon=True).start()

    def _run(self, frame):
        lab     = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe   = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l       = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        small   = cv2.resize(enhanced, (LLAVA_IMG_SIZE, LLAVA_IMG_SIZE))
        _, buf  = cv2.imencode('.jpg', small, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        img_b64 = base64.b64encode(buf).decode('utf-8')
        payload = {
            "model": "llava:7b",
            "prompt": ("Read ALL text visible in this image out loud. "
                       "List every word or number you see, in reading order. "
                       "If no text, say: No text found. Keep it under 25 words."),
            "images": [img_b64], "stream": False,
            "options": {"temperature": 0.05, "top_p": 0.1, "num_predict": 60},
        }
        try:
            res  = requests.post(OLLAMA_URL, json=payload, timeout=60)
            text = res.json().get("response", "").strip()
            with self._lock:
                self._result = {"text": text, "ready": True}
        except Exception as e:
            print(f"[OCR] {e}")
        finally:
            self._running = False

    def pop(self):
        with self._lock:
            if self._result["ready"]:
                text = self._result["text"]
                self._result["ready"] = False
                return text
        return None

    @property
    def is_running(self): return self._running


# ═══════════════════════════════════════════════════════════════════
#  YOLO HELPERS
# ═══════════════════════════════════════════════════════════════════

def extract_detections(results, names, fw, fh):
    fa  = fw * fh
    out = []
    for box in results[0].boxes:
        label        = names[int(box.cls)]
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        bw, bh       = x2 - x1, y2 - y1
        af           = (bw * bh) / fa
        cx           = x1 + bw / 2
        cy           = y1 + bh / 2
        conf         = float(box.conf[0])
        out.append((label, (x1, y1, x2, y2), af, cx, cy, conf))
    return out


# ═══════════════════════════════════════════════════════════════════
#  MINIMAP (Bird's-Eye View Top-Down Radar)
# ═══════════════════════════════════════════════════════════════════

def draw_minimap(tracked: list, w=160, h=120) -> np.ndarray:
    mm = np.full((h, w, 3), 20, dtype=np.uint8)
    for i in range(1, 5):
        cv2.line(mm, (i*w//5, 0), (i*w//5, h), (40, 40, 40), 1)
    for i in range(1, 4):
        cv2.line(mm, (0, i*h//4), (w, i*h//4), (40, 40, 40), 1)
    cam_x, cam_y = w//2, h-8
    cv2.polylines(mm, [np.array([(cam_x, cam_y), (cam_x-40, 10), (cam_x+40, 10)])],
                  True, (0, 100, 0), 1)
    cv2.circle(mm, (cam_x, cam_y), 4, (0, 200, 0), -1)
    for d in tracked:
        mx        = int((d["cx"] / FRAME_W) * w)
        dist_frac = 1.0 - min(d["af"] * 4, 1.0)
        my        = int(dist_frac * (h-20) + 5)
        prox      = proximity_label(d["af"])
        color     = PROX_COLORS[prox]
        cv2.circle(mm, (mx, my), 5, color, -1)
        cv2.putText(mm, d["label"][:3].upper(), (mx+5, my+4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, color, 1, cv2.LINE_AA)
        vx, vy = d["vx"] / 300, d["vy"] / 300
        ev = (int(mx + vx * 30), int(my + vy * 20))
        cv2.arrowedLine(mm, (mx, my), ev, (200, 200, 200), 1, tipLength=0.3)
    cv2.putText(mm, "TOP VIEW", (4, h-4), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (80, 80, 80), 1)
    return mm


# ═══════════════════════════════════════════════════════════════════
#  COUNT SUMMARY BAR
# ═══════════════════════════════════════════════════════════════════

def draw_count_summary(frame, tracked: list):
    if not tracked: return
    counts: dict[str, int] = {}
    for d in tracked:
        lbl = d["label"].lower()
        counts[lbl] = counts.get(lbl, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    x, y = 8, 70
    for lbl, cnt in sorted_counts[:6]:
        col = ((0,0,255) if cnt >= 5 else (0,100,255) if cnt >= 3
               else (0,180,255) if cnt >= 2 else (160,220,160))
        txt = f"{_pluralise(lbl, cnt)}: {cnt}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1)
        cv2.rectangle(frame, (x-2, y-th-2), (x+tw+4, y+3), (0, 0, 0), -1)
        cv2.putText(frame, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.46, col, 1, cv2.LINE_AA)
        y += th + 8
        if y > FRAME_H - 60: break


# ═══════════════════════════════════════════════════════════════════
#  OPTICAL FLOW OVERLAY
# ═══════════════════════════════════════════════════════════════════

def draw_flow_overlay(frame, flow, step=24):
    h, w   = frame.shape[:2]
    y_pts, x_pts = np.mgrid[step//2:h:step, step//2:w:step]
    fx = flow[y_pts, x_pts, 0]
    fy = flow[y_pts, x_pts, 1]
    mag  = np.sqrt(fx**2 + fy**2)
    mask = mag > 2.5
    for y, x, dvx, dvy in zip(
        y_pts[mask].ravel(), x_pts[mask].ravel(),
        fx[mask].ravel(), fy[mask].ravel()
    ):
        end = (int(x + dvx * 2), int(y + dvy * 2))
        cv2.arrowedLine(frame, (int(x), int(y)), end, (0, 180, 180), 1, tipLength=0.4)


# ═══════════════════════════════════════════════════════════════════
#  VELOCITY VECTORS
# ═══════════════════════════════════════════════════════════════════

def draw_velocity_vector(frame, d: dict):
    cx, cy = int(d["cx"]), int(d["cy"])
    speed  = math.hypot(d["vx"], d["vy"])
    if speed < 8: return
    scale = min(speed / 30, 3.0)
    ex    = int(cx + d["vx"] / speed * 40 * scale)
    ey    = int(cy + d["vy"] / speed * 40 * scale)
    color = (0, 0, 255) if d["approaching"] else (200, 200, 0)
    cv2.arrowedLine(frame, (cx, cy), (ex, ey), color, 2, tipLength=0.35)


# ═══════════════════════════════════════════════════════════════════
#  BOUNDING BOXES & THREAT METERS
# ═══════════════════════════════════════════════════════════════════

def draw_detection_boxes(frame, tracked: list):
    for d in tracked:
        x1, y1, x2, y2 = [int(v) for v in d["box"]]
        prox  = proximity_label(d["af"])
        color = PROX_COLORS[prox]
        ts    = threat_score(d)

        if d["ttc"] and d["ttc"] < TTC_WARN_SECS:
            pulse   = abs(int(time.time() * 6) % 4 - 2)
            cv2.circle(frame, (int(d["cx"]), int(d["cy"])), int(30 + pulse * 8), (0,0,255), 2)

        thick = 1 if ts < 30 else 2 if ts < 60 else 3
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)

        bar_h    = y2 - y1
        bar_fill = int(bar_h * ts / 100)
        cv2.rectangle(frame, (x2+5, y2), (x2+10, y1), (30, 30, 30), -1)
        bar_c = ((0,255,0) if ts < 30 else (0,165,255) if ts < 60 else (0,0,255))
        cv2.rectangle(frame, (x2+5, y2), (x2+10, y2-bar_fill), bar_c, -1)

        arrow   = "↑" if d["approaching"] else ""
        ttc_tag = f" {d['ttc']:.1f}s" if d["ttc"] and d["ttc"] < TTC_WARN_SECS else ""
        pill    = f"#{d['id']} {d['label']}{arrow}{ttc_tag}"
        (tw, th), _ = cv2.getTextSize(pill, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        py = max(y1 - 20, 0)
        cv2.rectangle(frame, (x1, py), (x1+tw+8, py+th+7), color, -1)
        cv2.putText(frame, pill, (x1+4, py+th+2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,0), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{int(d['conf']*100)}%",
                    (x1+2, y2-4), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200,200,200), 1, cv2.LINE_AA)
        draw_velocity_vector(frame, d)


# ═══════════════════════════════════════════════════════════════════
#  HEADS-UP DISPLAY (HUD)
# ═══════════════════════════════════════════════════════════════════

def _blend_rect(img, pt1, pt2, color, alpha, radius=6):
    ov = img.copy()
    x1, y1 = pt1; x2, y2 = pt2
    cv2.rectangle(ov, (x1+radius, y1), (x2-radius, y2), color, -1)
    cv2.rectangle(ov, (x1, y1+radius), (x2, y2-radius), color, -1)
    for cx_, cy_ in [(x1+radius,y1+radius),(x2-radius,y1+radius),
                     (x1+radius,y2-radius),(x2-radius,y2-radius)]:
        cv2.circle(ov, (cx_, cy_), radius, color, -1)
    cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)


def draw_hud(frame, mode, fps, motion_score, status_text,
             ai_pending, tracked, minimap_img, cam_source, cam_connected,
             flow_overlay=False):
    H, W = frame.shape[:2]
    meta = MODE_META[mode]

    # ── Camera source indicator ──────────────────────────────────
    cam_color = (0, 255, 100) if cam_connected else (0, 80, 255)
    cam_label = f"CAM: {cam_source}"
    cv2.putText(frame, cam_label, (8, H - 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, cam_color, 1, cv2.LINE_AA)

    if flow_overlay:
        cv2.putText(frame, "[FLOW ON]", (W-90, 76),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 180, 180), 1, cv2.LINE_AA)

    _blend_rect(frame, (8, 8), (260, 52), (0, 0, 0), 0.68)
    cv2.putText(frame, f"● {meta['label']}",
                (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.65, meta["color"], 2, cv2.LINE_AA)

    engine_label = "♪ NEURAL" if (EDGE_TTS_OK and PYGAME_OK) else "♪ BASIC"
    engine_color = (0, 200, 100) if (EDGE_TTS_OK and PYGAME_OK) else (150, 150, 150)
    cv2.putText(frame, engine_label, (18, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, engine_color, 1, cv2.LINE_AA)

    _blend_rect(frame, (W-200, 8), (W-8, 52), (0, 0, 0), 0.68)
    cv2.putText(frame, f"FPS:{fps:4.1f}  OBJ:{len(tracked):02d}",
                (W-190, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1, cv2.LINE_AA)

    bar_w = int((motion_score / 100.0) * W)
    bar_c = ((0,255,0) if motion_score < 30 else
             (0,165,255) if motion_score < 60 else (0,0,255))
    cv2.rectangle(frame, (0, 54), (bar_w, 58), bar_c, -1)
    cv2.rectangle(frame, (0, 54), (W, 58), (35, 35, 35), 1)

    if ai_pending:
        spin  = ['◐','◓','◑','◒'][int(time.time() * 5) % 4]
        label = "OCR..." if mode == 4 else "Analyzing..."
        cv2.putText(frame, f"{spin} {label}", (W//2-65, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 1, cv2.LINE_AA)

    imminent = [d for d in tracked if d["ttc"] and d["ttc"] < TTC_WARN_SECS]
    if imminent:
        worst = min(imminent, key=lambda d: d["ttc"])
        pulse = abs(int(time.time() * 5) % 4 - 2)
        alert = f"!! COLLISION {worst['label'].upper()} {worst['ttc']:.1f}s !!"
        cv2.putText(frame, alert, (W//2-180, 88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255), 2+pulse, cv2.LINE_AA)

    if mode in (1, 3, 5) and tracked:
        draw_count_summary(frame, tracked)

    if minimap_img is not None:
        mh, mw = minimap_img.shape[:2]
        frame[H-mh-8:H-8, W-mw-8:W-8] = minimap_img
        cv2.rectangle(frame, (W-mw-9, H-mh-9), (W-7, H-7), (80,80,80), 1)

    if status_text:
        mc   = (W - (180 if minimap_img is not None else 20)) // 10
        disp = status_text[:mc-1] + "…" if len(status_text) > mc else status_text
        _blend_rect(frame, (0, H-42), (W, H), (0,0,0), 0.72)
        cv2.putText(frame, disp, (10, H-14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220,220,220), 1, cv2.LINE_AA)

    cv2.putText(
        frame,
        "[1]NAV [2]ENV [3]HAZ [4]OCR [5]WALK [F]Flow [S]Snap [Q]Quit",
        (8, H-14), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (80,80,80), 1, cv2.LINE_AA
    )

    if mode == 3:
        pulse = abs(int(time.time() * 4) % 8 - 4) / 4.0
        ov    = frame.copy()
        cv2.rectangle(ov, (0,0), (W,H), (0, 0, int(pulse * 55)), -1)
        cv2.addWeighted(ov, 0.35, frame, 0.65, 0, frame)

    return frame


# ═══════════════════════════════════════════════════════════════════
#  SNAPSHOT RECORDER
# ═══════════════════════════════════════════════════════════════════

def save_snapshot(frame, mode, tracked):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SNAPSHOT_DIR, f"navhat_{ts}.jpg")
    cv2.imwrite(path, frame)
    meta = {
        "timestamp": ts,
        "mode": MODE_META[mode]["name"],
        "objects": [{"id": d["id"], "label": d["label"],
                     "threat": round(threat_score(d), 1)} for d in tracked]
    }
    with open(path.replace(".jpg", ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    speak("Snapshot saved.")
    print(f"[SNAP] Saved: {path}")


# ═══════════════════════════════════════════════════════════════════
#  TERMINAL DASHBOARD
# ═══════════════════════════════════════════════════════════════════

_dash_printed = False
_last_dash    = 0.0

def print_dashboard(mode, fps, motion, status, obj_count, top_threat, tracked, cam_source):
    global _dash_printed, _last_dash
    now = time.time()
    if now - _last_dash < 2.0: return
    _last_dash = now

    mn  = MODE_META[mode]["name"]
    bl  = int(motion / 5)
    bar = "█" * bl + "░" * (20 - bl)
    mt  = "HIGH" if motion > MOTION_THRESHOLD else "low "
    tt  = f"{top_threat:4.0f}" if top_threat else "  --"

    counts: dict[str, int] = {}
    for d in tracked:
        lbl = d["label"].lower()
        counts[lbl] = counts.get(lbl, 0) + 1
    count_str = "  ".join(
        f"{_pluralise(l, c)}:{c}" for l, c in
        sorted(counts.items(), key=lambda x: -x[1])[:5]
    ) or "none"

    audio_str = "edge-tts neural" if (EDGE_TTS_OK and PYGAME_OK) else \
                "pyttsx3 fallback" if PYTTSX_OK else "SILENT"

    if _dash_printed:
        sys.stdout.write("\033[11A\033[J")
    _dash_printed = True
    print(f"┌─ NavHat PRO v6.0 ──────────────────────────────────────────┐")
    print(f"│  Mode     : {mn:<8}  FPS : {fps:5.1f}  Objects: {obj_count:3d}          │")
    print(f"│  Camera   : {cam_source[:48]:<48}  │")
    print(f"│  Motion   : [{bar}] {motion:4.1f}% {mt}         │")
    print(f"│  Threat   : {tt}/100  Audio: {audio_str:<20}         │")
    print(f"│  Objects  : {count_str[:50]:<50}  │")
    print(f"│  Status   : {str(status)[:50]:<50}  │")
    print(f"│  Keys     : [1]Nav [2]Env [3]Haz [4]OCR [5]Walk           │")
    print(f"│             [F]Flow [S]Snap [Q]Quit                        │")
    print(f"└─────────────────────────────────────────────────────────────┘")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════

def main():
    print(__doc__)
    print(f"[CAM] ESP32-CAM IP: {ESP32_IP}")
    print(f"[CAM] Stream URL  : {ESP32_STREAM_URL}")
    print(f"[CAM] Initializing stream reader...")

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    _ensure_audio_thread()

    # ── Start ESP32-CAM stream reader ──
    cam = ESP32CamStream()
    cam.start()

    # Wait up to 5s for first frame
    t_wait = time.time()
    while time.time() - t_wait < 5.0:
        ok, _ = cam.read()
        if ok:
            break
        time.sleep(0.1)

    if not cam.read()[0]:
        print("[CAM] WARNING: No frame yet from ESP32. Will keep trying in background.")

    yolo    = YOLO(YOLO_MODEL_PATH)
    tracker = AdvancedTracker()
    motion  = MotionDetector()
    llava   = LLaVAEngine()
    ocr     = OCREngine()
    walk    = WalkingAssist()

    MODE         = 1
    last_trigger = time.time() - 60
    status_text  = "NavHat PRO v6.0 ready"
    fps_times    = collections.deque(maxlen=FPS_WINDOW)
    motion_score = 0.0
    flow_field   = np.zeros((FRAME_H, FRAME_W, 2), dtype=np.float32)
    tracked_data = []
    show_flow    = False
    last_dt      = 0.033
    top_threat   = 0.0
    no_frame_count = 0

    # Placeholder frame shown while waiting for camera connection
    placeholder = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    cv2.putText(placeholder, "Waiting for ESP32-CAM...", (60, FRAME_H//2 - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(placeholder, f"URL: {ESP32_STREAM_URL}", (40, FRAME_H//2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
    cv2.putText(placeholder, "Check Serial Monitor for ESP32 IP address", (40, FRAME_H//2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 200, 100), 1)

    speak("NavHat ready. Navigation mode active.", zone="center")

    try:
        while True:
            t0 = time.time()
            ret, frame = cam.read()

            if not ret:
                no_frame_count += 1
                display = placeholder.copy()
                cv2.putText(display, f"Retrying... ({no_frame_count})", (60, FRAME_H//2 + 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 80, 255), 1)
                cv2.imshow("NavHat PRO v6.0", display)
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    break
                continue

            no_frame_count = 0
            now     = time.time()
            display = frame.copy()
            motion_score, flow_field = motion.detect(frame)

            if show_flow and MODE in (1, 3, 5):
                draw_flow_overlay(display, flow_field)

            ai_pending = False

            # ── MODE 1: NAVIGATION ──────────────────────────────
            if MODE == 1:
                results      = yolo(frame, conf=YOLO_CONF, verbose=False)
                raw          = extract_detections(results, yolo.names, FRAME_W, FRAME_H)
                tracked_data = tracker.update(raw, last_dt)
                draw_detection_boxes(display, tracked_data)
                if now - last_trigger >= NAV_INTERVAL:
                    last_trigger = now
                    msg, dom_zone, ts = build_grouped_nav_speech(tracked_data)
                    if msg:
                        speak(msg, urgent=(ts >= 60), zone=dom_zone, threat_score=ts)
                        status_text = msg

            # ── MODE 2: ENVIRONMENT ─────────────────────────────
            elif MODE == 2:
                tracked_data = []
                ai_pending   = llava.is_running
                if now - last_trigger >= ENV_INTERVAL and not llava.is_running:
                    last_trigger = now
                    llava.trigger(frame)
                    status_text = "Scanning environment..."
                result = llava.pop()
                if result:
                    speak(result, zone="center", threat_score=0, env=True)
                    status_text = result

            # ── MODE 3: HAZARD GUARD ────────────────────────────
            elif MODE == 3:
                results      = yolo(frame, conf=YOLO_CONF, verbose=False)
                raw          = extract_detections(results, yolo.names, FRAME_W, FRAME_H)
                tracked_data = tracker.update(raw, last_dt)
                draw_detection_boxes(display, tracked_data)
                if now - last_trigger >= HAZARD_INTERVAL:
                    last_trigger = now
                    msg, dom_zone, ts = build_hazard_speech(tracked_data)
                    if msg:
                        speak(msg, urgent=True, zone=dom_zone, threat_score=ts)
                        status_text = msg

            # ── MODE 4: OCR ─────────────────────────────────────
            elif MODE == 4:
                tracked_data = []
                ai_pending   = ocr.is_running
                kernel       = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
                display      = cv2.filter2D(display, -1, kernel)
                cv2.putText(display, "POINT CAMERA AT TEXT",
                            (FRAME_W//2-140, FRAME_H//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,180,0), 2, cv2.LINE_AA)
                if now - last_trigger >= OCR_INTERVAL and not ocr.is_running:
                    last_trigger = now
                    ocr.trigger(frame)
                    status_text = "Reading text..."
                result = ocr.pop()
                if result:
                    speak(f"Text says: {result}", zone="center")
                    status_text = f"Text: {result}"

            # ── MODE 5: WALKING ASSIST ──────────────────────────
            elif MODE == 5:
                results      = yolo(frame, conf=YOLO_CONF, verbose=False)
                raw          = extract_detections(results, yolo.names, FRAME_W, FRAME_H)
                tracked_data = tracker.update(raw, last_dt)

                instruction, safe_zone = walk.analyse(tracked_data, FRAME_W, FRAME_H)
                display = walk.draw_overlay(display, tracked_data, instruction)
                draw_detection_boxes(display, tracked_data)

                if instruction:
                    ts_val = max((threat_score(d) for d in tracked_data), default=0)
                    urgent = "Stop" in instruction or "STOP" in instruction
                    speak(instruction, urgent=urgent,
                          zone=safe_zone, threat_score=ts_val)
                    status_text = instruction

                if now - last_trigger >= WALK_INTERVAL:
                    last_trigger = now

            # ── TOP THREAT CALCULATION ──────────────────────────
            if MODE in (1, 3, 5) and tracked_data:
                scores     = [threat_score(d) for d in tracked_data]
                top_threat = max(scores) if scores else 0.0
            else:
                top_threat = 0.0

            minimap = draw_minimap(tracked_data) if tracked_data else None
            elapsed = time.time() - t0
            last_dt = elapsed
            fps_times.append(elapsed)
            fps = 1.0 / (sum(fps_times) / len(fps_times)) if fps_times else 0

            display = draw_hud(display, MODE, fps, motion_score,
                               status_text, ai_pending, tracked_data, minimap,
                               cam.source, cam.connected, show_flow)

            cv2.imshow("NavHat PRO v6.0", display)
            print_dashboard(MODE, fps, motion_score, status_text,
                            len(tracked_data), top_threat, tracked_data, cam.source)

            # ── KEYBOARD NAVIGATION ──────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key == ord('1') and MODE != 1:
                speak("Navigation mode.")
                MODE = 1; last_trigger = 0
                tracker = AdvancedTracker()
                status_text = "Navigation mode"

            elif key == ord('2') and MODE != 2:
                speak("Environment mode.", env=True)
                MODE = 2; last_trigger = 0
                status_text = "Environment mode"

            elif key == ord('3') and MODE != 3:
                speak("Hazard guard mode.")
                MODE = 3; last_trigger = 0
                tracker = AdvancedTracker()
                status_text = "Hazard guard mode"

            elif key == ord('4') and MODE != 4:
                speak("Text reader mode. Point camera at text.")
                MODE = 4; last_trigger = 0
                status_text = "Text reader mode"

            elif key == ord('5') and MODE != 5:
                speak("Walking assist mode. I will guide your path.")
                MODE = 5; last_trigger = 0
                tracker = AdvancedTracker()
                status_text = "Walking assist mode"

            elif key == ord('f'):
                show_flow = not show_flow
                speak("Flow overlay on." if show_flow else "Flow overlay off.")

            elif key == ord('s'):
                save_snapshot(display, MODE, tracked_data)

            elif key == ord('q'):
                speak("Goodbye.")
                time.sleep(1.5)
                break

    finally:
        cam.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
