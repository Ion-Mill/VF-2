<!-- doc_id: NGC-ESM-08 | title: NGC - I/O and TC PCB - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---i-o.html | retrieved_at: 2026-10-03T18:03:13 | retrieved_via: direct | original_file: NGC-ESM-08__norev__20261003.html | original_sha256: c55dbf37720fd10cf7eff6ba452bf2c3ab6a818be3b8bdec118a0841d2a341de | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-08 |
| title | NGC - I/O and TC PCB - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---i-o.html |
| retrieved\_at | 2026-10-03T18:03:13 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-08\_\_norev\_\_20261003.html |
| original\_sha256 | c55dbf37720fd10cf7eff6ba452bf2c3ab6a818be3b8bdec118a0841d2a341de |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [8.1 I/O PCB Hinge Door - Installation](#tab_i-o-pcb-hinge-door---installation_0)
* [8.2 I/O PCB - Replacement](#tab_i-o-pcb---replacement_0)
* [8.3 Tool Changer PCB - Replacement](#tab_tool-changer-pcb---replacement_0)
* [8.4 I/O PCB - Troubleshooting Guide](#tab_i-o-pcb---troubleshooting-guide_0)
* [8.5 Diagnostic Data](#tab_diagnostic-data---ngc_0)

# 8.1 I/O PCB Hinge Door - Installation

## I/O PCB Hinge Door - Installation

---

**AD0444**

## Introduction

This procedure will show you how to install the hinged door on the I/O PCB.

**This Document Applies to the Following Kits:**

93-1000297 DOOR, HINGED FOR I/O PCB

93-1000573 DOOR, HINGED CAN INSTALL KIT FOR I/O PCB

## Hinge Door - Installation

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/hpc-electrical-install---ngc-kits/IO-Hinged-Door-Hard-Stop.png)

### 1

Open the control cabinet. Remove the cover for the I/O PCB.

Install the two socket head cap screws to the top and bottom hinge plate**[1]**.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/hpc-electrical-install---ngc-kits/HPC_electrical_install_hinge_door.png)

### 2

Install these parts:

* Use (2) screws [2] to install the top hinge plate [1].
* Use (2) screws [3] to install the bottom hinge plate [4].
* Use (4) screws [5] to install the (2) door brackets [6].
* door panel [F]

# 8.2 I/O PCB - Replacement

## **I/O PCB** - Replacement - NGC

---

**AD0413**

## Introduction

This procedure will show you how to replace the I/O PCB on an NGC machine.

**Download and fill out the NGC I/O PCB Inspection Report Checklist below before replacing any parts. It can be found at the [I/O and TC PCB troubleshooting guide](https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---i-o.html#tab_i-o-pcb---troubleshooting-guide_0).**

**This procedure applies to these kits:**

* **93-32-3490C** IO PCB, SIO-C NGC

**Machine Compatibility:**

* P/N **93-32-3490C** is fully backwards compatible with P/N **93-32-3490B, 93-32-3490A, 93-32‑3480A, 93-32-3480C**, and**93-32‑3482C**
* **Note:**If replacing an earlier version I/O PCB some connectors have changed location. Some cables will need to have more slack pulled from the cable channel or from the enclosure.
* You will also need to order a **93-32-5502** Tool Changer CCA kit if the machine is equipped with DC-Motor tool changer or a bar feeder.

## Replacement

### 1

Push **[POWER OFF]**.

Set the main circuit breaker to the OFF position.

Lock the main circuit breaker. Use an approved lock with an approved safety tag.

**Caution:** When you handle a PCB, you must wear an Electrostatic Discharge (ESD) strap.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/iopcb---34-349x---replacement---ngc/AD0413-IO-Board-Jumpers.png)

### 2

Record the position of the push-on jumpers [1] on the PCB.

Put an identification label on each cable that is attached to the PCB. This makes the installation easier. Disconnect these cables.

Remove the I/O PCB and place it next to the replacement PCB [2].

Remove the push-on jumpers [1] from the removed PCB and put them onto the replacement PCB [2].

**Note:** The jumpers shown in the image are at **P2**, **P12**, and **JP1** on the I/O PCB. Boards can have these as well as other jumpers depending on the options the machine has.

**Caution:** Carefully compare the two I/O PCBs to make sure you install each jumper in the correct position. If you do not correctly install each of the jumpers, the I/O PCB cannot operate correctly.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/iopcb---34-349x---replacement---ngc/tc_pcb_34_3490.png)

### 3

**Note: If the machine is equipped with a tool changer that has a brush motor or bar feeder:**Install the (4) standoffs [1] on the I/O PCB. Do not install the Tool Changer PCB until after the I/O is installed.

Install the I/O PCB in the electrical cabinet.

If equipped with a brush motor TC or bar feeder: Mount the 93-32-5502 Tool Changer PCB to the standoffs. Connect wires:

* Connect cable P/N 33-0413 from J1 [2] on the TC PCB to P74 [3] on the I/O PCB.
* Connect cable P/N 33-0412 from P55A [4] on the TC PCB to P55 [5] on the I/O PCB.
* Connect cable P/N 33-0349 from P4 on PSUP PCB to the P55 [7] on the TC PCB.
* Connect the tool changer/bar feeder cable to P58 [6].
* For EC models, connect the external resistor at P57 [8].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/iopcb---34-349x---replacement---ngc/tc_pcb_34_3490_connect_all_cables.png)

### 4

Connect all cables.

**Note:** If updating from an earlier version I/O PCB some plug locations have changed.

* The plugs on top of the I/O [1] will need to have slack pulled from the channel.
* Rotary axis brakes [2] have moved up on the left side of the I/O, these cables will need to be routed differently.
* The coolant and TSC plugs [3] have moved to the bottom of the I/O. Some slack will need to be pulled from the channel or from the enclosure to reach the new location.
* P28 [4] for the TSC Vaccum Sensor has moved. Some slack may need to be pulled from the strain relief on the enclosure to reach the new location.
* The tool changer output cable moves to P58 and cable 33-0349 to P55A on the Tool Changer PCB.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO-PCB-w-New-Filters.jpg)

