#!/usr/bin/env python3
"""
NavHat PRO — ESP32-CAM Stream Latency & Health Diagnostic Utility
Runs a standalone connection benchmark against the ESP32-CAM MJPEG stream.
"""

import cv2
import time
import requests
import numpy as np
import sys

ESP32_IP = "10.154.74.40"
STREAM_URL = f"http://{ESP32_IP}:80/stream"

def test_stream():
    print("=" * 60)
    print("   NavHat PRO — Camera Stream Diagnostic Benchmark        ")
    print("=" * 60)
    print(f"Connecting to: {STREAM_URL}")
    print("Press 'Q' in the video window or Ctrl+C to stop.\n")

    try:
        response = requests.get(STREAM_URL, stream=True, timeout=5)
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} received.")
            return
        print("[SUCCESS] Stream connected successfully!\n")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("Tip: Verify your ESP32-CAM IP and ensure you are on the same 2.4GHz WiFi.")
        return

    buf = bytes()
    fps_count = 0
    t_start = time.time()
    t_last_fps = time.time()

    for chunk in response.iter_content(chunk_size=4096):
        buf += chunk
        start = buf.find(b'\xff\xd8')
        end   = buf.find(b'\xff\xd9')

        if start != -1 and end != -1 and end > start:
            jpg_bytes = buf[start:end+2]
            buf = buf[end+2:]
            arr = np.frombuffer(jpg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

            if frame is not None:
                fps_count += 1
                now = time.time()
                if now - t_last_fps >= 1.0:
                    fps = fps_count / (now - t_last_fps)
                    print(f"\r[STREAM ACTIVE] Resolution: {frame.shape[1]}x{frame.shape[0]} | FPS: {fps:.1f} | Frame Size: {len(jpg_bytes)/1024:.1f} KB", end="")
                    sys.stdout.flush()
                    fps_count = 0
                    t_last_fps = now

                cv2.putText(frame, f"DIAGNOSTIC STREAM: {frame.shape[1]}x{frame.shape[0]}", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 1, cv2.LINE_AA)
                cv2.imshow("NavHat Camera Stream Test", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    cv2.destroyAllWindows()
    print("\nBenchmark ended.")

if __name__ == "__main__":
    test_stream()
