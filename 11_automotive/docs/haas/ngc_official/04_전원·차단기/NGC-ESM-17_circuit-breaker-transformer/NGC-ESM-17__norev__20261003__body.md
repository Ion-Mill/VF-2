<!-- doc_id: NGC-ESM-17 | title: NGC - Circuit Breaker and Transformer - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---circuit-breaker-and-transformer.html | retrieved_at: 2026-10-03T18:04:01 | retrieved_via: direct | original_file: NGC-ESM-17__norev__20261003.html | original_sha256: a8614bb1aeb2cdfdd43437fd015bfe5c0a681acfd025a567ed085ba3140a168f | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-17 |
| title | NGC - Circuit Breaker and Transformer - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---circuit-breaker-and-transformer.html |
| retrieved\_at | 2026-10-03T18:04:01 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-17\_\_norev\_\_20261003.html |
| original\_sha256 | a8614bb1aeb2cdfdd43437fd015bfe5c0a681acfd025a567ed085ba3140a168f |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [17.1 Main Circuit Breaker - Replacement](#tab_main-circuit-breaker---replacement_0)
* [17.2 Main Transformer - Replacement](#tab_main-transformer---replacement_0)
* [17.3 Main Transformer - Troubleshooting](#tab_troubleshooting_0)
* [17.4 Circuit Breaker - Troubleshooting](#tab_circuit-breaker---troubleshooting_0)
* [17.5 Terminal Block - Replacement](#tab_17-4-main-trans_0)

# 17.1 Main Circuit Breaker - Replacement

## **Main Circuit Breaker** - Replacement

---

**AD0286**

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-circuit-breaker---replacement/CB_Breaker_cover_image.png)

This procedure tells you how to replace the main circuit breaker in the electrical cabinet. The circuit breaker in the kit can be different from the installed circuit breaker, but it operates the same.

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

## Document Applies to these Parts

Kit Required: CIRCUIT BREAKER REPLACEMENT KIT

|  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| **Breaker Amperage** | 15A | 20A | 40A | 80A | 125A |
| **Kit P/N** | 93-2550 | 93-2551 | 93-2552 | 93-2553 | 93-2554 |

## Main Circuit Breaker - Replacement

### 1

Push **[POWER OFF]**.

**Danger:** Disconnect the electrical service to the machine.

**Important:** With and AC Volt meter, measure across the L1 - L3 on top of the main breaker. If AC voltage is still present go to the source and check that the correct service breaker was disconnected.

**Danger:** After you disconnect the service to the machine, wait for the LEDs on the early power-fault detection module (EPFDM) and the vector drive to go off fully. This may take 20 or more minutes.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-circuit-breaker---replacement/CBreaker_Repl_Remove_Old_Brk2.png)

### 2

Record the color sequence of the main electrical supply wires [1] that go to the circuit breaker [2]. Disconnect the wires.

Disconnect the contactor cables [3] from the circuit breaker.

If the contactor [5] is installed on the rear of the circuit breaker, disconnect the (3) transformer cables [4] at the transformer.

Remove the circuit breaker assembly [2] from the machine.

Remove the circuit breaker from the breaker mount bracket.

Discard the circuit breaker if it is not under warranty.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-circuit-breaker---replacement/CBreaker_Repl_Assemble_Breaker.png)

### 3

Use (2) long screws [4] to attach the new circuit breaker [2] to the breaker mount bracket [1].

Select the holes on the bracket that allow the switch on the circuit breaker to fit through the hole on the locking bracket [5].

Use (3) short screws [3] to attach the locking bracket [5] to the breaker mount bracket [1].

Select the holes on the locking bracket that allow the toggle [6] to move freely.

**Note:**The circuit breaker you receive may look different from the one illustrated. Assembly is the same.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-circuit-breaker---replacement/old_contactor_with_new_contactor.png)

### 4

Do this step only if the contactor was installed on the rear of the used circuit breaker assembly.

* Install the the contactor adapter bracket P/N 25-12101 [2] to the back wall of the cabinet.
* Install the contactor [3] included in the kit to the adapter bracket.
* Connect the cables going to the contactor.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-circuit-breaker---replacement/cbreaker_install_new_2.png)

