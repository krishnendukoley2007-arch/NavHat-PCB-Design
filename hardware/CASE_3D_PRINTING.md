# 🖨️ NavHat PRO — 3D Enclosure & Wearable Mounting Specs

Recommendations for 3D printing the headwear enclosure, ultrasonic horn mounts, and ESP32-CAM gimbal bracket.

---

## 📐 Mechanical Layout & Mounting Geometry

```text
               +--------------------------------------+
               |        Forward Ultrasonic Sensor     |
               |             (0° Level Pitch)         |
               +-------------------+------------------+
                                   |
         +-------------------------+-------------------------+
         |                                                   |
         v (-45° Yaw Angle)                                  v (+45° Yaw Angle)
+-----------------------+                           +-----------------------+
|  Left Ultrasonic Horn |                           | Right Ultrasonic Horn |
+-----------------------+                           +-----------------------+
         |                                                   |
         +-------------------------+-------------------------+
                                   |
                                   v (Centered Above Brim)
               +--------------------------------------+
               |      ESP32-CAM Adjustable Mount      |
               |        (10° Downward Tilt Angle)     |
               +--------------------------------------+
```

### Critical Angles
1. **Lateral Ultrasonic Spread**: Left and Right ultrasonic sensors should be angled outward by **$40^\circ - 45^\circ$** relative to the center sensor. This provides continuous coverage across the wearer's walking envelope while minimizing acoustic multipath interference.
2. **ESP32-CAM Tilt**: The camera node should be positioned with a **$10^\circ - 15^\circ$ downward pitch** so that ground-level obstacles (steps, curbs, tripping hazards) enter the camera's field of view $2-4$ meters ahead of the user.

---

## 🖨️ Recommended 3D Printing Parameters

| Parameter | Recommended Setting | Rationale |
| :--- | :--- | :--- |
| **Material** | PETG or PLA+ | PETG offers superior UV and impact resistance for outdoor wear |
| **Layer Height** | $0.20\text{ mm}$ (Quality) | Balances print speed and structural detail |
| **Infill Density**| $25\% - 30\%$ | Lightweight for head comfort |
| **Infill Pattern**| Gyroid or Grid | Uniform directional rigidity |
| **Wall Loops** | 3 Perimeters | Ensures durable screw mounting tabs |
| **Supports** | Tree / Organic Supports | Clean release from sensor circular cutouts |
| **Total Weight** | $< 85\text{ grams}$ | Minimizes neck strain during prolonged use |

---

## 🧢 Attachment Options
- **Cap Brim Clip**: Dual tension clamp snaps securely onto standard baseball cap brims.
- **Elastic Headband**: Slot cutouts accommodate $25\text{ mm}$ adjustable elastic headbands.
- **Chest Harness Adapter**: Standard GoPro-style mounting tab for hands-free chest rig attachment.