### 5

**IMPORTANT:**When replacing**34-349XA/B** I/O PCB with **34-3490C**, do not reinstall the SIO filter board [1] and remove any single [2] or dual [3] solenoid filters in the CALM cabinet. The new I/O PCB board has these filters built into the board.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO-PCB-with-VFD-adapter-board.png)

### 6

**IMPORTANT:**When replacing **34-349XA/B** I/O PCB with **34-3490C** and VFD ADAPTER PCB is installed, do not re-install the VFD ADAPTER PCB into the **34-3490C I/O PCB** as this VFD ADAPTER PCB is now built in.

## Operation Test

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/iopcb---34-349x---replacement---ngc/tc_pcb_34_3490_io_config_check.png)

### 1

Power on the machine with your Haas Control Key.

You get an alarm that you cannot stop until the Main Crc and Factory Crc numbers [3] are the same. Do these steps to stop the alarm:

Press **[DIAGNOSTIC]**.

Use the CURSOR arrows to go to I/O Config [2] in the Diagnostics tab [1].

Press **[F3]** to Update Config Table[4].

Press **[RESET]** to continue.

If the alarm does not stop, push **[POWER OFF]**, and then push **[POWER ON]**.

 **Note:**  After installation, make sure the SIO Version and I/O TC Version are up to date. Refer to [I/O Firmware Compatibility](https://www.haascnc.com/content/haascnc/en/service/online-manuals/next-gen-control-electrical---service-manual/ngc---firmware-update.html) chart for the most current versions. If not, update the firmware to the correct version.

### 2

Operate the spindle, tool changer, coolant, through-spindle coolant (TSC/HPC), P-cool spigot, Emergency Stop, beacon, operator door, barfeeder, and all optional equipment.

Make sure that all machine parts and installed options work correctly. If the Side Mount Tool Changer operates slowly, cycle power.

In an EC series machine, make sure the external resistor you connected to P57 does not heat up while the machine is idle.

# 8.3 I/O - Tool Changer PCB - Replacement

## **I/O - Tool Changer PCB**- Replacement - NGC

---

**AD0386**

## Introduction

This procedure will show you how to replace the Tool changer PCB on a NGC machine.  This tool changer PCB is used on 34-349x I/O PCB that have a DC-Motor Tool changer or a bar feeder option.

**This procedure applies to these kits:**

* 93-32-5502 PCB, Tool Changer - NGC

**Machine Compatibility:**

* 34-349x I/O PCB

## Replacement

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/iopcb---34-349x---replacement---ngc/tc_pcb_34_3490.png)

Remove the old TC PCB from the standoffs [1] on the I/O PCB. Install the replacement TC PCB on the standoffs.

Connect cable P/N 33-0413 from J1 [2] on the TC PCB to P74 [3] on the I/O PCB.

Connect cable P/N 33-0412 from P55A [4] on the TC PCB to P55 [5] on the I/O PCB.

Connect cable P/N 33-0349 from P4 on PSUP PCB to the P55 [7] on the TC PCB.

Connect the tool changer/bar feeder cable to P58 [6].

For EC models, connect the external resistor at P57 [8].

**Note:**  After installation make sure the SIO Version is 3.17 or higher and the I/O TC Version is 2.06 or higher.  If not update the firmware to the correct version.  Refer to [I/O PCB Firmware - Update - NGC](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) procedure.

# 8.4 I/O PCB - Troubleshooting Guide

## **I/O PCB** - Troubleshooting Guide - NGC

---

**TG0002**

Revision C - 08/2026

## Introduction

**Download and fill out the NGC I/O PCB Inspection Report Checklist below before replacing any parts.**

[NGC I/O PCB Inspection Report Checklist](https://www.haascnc.com/content/dam/haascnc/service/guides/references/i-o-inspection-checklist/ID0008_Rev_C.pdf)

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_34-3480A.png)

**34-348xA**

* Release Date: 09/2014
* **Main Firmware Version: 01.XX**

  **Note:**Firmware version cannot be upgraded to version 02.XX
* **TC Firmware Version: 01.XX**

  **Note:** Firmware version cannot be upgraded to version 02.XX

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_34-3480C.png)

**34-348xC**

* Release Date: 05/2016
* **Main Firmware Version: 02.XX**

  **Note:** Firmware version cannot be upgraded to version 03.XX
* **TC Firmware Version: 01.XX**

  **Note:** Firmware version cannot be upgraded to version 02.XX
* Backwards compatible with 34-348xA
* Y/D Feedback Support
* TSC/HPC 1K Fan Support

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_34-3490A.png)

**34-349xA/B**

