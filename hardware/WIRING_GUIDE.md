# 🔌 NavHat PRO — Hardware Wiring & Assembly Guide

This guide details the step-by-step physical assembly, breadboard prototyping instructions, and signal conditioning mechanics for the NavHat PRO wearable.

---

## 🗺️ Complete System Interconnect Diagram

```text
                               +5V Boost Out
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
    v (VCC)                          v (VCC)                          v (VIN)
+-------------+              +---------------+                 +---------------+
| HC-SR04 (F) |              |  HC-SR04 (L)  |                 |  HC-SR04 (R)  |
| VCC Trig Echo GND          | VCC Trig Echo GND               | VCC Trig Echo GND
+--+----+---+--+             +--+----+---+---+                 +--+----+---+---+
   |    |   |  |                |    |   |   |                    |    |   |   |
   |    |   |  +---+            |    |   |   +---+                |    |   |   +---+
   |    |   |      |            |    |   |       |                |    |   |       |
   |    |   v      |            |    |   v       |                |    |   v       |
   |    | [1k/2k]  |            |    | [1k/2k]   |                |    | [1k/2k]   |
   |    |  DIV     |            |    |  DIV      |                |    |  DIV      |
   |    |   |      |            |    |   |       |                |    |   |       |
   |    |   v      |            |    |   v       |                |    |   v       |
   | GPIO GPIO     |         GPIO GPIO   |       |             GPIO GPIO   |       |
   |  13   18      |          14   33    |       |              19   23    |       |
   |               |                     |       |                         |       |
   +---------------+---------------------+-------+-------------------------+-------+
                                                 |
                                            Common GND
                                                 |
                                     +-----------+-----------+
                                     |                       |
                                     v (GND)                 v (GND)
                              +--------------+        +--------------+
                              |   ESP32 Dev  |        |  ESP32-CAM   |
                              |    Module    |        |  (Separate   |
                              |              |        |   5V Rail)   |
                              +------+---+---+        +--------------+
                                     |   |
                             GPIO 25 |   | GPIO 4
                              (PWM)  |   |  (PWM)
                                     v   v
                               [Left]     [Right]
                               Piezo       Piezo
                              Buzzer      Buzzer
```

---

## ⚡ 5V $\rightarrow$ 3.3V Voltage Divider Implementation

> [!WARNING]
> Never connect the **ECHO** pin of an HC-SR04 sensor directly to an ESP32 GPIO pin without a voltage divider. The HC-SR04 outputs a $5.0\text{V}$ pulse, whereas ESP32 GPIO pins are rated for a maximum of $3.6\text{V}$.

Each of the 3 ultrasonic sensors must have its ECHO signal wired through this network:

```text
HC-SR04 ECHO (5.0V) ────► [ 1 kΩ Resistor ] ───┬───► ESP32 ECHO GPIO (3.33V Safe)
                                               │
                                       [ 2 kΩ Resistor ]
                                               │
                                              GND
```

### Calculation
$$V_{\text{out}} = 5.0\text{V} \times \frac{2000\,\Omega}{1000\,\Omega + 2000\,\Omega} = 3.333\text{V}$$

---

## 🔋 Power Chain & Battery Wiring

1. Solder the LiPo battery positive ($+$) and negative ($-$) terminals to the **B+** and **B-** pads of the **TP4056** charging module.
2. Connect the **OUT+** and **OUT-** pads of the TP4056 to the input of the **5V Step-Up Boost Converter** through a power switch.
3. Adjust the potentiometer on the boost converter until the output measures precisely **$5.05\text{V} - 5.15\text{V}$**.
4. Route the 5V rail to:
   - All three **HC-SR04 VCC** pins
   - The **LD1117-3.3V LDO** input (which powers ESP32 VDD)
   - The **ESP32-CAM 5V** pin
5. Tie all grounds together into a single star-ground plane to prevent ground loop noise on sensor reads.
