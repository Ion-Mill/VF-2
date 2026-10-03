<!-- doc_id: NGC-ESM-15 | title: NGC - 320V Power Supply - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---320v-power-supply.html | retrieved_at: 2026-10-03T18:09:40 | retrieved_via: direct | original_file: NGC-ESM-15__norev__20261003.html | original_sha256: 418f79fa49bbcbce920d6232af12dcdc2258297a3accd0c3108ef49bb2efb492 | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-15 |
| title | NGC - 320V Power Supply - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---320v-power-supply.html |
| retrieved\_at | 2026-10-03T18:09:40 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-15\_\_norev\_\_20261003.html |
| original\_sha256 | 418f79fa49bbcbce920d6232af12dcdc2258297a3accd0c3108ef49bb2efb492 |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [15.1 320V Power Supply - Replacement](#tab_320v-power-supply---replacement_0)
* [15.2 320V Power Supply - Troubleshooting](#tab_320v-power-supply---troubleshooting_0)

# 15.1 320V Power Supply Replacement - (93-32-5557B)

## **320V Power Supply** Replacement - (93-32-5557B)

---

**AD0422**

## Introduction

This procedure will show you how to replace 320V Power Supply on a Next Generation Control.

**This Document Applies to these Parts:**

* 93-32-5557B

## Electrical Safety

**DANGER:** Working with the electrical services required for CNC machines is **extremely hazardous** and can result in **serious injury or death**.

Before connecting line wires to the CNC:

* **Turn off all power** to the machine at the source.
* Perform a **Lockout-Tagout (LOTO)** procedure to ensure the power remains off during service.
* **Verify** that power has been disconnected by using an **AC voltage detector** on all incoming lines.

If you are **uncertain** about how to safely disconnect power or perform LOTO procedures:

* **Do not proceed.**
* Contact **qualified personnel** or obtain **appropriate assistance** before continuing.

Failure to follow these precautions may result in **electrical shock**, **equipment damage**, or **fatal injury**.

**Danger:** Before beginning any work inside the control cabinet, verify that the **High Voltage indicator light** on the **320V Power Supply / Vector Drive** has been **off for a minimum of five (5) minutes**. This waiting period ensures that residual voltage has dissipated and reduces the risk of electric shock.

Certain service procedures involve **high-risk electrical components** and may pose **serious injury or fatality hazards**. Technicians must **not attempt** any procedure unless they have a **complete understanding** of the steps involved and the associated risks.

If there is **any uncertainty** regarding a procedure, contact your **Haas Factory Outlet (HFO)** to arrange for a qualified service technician.

## Replacement / Installation - NGC

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/320v-power-supply---chc/ngc_320V_HVPS_install_diagram_93-32-5557A.png)

1. **[POWER OFF]**the machine  and wait until the High Volt light is completely turned off.
2. Mark and remove all the cables from the 320V Power supply.
    **Note:** The new 320V Power Supply [1] does not need the +12VDC supply that was connected to J3 on the old power supply.
3. Install the new 320V Power Supply [1].
4. Connect the PS Fault cable to J4 [2].
5. Install the VMON cable that comes in the kit and connect it to J2 [3].
6. Connect the Regen cable [4] to the terminal strip.
    **Note:**  For machines that had the molex connectors use the Regen cable extension P/N 33-0470 that comes in the kit.
7. Connect the 320VDC cable [5] to the terminal strip.
    **Note:**  For machines that had the molex connectors use the 320VDC cable  P/N 33-04902E that comes in the kit.
8. Connect the 230VAC Input cable [6] to the terminal strip.
    **Note:**  For machines that had the molex connectors use the Power extension cable P/N 33-0469 that comes in the kit
9. Connect the Ground cable and make sure all terminals are tight.  **[POWER ON]** and test the machine operation.

# 15.2 320V Power Supply (MMPS) - Troubleshooting Guide

## **320V Power Supply (MMPS)** - Troubleshooting Guide - NGC

---

**TG0012**

## Overview

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/hvps_types_ngc.png)

The High Voltage Power Supply (MMPS - MINIMILL Power Supply) is the source of power for the servo amplifiers.

It operates with 3 phase 208Vac or 240Vac single phase power. It rectifies the incoming AC power and supplies 320-340Vdc to the servo amplifiers.

The High Voltage Power Supply also contains the regeneration circuit used for dynamic braking.

**Types of 320V Power Supplies:**

1. 32-5557 320V Power Supply (Molex Connectors)
2. 32-5566 320V Power Supply ( Terminal Strip)
3. 32-5566A 320V Power Supply (Terminal Strip with Fuse)
   **Important:** Do not discharge the 32-5566A MMPS using a resistor, this will cause the fuse to blow.  Instead wait until the HV led light has turned off.

## Electrical Safety

**DANGER:** Working with the electrical services required for CNC machines is **extremely hazardous** and can result in **serious injury or death**.

Before connecting line wires to the CNC:

* **Turn off all power** to the machine at the source.
* Perform a **Lockout-Tagout (LOTO)** procedure to ensure the power remains off during service.
* **Verify** that power has been disconnected by using an **AC voltage detector** on all incoming lines.

If you are **uncertain** about how to safely disconnect power or perform LOTO procedures:

* **Do not proceed.**
* Contact **qualified personnel** or obtain **appropriate assistance** before continuing.