* Release Date: 05/2018
* **Main Firmware Version: 03.XX - 04.XX**
  **Note:** See the  [I/O Firmware Compatibility](https://www.haascnc.com/content/haascnc/en/service/online-manuals/next-gen-control-electrical---service-manual/ngc---firmware-update.html) chart for recommended firmware version.
* **TC Firmware Version: 02.XX**
  **Note:** The 02.xx version will show if the I/O PCB has a TC PCB installed.  If the TC PCB is not installed the firmware version will show "No TC".
* Backwards compatible with **34-348xA/B**
* Redundant Axis Brake Support
* Optional TC PCB
* Outputs have LED's lights

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO-PCB-Board-34-349xC.jpg)

**34-349xC**

* Release Date: 03/2023
* **Main Firmware Version: 04.XX**
  **Note:** See the [I/O Firmware Compatibility](https://www.haascnc.com/content/haascnc/en/service/online-manuals/next-gen-control-electrical---service-manual/ngc---firmware-update.html) chart for recommended firmware version.
* **TC Firmware Version: 02.XX**
  **Note:** The 02.xx version will show if the I/O PCB has a TC PCB installed.  If the TC PCB is not installed the firmware version will show "No TC".
* Backwards compatible with **34-348xA/B/C** and **34-349xA/B**
* Redundant Axis Brake Support
* Optional TC PCB
* Outputs have LED's lights
* Supports low power valves by incorporating the I/O power supply and solenoid filters into the board
* Variable frequency drive (VFD) adapter board is built in
* E-stop Debounce circuit is also built in

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/io_connector_pins.png)

**I/O PCB Connector and Pin Information**

As of NGC software version 100.17.000.1016 or higher connector and pin number has been added to the I/O diagnostic tab.  The PCB board name has also been added.  This will help when troubleshooting a machine and trying to figure out which connector and pin number to probe.

The format for the connector and pin numbers are Pmm.nn where mm is the connector number and nn is the pin number.  For example, connector P56 and pin 5 would be represented as P56.5.  In some cases, a given signal may be present on more than one pin or connector.  In this case, they will be separated by a comma.

In addition to providing information on I/O signals, the table now includes rows for things like power and ground pins.

You can also use the search function to search for specific connector numbers.  For example you can search for connector P3 then press the [F1],  this will display all the input and output fuctions of connector P3.

## PCB serial number

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/ngc-control/main-processor-pcb-images/PCB-serial-number-(web).png)

**Note:** The PCB's serial number must be included in the inspection report checklist. The serial number is on a sticker [1] on the top of the inspection checklist.

