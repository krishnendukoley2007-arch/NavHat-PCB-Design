# 🧠 NavHat PRO — Vision & Spatial Audio Engine

This directory contains the Python Edge AI Vision and Spatial Audio application for NavHat PRO.

---

## 📂 File Overview

| File | Purpose |
| :--- | :--- |
| **[`navhat_vision.py`](navhat_vision.py)** | Core application loop integrating YOLOv11 tracking, LLaVA reasoning, Farneback optical flow, and 3D spatial audio. |
| **[`config.json`](config.json)** | Centralized configuration for camera IPs, thresholds, timeouts, and neural voice settings. |
| **[`model.cfg`](model.cfg)** | Target YOLO model selector (`yolo11n.pt` / `yolov8n.pt`). |
| **[`requirements.txt`](requirements.txt)** | Python package dependencies. |
| **[`setup.bat`](setup.bat)** | Automated Windows setup script (creates virtualenv and runs `pip install`). |
| **[`run.bat`](run.bat)** | One-click Windows application launcher. |
| **[`test_camera.py`](test_camera.py)** | Diagnostic utility to benchmark ESP32-CAM stream latency and frame rate. |
| **[`test_audio.py`](test_audio.py)** | Diagnostic test for Microsoft Edge Neural TTS and 5-channel binaural panning. |
| **[`test_llava.py`](test_llava.py)** | Standalone test script for local Ollama / LLaVA-7B multimodal inference. |

---

## 🏎️ Running Standalone Benchmarks

```bash
# Test Camera Stream Latency
python test_camera.py

# Test 3D Spatial Audio (Put on headphones)
python test_audio.py

# Benchmark Local LLaVA-7B Inference
python test_llava.py
```