### 5

The bracket for the circuit breaker assembly has (2) sets of holes to attach it to the electrical cabinet.

Look at the circuit breaker.

* If the circuit breaker is the same as a breaker in the first group [1], use the top set of holes.
* If the circuit breaker is the same as a breaker in the second group [2], use the bottom set of holes.

Attach the circuit breaker assembly to the electrical cabinet.

Install the main breaker cover. Refer to Main Breaker Cover Installation procedure included in the kit.

Connect the cables. Refer to [Haas Main CIrcuit Breaker - Torque Specifications](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/haas-main-circuit-breaker---torque-specification.html) for what value to torque the circuit breaker power leads.

Turn on the electrical service to the machine, and test for correct operation and phasing.

# 17.2 Main Transformer - Replacement

## **Main Transformer** - Replacement

---

**AD0408**

## Introduction

This section applies to all size main transformer replacements and machine models.

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

## Transformer Replacement

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer-replacement---ad0408/trans_remove_1A.png)

### 1

Turn off the main breaker and lock out the machine from use. Verify there is no power going to the transformer with a volt meter.

Loosen the (4) screws and remove the cover plate [1].

**NOTE:** Before removing the transformer wires take couple pictures of where cables are connected.

Label and disconnect the wires from the appropriate taps [2], TB2 the 240 VAC terminal block [3], and TB1 the 120 VAC terminal block [4].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer-replacement---ad0408/trans_remove_2.png)

### 2

Insert a piece of wood [1] (1"X4" approx.) to support the transformer. Remove the (4) corner bolts only and remove the transformer.

Install the replacement transformer in the reverse order it was removed.

**Important:** If the transformer comes with its own hardware, you **must** use it. **Do not** reuse hardware

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/low-to-high-voltage--40hp-conversion-kit---ad0627/Transformer-Hardware.png)

### 3

Install the hardware shown in the image.

1. Hex Head Bolt
2. Lock Washer
3. Black Oxide Hard Washer

Apply blue loc-tite and torque the (4) bolts to 15 ft-1b (20 Nm).

**NOTE:** Do not over torque the bolts as it will cause the back plate to warp.

## Thermal Sensor

The following section applies to only the transformers that are equipped with a thermal sensor (see table below).

|  |  |  |
| --- | --- | --- |
| **Transformers with a Thermal Sensor** | | |
| 32-5800H | 32-5810K | 32-5811C |
| 32-5814B | 32-5822D | 32-5825F |
| 32-5826 | 32-5829 | 32-5830A |
| 32-5831A | 32-5832A | 32-5833B |
| 32-5834B | 32-5835B | 32-5836 |
| 32-5837 | 32-5830E |  |

For **Coldfire Control:**

* Plug the thermal sensor to I/O PCB at P82.
* Change parameter 1397 TRANSFORMER OVER HEAT MAX TIME to 60000.  A value of zero will disable this feature.
   **Note:** If the machine software does not have parameter 1397 TRANSFORMER OVER HEAT MAX TIME available, tuck the overheat cable inside the wire track.

For **Next Generation Control:**

* Plug the thermal sensor I/O at P34.
* Upload a new configuration file. The configuration file is updated when the part is ordered.

# 17.3 Power On/Off Circuit - Main Transformer - Troubleshooting Guide

## **Power On/Off Circuit - Main Transformer** - Troubleshooting Guide - NGC

---

**TG0004**

## Introduction

This document will show you how to troubleshoot the power on/off circuit and the main transformer on a machine with the Next Generation Control.

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

## Power On/Off Circuit

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/Machine_Power_ON_OFF_Circuit_Diagram.png)

