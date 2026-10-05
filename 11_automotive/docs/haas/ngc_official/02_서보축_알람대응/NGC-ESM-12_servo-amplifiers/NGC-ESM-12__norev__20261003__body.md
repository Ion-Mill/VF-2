<!-- doc_id: NGC-ESM-12 | title: NGC - Servo Amplifiers - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---servo-amplifiers.html | retrieved_at: 2026-10-03T18:03:49 | retrieved_via: direct | original_file: NGC-ESM-12__norev__20261003.html | original_sha256: d8a5311dbe280a320d79d30cc402afae38e77d52fa0fe23d45245a0f2cc4eb2a | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-12 |
| title | NGC - Servo Amplifiers - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---servo-amplifiers.html |
| retrieved\_at | 2026-10-03T18:03:49 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-12\_\_norev\_\_20261003.html |
| original\_sha256 | d8a5311dbe280a320d79d30cc402afae38e77d52fa0fe23d45245a0f2cc4eb2a |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [12.1 Servo Amplifier Identification Guide](#tab_12-1-servo-amplifier-identification-guide_0)
* [12.2 Servo Amplifier Replacement](#tab_amplifier-replacement_0)
* [12.3 Servo Amplifier Troubleshooting](#tab_amplifier-troubleshooting_0)

## **Servo Amplifier** - Identification Guide

---

**RD0095**

Revision B - 07/2026

## Introduction

The 30A and 45A servo amplifiers are available in two versions **analog** and **digital**. Although the two types perform similar functions, they are **visually identical**, which means you cannot distinguish them by appearance alone.

The **only reliable way** to tell them apart is by checking the **part number**.
This document explains **where to locate the part number** on the amplifier and how to use it to determine whether the unit is analog or digital.

**Note:**For servo amplifier replacement procedures and compatibility information, refer to the following document: [Servo Amplifier - Replacement AD0280](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/servo-amplifier---replacement.html)

## 30A Servo Amplifier

# 30A Analog Servo Amplifier

![](https://www.haascnc.com/content/dam/haascnc/service/guides/references/servo-amplifier---identification-guide---rd0095/30A_analog_amplifier.png)

For the **30A Analog Servo Amplifier**, the part number is located **on the top of the amplifier housing**.

**Assembly Part Number:**  32-5550X

**Current Firmware:** V1.XX

# 30A Digital Servo Amplifier

![](https://www.haascnc.com/content/dam/haascnc/service/guides/references/servo-amplifier---identification-guide---rd0095/30A_digital_amplifier.png)

For the **30A Digital Servo Amplifier**, the part number is located **on the top of the amplifier housing**.

**Assembly Part Number:**  32-9118X

**Current Firmware:** V2.XX

## 45A Servo Amplifier

# 45A Analog Servo Amplifier

![](https://www.haascnc.com/content/dam/haascnc/service/guides/references/servo-amplifier---identification-guide---rd0095/40A_analog_amplifier.png)

For the **45A Analog Servo Amplifier**, the part number is located **on the top of the amplifier housing**.

**Assembly Part Number:**  32-3551X

**Current Firmware:** V1.XX

# 45A Digital Servo Amplifier

![](https://www.haascnc.com/content/dam/haascnc/service/guides/references/servo-amplifier---identification-guide---rd0095/40A_digital_amplifier.png)

For the **45A Digital Servo Amplifier**, the part number is located **on the top of the amplifier housing**.

**Assembly Part Number:**  32-9119X

**Current Firmware:** V2.XX

# 12.1 Servo Amplifier Replacement

## **Servo Amplifier** - Replacement

---

**AD0280**

Revision C - 08/2026

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/servo-amplifier---replacement---ad0280/servo_amp_intro.jpg)

This procedure tells you how to remove a servo amplifier and install a smart servo amplifier.

If you replace a servo amplifier that was made before 2007, refer to [PCB Auxiliary (AUX) Load - Replacement](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/servo-amplifier---pcb-auxiliary--aux--load---replacement.html).

**Document Applies to these Parts**

* **93-32-5549**  AMP, 90A BL SMART
* **93-32-5550J**  AMP, 30A BL SMART
* **93-32-5550N**    AMP, 30A BL SMART
* **93-32-3551J**       AMP, 45A BL SMART
* **93-32-3551N**     AMP, 45A BL SMART
* **93-32-5552G**     AMP, 60A BL SMART
* **93-4988**      AMP,  60A BL SMART
* **93-4989**      AMP,  90A BL SMART
* **93-5088**AMP, 30A DIGITAL AMP
* **93-5089**AMP, 45A DIGITAL AMP

**NOTE:** The Digital Amplifiers are fully backward compatible with BL Smart Amplifiers.

**NOTE:** Refer to the [Servo Amplifier - Identification Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/reference-documents/servo-amplifier---identification-guide---rd0095.html) for more information.

**Warning**: **Do not** use power tools on the amplifier terminal block screws. Damage caused by the use of power tools is not covered under warranty and may result in the warranty being voided.

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

## Replacement

### 1

Push **[POWER OFF]**.

Set the main circuit breaker to the **[OFF]** position.

Lock the main circuit breaker. Use an approved lock with an approved safety tag.

**Danger:** If the voltage indicator light is on, do not touch the electrical components. The high voltage in the electrical cabinet can kill you. Wait for the voltage indicator LED to go off fully.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/servo-amplifier---replacement---ad0280/Amp-Replacement_Remove_Amp.png)

### 2

Disconnect the cables from the used servo amplifier. Remove the used servo amplifier.

Install the replacement smart servo amplifier [1].

Connect the current command [2] cable.

Connect the servo cables [3]. The cables are color-coded.

Connect the high-voltage jumpers [4] to the terminals on the adjacent servo amplifier.

# 12.1 Servo Amplifier Troubleshooting Guide

## **Servo Amplifier** - Troubleshooting Guide - NGC

---

**TG0125**

Revision F - 8/2026

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/servo_amplifiers_overview_troubleshooting_guide_Rev_B.png)

There are four versions of Haas amplifiers. 30A [1], 45A [2], 60A [3], and 90A [4]. All four operate the same way.

Smart Amplifier assemblies are powered from the 320 VDC Bus from the Vector Drive assembly or Minimill Power Supply. They each have a red LED FAULT light, and a green LED POWER ON light to show the status of the amplifier.

**Note:**Machines may be equipped with either Digital or Analog servo amplifiers, depending on the machine configuration.

To determine which type of amplifier is installed on your machine, refer to [Servo Amplifier - Identification Guide - RD0095](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/servo-amplifier---identification-guide---rd0095.html#gsc.tab=0) before troubleshooting.

**Warning**: **Do not** use power tools on the amplifier terminal block screws. Damage caused by the use of power tools is not covered under warranty and may result in the warranty being voided.

**Download and fillout the Amplifier Inspection Report Checklist below before replacing any parts.**

[Amplifier Inspection Report Checklist](https://www.haascnc.com/content/dam/haascnc/service/guides/references/amplifier-inspection-checklist/ID0003_Rev_B.pdf)

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
| **Alarm 993** AMPLIFIER SHORT CIRCUIT and **1.993 - 11.993**  **Alarm 2040** VECTOR DRIVE OR SPINDLE AMPLIFIER-SHORT CIRCUIT | Amplifier detected a short. | Check cables for contamination or damage. |
| Refer to the service news [HBC-N-03/17/25](https://hbc.haascnc.com/service/op/content/view/45) for how to troubleshoot if the alarm intermittently occurs while the machine is running. |
| The amplifier has a internal short circuit. | Do the **Amplifier Short Circuit Inspection**section. **Note:** If a short-circuit is found, inspect the cable and motor for a short circuit before installing a new amplifier. |
| Terminal connections are not tight. | Check that all terminal connections are tight and secure. |
| **Alarm 986** CALIBRATION FAULT and **1.986 - 11.986** | Amplifier internal calibration. | Check the command cable from the Maincon PCB to amplifier. Check the 320 VDC voltage to amplifiers. |
| **Alarm 986** CALIBRATION FAULT when first powering on machine. The  alarm requires the machine to have power cycled | Amplifier internal calibration | Refer to the service news [HBC-N-03/17/25](https://hbc.haascnc.com/service/op/content/view/45) for what to troubleshoot on the amplifier. |
| **Alarm 992** AMPLIFIER OVER CURRENT and **1.992 - 11.992** | Axis mechanical blockage. | Axis mechanical blockage. |
| **Alarm 994** AMPLIFIER OVER LOAD and **1.994 - 11.994** | Incorrect application. | Change speed and check for tool damage. |
| Axis mechanical blockage. | Remove Blockage. |
| **Alarm 991** AMPLIFIER OVER TEMPERATURE and 1.994 - 11.994 | Problem with the cooling fan. | Check cooling fan. |
| **Alarm 1.9911 - 11.9911** Axis Amplifier Cable Disconnected | The cable connected to the amp is damaged or disconnected | Check that both ends of the cable going between the main processor and the servo amplifier are fully connected. Check the entire length of the cable to see if there is any damage. |
| The firmware on the amplifier is outdated | If the alarm can be reset from the Haas Control, the amplifier needs to be replaced. If the alarm gets reset, he machine needs to be power cycled **before running the machine again**. Refer to the [HBC-N-03/14/2025](https://hbc.haascnc.com/service/op/content/view/45) for more details. |
| NGC machines equipped with a 60A servo amplifier  **Alarm 3.991** Z-AXIS AMPLIFIER OVER TEMPERATURE. | Erroneous alarm generated by electrical noise. | * Install a ferrite filter P/N 64-1252 to the Z-axis motor power cables [2]. * If the machine has the ferrite filter installed and the alarm persist replace the 60A servo amplifier with (P/N 93-32-5552F or later). * If the machine already has the 60A servo amplifier (P/N 93-32-5552F or later), check the amplifier for a overheat condition. Look at the servo fan for correct operation and the cutting application before changing any parts.  ![](https://service.haascnc.com/sites/default/files/Locked/3/ferrite-filter.png) |
| **Alarm 4.9921** Velocity Error Too Largeappears on a Tool Room Lathe 1/2. | Mis wired Spindle Amplifier. | See the **TL Spindle Amplifier Inspection** section below for the corrective action. |
| Axis instability, humming, vibration, or oscillation when installing a digital amplifier. | Compatibility issue between digital amplifiers and Size 02 and Size 04 servo motors. | Refer to [HSA-0083-04/13/2026](https://www.haascnc.com/service/distributor-only/sa---service-alert---news/small-servo-motor-with-digital-amplifiers.html#gsc.tab=0) for the corrective action. |
| Pocket Mill with 8K Spindle is receiving **Alarm 992** AMPLIFIER OVER CURRENT | The machine is equipped with digital spindle motor amplifier. | Inspect the spindle motor amplifier to determine whether it is a digital or analog amplifier. Refer to  [Servo Amplifier - Identification Guide - RD0095](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/servo-amplifier---identification-guide---rd0095.html#gsc.tab=0) for identification instructions. If a digital amplifier is installed, replace it with an analog amplifier. |
| UMC-500 poor cut quality | The machine is equipped with digital axis amplifiers. | Inspect the axis amplifiers to determine whether they are digital or analog amplifiers. Refer to [Servo Amplifier - Identification Guide - RD0095](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/servo-amplifier---identification-guide---rd0095.html#gsc.tab=0) for identification instructions. If digital amplifiers are installed, replace them with analog amplifiers. |

## Mechanical Blockage

**Corrective Action:**

Make sure the axis has a clear path of travel. Tools, part fixtures, or workpieces that are too large can crash into the machine enclosure.

Look at the machine's alarm history. Overload alarms followed by over current alarms are a sign of a crash.

Look at the machine enclosure, spindle and tooling for damage. Damage to the tooling, fixtures and enclosure are signs of a crash.

If there are no signs of a crash, inspect the ballscrew and linear guides. They must move or turn freely by hand.

## Amplifier Short Circuit Inspection

Check the amplifier for a short. Power off the machine. Disconnect the cables for the axis servo motor at the amplifier that generates the alarm.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/amplifier-short-to-gnd.png)

Set the multimeter to ohms, and take the following reading:

* Place the black lead on the ground screw [1].
* Place the red lead on the RED terminal [2] and record the resistance reading.
* Repeat this with the red lead on theWHT, BLK, HV(+), and HV(-) terminals and record the resistance reading for each.

**Note:** If the multimeter allows you to set the Ohms range, set it to the MegaOhms range.

If the multimeter does not show (O.L) for each of these readings then the amplifier is damaged.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/amplifier-short-to-dc-bus-negative.png)

Set the multimeter to ohms, and take the following reading:

* Place the black lead on the HV (-) terminal [1].
* Place the red lead on the RED terminal [2] and record the resistance reading.
* Repeat this with the red lead on theWHT, and BLK terminals and record the resistance reading for each.

**Note:**If the multimeter allows you to set the Ohms range, set it to the MegaOhms range.

The multimeter should show a resistance in the MegaOhms range for each of these readings.

If the resistance reading is very low then the amplifier is damaged.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/amplifier-short-to-dc-bus-positive.png)

Set the multimeter to ohms, and take the following reading:

* Place the black lead on the HV (+) terminal [1].
* Place the red lead on the RED terminal [2] and record the resistance reading.
* Repeat this with the red lead on theWHT, and BLK terminals and record the resistance reading for each.

**Note:**If the multimeter allows you to set the Ohms range, set it to the MegaOhms range.

The multimeter should show a resistance in the MegaOhms range for each of these readings.

If the resistance reading is very low then the amplifier is damaged.

## Servo Motor Short Circuit Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/Measure_servo_motor_resistance_amp_tsg.png)

**Corrective Action:**

**Check the cables for a short:** Make sure the axis servo motor cables are not contaminated or pinched. Contaminated or pinched cables can cause a short. Replace the cables if necessary.

**Inspect the servo motor.** Disconnect and inspect the power cable connector at the motor. Make sure that there is no coolant contamination. Coolant contamination can cause this alarm and damage the amplifier. Measure the resistance from the pins labeled A, B and C at the motor connector to chassis ground.

* The reading should show an open circuit.
* If there is not open resistance, the servo motor is at fault.

## Review the Part Program

**Corrective Action:**

The machine load is too high. Decrease the feeds to decrease the machine load. Examine the cutting tool for damage.

Test the axis that generates the alarm. Write a program in MDI to move the axis. If any movement at any feed rate causes the alarm, then the servo amplifier is at fault.

## Low Voltage Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/maincon_check_J19_low_voltage_power_supply.png)

**Corrective Action:**

Measure the low voltage power supply voltage levels at the Maincon PCB. Make sure you do not short or cross your multimeter pins.

Cycle power to the machine. If the fault stays, then the amplifier is faulty.

If every axis amplifier in the machine generates the alarm at the same time, and the low voltage power supply is correct, then the Maincon PCB may be at fault.

|  |  |
| --- | --- |
| **Pins** | **Correct Voltage** |
| +5 and GND | +4.90 to +5.20 V dc |
| +12 and GND | +11.85 to +12.50 V dc |
| -12 and GND | -11.85 to -12.50 V dc |

## Cooling Fan

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/Measure_Voltage_Across_The_Pins_On_The_90B_Cable_For_The_Servo_Amplifier_Cooling_Fan.png)

**Corrective Action:**

**Note:**The maximum temperature for safe operation of Haas CNC machines is 122 °F (50 °C). The amplifier over temperature sensor will trigger at 195 °F (90 °C).

Make sure the cooling fan for the servo amplifiers operates correctly.

If the fan does not operate correctly, measure the voltage it receives. Disconnect the cable from the cooling fan. Measure the voltage between the leads of the cable. The correct voltage 120 VAC.

* If the cable has the correct voltage, the cooling fan is defective.

## TL 1/2 Spindle Amplifier Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/ngc-troubleshooting-videos-page/servo-amps/TL-Spindle-Amp-Wiring.png)

**Corrective Action:**

Open the electrical control of the machine and inspect the phasing of the spindle amplifier.

**Note:**Refer to the image to verify the correct phasing between the spindle motor and spindle amplifier on a Toolroom Lathe 1/2.

## Electrical Diagram

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/servo-amplifier---troubleshooting-guide/sigma5_electrical_schematic.png)