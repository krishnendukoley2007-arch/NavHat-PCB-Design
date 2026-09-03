# 🏭 NavHat PRO — PCB Manufacturing & Gerber Guidelines

Instructions for ordering the NavHat PRO sensor node PCB through online fabrication services like **JLCPCB**, **PCBWay**, or **OSH Park**.

---

## 📐 PCB Specifications

| Parameter | Recommended Value | Notes |
| :--- | :--- | :--- |
| **Layers** | 2 Layers | Top: Signal & Power / Bottom: Solid Ground Plane |
| **Dimensions** | Approx. $75\text{ mm} \times 65\text{ mm}$ | Optimized for cap brim / headband mount |
| **Material** | Standard FR-4 | High TG ($150-170^\circ\text{C}$) recommended |
| **Board Thickness** | $1.6\text{ mm}$ (or $1.2\text{ mm}$ for weight saving) | $1.2\text{ mm}$ provides lighter wearable profile |
| **Copper Weight** | $1\text{ oz}$ ($35\mu\text{m}$) | Adequate for $\le 1.5\text{A}$ power rail |
| **Min Trace / Spacing** | $6\text{ mil} / 6\text{ mil}$ ($0.15\text{ mm}$) | Standard fab process |
| **Min Hole Size** | $0.3\text{ mm}$ | Standard via sizing |
| **Solder Mask Color** | Matte Black or Dark Green | Visual preference |
| **Silkscreen** | White | High contrast |
| **Surface Finish** | HASL with Lead or Lead-Free / ENIG | ENIG recommended for flat SMD pads |

---

## 📦 Standard Gerber File Export Naming

When generating Gerber archives from Autodesk Fusion 360 or KiCad, ensure the standard RS-274X layer mapping:

```text
NavHat_Gerber_v1.0.zip
├── NavHat.GTL        # Top Copper Layer
├── NavHat.GBL        # Bottom Copper Layer
├── NavHat.GTS        # Top Solder Mask
├── NavHat.GBS        # Bottom Solder Mask
├── NavHat.GTO        # Top Silkscreen Overlay
├── NavHat.GBO        # Bottom Silkscreen Overlay
├── NavHat.GKO / .GML # Board Outline (Edge Cuts)
└── NavHat.TXT / .DRL # NC Drill File
```

---

## 🛠️ Step-by-Step Ordering Process (JLCPCB)
1. Export the Gerber archive `.zip` from the Electronics workspace.
2. Go to [JLCPCB.com](https://jlcpcb.com/) and click **Order Now**.
3. Upload `NavHat_Gerber_v1.0.zip`. The online Gerber viewer will render both top and bottom copper layers.
4. Verify board dimensions ($75\text{ mm} \times 65\text{ mm}$) and select **2 Layers**.
5. Select **Surface Finish: LeadFree HASL** or **ENIG-RoHS**.
6. Submit the order for fabrication (typical turnaround: 2-3 business days).