The serial number will start with two letters, followed by eight digits. Include both the letters and numbers on the inspection report.

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
| Symptom / Alarm | Possible Cause | Corrective Action |
| Alarm **9924 CONTROL AND IO BOARD COMMUNICATION LOST**  Alarm **9925 CONTROL AND IO BOARD COMMUNICATION DID NOT INITIALIAZE**.  Alarm **9915 IO BOARD CONFIGURATION CRC MISMATCH** | The I/O PCB built-in Low Volt Power Supply (LVPS) voltages are not present or the LVPS is not working. | Troubleshoot the I/O PCB LVPS.  Refer to the **I/O PCB Low Volt Power Supply** section below. |
| Alarm **9924 CONTROL AND IO BOARD COMMUNICATION LOST** | The I/O PCB is not receiving any power | Check the PSUP breaker that supplies power to the I/O board. If the breaker is on, there should be LED lights on the I/O PCB. Check to see if the lights on the I/O board are on. |
| There is an issue with the RJ45 cable connected from the I/O PCB to the Maincon board. | This RJ45 cable connected to J1 on the I/O PCB may be damaged. Check the cable and connectors for damage. Swap the cable with another RJ45 and try to clear the alarm. If the alarm clears then the original cable needs to be replaced. |
| Alarm **9924 CONTROL AND IO BOARD COMMUNICATION LOST** is generated intermittently. | There is electrical noise interfering with communication signals connected to the I/O PCB. | Use a service key and navigate to the **MISC** page on the control by pressing **Diagnostics -> MISC.** Look at the **IOPerformance** fields that show the communication errors that have been generated. See the **Check IO Performance** section below.  If the number of errors is growing, this indicates electrical noise in the control cabinet.   1. Press [**E-STOP]** to turn the servos off. Then check to see if the number of errors continues to grow. 2. Check that all ferrite filters are installed on communication cables. 3. Check that the amplifier power cables are properly grounded to chasis. |
| Alarm **9924  CONTROL AND IO BOARD COMMUNICATION LOST** and **9100 NON RESETTABLE SYSTEM ERROR** | Same possible causes as **9924** alarm above. | Follow the Corrective Action listed above for **9924** alarms. If this action doesn't clear the alarm, cycle power on the machine. If the alarm is present after cycling power, take an error report and contact **Haas Service**. |
| **Alarm 9924 CONTROL AND IO BOARD COMMUNICATION LOST** and **Alarm 9101 RESETTABLE SOFTWARE ERROR** | Same possible causes as **9924** alarm above. | Follow the Corrective Action listed above for **9924** alarms. If this action doesn't clear the alarm, cycle power on the machine. If the alarm is present after cycling power, refer to the  **IO Board Minimum Configuration Test** section. |
| Alarm **9100 NON RESETTABLE SOFTWARE ERROR** at Power On, or Alarm **9915 IO BOARD CONFIGURATION MISMATCH.** | Main CRC and Factory CRC do not match due to the I/O PCB being swapped out. | 1. Press **[POWER OFF]**. 2. Put the USB memory device into the control. Note: The USB memory device must contain your **Haas Control Key** and the correct **configuration files**. 3. Press **[POWER ON]**. 4. Press **[DIAGNOSTIC]**. 5. Go to I/O Config [2] in the Diagnostics tab [1]. 6. Press **[F3]** to Update Config Table [4]. 7. Press **[RESET]** to continue. If the alarm does not clear, cycle the machine power.   The Main CRC and the Factory CRC[3] are now the same. ![](https://service.haascnc.com/sites/default/files/Locked/3/update_io_config_table1.png) |
| Alarm **9933** SOFTWARE VERSION MISMATCH and **9100**  NON RESETTABLE SOFTWARE ERROR | The firmware update failed, or I/O firmware is corrupted. | Reload the I/O PCB main firmware refer to [Next Generation Control - I/O PCB Main Firmware - Update](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html). |
| Alarm **9899 IOPCB CAN FAULT** and/ or **9105 IO BOARD COMMAND EXECUTION FAILURE.** See the [CAN Bus Systems Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/online-manuals/can-systems---service-manual/can-systems---troubleshooting.html) for more information. | The CAN node I/O Configuration is incorrect. | Update the I/O configuration via the I/O Config tab. |
| The incorrect CAN node is enabled. | Verify that Factory Settings 9000.001 -> 9031.001 are set correctly. Only active nodes should be enabled. |
| The Autodoor CAN PCB does not have power. | Verify that the Low Volt Power supply is supplying power to the CAN Autodoor PCB. |
| The CAN node Communication cable is disconnected. | Power down machine for at least a minute. Verify all CAN communication cables are connected correctly. |
| The CAN Module ID Selector is incorrect. | Power down machine for at least a minute. Set ID selector correctly. Power up machine. |
| The CAN Modules have incorrect termination. | Power down machine for at least a minute. Verify that only last node in the chain is terminated. Power up machine. |
| The CAN Node needs to be reset. | Disable CAN Node via 9000.001 -> 9031.001. If the machine recovers (I/O page isn’t “X”) after disabling a particular node, try to enable the node again. |
| Spindle load pegs to 200% | There is a problem with the 120 VAC outputs circuit components (solenoids, Wye-Delta, Oil Pump etc.) | Inspect the wiring, pins, and connectors for this circuit.  Inspect the I/O board for faults. Replace the I/O if necessary |
| Machine generates multiple Alarm **20014.1** SIO TOOL CHANGER PCB IS NOT PRESENT and **20014.0** SIO TOOL CHANGER PCB PRESENT after the I/O TC PCB is installed. | The I/O or TC PCB firmware is outdated. | Update I/O Main and TC firmware version to the latest.  Refer to [Next Generation Control - I/O PCB Main Firmware - Update](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html). |
| Machines equipped with I/O PCB P/N: **34-3490A/B** with an auxiliary estop that generates an estop alarm after the closing of machine doors. | The doors closing have shaken the estop and caused a momentarily disconnect and caused an estop of the machine. | A debounce capacitor will need to be added to the I/O PCB. Refer to the [E-Stop - Debounce](https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/e-stop-debounce---ad0546.html) procedure. |
| Main I/O Firmware fails to load. | TC PCB is causing the failure. | Remove the TC PCB from the Main I/O PCB.  Then try the Firmware upgrade again. |
| **Alarm 2001** EMERGENCY STOP SWITCH ERROR | There is a loose connection from the Hydraulic Union Safety Device adaptor to the I/O PCB.  **Only applies to these machines built after 12/20/2023****:**  **ST - 10/15/20/25/28/30/35/L/Y/LY**  **REBOOT ONLY: ST-40/40Y/45/45Y (note: For ST-45/45L/45Y machines equipped with optional workholding)** | Check the cable connected to the I/O PCB at P12, make sure the cable is not damaged or has a loose connection. |

## Serial I/O PCB Alarms

Depending on the machine software version, I/O PCB main firmware version you will get a different alarm, see table below:

|  |  |  |
| --- | --- | --- |
| **Alarm# / Title**  **Software 100.17.000.2021 and lower**  **I/O PCB Main Firmware 02.04 and lower** | **Alarm# / Title**  **Software 100.17.000.2030 and higher**  **I/O PCB (34-348xC) Main Firmware 02.05 and higher** | **Alarm Troubleshooting** |
|  | **9830**-IOPCB MEMORY DATA LOCKED | Attempts were made to download an I/O configuration file while configuration memory was locked. |
| **850**-INTERNAL I/O ERROR | **9800**-INTERNAL I/O ERROR- SHIFT CHAIN | An internal I/O circuit board error has been sensed in it's shift chain. - Press the **[RESET]** button. Power off, and inspect the circuit components on the I/O PCB, see section below. |
| **9801**-INTERNAL I/O ERROR-TC COMMUNICATION | An internal I/O circuit board error has been sensed where the main and tool changer microcontrollers could not communicate. - Press the **[RESET]** button.  Inspect the tool changer relays, make sure the relay sockets are solder into the PCB board.  Do not replace the I/O PCB.  For IO PCB (34-348xA):  ·         Upgrade the I/O PCB Tool Changer firmware to the latest 01.xx version.  For IO PCB (34-348xC):  ·         Update the I/O PCB Main firmware to the latest 02.xx version.  ·         Update the I/O PCB Tool Changer firmware to the latest 01.xx version.  For IO PCB (34-349x):  ·         Update the I/O PCB Main firmware to the latest 03.xx version.  Refer to [Next Generation Control - I/O PCB Main Firmware - Update](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) procedure. |
| **9900**-IOPCB COMMUNICATION LOST | **9802**-SIO MCU COMMUNICATION LOSS | Communication has been lost to the I/O PCB. Check that the I/O PCB has power by looking for the 12/24V green LED's. Look for a tripped circuit breaker. If the board has power, then |
| 1. Check the RJ-45 cable connection from Maincon PCB (J14) to I/O PCB (J4). To test the cable refer to [Network Cable Tester Tool procedure](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/network-cable-tester-tool.html). |
| 2. Check the 3-Phase power input from PSUP (P4) to I/O PCB (P55). |
| 3. Inspect the RJ-45 connector on the Maincon PCB & I/O PCB for bent pins. |
| Upgrade the software to 100.17.000.2045 or higher. If you get this alarm with version 100.17.000.2045 or higher download an error report and e-mail to Haas service. |
|  | **9831**-I/O # ERROR | The main processor has command an output that is not configured in the I/O configuration file. |
|  | **9832**-SIO COMMUNICATION ERROR | The I/O PCB has received partial or invalid communication from the main processor. |
|  | **9833**-PCB OVER TEMPERATURE | The I/O PCB is reporting a temperature that exceeds limits (65 degrees C) |
|  | **9834**-12V FAULT | The 12V supply on the I/O PCB is outside of its limits of 10 to 14V. |
| **175**-GROUND FAULT DETECTED | **9803**-120VAC GROUND FAULT | A 120 VAC ground fault condition was detected by the I/O PCB.  The ground fault signal gets generated by the PSUP PCB.  The ground fault signal gets sent to  I/O PCB at  P56 for monitoring. Check all 120V outputs for possible shorts to earth ground. See ground fault troubleshooting section below. |
| **9804**-240VAC GROUND FAULT | A 240 VAC ground fault condition was detected by the I/O PCB.  The ground fault signal gets generated by the PSUP PCB.  The ground fault signal gets sent to I/O PCB at  P56 for monitoring. Check all 240 V outputs for possible shorts to earth ground. This includes short circuits in any amplifier or vector drive output as well as any 240V pumps or chip conveyor. See ground fault troubleshooting section below. |
| **9903**-120 VAC SHORT CIRCUIT | **9805**-120VAC PHASE C SHORT CIRCUIT | A short circuit was detected in the 120V outputs from the I/O PCB. Check all 120V outputs for possible shorts to earth ground. See ground fault troubleshooting section below. |
|  | **9835**-120VAC PHASE C OVER CURRENT | A partial short circuit was detected in the 120V outputs from the I/O PCB. Check all 120V outputs for possible shorts to earth ground. See ground fault troubleshooting section below. |
|  | **9836**-120VAC PHASE C NO CURRENT | An output was turned on but no change in current was detected. Check for broken wires/cables. |
|  | **9837**-CALIBRATION ERROR | I/O PCB Calibration error. Either calibration did not occur during power up. Or the new calibration values don't match the previous values. |
|  | **9838**-TSC FAN FAILURE | The fan for the TSC heat sink stopped; could cause TSC over heating later on. |
|  | **9820**-TSC HEAT SINK OVER TEMP | The TSC Heat sink temperature is over the limit of 85°C. Check for a damaged fan. |
| **9904**-PCOOL MALFUNCTION | **9806**-PCOOL SHORT CIRCUIT | The programmable coolant circuit has detected a short circuit (>2.5A) and has shut down. Press the **[RESET]** button to clear alarms. If necessary, cycle power on the machine. Check for a shorted cable. |
| **9807**-PCOOL GROUND FAULT | The programmable coolant circuit has detected a ground fault condition and has shut down. Press the **[RESET]** button to clear alarms. If necessary, cycle power on the machine. Check for a shorted cable to earth ground. |
| **9808**-PCOOL OVERHEAT | The programmable coolant circuit has overheated and shut down. Give time for it to cool, then press the **[RESET]** button to clear alarms. Check for obstructions to Pcool movement. |
|  | **9839**-PCOOL STALLED | A high current (2.5A> I >1A) was detected in the programmable coolant circuit. Check for obstructions to Pcool movement. Check for binding in the Pcool unit. |
|  | **9840**-PCOOL OVERLOAD | The programmable coolant circuit has detected an overload condition. Check for binding in the Pcool unit. |
|  | **9841**-PCOOL MOTOR DISCONNECTED | The programmable coolant circuit was commanded on but no current was detected. Check to see if the Pcool will turn when commanded. Check for broken wires.   If the machine is equipped with 34-3090B I/O PCB make sure the Main I/O firmware has version 3.18 or higher. Refer to [Next Generation Control - I/O PCB Main Firmware - Update](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) procedure. |
| **9905**-IOPCB TOOL CHANGER FAULT | **9809**-TOOL CHANGER BUS SHORT CIRCUIT | The I/O PCB experienced an internal short circuit. Replace the 4 tool changer relays. If problem persists, then replace the I/O PCB. |
| **9810**-INTERNAL I/O ERROR-TC TRANSISTOR FAILURE | The I/O PCB tool changer (or bar feeder) transistor appears to be damaged. Replace the I/O PCB. |
| **9811**-TOOL CHANGER CABLE SHORT CIRCUIT | One of the tool changer outputs has detected a short circuit. Check all tool changer motor outputs for possible short circuits. |
| **9812**-TOOL CHANGER GROUND FAULT | A ground fault condition was detected by the I/O PCB tool changer. Check all tool changer motor outputs for possible short circuits to earth ground. |
| **9813**-TOOL CHANGER REGEN SHORTED | The I/O PCB experienced a short circuit on the tool changer regen circuit. Check for a short circuit on it's external regen resistor at P57. |
| **9814**-CAROUSEL BRAKE RESISTOR OVER TEMPERATURE | TBD |
| **9815**-ARM BRAKE RESISTOR OVER TEMPERATURE | TBD |
| **9816**-REGEN OVERLOAD | TBD |
| **9817**-MULTIPLE MOTOR COMMANDS | TBD |
| **9818**-TOOL CHANGER OVERLOAD | TBD |
|  | **9842**-OVER VOLTAGE | TBD |
|  | **9822** - IOPCB VERTICAL BRAKE FAILURE | NGC machines equipped with **I/O PCB P/N: 34-3490A/B** and a servo brake motor may generate alarm 9822 IOPCB Brake.  Upgrade the Main I/O PCB firmware to 3.06 or higher.  Refer to [I/O PCB Firmware - Update - NGC](https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) procedure. |
| Upgrade the Main [I/O PCB Firmware](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/how-to/next-generation-control---i-o-pcb-main-firmware---update.html) to **4.21** or higher.  [HSG-A 07-11-2023](https://www.haascnc.com/content/haascnc/en/service/distributor-only/sa---service-alert---news/alarm-9822-iopcb-vertical-brake-failure.html) |
| **880** - UNDER VOLTAGE ON 160V DC BUS | **9843**-TC UNDER VOLTAGE | The system detected an undervoltage condition from the TC circuit or the TC PCB.  Check the 115 VAC input to the TC PCB, check for shorts on the tool changer motors.   1. Phase missing on the 120VAC power from the PSUP 2. Low voltage level in the 120VAC power from the PSUP 3. Open diode (s)  in the 120Vac bridge rectifier circuit either in the I/O PCB (34-348x A, 34-348x C  PCBs) or the TC PCB 34-5502 used on 34-349X I/O PCBs 4. Faulty TC PCB 34-5502 PCB 5. Faulty I/O PCB |
|  | **9844**-REGEN OPEN | TBD |
|  | **9845**-CONFIGURATION CONFLICT | TBD |
|  | **9846**-MOTOR STALLED | TBD |
|  | **9847**-MOTOR DISCONNECTED | The control software and the I/O firmware are not compatible, or the I/O firmware is outdated. |
| **9906**-CHIP CONVEYOR MALFUNCTION | **9819**-CHIP CONVEYOR SHORT CIRCUIT | TBD |
|  | **9848**-CHIP CONVEYOR MOTOR DISCONNECTED | TBD |

## IO PCB LE7 Light

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/high-voltage-power-supply-(mmps)---troubleshooting-guide/io-pcb-le7-location.png)

**Note:** The image above shows the location for **LE7** on IO board **34-349C**. The position of **LE7** can differ based on the version of IO PCB on the machine.

**LE7** [1] is one of the lights that come on when the machine is powered up. **LE7** has three states that it can be used to troubleshoot potential issues:

**LE7 is OFF**

1. This indicates the IO PCB is not receiving power or the software isn't functioning correctly. Check the breakers and make sure the IO board is receiving proper power.

**LE7 is Blinking - This can mean several things:**

1. This indicates that the board is not communicating the IO states at the regular rate. It is normal for this to happen when the machine is booting up and also during firmware upgrades.
2. Check the serial communication cable going to the Maincon.
3. **LE7** will also be blinking if there is an internal IO PCB alarm **(9800 Internal error/shift)**.
4. Since **LE7** blinks when booting up, if the control screen won't turn on and **LE7** is blinking this may indicate that the Maincon is stuck in it's boot process. **This doesn't mean that there is an issue with the IO board, but can indicate the state of the machine.**

**LE7 is On Solid**

1. This is the normal state of **LE7** when the machine is powered on and booted up. It indicates the IO is communicating with the Maincon.

## Lathe I/O PCB Hydraulic Union Safety Device Connection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/io-kill-switch-connection.png)

1. Push **[POWER OFF]**. Go to P12 on the I/O PCB, unplug the Hydraulic Union Safety Device adaptor.
2. Plug the cable back into P12 making sure its fully seated in the port. Push **[POWER ON]**. Push **[ALARMS]**. Push **[RESET]**.
3. Verify that the EMERGENCY STOP alarm has cleared.

## Check IO Performance

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/ngc-control/diagnostic-data/io-errors.png)

