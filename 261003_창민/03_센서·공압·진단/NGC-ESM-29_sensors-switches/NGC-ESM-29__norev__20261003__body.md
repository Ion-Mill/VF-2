<!-- doc_id: NGC-ESM-29 | title: NGC - Sensors and Switches - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---sensors-and-switches.html | retrieved_at: 2026-10-03T18:03:26 | retrieved_via: direct | original_file: NGC-ESM-29__norev__20261003.html | original_sha256: 79144a310667fa6698688a5c05242e73eb5e91f7509ae3a3c3785bc8b5557788 | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-29 |
| title | NGC - Sensors and Switches - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---sensors-and-switches.html |
| retrieved\_at | 2026-10-03T18:03:26 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-29\_\_norev\_\_20261003.html |
| original\_sha256 | 79144a310667fa6698688a5c05242e73eb5e91f7509ae3a3c3785bc8b5557788 |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [29.1 Analog Sensors](#tab_analog-sensors_0)
* [29.2 Proximity Sensors](#tab_proximity-sensors_0)
* [29.3 Safety Interlocks](#tab_safety-interlocks_0)
* [29.4 Light Curtain](#tab_light-curtain_0)
* [29.5 Pressure Sensors](#tab_pressure-sensors_0)

# 29.1 Analog Sensors - Troubleshooting Guide

## **Analog Sensors** - Troubleshooting Guide - NCG

---

**TG0027**

Revision C - 12/2025

## Analog Input Troubleshooting Video

The following service video provides information on troubleshooting analog inputs.

**Note:** This service video is for reference only and does not replace the written procedure.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/chc-maincon-mocon-software-update/Analog_Sensor_Gauges_4.png)

A Haas machine, depending on the vintage, has anywhere between one and eight analog sensors in various systems throughout the machine. All of these sensors share a common ground. A problem with one of these sensors could potentially affect the signal from all of them, making troubleshooting difficult. If you are troubleshooting a problem with any of these sensors, their cables or the Maincon/ I/O PCB follow these simple steps:

1. Look at the gauge page and identify the readings that look unreasonable. For example, if the spindle motor temperature [1] reads 0-degrees Fahrenheit and the shop is at 77-degrees this is not reasonable.
2. If one of these cables or sensors has a short-circuit. The gauge display will show several readings that are not reasonable.
3. Unplug each analog sensor one at a time. Look for the other gauge readings to return to something reasonable.

   **Note:** Some signals may take up to 30 seconds to react.
4. When you find the sensor that is causing the inaccurate readings you have most likely found the problem. Check the cable for damage. Check the sensor.

   **Note:** The cable or the sensor are more likely to be the cause of the problem than the Maincon / I/O PCB.

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| **Alarm 120** Low Air Pressure Or Flow | The compressed air supplied to the machine is below the minimum pressure or flow required. | Check for contamination in air pressure sensor. If contamination is found, sensor must be replaced.  **Important:**Ensure that air supply to the machine is clean and dry to avoid repeat failures. |
| Intermittent **Alarm 120**Low Air Pressure Or Flow.  The control reports different air pressure to the mechanical gauge.  Wiggling the cable on the pressure sensor changes the pressure reported on the control. | Defective 150 PSI pressure sensor. | Replace the pressure sensor.  [HBC - 10/10/2025](https://hbc.haascnc.com/service/op/content/view/101) |
| **Alarm 9916** EXCESSIVE THERMAL COMPENSATION DISTANCE | There is electrical noise on the signal or the thermal sensor is faulty. | Check the thermal sensor input in diagnostics and see if the signal is fluctuating.  If signal is fluctuating,  inspect the amplifiers and make sure there is a ferrite bead on ALL axis power cables. Check for loose connection or damage to the thermal sensor cable.  If all checks have been done the thermal sensor is faulty. |
| **Alarm 9940** AXIS THERMAL SENSOR FAULT | There is electrical noise on the signal or the thermal sensor is faulty. | Check the thermal sensor input in diagnostics and see if the signal is fluctuating.  If signal is fluctuating,  inspect the amplifiers and make sure there is a ferrite bead on ALL axis power cables. Check for loose connection or damage to the thermal sensor cable.  If all checks have been done the thermal sensor is faulty. |
| The cable or sensor is disconnected. | Check for loose connection or damage to the thermal sensor cable. |
| At Power On:  **Alarm 4.9940** AXIS THERMAL SENSOR FAULT  Is generated. | The I/O Main Firmware is outdated. | Make sure the I/O Main Firmware is version 4.09 or higher.  Refer to the [I/O Firmware Upgrade](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) procedure. |
| After software update machine generates  **Alarm 4.9916 / 9916**EXCESSIVE THERMAL COMPENSATION DISTANCE  OR  **4.9940 / 9940**AXIS THERMAL SENSOR FAULT | Invalid I/O configuration files. | Make sure that the thermal sensor is mapped to the correct I/O analog input. |
| This applies to UMC machines:  Axis thermal sensor cable is plugged into the wrong analog input. | Make sure the axis thermal sensor cable is plugged into P45 on the I/O PCB. |
| There is electrical noise on the signal or the thermal sensor is faulty. | Check the thermal sensor input in diagnostics and see if the signal is fluctuating.  If signal is fluctuating,  inspect the amplifiers and make sure there is a ferrite bead on ALL axis power cables. Check for loose connection or damage to the thermal sensor cable.  If all checks have been done the thermal sensor is faulty. |
| **ALARM 9941** CRASH DETECTED (spindle head accelerometer) | The machine detected a crash | Verify the program machine movements to make sure the machine does not crash |
| The Accelerometer unit, cable or spindle head CAN board is damaged | * Verify analog inputs are not 0 (cable unplugged) * I/O board minimum version 4.09 (update to latest if possible) * Spindle head CAN board minimum 1.10 (update to latest if possible * Make sure to take an error report **(SHIFT+F3)**, error reports will have information about the crash direction and magnitude in the JavaConsoleLog.txt file (refer to **Crash Detection Section** in the [Accelerometer Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/accelerometer---troubleshooting-guide.html) for further information) |
| **ALARM 966** EXCESSIVE TOOL IMBALANCE (board accelerometer) | Excessive tool vibration is generated by on board accelerometer | Verify that everything is properly balanced, such as tools and spindles |
| Reduce sensitivity using **Setting 245**   * **Setting 245** = Normal: Means that parameter 856 is directly used * **Setting 245** = Low: Means that parameter 856 is multiplied by 1.5 * **Setting 245** = Off: Alarm 966 will not be thrown.   NOTE: Setting 245 will not persist when the power is cycled  Please refer to the  [Accelerometer Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/accelerometer---troubleshooting-guide.html) for further information |
| Spindle motor temperature sensor fluctuating | Electrical noise around that area. | A ground wire should added from the motor lift bracket to the spindle heat shield. Refer to: [HSG-N 08-23-2024](https://service.haascnc.com/service-news/added-ground-wire-40t50t-gearbox-head). |

## NGC - Analog Sensor Information

**Note:** The connector location of these sensors can change,  please check the location on the screen.  Press **[DIAGNOSTIC]** and go to the **I/O** tab and search for keyword **"ANALOG"** and press **[F1]**.

The raw data analog sensors that are connected to the Maincon PCB, can be view under the Mocon tab.

|  |  |  |  |
| --- | --- | --- | --- |
| **Gauge Name / Analog Sensor** | **Analog Sensor Location** | **Analog Sensor Connector Location\*** | **Alarm / Warning** |
| **Mills:**TSC Pressure  **Lathe:**HPC Pressure | **Mills:**On the TSC pump.  **Lathe:**On the HPC pump. | I/O PCB P39.21 | **Mills:**Alarm 151 LOW THRU-SPINDLE COOLANT  **Lathe:**Alarm 8151 HPC LOW PRESSURE. |
| **EC-1600:** Y-axis temperature sensor. | On the Y-axis column. | I/O PCB P39.19 | N/A |
| **Lathe:**X-axis temperature sensor. | On the X-axis ballscrew ballnut. | I/O PCB P2.14 | N/A |
| Coolant Level | On the coolant level float. | I/O PCB P43.1 | Low coolant Icon will apper when the coolant level is low.  The Low Coolant Concentrate icon will appear when machine is equipped with the Coolant Refill option. |
| Coolant Temperature | On the coolant filter. | I/O PCB P44.1 | This temperature is for display purposes only and is shown on the gauge tab if the hardware is installed and enabled. |
| HPU Low Hydraulic Pressure | On the hydraulic power unit. | I/O PCB P48.7 | **Alarm 8134** LOW HYDRAULIC PRESSURE ON START  **Note:** UMC's that are equipped with Hydraulic Brakes for the B and C-axis can generate this alarm after a software upgrade if the hydraulic analog pressure sensor input is not mapped correctly.  Make sure the IO Configuration file has the correct mapping. |
| HPU Oil Temperature | On the hydraulic power unit. | I/O PCB P46.1 | Alarm 2096 HPU OIL TEMPERATURE TOO HIGH |
| Spindle Temperature | On the spindle head. | I/O PCB P39.24 | This temperature is for display purposes only and is shown on the gauge tab if the hardware is installed and enabled. |
| Spindle Motor Temperature | On the spindle motor . | I/O PCB P39.22 | Alarm 254 SPINDLE MOTOR OVERHEAT |
| Analog Air Pressure | On the air-lube cabinet. | I/O PCB P34.5 | Alarm 120 LOW AIR PRESSURE |
| Ambient Temperature | Refer to [Machine Ambient Temperature Sensor Location - Identification](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/reference-documents/machine-ambient-temperature-sensor-location---identification.html) document. | I/O PCB P51.1 | This temperature is for display purposes only and is shown on the gauge tab if the hardware is installed and enabled. |
| DC Voltage | Inside the vector drive (the sensor is not serviceable). | Maincon PCB J16 | Alarm 160 LOW INCOMING LINE VOLTAGE |
| AC Line Voltage | On the power-fail-detect-module (the sensor is not serviceable). | Maincon PCB J3 | Alarm 937 INPUT LINE POWER FAULT |
| Electronics Temperature | On the Maincon PCB (the sensor is not serviceable). | N/A | Alarm 253 ELECTRONICS OVERHEAT |

# 29.2 Proximity Sensor - Troubleshooting Guide

## **Proximity Sensor** - Troubleshooting Guide

---

**TG0114**

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/proximity-sensor---troubleshooting-guide/prox_sensor_tsg_overview_Rev_B.jpg)

The image shows the various types of proximity sensors used on Haas machines.

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| Positioning error or timeout alarms.  The diagnostic bit fluctuates while the monitored components are idle. | Noise or electrical interference from high-power cables. | Re-route the cable away from high power sources. Apply a ferrite bead to the sensor cables at the I/O board. |
| There is a poor connection, or a signal interference from contamination. | Clean, reseat connectors, and correct the cause of contamination. |
| The diagnostic bit does not change state. | There is metal particles on the face of the sensor. | Metal particles will not let the switch change state. Clean metal particles from the face of the proximity sensor. |
| The sense gap between the sensor face and the trip flag is not correct. | Align the trip flag or sensor, make sure the gap between the face of the sensor and the trip flag does not exceed 0.126 inces. |
| The cables or the I/O PCB is at fault. | Troubleshoot the cables or the I/O PCB. |
| **Alarm 145-147** AXIS LIMIT SWITCH alarms. | There is metal particles on the face of the proximity sensor. | Metal particles will not allow the sensor to change state. Clean metal particles from the face of the proximity sensor. |
| The proximity sensor connector has a loose connection. | Check the proximity M12 connector make sure the connection is tight. |
| The cable from the control to the proximity sensor has an open connection. | Check the proximity sensor and extenstion cables for damage. |
| The sense gap between the sensor face and the trip flag is not correct. | Align the trip flag or sensor, make sure the gap between the face of the sensor and the trip flag does not exceed 0.126 inces. |
| **Alarm 103-105** AXIS SERVO ERROR TOO LARGE alarms. | There is metal particles on the face of the proximity sensor. | Metal particles will not allow the sensor to change state. This will cause the axis to home in the opposite direction, causing the axis to hit the hard stop. Clean metal particles from the face of the proximity sensor. |
| **Alarm 165-167** AXIS ZERO RETURN MARGIN IS TOO SMALL | False sensor trip due to chip or home sensor problem, or the axis grid offset parameter is not set properly | Check for metal chips around the sensor or trip flag. Check the sensor for damaged cables. Set the axis grid offset parameter. |

## Signal Noise / Signal Interference

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/proximity-sensor---troubleshooting-guide/prox_sensor_tg_check_contamination_Rev_C.png)

Make sure that the proximity sensor cable is not damaged, and that it is separated from high-power spindle/axis/pump cables.

Make sure that the connectors and pins for the proximity sensors are not contaminated. Make sure the pins have not backed out of the connector.

Check for contamination on the proximity sensor. Contamination on the face of the proximity sensor can create a false signal. Fix the cause of the contamination.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/proximity-sensor---troubleshooting-guide/prox_sensor_tg_align_sensor.png)

Put a screw in front of the face of the sensor to test its operation. If the proximity sensor LED turns on and off, and the diagnostic bit changes status, then the sensor is working correctly. Align the trip flag so that it triggers the proximity sensor.

## Cable Damage

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/proximity-sensor---troubleshooting-guide/prox_sensor_tg_bad_cable_Rev_B.jpg)

Check the proximity sensor and extenstion cables for damage.

If there is no damage to the cables, refer to:

* [Next Generation Control - I/O PCB - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/next-generation-control---i-o-pcb---troubleshooting-guide.html)
* [Classic Haas Control - I/O PCB - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/classic-haas-control---i-o-pcb---troubleshooting-guide.html)

## Malfunctioning Proximity Sensor

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/proximity-sensor---troubleshooting-guide/prox_sensor_location.png)

For 12 VDC proximity sensors, test the voltage at the proximity sensor. The 3-wire 5 VDC sensor receives voltage from the processor PCB. It is the same voltage that is sent to the axis encoder. If the axis encoder works correctly, and there are no encoder alarms, the sensor receives the correct voltage.

Always check for voltage from the back of the connector with needle-tip probes. If there is voltage present at the proximity sensor, but it will not change status, the sensor is at fault.

## N.O. 2 Wire 12V Proximity Sensor: (Black lead to ground and red lead to the brown wire)

|  |  |  |  |
| --- | --- | --- | --- |
| **Proximity Sensor State** | **LED** | **Voltage (VDC)** | **Diagnostic Bit** |
| Without Activation | OFF | 9-12 | 1 |
| Activated | ON | 2-3 | 0 |

## N.C. 2 Wire 12V Proximity Sensor: (Black lead to ground and red lead to the brown wire)

|  |  |  |  |
| --- | --- | --- | --- |
| **Proximity Sensor State** | **LED** | **Voltage (VDC)** | **Diagnostic Bit** |
| Without Activation | ON | 2-3 | 0 |
| Activated | OFF | 9-12 | 1 |

## N.O. 3 Wire 12V Proximity Sensor: (Black lead to ground and red lead to the black wire)

|  |  |  |  |
| --- | --- | --- | --- |
| **Proximity Sensor State** | **LED** | **Voltage (VDC)** | **Diagnostic Bit** |
| Without Activation | OFF | 9-12 | 1 |
| Activated | ON | 0-2 | 0 |

## N.C. 3 Wire 5V Proximity Sensor - Home Switches: (Black lead to ground and red lead to the black wire)

|  |  |  |  |
| --- | --- | --- | --- |
| **Proximity Sensor State** | **LED** | **Voltage (VDC)** | **Diagnostic Bit** |
| Without Activation | OFF | 0-2 | 0 |
| Activated | ON | 3-5 | 1 |

# 29.3 Pneumatic Safety Interlocks

## Pneumatic Safety Interlocks

[Pneumatic Safety Door Interlocks - Troubleshooting Guide](https://www.haascnc.com/service/troubleshooting-and-how-to/troubleshooting/pneumatic-safety-door-interlocks-troubleshooting-guide.html)

# 29.4 Light Curtain

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/light-curtain---troubleshooting/Light-Curtain-APL-vs.-HRPCobot.jpg)

The light curtain is a transmitter/emitter and receiver system. When the light curtain is broken, the APL or machine motion will stop until the curtain is unbroken and cycle start is pressed.

There are two types of light curtains:

* Light Curtain for APL [1]
* Light Curtain for HRP/Cobots [2]

**NOTE:** The main appearance difference between the Light Curtain for APL [1] vs. HRP/Cobots [2] is that the Light Curtain for APL [1] has programmable buttons [3] on the bottom whereas the Light Curtain for HRP/Cobots [2] has no programmable buttons on the bottom.

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| **Light Curtain for APL Only**: The light curtain logic is reversed. When the light curtain is broken the icon (shown below) is not displayed and the I/O is a 0 and the APL motion is not stopped.  ![](data:image/png;base64...) | The Light curtain parameters are set incorrectly so the logic is reversed. | Reset the light curtain parameters. See the **Light Curtain for APL - Reset Parameters** section below. |
| The programming buttons were unintentionally pressed changing the parameters. | A cover can be made to cover the programmable buttons. See the**Light Curtain for APL - Programming Button Cover**section below. |
| **Light Curtain for HRP/Cobot Only:** The Light Curtain icon does not clear when the Light Curtain is not tripped.  ![](data:image/png;base64...) | The electrical connections are not correct. | Check the connections from the Light Curtain to I/O PCB. Refer to the **Electrical Schematic** section below. |
| There is something interfering the light curtain. | Remove the object interfering the light curtain protective field. |
| On Multi-sided light curtain the mirrors are not correctly align. | Make sure you correct the position of the mirrors.  Refer to the [Light Curtain Installation - AD0704](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/light-curtain---installation---ad0704.html) procedure. |
| The Light Curtain when broken does not trigger the machine to stop APL motion. | There is no input from the light curtain to the machine. | Light Curtain wired correctly and receiving power. Check from the PSUP > 24V Transformer > I/O > Light Curtain. Refer to the **Electrical Diagram**section below. |
| Light Curtain transmitter and receiver are not aligned. |
| The Light Curtain **Parameter 2191**is not enabled. |
| The **Setting 376**Light Curtain Enable is not turned ON. |
| **Light Curtain for APL Only:** Reset the light curtain parameters. |

## Light Curtain for APL - Reset Parameters

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/light-curtain---troubleshooting/Reset-Factory-Parameters.png)

Follow the following steps to reset the Light Curtain Factory Parameters.

1. Press the Menu button to enter parameterization mode.

2. Press the Menu button repeatedly until the F2 icon starts flashing.

3. Press the OK button. This will take you to the 2nd parmaterization level.

4. Press the Menu button repeatedly until the H3 icon starts flashing.

5. Press the OK button. The Light Curtain Parameters will be reset.

See the Light Curtain User Manual below for more information.

[Light Curtain - User Manual](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/light-curtain---troubleshooting/Pepperl%2BFuchs%20Light%20Curtain%20Manual.pdf)

## Light Curtain for APL - Electrical Diagrams

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/light-curtain---troubleshooting/Light-Curtain-Wiring-Schematic-1.png)