## Electrical Wiring for Haas Machines

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptoms** | **Probable Cause** | **Corrective Action** |
| **Alarm 2095** TRANSFORMER OVERHEAT occurs at Power on. | The machine detected a open circuit from the thermal switch at the transformer. | Make sure the sensor is connected to the pigtail on P34 on I/O PCB. If is connected, jumper the wires. If alarm goes away check the overheat sensor by measuring the temperature on the transformer the sensor is normally closed until trip point 275F / 135C. |
| The transformer overheat cable pins making intermittent contact. | Check the connector to make sure the connector is crimped correctly. |
| **Alarm 2095** TRANSFORMER OVERHEAT occurs after the machine has been on for a long time, or during operation. | The speeds and feeds are too high. | Make sure the feeds and speeds are correct for the work. |
| The transformer overheat cable pins making intermittent contact. | Check the connector to make sure the connector is crimped correctly. |
| The machine is located in a hot environment. | Monitor the transformer temperature throughout the day. If the internal transformer exceeds 275F / 135C degrees throughout the day add the CABCOOL option. |
| **Alarm 175** GROUND FAULT DETECTED. | There is a short circuit in one of the 115 / 230 VAC components. | Refer to the Ground Fault Circuit Monitor section in the [Next Generation Control - I/O PCB - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/next-generation-control---i-o-pcb---troubleshooting-guide.html). |
| The Main Circuit Breaker Trips When you Press the **[POWER ON]** Button. | There is a short-circuit in the main transformer. | To troubleshoot the main transformer follow these simple steps:  1. Turn off the main circuit breaker. 2. Disconnect the 120 and 240 VAC output wires from the transformer. 3. Turn on the machine. If the breaker trips the transformer is damaged. |
| The Vector Drive has a short-circuit. | Refer to the: [Vector Drive - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/vector-drive---troubleshooting-guide.html) |
| The 320 VDC Power Supply has a short circuit. (OM, OL, MM, TM, TL, SR-100 Only) | Refer to the: [High Voltage Power Supply (MMPS) Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/high-voltage-power-supply--mmps----troubleshooting-guide.html). |
| One of the servo amplifiers has a short-circuit. | Refer to the [Servo Amplifier - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/servo-amplifier---troubleshooting-guide---ngc.html). |
| The incoming voltage is not correct. | 1. Using a volt meter. Measure the incoming voltage at the top of the main circuit breaker. 2. Make sure the incoming voltage is within the main transformer tap range. |
| **Alarm 9100.005** POWER SUPPLY UNDEFINED. Pass/Fail lamps lit on PSUP PCB. | There is a missing phase on the transformer. | Check the three phase 240 VAC output on the transformer TB2. If there is a missing phase check for a loose connections on the terminal block TB2. Trace the missing phase all the way back to the main circuit breaker. |
| The machine will not turn on when the **[POWER ON]** button is pressed. | The main circuit or service panel circuit breaker is turned off. | Make sure the main circuit breaker or service panel breaker is turned on. |
| The T5 transformer jumper is not set correctly or the T5 transformer is defective. | See the T5 transformer troubleshooting section below. |
| There is problem with the **[POWER ON]** or **[POWER OFF]** circuit. | Make sure that the wires going to the **[POWER ON] [POWER OFF]** contactors terminals are secure. Check the cable from SKIBF to PSUP PCB see the above electrical diagrams. |
| The main circuit breaker is defective. | 1. Turn off the machine's main circuit breaker. 2. Turn off the electrical service to the machine. 3. Make sure that there is no voltage to the machine. 4. Turn the machine's main circuit breaker to the ON position. 5. Measure continuity between the top and bottom poles. If there is no continuity, replace the circuit breaker. |
| The K1 contactor coil is not receiving power or the wires are not connected on the correct terminals on the coil. | Check that the K1 contactor is receiving approximately 24 VAC from the T5 transformer. See above diagrams. |
| The auto off circuit is open. | Check the cable connection from the PSUP (P17) to I/O PCB (P56). |
| Machine equipped with CABCOOL shuts off intermittently. | The main transformer is not tapped in the correct range. | Measure the incoming voltage and check that the main transformer taps are placed on the correct range.  **Note:** The main transformer generates a 240V/120V .  The cabcool runs off the 120V, if the 120V is not at nominal, then when the Cabcool turns on, the voltage can sag and cause the machine to turn off. |
| The CABCOOL thermal switch outlet (32-0376A) wiring is on the same phase that PSUP monitors for low voltage condition. | Refer to the [CABCOOL - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/Cabinet-Cooler-TSG.html). |
| The main transformer installed on the machine is not compatible with the CABCOOL option.  **Note:**  This probable cause does not apply to machines with the 480V option. | Refer to the [CABCOOL Installation](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/cabinet-cooler---installation---ad0071.html) procedure for correct power requirements. |
| The machine will not turn on. | The F1 fuse is blown on the PSUP. | Check F1 fuse on PSUP and replace if necessary.  Check the JP1 jumper to be installed on PSUP if the machine has a High Voltage service input (380-480 VAC).  **Note:**If the machine has a 60 hp vector drive, make sure a 2A CERAMIC FUSE is installed at F1. |