**Note:**The **MISC** tab can only be seen when a service key is used on the machine.

Enter service mode using the service key.

Press **Diagnostics** and then going to the **MISC** tab [1].

Monitor the Total Errors and CRC Errors for both Transmitting (Tx) and Receiving (Rx) [2].

If the number of errors is growing, there is likely electrical noise present in the control cabinet.

Press **[E-STOP]** to turn off the servo motors. Check if this stops the number of errors from growing. Electrical noise may be produced by the power cables coming from the servo amplifiers located above the IO board.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/ngc-control/diagnostic-data/amplifier-groundings.png)

If the number of errors stops increasing when the servos are off, make sure that all ferrite filters are installed on communication cables and that amplifier power cables coming from the amplifiers and vector drives are properly grounded.

Make sure there are ferrite filters [1] ground connections [2] and that the exposed shielding is grounded on all amplifiers [3].

## Ground Fault Circuit Monitor

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ground_fault.png)

On the NGC control there is a ground fault circuit monitor. This circuit monitors the 115V and 230V for a ground fault condition.

1. For 175 GROUND FAULT alarm. Determine if the alarm is caused by a 115 or 230 VAC component.
2. Press the **[DIAGNOSTIC]** button, cursor to the I/O tab.
3. Type in: "Ground", then press **[F1]**.
4. Look at the \_120VAC/\_240VAC\_GROUND FAULT analog value. The circuit with the highest value is the one that reported the ground fault.
5. Test the components that operate in that voltage range, for a short-circuit (see the table below).
6. The ground fault analog value will drop when the component with the short circuit is disconnected from the machine control.