**[1]** Connect cable **33-1910A** CBL90B 115V TO 24V PS from PSUP **P5/6/7** to **32-9122** 24VDC Power Supply.

**[2]** Connect 24VDC Power Supply Cable **32-9122** from **33-1910A** CBL90B 115V TO 24V PS to **33-0344B** CBL LIGHT CURTAIN HARNESS WITH FILTER OV.

**[3]** Cable **33-0344B**CBL LIGHT CURTAIN HARNESS WITH FILTER

**[4]** Connect cable **32-1847**CBL LIGHT CURTAIN TRANSMITTER to the Light Curtain Transmitter.

**[5]** Connect cable**33-1558**CBL LIGHT CURTAIN RECEIVER to the Light Curtain Receiver.

**[6]** Connect Cable **33-0344B**CBL LIGHT CURTAIN HARNESS WITH FILTER to the I/O PCB at **P1**.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/light-curtain---troubleshooting/Light-Curtain-Wiring-Schematic-Cable-Detail.png)

# 29.5 Pressure Sensors - Troubleshooting Guide

## Pressure Sensors - Troubleshooting Guide

---

Under construction - 10/2025

Information on this page can not be relied on.

## Introduction

This section shows how to troubleshoot the various type of pressure sensors used on Haas machines.

Pressure sensors are found on both pneumatic and hydraulic systems and can be analog or digital types of sensors.

