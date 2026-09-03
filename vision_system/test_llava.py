#!/usr/bin/env python3
"""
NavHat PRO — Local LLaVA-7B / Ollama Benchmark & Diagnostic Utility
Verifies local Ollama server connectivity and measures multimodal inference latency.
"""

import requests
import time
import numpy as np
import cv2
import base64

OLLAMA_URL = "http://localhost:11434/api/generate"

def test_ollama():
    print("=" * 60)
    print("   NavHat PRO — LLaVA-7B Multimodal Benchmark Utility     ")
    print("=" * 60)
    print("1. Checking Ollama connection at http://localhost:11434...")

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"[SUCCESS] Ollama is running. Available models: {', '.join(models)}")
            if not any("llava" in m for m in models):
                print("[WARNING] 'llava:7b' not found in model list. Run: ollama pull llava:7b")
        else:
            print(f"[ERROR] Ollama returned status {r.status_code}")
            return
    except Exception as e:
        print(f"[ERROR] Could not connect to Ollama: {e}")
        print("Tip: Make sure Ollama is installed and running ('ollama serve').")
        return

    print("\n2. Generating synthetic test image & sending test query...")
    # Create test color gradient image
    img = np.zeros((336, 336, 3), dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (316, 316), (0, 180, 255), -1)
    cv2.putText(img, "NavHat PRO", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    _, buf = cv2.imencode('.jpg', img)
    img_b64 = base64.b64encode(buf).decode('utf-8')

    payload = {
        "model": "llava:7b",
        "prompt": "Describe this image in under 10 words.",
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 30}
    }

    t0 = time.time()
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=60)
        elapsed = time.time() - t0
        text = res.json().get("response", "").strip()
        print(f"[SUCCESS] LLaVA responded in {elapsed:.2f} seconds:")
        print(f'>> "{text}"')
    except Exception as e:
        print(f"[ERROR] Inference failed: {e}")

if __name__ == "__main__":
    test_ollama()
