# 🧠 NavHat PRO — 5 AI Modes Technical Deep Dive

A comprehensive operational manual detailing the mathematical logic, detection pipelines, and failure mode mitigation for all 5 intelligent operating modes.

---

## 1. Mode 1: Navigation (`NAV`)

### Objective
Real-time tracking of surrounding mobile and static entities, providing grouped spatial awareness with directional 3D stereo audio.

### Processing Pipeline
1. **Object Detection**: YOLOv11/v8 extracts bounding boxes and confidence scores ($\text{conf} \ge 0.42$).
2. **IoU Tracking**: The `AdvancedTracker` associates detections across consecutive frames using Intersection-over-Union ($\text{IoU} \ge 0.25$) and estimates directional centroid velocity $(v_x, v_y)$.
3. **Pluralisation & Directional Grouping**: Detections of identical classes are aggregated into plural quantities (*"two people"*, *"three cars"*) and sorted by dominant threat.
4. **Smart Cooldown Filter**: Prevents cognitive overload by enforcing a $4.0\text{s}$ cooldown per object unless proximity escalates (e.g. from `NEARBY` to `CRITICAL`).

---

## 2. Mode 2: Environment (`ENV`)

### Objective
Contextual scene understanding for unfamiliar environments, indoor navigation, and general orientation.

### Processing Pipeline
1. Captures a $336\times 336$ downscaled frame every $12\text{ s}$.
2. Queries local **LLaVA-7B** via Ollama API using a specialized system prompt:
   > *"Describe picture and vibe for a blind man in under 15 words. Be direct, casual, and literal."*
3. **SceneMemory Deduplication**: Computes the Bag-of-Words (BoW) cosine similarity against the last 3 scene descriptions:
   $$\text{Similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$
   If $\text{Similarity} \ge 0.72$, speech announcement is suppressed to prevent repetitive chatter when stationary.

---

## 3. Mode 3: Hazard Guard (`HAZARD`)

### Objective
Immediate detection and priority warning for life-threatening obstacles (approaching motor vehicles, bicycles, steps, tripping hazards, knives).

### Mathematical Model
$$\text{Threat} = W_{\text{base}} + (A_f \times 120) + (15 \text{ if approaching}) + \min\left(\frac{v}{50}, 20\right) + (25 \text{ if } \text{TTC} < 3.5\text{s})$$

* **Critical Interruption**: When threat score $\ge 60$, the system generates an urgent tone, raises pitch by $+15\text{Hz}$, and cuts off any currently playing speech.
* **Collision Warning HUD**: Emits a flashing red collision beacon if calculated Time-to-Collision ($\text{TTC}$) drops below $3.5\text{ s}$.

---

## 4. Mode 4: Text Reader / OCR (`OCR`)

### Objective
Transcribing printed signage, street names, restroom indicators, bus numbers, and packaging labels.

### Processing Pipeline
1. **CLAHE Contrast Normalization**: Converts frame to LAB color space and applies Contrast Limited Adaptive Histogram Equalization with clip limit 3.0 and $8\times 8$ grid size.
2. **Sharpening Convolution**: Applies a $3\times 3$ high-pass Laplacian sharpening kernel:
   $$K = \begin{bmatrix} 0 & -1 & 0 \\ -1 & 5 & -1 \\ 0 & -1 & 0 \end{bmatrix}$$
3. **Zero-Shot Reading**: Prompts LLaVA with temperature $0.05$ for high-precision text transcription.

---

## 5. Mode 5: Walking Assist (`WALK`)

### Objective
Real-time tactile corridor path guidance to steer the user around obstacles in busy pedestrian environments.

### 5-Zone Division

```text
  0%           20%          40%          60%          80%          100%
  ├────────────┼────────────┼────────────┼────────────┼────────────┤
    FAR LEFT       LEFT        CENTER        RIGHT       FAR RIGHT
    ZONE 0        ZONE 1       ZONE 2       ZONE 3        ZONE 4
```

* **Zone State Evaluation**:
  - $A_f \ge 0.18$: Marked as **CRITICAL** (Red)
  - $A_f \ge 0.08$: Marked as **BLOCKED** (Orange)
  - $A_f < 0.08$: Marked as **CLEAR** (Green)
* **Guidance Logic**:
  - Center Critical $\rightarrow$ *"Stop. Obstacle directly ahead, very close."*
  - Center Blocked & Left Clear $\rightarrow$ *"Move left. Path clearer on your left."*
  - Center Blocked & Right Clear $\rightarrow$ *"Move right. Path clearer on your right."*
  - All Clear $\rightarrow$ *"Path clear. Move forward."*