**Components to Check when a Ground Fault Alarm Occurs**

**Note:** \*These devices can be disconnected from the I/O PCB without an alarm being generated.

|  |  |  |
| --- | --- | --- |
| **Machine Components** | **I/O PCB Location** | **Operating Voltage** |
| 4th and 5th Axis Brake Solenoids\* | P16 - P17 | 120 VAC |
| Worklights\* | P18 - P21 | 120 VAC |
| High Intensity Lights\* | P22 | 120 VAC |
| GFI | P23 | 120 VAC |
| Door Interlocks\* | P40, P41, P42 | 120 VAC |
| Lube Panel Solenoids | P35, P36 | 120 VAC |
| Y/D Contactor Coil | P37, P38 | 120 VAC |
| DC Tool Change Motors\* | P58 | 160 VDC, generated from the 120 VAC |
| Spindle Motor Fan / Oil Pump | P32 | 120 VAC |
| Sub Spindle Fan / Hydraulic Pump Fan | P33 | 120 VAC |
| TSC/HPC Pump\* | P31 | 240 VAC |
| Coolant Pump\* | P29 | 240 VAC |
| Chip Auger / Conveyor\* | P24, Quad PCB | 240 VAC |
| Axis Motors |  | 240 VAC |
| Spindle Motor |  | 240 VAC |
| Hydraulic Pump Motor |  | 240 VAC |