## T5 Transformer Troubleshooting

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/Measure_voltage_pins_3_and_8_on_T5_transformer.png)

The T5 transformer is a step down transformer that steps down the incoming voltage to approximately 24VAC. When the **[POWER ON]**  button is pressed this voltage is applied to the coil on the K1 contactor, then the machine will turn on.

**Transformer Primary Check:**

1. Make sure the jumper is in the correct position for the input voltage.
2. Disconnect the T5 transformer from the PSUP PCB.
3. Find the cable for the T5 transformer. Measure the resistance between pins 3 (black) and 8 (yellow) on the cable. Use a multimeter set to ohms.
4. When the T5 transformer operates correctly, you have one of these conditions:

Low Voltage T5 Transformer (32-1964)

* Jumper at (221-240V) position the multimeter measures between 54 - 66 ohms.
* Jumper at (180-220V) position the multimeter measures between 45 - 55 ohms.

High Voltage T5 Transformer (32-1965)

* Jumper at (441 - 480V) position the multimeter measures between 216 - 264 ohms.
* Jumper at (381- 440V) position the multimeter measures between 180 - 220 ohms.
* Jumper at (340- 380V) position the multimeter measures between 153 - 187 ohms.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/Measure_Voltage_pins_1_5_6_T5_transformer.png)

**Voltage Check**

1. Make sure the jumper is in the correct position for the input voltage.
2. Use a multimeter set to Volts AC measure across pins 1 and 5, 1 and 6, 5 and 6.

* You should measure 21.6 - 26.4 VAC between pins 1 and 5.
* You should measure 10.8 - 13.2 VAC between pins 1 and 6.
* You should measure 10.8 - 13.2 VAC between pins 5 and 6.

## Electrical Diagrams

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/electrical_diagram_overview_power_on_off_3.png)

**Machine Power On/Off Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/skibf_to_psup_diagram_4.png)

**PSUP (P16) to SKIBF (J20) / SKIBF (J5) Detail Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/psup_to_io_4.png)

**PSUP (P17) to I/O PCB (P56) Detail Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/next-generation-control---power-on-off-circuit,-main-transformer---troubleshooting-guide/k1_t5_to_psup.png)

**T5 to PSUP (P13) / K1 to PSUP (P12) Detail Diagram**

# 17.4 Circuit Breaker - Troubleshooting Guide

## **Circuit Breaker** - Troubleshooting Guide

---

**TG0051**

Circuit Breaker Testing

## Symptoms Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Probable Cause** | **Solution** |
| **Alarm 552**TRIPPED CIRCUIT BREAKER | There is a short circuit on the Coolant Pump Motor or Cable. | Refer to the [Standard Coolant - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/standard-coolant---troubleshooting-guide---ngc.html): **Defective Pump** section. |
| The circuit breaker is defective. | Test the circuit breaker inrush current and duration time.  Refer to the **Coolant Pump Breaker Troubleshooting** section below. |
| The PSUP PCB is defective. | If the machine generates alarm 552 and the circuit breaker did not trip, then the PSUP may be at fault.  Refer to the [PSUP PCB Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/next-generation-control---power-distribution-pcb-and-pfdm---trou.html): **PCB Inspection component** section. |

## Coolant Pump Circuit Breaker

This guide is meant to be used for troubleshooting circuit breakers 61-7361 (10A) and 61-7352 (15A) used for machine coolant applications.
**Note:** This guide does not apply to the Variable Flow coolant or the Shower coolant option as these use VFDs.

**Required Tools:**

* **AC Clamp Meter** able to measure **Inrush Current**

