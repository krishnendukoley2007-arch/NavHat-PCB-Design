#!/usr/bin/env python3
"""
NavHat PRO — 3D Spatial Audio & Neural TTS Test Utility
Tests Microsoft Edge-TTS generation and 5-zone stereo panning through headphones.
"""

import asyncio
import tempfile
import os
import time

try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    PYGAME_OK = True
except Exception as e:
    PYGAME_OK = False
    print(f"[FATAL] pygame initialization failed: {e}")

try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False
    print("[WARN] edge-tts not installed. Run 'pip install edge-tts'.")

PAN_MAP = {
    "Far Left":  (1.0, 0.1),
    "Left":      (1.0, 0.4),
    "Center":    (1.0, 1.0),
    "Right":     (0.4, 1.0),
    "Far Right": (0.1, 1.0),
}

async def generate_speech(text: str, tmp_path: str):
    communicate = edge_tts.Communicate(
        text,
        voice="en-IN-NeerjaNeural",
        rate="+60%",
        pitch="+0Hz",
        volume="+0%"
    )
    await communicate.save(tmp_path)

def test_zone(zone_name: str):
    print(f"\n[TESTING ZONE] >> {zone_name} (Pan: {PAN_MAP[zone_name]})")
    text = f"Obstacle on your {zone_name.lower()}"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir=tempfile.gettempdir())
    tmp_path = tmp.name
    tmp.close()

    try:
        asyncio.run(generate_speech(text, tmp_path))
        sound = pygame.mixer.Sound(tmp_path)
        ch = pygame.mixer.find_channel(True)
        if ch:
            pan = PAN_MAP[zone_name]
            ch.set_volume(pan[0], pan[1])
            ch.play(sound)
            while ch.get_busy():
                time.sleep(0.05)
    except Exception as e:
        print(f"[ERROR] Speech test failed: {e}")
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

def main():
    print("=" * 60)
    print("   NavHat PRO — 3D Spatial Audio & Stereo Panning Test     ")
    print("=" * 60)
    print("Please put on your stereo headphones.\n")

    if not PYGAME_OK or not EDGE_TTS_OK:
        print("[ERROR] Required audio libraries missing. Check dependencies.")
        return

    for zone in PAN_MAP:
        test_zone(zone)
        time.sleep(0.5)

    print("\n[COMPLETE] 3D Audio sweep complete across all 5 zones!")

if __name__ == "__main__":
    main()