Failure to follow these precautions may result in **electrical shock**, **equipment damage**, or **fatal injury**.

**Danger:** Before beginning any work inside the control cabinet, verify that the **High Voltage indicator light** on the **320V Power Supply / Vector Drive** has been **off for a minimum of five (5) minutes**. This waiting period ensures that residual voltage has dissipated and reduces the risk of electric shock.

Certain service procedures involve **high-risk electrical components** and may pose **serious injury or fatality hazards**. Technicians must **not attempt** any procedure unless they have a **complete understanding** of the steps involved and the associated risks.

If there is **any uncertainty** regarding a procedure, contact your **Haas Factory Outlet (HFO)** to arrange for a qualified service technician.

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| **Alarm 648**DC BUS SHORTED and **Alarm 160** LOW INCOMING AC LINE VOLTAGE | There is a problem with the DC Bus or the MMPS is shorted. | Compare the measured DC voltage to the Diagnostic page. |
| Inspect the MMPS for short circuits |
| **Alarm 647** REGEN LOAD SHORTED | There is a problem with the REGEN or the MMPS is shorted. | Measure the resistance across the REGEN load |
| Inspect the MMPS for short circuits |
| **Alarm 119** INPUT AC LINE OVERVOLTAGE and **Alarm 650** DC BUS OVER VOLTAGE | There is a problem with the REGEN or the MMPS is faulty. | Measure the resistance across the REGEN load. |
| Incorrect DC Buss Voltage Display on the Gauge | The incoming line voltage is low. | Measure the incoming line voltage and determine if is within specification.  For 480V machines check the transformer taps, to make sure they are set to the correct range. |
| The voltage monitor cable is not plugged in or not connected incorrectly. | Use the electrical diagrams to make sure the Vmonitor cable is connected correctly. |
| The 320V power supply is not putting out the correct voltage signal. | The 320V power supply will produce approximately 1VDC for every 100VAC.  If not the drive is defective. |

## DC BUS

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/hvps_dc_buss_check.png)

**Corrective Action:**

**Diagnostic DC Voltage Check**

1. Press the **[POWER ON]** button.
2. Measure the DC voltage between pins 1 and 2 of connector J4 on the MMPS.
3. Compare the measured voltage with the DC VOLTAGE on the diagnostics page on the control. The readings must match +-2%.
4. Press the **[POWER OFF]** button.
5. Disconnect the DC Bus cables from connector J3 on the MMPS.
6. Press the **[POWER ON]** button.
7. Monitor the DC VOLTAGE on the diagnostics page of the control. If the readings do not match, the problem can be:
   * A bad connection on the cable that carries the voltage monitor signal to the controller PCBs. Make sure there is a tight connection on the J6 connector on the MMPS and the J16 on the NGC Maincon PCB.
   * A faulty MMPS if you have incorrect voltage at J16 on the NGC Maincon PCB.
   * A faulty NGC Maincon PCB if you have the correct voltage on the cable at the J16 on the NGC controller PCB. There is 0.01 VDC for every 1 VDC Bus. For example, 320 VDC must show 3.2VDC.

**Low DC Buss caused by shorted Amplifiers Check**

1. Press the **[POWER OFF]** button.
2. Disconnect the DC Bus cables from connector J3 on the MMPS.
3. Press the **[POWER ON]** button.
4. Monitor the DC VOLTAGE on the diagnostics page of the control.
   * If the DC Bus goes back to the nominal value, there is a short in one of the servo amplifiers. A low resistance or a short is a sign of a faulty servo amplifier.
   * If the readings match and the alarm continues, then the problem is a faulty MMPS.

## Short Circuit Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/TERMINAL-CHECK.png)

**Corrective Action:**

Inspect the MMPS. Disconnect all cables from the MMPS.

**Bridge rectifier to chassis check.**

1. Set your meter to resistance mode (Ohms).
2. Check terminals 1, 2, and 3 to chassis ground. If the reading does not show an open circuit (O.L) the MMPS is damaged.

**Bridge rectifier to DC bus terminal check**

1. Set the meter in diode test mode.
2. Put the black lead on J3 pin 2. With the red lead, check terminals 1, 2, and 3 of J1.
3. Wait until the reading on your meter settles. If the meter does not show show an open circuit (O.L) the MMPS is damaged.
4. Put the black lead on J3 pin 1. With the red lead, check terminals 1, 2 & 3 of J1.
5. Wait until the reading on your meter settles. If the meter does not show show an open circuit (O.L) the MMPS is damaged.

## REGEN Load Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/REGEN-INSPECTION.png)

**Corrective Action:**

**REGEN Load Check:**

1. Set the meter to resistance mode (Ohms).
2. Disconnect the REGEN load from the MMPS from connector J5.
3. Measure the resistance across the leads. The reading must be between 9.5 and 12.5 ohms. If the REGEN load is within specification, there can be a problem with the MMPS.
4. Measure the resistance across pins 1 on J3 and pin 3 of J5 of the MMPS. A short is a sign of a faulty MMPS.

## Electrical Diagrams

**320V Power Supply Diagram (32-5566 / 32-5566A)**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/ngc_hvps_electrical_diagram_32-5566.png)

**320V Power Supply Diagram (32-5557)**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/ngc_hvps_electrical_diagram_32-5557.png)

**320V Power Supply - Voltage Monitor Cable - 33-5790C**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/320v_mmps_33-5790C_cable_diagram.png)