The table below shows the coolant pump and circuit breaker combination used for the various coolant options.

|  |  |  |  |
| --- | --- | --- | --- |
| **Coolant Options** | **Coolant Pump Motor** | **Circuit Breaker** | |
| **Motor Rating / Phases** | **Current Rating** | **Location** |
| Standard flood coolant | 1.00HP / 3PH or 0.25HP / 1PH | 10A | PSUP PCB |
| High pressure flood coolant | 1.50HP / 3PH | 10A | PSUP PCB |
| TSC 300 PSI | 1.50HP / 3PH | 15A | PSUP PCB or TMD PCB |
| TSC 1000 PSI | 3.00HP / 3PH |

## Measure the Inrush Current and Duration Time

**Figure 1:** I/O PCB motor power cable connections.  **Figure 2:** TMD PCB motor power cable connection.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/circuit-breaker-troubleshooting-guide/circuit_breaker_troubleshooting_guide_tmd_connectors.png)

### 1

Trace back the pump power cable to locate the connection point inside the electrical control.

This will either be on the I/O PCB P29, P31 or the TMD PCB P1 which is mounted on the I/O hinge door depending on the machine.

**NOTE FOR TSC**

If the strip length on the TSC pump power cable is too tight to fit a current clamp around the individual conductors, the inrush and nominal running current can be measured from cable **33-1980** connected to **I/O PCB P30**.

If the pump power cable is connected to the **I/O PCB**. On cable **33-1980** **the gray conductor** is **phase A (77)**, the **orange is phase B (78)**, and the **brown is phase C (79)**.

If the TSC pump power cable is connected to the **TMD PCB**, then the inrush and nominal running current can be measured from cable **33-0987B connected to P4** on the **TMD PCB**.

On cable **33-0987B** the **red conductor is phase A (77)**, **white is phase B (78)**, and **black is phase C (79)**.

**Figure 3:** Correct method to measure current.  **Figure 4:** Incorrect method to measure current.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/circuit-breaker-troubleshooting-guide/circuit_breaker_troubleshooting_guide_ac_clamp_meter.png)

### 2

Using a current clamp meter set to measure the **Max/Inrush AC** current, clamp the meter around a single conductor on the cable.

Turn the pump on and measure the inrush current and its duration time which is the time from the moment the pump is turned on to the time the circuit breaker trips.

Repeat this 2-3 times making sure to record the inrush current and duration time. Repeat this step on all the remaining conductors on the power cable excluding the green ground conductor.

### 3

Compare the recorded inrush currents and duration times to the **NOMINAL COOLANT PUMP INRUSH CURRENT VALUES PER PHASE** table on **Figure 6**.

* If the breaker did not trip, measure the nominal running current of the pump as described in the section below.

**Figure 6:** Known nominal inrush values per motor phase for coolant pumps. Values are nominal +/- 20% of the value listed.

**NOTE:** For TSC and High Pressure Coolant options, do not measure the inrush current with the pump out of the coolant reservoir as these have a pressure switch which will alarm out.

|  |  |  |  |
| --- | --- | --- | --- |
| **Nominal Coolant Pump Inrush Current Values per Phase** | | | |
| Pump Motor | Red Conductor | White Conductor | Black Conductor |
| Phase A (77) | Phase B (78) | Phase C (79) |
| Rating / Phases | Inside Coolant Reservoir | Inside Coolant Reservoir | Inside Coolant Reservoir |
| 0.25HP / 1 PH (SINGLE PHASE MOTOR) | - | 5 A | 5 A |
| 1.00HP / 3PH | 17 A | 17 A | 17 A |
| 1.50HP / 3PH (TSC) | 25 A | 25 A | 25 A |
| 3.00HP / 3PH (TSC) | 32 A | 32 A | 32 A |

## Measure the Nominal Running Current

To measure the nominal running current of the pump, the coolant hose at the machine needs to be disconnected to prevent head pressure from skewing the nominal running current measurement.

**IMPORTANT:  This does not apply to TSC and the High Pressure Coolant option.**

**Figure 7:** Pump hose for Flood Coolant.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/circuit-breaker-troubleshooting-guide/circuit_breaker_troubleshooting_guide_disconnect_coolant_pump.png)