When troubleshooting an alarm that might involve a pressure sensor, its important to start by identifying the type of sensor in the system.

The sections below show how to determine the pressure sensor type, as well as how to determine if the sensor is faulty.

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| **Alarm 120 Low Air Pressure or Flow** | The pressure sensor on the air manifold in the lube cabinet is not accurately measuring the incoming air to the machine | See the **pneumatic analog pressure sensor** section below for how to determine if the pressure sensor is operating correctly. |
| **Alarm 40.4143 Pallet Changer Low Hydraulic Pressure On Start** |  | See the **hydraulic analog pressure sensor** section below for how to determine if the pressure sensor is operating correctly. |

## Pneumatic Analog Pressure Sensors

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/pressure-sensors---tsg/air-pressure-gauge-and-diagnostic.png)

### 1

The pressure sensor in the lube panel is an analog pressure sensor. This sensor monitors the incoming air pressure to the machine.

First, check the Gauges tab under diagnostics and look at the air pressure gauge reading [1].

**Note:**You can tell if the sensor is going to a CAN BUS board or directly to the IO by looking at the **Board** and **Connector** labels. This image shows a a machine where the pressure sensor is connected directly to the IO PCB at P34 [3]

Look at the reading on the IO tab for the analog value being reported to the control [2].

### 2

## Hydraulic Analog Pressure Sensor

## Pneumatic Pressure Switch

## Hydraulic Pressure Switch

### 1