## I/O PCB Low Volt Power Supply

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/io_pcb_lvps_voltages.png)

The I/O PCB is equipped with a built in Low Volt Power Supply (LVPS).  This power supply generates 3 DC voltages:  **+24V, +15V and +12V**[1].

These voltages are used to power low volt circuits on the I/O PCB and also to power external devices like Probes, Axis Brakes, and User Inputs.

There are 3 LEDs that show the presence of these voltages on the I/O PCB.

* When the I/O LVPS is working correctly these LED's will glow solid.
* When there is a short circuit on the low volt circuits these LED's can begin to flash on and off.
  + When this happens you will need to find the source of the short circuit, start by disconnecting devices that are being powered by the LVPS like the Probe, Axis Brakes, User Inputs until LED lights begin to remain solid.
* When the LED's are OFF and the machine is turned on.  The I/O PCB may not be getting the 115VAC Voltage input [2] or the Circuit Breaker for the I/O PCB may have tripped.

## PCB Component Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_component_inspection_2.png/_jcr_content/renditions/cq5dam.thumbnail.319.319.png)

Intermittent alarms or symptoms can be caused by component failure. Below is a list of possible failures:

1. Missing solder on all or some components pins
2. Poor solder
3. Solder bridges
4. Wrong component installation (orientation)
5. Missing components

   **Note:** Some PCB's have unused circuits and are missing components intentionally, look for broken off components.
6. Broken components
7. Broken pins on IC's
8. Bent pins on the connectors

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_io_front_component_inspection.png)

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_io_back_component_inspection.png)

Use a magnifying glass to inspect the circuit components on the front and back of the I/O PCB. Below are the circuit component zones to inspect:

1. 24 VDC, 160 VDC circuit components (DC motor tool changers, axis brake, probe).
2. 120 VAC outputs circuit components (solenoids, Wye-Delta, Oil Pump etc.)
3. 240 VAC outputs circuit components (Coolant, TSC, Auger).
4. Check the RJ45 connector for loose housing and bent pins.

**Important:** If you find a damaged component, replace the I/O PCB, inspect the new I/O PCB circuit components before installing.

## IO Board Minimum Configuration Test

The following procedure verifies IO PCB operation using the minimum required connections. This test isolates the IO PCB from the rest of the machine and can help determine whether the IO PCB is faulty or if an external component is preventing communication.

Perform this procedure if the following conditions are present:

* LE 3, LE 4, and LE 5 are ON.
* LE 2 is ON.
* LE 7 is OFF.
* The IO PCB is not displayed on the Diagnostics > System page after power-up.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO_Board_Minimum-Configuration_Test_LE2.png)

### 1

LE 2 monitors communication between the Maincon and the IO PCB. With the RJ45 cable connected from J14 on the Maincon to J4 on the IO PCB, LE2 should illuminate after the machine has completed boot-up, regardless of whether any other devices are connected to the IO PCB.