### 1

Disconnect the coolant hose [7] from the machine and secure the hose tightly to the coolant tank reservoir. This is important as not securing the hose will cause it to spray coolant everywhere.

**Figure 8:** Correct method to measure current.  **Figure 9:** Incorrect method to measure current.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/circuit-breaker-troubleshooting-guide/circuit_breaker_troubleshooting_guide_ac_clamp_meter_section_2.png)

### 2

Using a current clamp meter set to measure nominal AC current, clamp the meter around a single conductor on the power cable. After checking the pump hose is secured, turn the pump on and let it run for 5 seconds.

Record the nominal running current from the current clamp and then stop the pump. Repeat this step for all the remaining conductors on the power cable making sure to record the nominal running current for each conductor excluding the green ground conductor.

### 3

Remove the pump from the coolant reservoir and repeat step 2 and 3 with the coolant pump outside of the coolant reservoir.

### 4

Compare the recorded nominal running current values from step 2 and 3 to the known nominal running current values for the specific pump size as shown below.

* If the recorded nominal current values are within the known nominal current values +/- 20%, then the pump and circuit breaker are not faulty and the other parts of the coolant system should be inspected.
* If the recorded nominal current values are higher than the known nominal running current values shown, then the pump needs to be inspected for any faults which could be causing the higher running currents.

**Figure 10:** Known nominal running current values per motor phase for coolant pumps. Values are nominal +/- 20% of the value listed. For TSC and High Pressure Coolant options, do not measure the nominal running current with the pump out of the coolant reservoir as these have a pressure switch which will alarm out.

|  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| **Known Nominal Coolant Pump Running Current Values per Phase** | | | | | | |
| Pump Motor | Red Conductor | | White Conductor | | Black Conductor | |
| Phase A (77) | | Phase B (78) | | Phase C (79) | |
| Rating / Phases | Inside Coolant Reservoir | Outside  Coolant Reservoir | Inside Coolant Reservoir | Outside  Coolant Reservoir | Inside Coolant Reservoir | Outside  Coolant Reservoir |
| 0.25HP / 1 PH | - | - | 1.3 A | 0.6 A | 1.3 A | 0.6 A |
| 1.00HP / 3PH | 3 A | 1.2 A | 3 A | 1.2 A | 3 A | 1.2 A |
| 1.50HP / 3PH (TSC) | 3.0 A | Do not measure | 3.0 A | Do not measure | 3.0 A | Do not measure |
| 3.00HP / 3PH (TSC) | 4.5 A | Do not measure | 4.5 A | Do not measure | 4.5 A | Do not measure |

# 17.4 Main Transformer - Terminal Block - Replacement

## **Main Transformer** - Terminal Block - Replacement

---

**AD1003**

Revision A - 09/2026

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer---6-position-terminal-block---replacement---ad1003/TB2_Installed.png)

This procedure provides instructions for installing the TB2 240VAC replacement kit. The kit upgrades the existing 3-pole 4-port terminal block to a 3-pole 6-port terminal block.

**This document applies to the following service kits:**

* **93-6585** TERM.BLK 6POS/POLE XFMR TB2 REPLACEMENT

**Installation Requirements:**

* Philips Screwdriver
* Multi-Meter

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

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer---6-position-terminal-block---replacement---ad1003/Step_1.png)

Power off machine and disconnect main power plug then wait a few minutes to allow for power to fully dissipate.

Remove acrylic cover [1] by removing mounting screws.

Remove power out cables [2].

Remove power in cables [3].

**Note:** Cables can be disconnected using screw terminals shown behind acrylic cover [1].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer---6-position-terminal-block---replacement---ad1003/Step_2.png)

Remove mounting screws [1] to remove the terminal block [2].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/main-transformer---6-position-terminal-block---replacement---ad1003/Step_3.png)

Install new terminal block using the same mounting hardware.

Re-connect input power cables [1].

Power on machine and verify that 240VAC ±10% is coming from each phase section from the screw terminals [2].

After power verification, turn off machine then connect the previously removed output cables [3].

**Note:** Be sure to re-install acrylic protective covers that were removed.