If LE2 does not illuminate after the machine has booted, there is likely a communication issue between the Maincon and the IO PCB. Inspect the RJ45 cable and verify that it is properly connected at both ends.

To help isolate the fault, move the RJ45 cable from J14 to J13 on the Maincon. If LE2 illuminates when connected to J13, the J14 port on the Maincon may be damaged or faulty.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO_Board_Minimum-Configuration_Test.png)

### 2

Disconnect all connections from the IO PCB and Maincon except those listed below. Refer to the image for the required connections.

IO PCB Connections:

* RJ45 cable from J4 on the IO PCB to J14 on the Maincon.
* 120 VAC input connected to P55 on the IO PCB from P4 on the PSUP PCB.
* Cable from P56 on the IO PCB to P17 on the PSUP PCB.

Maincon Connections:

* Cable from J3 on the Maincon to P20 on the PSUP PCB.
* HDMI cable from J4 on the Maincon to the LCD PCB.
* RJ45 cable from J7 on the IO PCB to J9 on the SKIBIF.
* RJ45 cable from J14 on the Maincon to J4 on the IO PCB.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO_Board_Minimum_Configuration_Test_LE7.png)

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/IO_Board_Minimum_Configuration_Test_LE_3-5.png)

### 3

After all connections have been verified, power on the machine and allow it to complete the boot sequence.

LED 7 [1] should either be ON or blinking.

* A blinking LE7 indicates that communication has been established, but the IO configuration does not match the configuration stored by the control (CRC mismatch).
* A solid LE7 indicates that the Maincon and IO PCB are communicating properly and the IO configuration matches the control.
* If LE7 remains OFF, an internal fault on the IO PCB is likely preventing the processor from communicating with the Maincon.

Assuming LE3, LE4, and LE5 are illuminated [2], a solid LE7 confirms that communication between the Maincon and IO PCB has been established successfully.

If LE3, LE4, and LE5 are ON and LE2 is ON, but LE7 remains OFF with the minimum configuration connected, replace the IO PCB.

## Electrical Diagrams

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_io_pcb_electrical_diagram.png)

**I/O PCB Interconnect Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_io_pcb_sp_inputs.png)

**I/O PCB (P39) to Mill - Spindle Head Inputs Detail Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/ngc_io_pcb_air_lube_inputs_outputs.png)

**I/O PCB (P34, P35) to Mill - Air/Lube Panel Detail Diagram**

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/ngc-io-tsg/P17_PSUP_To_P56_IO.png)

**PSUP (P17) to I/O PCB (P56) Detail Diagram**

## Related Content

[CAN I/O Systems](https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---can-systems.html)

[Robot Integration](https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---robot-and-automation.html)

[DIagnostic Data](https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---i-o.html#tab_diagnostic-data---ngc_0)

# 8.5 I/O PCB Diagnostic Data

## **Diagnostic Data** - NGC

---

## Introduction

This procedure tells you how to see this information:

* Analog Sensor Data
* Diagnostic Inputs/Outputs

## Diagnostic Data - Analog Sensors

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_analog_sensor_data.png)

### 1

Push **[POWER ON]**.

Push **[DIAGNOSTIC]** to access the Parameters, Diagnostics and Maintenance display [2].

Navigate to the primary Diagnostics tab [1].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_analog_sensor_data_open.png)

### 2

Navigate to the Gauges tab [1].

The screen shows the analog sensor data for the sensors that follow:

* Air Pressure
* Coolant Level
* Tsc Pressure
* Spindle Motor Temperature
* Electronics Temperature
* Vibration
* Dc Voltage
* Ac Line Voltage

## Diagnostic Data - Input / Output

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_analog_sensor_data.png)

### 1

Push **[POWER ON]**.

Push **[DIAGNOSTIC]** to go to the Parameters, Diagnostics and Maintenance display [2].

Navigate to the primary Diagnostics tab [1].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_IO_display.png)

### 2

Navigate to the I/O tab [1].

The Type column tells you if the item is an INPUT or OUTPUT.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_IO_search_GEAR.png)

### 3

Use the Search function to find applicable inputs or outputs. Type the letters to find, and then push **[F1]**.

This example finds the inputs and outputs that contain the word "GEAR."

The I/O screen shows the inputs or outputs with the word GEAR in them [2].

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---diagnostic-data/NGC_IO_activate_HIGH_GEAR.png)

### 4

The machine must be in Service mode to do this step.

You can change an output Value [1] to 0 or 1 to energize or de-energize the I/O PCB output.

Select the OUTPUT you want to change.

Push the number 1 or 0 and push **[ENTER]**.

This example energizes OUTPUT 32 GEAR\_BOX\_TO\_HIGH\_GEAR [3].

**Note:**This example automatically energizes INPUT VALUE for GEARBOX\_HIGH\_GEAR [2].

## Diagnostic Data - CAN PCB I/O

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/ngc-control/diagnostic-data/NGC_IO_CAN_Search.png)

### 1

Follow these steps to find the inputs and outputs for the various CAN PCBs:

* Press the **[DIAGNOSTIC]** button to and navigate to the I/O tab [1] from under the Diagnostic tab.
* Search ADPCB [2] to find inputs and outputs for the Autodoor PCB.
* Search EVPCB [3] to find inputs and outputs for the E-Vise PCB.
* Search LPPCB [4] to find the inputs amd outputs for the Lube Panel PCB.
* Search SPHD [5] to find the inputs and outputs for the Spindle Head PCB.