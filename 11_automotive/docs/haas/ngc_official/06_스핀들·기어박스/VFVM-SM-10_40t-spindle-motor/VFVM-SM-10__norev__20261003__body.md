<!-- doc_id: VFVM-SM-10 | title: VF/VM - 40T - Spindle Motor - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html | retrieved_at: 2026-10-03T18:06:52 | retrieved_via: direct | original_file: VFVM-SM-10__norev__20261003.html | original_sha256: fc0834e4bf41808d325446c57d9ffcdcacdafa1ac328a26b5233d5c729e330c6 | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | VFVM-SM-10 |
| title | VF/VM - 40T - Spindle Motor - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html |
| retrieved\_at | 2026-10-03T18:06:52 |
| retrieved\_via | direct |
| original\_file | VFVM-SM-10\_\_norev\_\_20261003.html |
| original\_sha256 | fc0834e4bf41808d325446c57d9ffcdcacdafa1ac328a26b5233d5c729e330c6 |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

VF/VM-Series - Service Manual

---

Go To :

* [10.1 40T Pin Drive Motor - Replacement](#tab_40t-pin-drive-motor---replacement_0)
* [10.2 30T/40T Spindle Motor - Troubleshooting](#tab_40t-spindle-motor---troubleshooting_0)
* [10.3 40T Spindle Motor - Brand Identification](#tab_10-3-40t-spindle-motor---identification_0)
* [10.4 40T Spindle Motor - HDF Requirements](#tab_10-5-hdf-requirements_0)

# 10.1 40T Pin Drive Motor - Replacement

## **40T - Pin Drive Motor** - Replacement - VMC

---

**AD0649**

*Applies to machines built after August 2016*

## Introduction

New motors ship with non-contact encoders (NCE's). If you have an early NGC machine you may have a magnetic encoder and will need to order the new cable for the NCE encoder before you make any repairs.

**This procedure applies to the following kits:**

* **93-30-11973:**SPNDL MTR 40T 12K INLINE PIN DRIVE
* **93-30-11980B:** SPNDL MTR 40T INLINE 15K PIN DRIVE
* **93-30-11995A:** SPINDLE MTR 40T INLINE 15K PIN DRIVE NCE
* **93-30-12117:** SPINDLE MTR 40T INLINE 12K PIN DRIVE NCE
* **93-30-14460:**SPNDL MTR 40T INLINE 18K PIN NCE VF SVC
* **93-30-12078:** SPNDL MTR 40T INLINE 12K PIN DRV
* **93-30-12078A:** SPNDLE MTR 40T INLINK 12K NCE GEN2 EC SVC

**Required Tools :**

* **T-0066**BELTED DRAWBAR GUIDE TORQUE KIT

**Note :** T-0066 is only applicable if a brass cap is found in an in-line spindle during a motor replacement.

**Note :**Machine software must be updated to 100.20.000.1110 or later before replacing spindle motor.

**Note:**  This procedure should only be performed by a Haas certified service technician.

## Replacement

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/Remove-Motor.png)

### 1

Remove the sheet metal surrounding spindle motor [1].

Remove TSC or air purge assembly [2].

Unplug encoder cable and ground [3].

Remove terminal block cover and disconnect wires from terminal black.

**Note:** Remove motor mounting screws and rotate motor 90° for easy access to terminal block.

Connect lifting hooks to bracket.

Remove motor.

**Note:** Make sure transfer tube is still fully seated into spindle drawbar after removing motor.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/identification.png)

### 2

Inspect the spindle visually for a brass cap. If a brass cap is located in the spindle, the spindle will need to removed following [VMC - 40-Taper - Inline Pin-Drive Spindle - Replacement](https://www.haascnc.com/content/haascnc/en/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t---spindle.html) procedure and the the brass cap will need to be removed as demonstrated in the next step.

If no brass cap is present proceed with the motor replacement.

**Important :** The brass caps interferes with current motor motor couplers and it needs to be removed.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/plug-removal.png)

### 3

**Note :** The brass cap is held in place using thread locking compound.

Place the spindle drive dogs between the vise jaws [2] and clamp securely. Proceed to align T-0066 with the brass cap pin holes [1].

Firmly press downwards on T-0066 [3] and loosen the brass cap [6] using a long breaker bar.

**Important :** Ensure the vise is clamped onto the spindle drive dogs and the face [5] is sitting flat against the top of the jaws [4].

Proceed to install the spindle back into the head casting and install the new motor.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/Prepare-Motor-for-Install.png)

### 4

Lift new motor from shipping crate.

**Note:** Make sure to note the brand of spindle motor you are installing. If you are unsure, see [Spindle Motor Brand Identification](https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html#tab_10-3-40t-spindle-motor---identification_0).

Lightly stone mounting surfaces [1],[2] with alcohol and wipe clean.

Apply Red-I Grease to motor coupling groove [3] and motor coupling pins [4].

## Configure HDF

The Hardware Definition File (HDF) allows you to configure your machine to be compatible with multiple spindle brands.

In the event of a spindle motor replacement, a service tech may easily swap out the motor and update the spindle motor brand configuration.

The table below lists the 40T spindle motor service kits that currently require a Hardware Definition File (HDF). **If you have recently installed one of these kits, contact your local Haas Factory Outlet to update your spindle motor brand configuration on your machine.**

**For Service Techs:** To update your spindle motor brand configuration:

1. Log in to the [Dealer-only Content (DOC)](https://haas-sso.helloid.com/RelayService/Redirect/2001b686-aa42-44a8-9640-d2af01123553) portal.
2. Navigate to the [Spindle Motor - Brand Configuration - NGC](https://www.haascnc.com/content/haascnc/en/service/distributor-only/ad---procedures/spindle-motor---brand-configuration---ngc.html) page.

**Note:**Only Haas Certified Service Technicians can log into this site.

|  |  |  |
| --- | --- | --- |
| Kit Number | Kit Name | Valid Date |
| 93-30-12078 | SPNDL MTR 40T INLINE 12K PIN DRV | 6/1/2025 |
| 93-30-12078A | SPNDL MTR 40T INLINE 12K NCE GEN2 EC SVC | 6/1/2025 |
| 93-30-12117 | SPNDL MTR 40T INLINE 12K NCE GEN2 VF SVC | 12/1/2024 |
| 93-30-12117A | SPNDL MTR 40T INLINE 12K NCE GEN2 VF SVC | 12/1/2024 |
| 93-30-11973 | SPNDL MTR 40T 12K INLINE PIN DRIVE | 6/1/2025 |
| 93-30-14276 | SPINDL MTR 40T DC-2 | 3/1/2025 |
| 93-30-14275 | SPINDL MTR 40T DC-1 | 1/1/2025 |

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/Check-Pin-Bushings-Transfer-Tube.png)

### 5

Verify the 3 rubber bushings for the pins are still installed to the spindle coupler and are not crushed [1].

Ensure transfer tube is seated on drawbar [2].

Align pins in motor coupler to holes in spindle coupler and lower slowly with caution.

Lightly rotate spindle nose to help align if necessary.

Once motor is fully lowered and seated, install motor plate screws hand tight.

Re-connect wiring for encoder and terminal block.

Re-install TSC or air purge.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/online-manuals/vf_vm/40t---pin-drive-motor---replacement/Align-Motor.png)

### 6

To align motor to spindle:

Run spindle at 1000 RPM clockwise/forward for 30 seconds.

Run spindle at 1000 RPM counterclockwise/reverse for 30 seconds.

Run spindle at 1000 RPM clockwise/forward for 1 minute.

Snug mounting screws while motor is running.

**Note:** When motors stops it will jolt to the side and misalign if not snugged down.

**Note:** The Octavis Vibration Analyzer can be used when aligning motor to find where vibration displacement spike is the smallest.

Torque screws per [Haas Torque Specifications](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/haas-fastener-torque-specifications.html).

Run the mill spindle vibration test per [Mill - Spindle Vibration - Tolerances](https://www.haascnc.com/service/troubleshooting-and-how-to/reference-documents/mill---spindle-vibration---tolerances.html).

Re-install the sheet metal assembly.

# 10.2 3oT/40T Spindle Motor - Troubleshooting

## **30T/40T - Spindle Motor** - Troubleshooting Guide - NGC

---

**TG0010**

Revision C - 04/2026

## Introduction

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/spindle_motor_tsg_introduction.png)

1. Drive shaft
2. Power leads
3. Built-in Spindle Motor Overheat switch connector
4. Spindle Motor Overheat Analog Sensor

**Download and fill out the Spindle Motor Inspection Report Checklist below before replacing any parts.**

[Spindle Motor Inspection Report Checklist](https://www.haascnc.com/content/dam/haascnc/service/guides/references/spindle-motor-inspection-checklist/ID0019_Rev_C.pdf)

## Symptom Table

|  |  |  |
| --- | --- | --- |
| **Symptom** | **Possible Cause** | **Corrective Action** |
| **Alarm 123** SPINDLE DRIVE FAULT  **Alarm 236** SPINDLE MOTOR OVERLOAD | Internal short circuit. | Test the spindle motor. |
| Failed temperature sensor. | Test the overheat sensor. |
| Over-aggressive application. | Adjust the program. |
| Vector drive shorted. | Test the vector drive. |
| Vector drive fans failed. |
| Cable connection incorrect or loose. | Inspect cables and connections. |
| The spindle motor cable is shorted. |
| Wye/Delta contacts burnt or shorted. | Test the Wye/Delta. |
| Spindle encoder belt worn or damaged. | Examine the encoder belt. |
| **Alarm 4.254** SPINDLE MOTOR OVERHEAT | Over-aggressive application. | Adjust program. |
| Spindle fan failed. | Check spindle fan and cable. |
| The input cable for the spindle head does not have a ferrite filter. | See **Spindle Motor Overheat** section below. |
| **Alarm 4.9975** S (SPINDLE) MOTOR TEMPERATURE CRITICAL OVERHEAT | This alarm is generated through the built-in spindle motor overheat switch. | See **Spindle Motor Overheat** section below. |
| **Alarm 4136** MOTOR CONFIGURATION FILE NOT SELECTED | Motor configuration file was not selected after new kit download. | Call your HFO to update your spindle motor brand configuration.  **For Service Techs:** Log-in to HBC. Navigate to Service > Utilities > [Documents and Software](https://hbc.haascnc.com/service/utilities/documents-and-software) >  12 - Activation Codes and Configuration Files > 5 -  Spindle Motor - Brand Configuration - NGC |
| **For 8.1/10/12 K 40T Spindle Motors Built between 10/2024 and 5/2025 only:** Decreased performance, epecially between 4k and 6k RPM. Long acceleration periods to commanded speeds. | Spindle Motor Parameters may be set incorrectly. | Check spindle motor brand. See [10.3 40T Spindle Motor Brand Identification](https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html#tab_10-3-40t-spindle-motor---identification_0). Contact your HFO with your spindle motor brand and serial number.  **For Service Techs:** Set the spindle motor brand. [Spindle Motor - Brand Configuration - NGC](https://www.haascnc.com/content/haascnc/en/service/distributor-only/ad---procedures/spindle-motor---brand-configuration---ngc.html). This is Distributor Only Content. |
| **Alarm 4136**MOTOR CONFIGURATION FILE NOT SELECTED  and Load Hardware Definition File menu is blank. | Missing configuration files. | Take an error report and contact your HFO.  For Service Techs: Set the spindle motor brand. [Spindle Motor - Brand Configuration - NGC](https://www.haascnc.com/content/haascnc/en/service/distributor-only/ad---procedures/spindle-motor---brand-configuration---ngc.html). This is Distributor Only Content. |
| Motor noise.  Poor finish on parts (Inline only). | Determine if the problem is mechanical or electrical. | 1. Run the spindle to where the noise is heard. 2. Turn off the machine. 3. If the noise is still heard then the problem is mechanical. 4. If the noise goes away then test all the electrical components in the spindle drive system. |
| Vibration due to damaged bearings. | Do a vibration analysis. |
| Coolant contamination. | Inspect the TSC union for leaks. |
| Spindle motor coolant damage. | Coolant intrusion due to TSC union leaking. | Inspect the TSC union for leaks.  Ensure the spindle motor has the latest compensation TSC union installed respectively to the machine:   * **93-2778:**TSC UNION ASSY COMP 40T VF RETROFIT SKIT * **93-2779:**TSC UNION ASSY COMP DT/DM RETROFIT SKIT        Refer to [AD0391](https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/bearing-tsc-union-to-compensating-tsc-union---upgrade---40-taper.html#gsc.tab=0) to upgrade from a bearingless TSC union to compensating TSC union.   Upgrade machine software to version **100.22.000.1000 or higher.** |
| Loud screeching during acceleration/deceleration or RPM change. | Motor parameters set incorrectly. | Contact your HFO to update Spindle Motor Parameters.  **For Service Techs:** Log-in to HBC. Navigate to Service > Utilities > [Documents and Software](https://hbc.haascnc.com/service/utilities/documents-and-software) >  12 - Activation Codes and Configuation Files > 5 -  Spindle Motor - Brand Configuration - NGC |

## Spindle Motor Overheat

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/spindle_motor_overheat_sensors.png)

**Alarm 4.254**

* This alarm is generated when the analog sensor [1] detects a limit in temperature for a certain amount of time.
* It can be also caused if there is too much electrical noise in the cable that provides wrong feedback to the control.  Make sure the cable has a ferrite filter installed at connection P39 on the I/O PCB. If the cable does not have a ferrite filter installed, install one. (P/N: 64-1252).
* The analog sensor data can be seen in **DIAGNOSTIC>I/O** tab, Analog input #9 SPINDLE MOTOR TEMPERATURE.

**Alarm 4.9975**

* This alarm is generated through the built-in spindle motor overheat switch [3].
* If spindle motor temperature checks correct.   Make sure that the cable is not damaged and that it is connected.  Check the connection at the Maincon PCB Channel 6.
* The spindle motor overheat switch status can be viewed on **Diagnostic>Mocon** tab, “CH 6 [S] Axis Brake Air Pressure” [4].

## Spindle Motor Test

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/Measure_motor_winding_short_circuit.png)

**Corrective Action:**

Disconnect all the wires from the terminal block that come from the electrical cabinet and remove the jumpers.

Use a multimeter to check these terminals on the motor:

* Measure between motor leads or terminals (1-4) (2-5) (3-6). If the difference between each pair is more than 0.1 Ohms, replace the spindle motor.
* Measure between motor leads or terminals (2-4 and 3-4) (1-5 and 3-5) (1-6 and 2-6). If the multimeter reading is not open (O.L.), replace the spindle motor.
* Measure between each individual motor lead or terminal and the motors armature. If the multimeter reading is not open (O.L.), replace the spindle motor.

## Vector Drive Test

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/Measure_Vector_Drive_Resistance_2-3_9-10-11.png)

**Corrective Action:**

Press **[POWER OFF]**.

If the vector drive voltage indicator light is on, do not touch the electrical components. The high voltage in the control cabinet can kill you. Wait for the voltage indicator LED on the vector drive to go off completely.

Inspect the vector drive.

Disconnect terminals 2 and 3 and check for a short to the spindle motor circuit by measuring the resistance of terminal 2 to 9, 10, and 11. Measure terminal 3 to 9, 10, and 11.

Go to [Vector Drive - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/vector-drive---troubleshooting-guide.html) to troubleshoot the vector drive.

## Wye/Delta Inspection

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/TG_Burnt_Contacts.jpg)

**Corrective Action:**

Check for loose connections or burn marks.

Go to [Wye-Delta Contactor - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/Wye_Delta_Contactor_Troubleshooting_Guide.html) to troubleshoot the Wye/Delta contactors.

## Spindle Motor Cables Test

**Corrective Action:**

1. Disconnect all the spindle motor cables from the amp/vector drive (terminals A, B, C. + GND).
2. If machine is equipped with a Wye-Delta contactor, disconnect the cable going to the motor. (L1,L2,L3 + GND).
3. Disconnect the spindle motor cables from the motor, including the ground cable.

   **Important:** At the motor end put electrical tape to each lead to make sure the leads do not touch each other.
4. At the electrical cabinet end, using a meter test for resistance across each lead. Take the same readings from the cable that goes to the motor from the Wye-Delta contactor.
   * If the meter reads O.L. then the cable is good.
   * If the meter reads a short circuit or low resistance the cable needs to be replaced.

Make sure all cable connections are not damaged. Use a multimeter to test each cable connection.

## Regen

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/Regen-Resistors.png)

**Corrective Action:**

Disconnect the REGEN load leads from the vector drive at terminals 1 and 2. Measure the resistance across the leads. The reading must be as follows:

* 2-resistor box: between 9.5 and 12.5 ohms.
* 3-resistor box: between 6.3 and 8.3 ohms ohms. (As shown in the illustration.)
* 4-resistor box: between 4.6 and 6.6 ohms.

Go to [Vector Drive - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/vector-drive---troubleshooting-guide.html) to troubleshoot the vector drive.

Go to [REGEN - Troubleshooting Guide](https://www.haascnc.com/content/haascnc/en/service/troubleshooting-and-how-to/troubleshooting/regen---troubleshooting-guide.html) to troubleshoot the REGEN resistors.

## Spindle Fan

**Corrective Action:**

Check for airflow on top of the spindle enclosure. Make sure there is air flow out of the spindle enclosure when the spindle is commanded to run. DT/DM were setup to blow air down onto the motor but it should now be blowing out the top. Change the fan direction to blow out the top.

Run this command in MDI: S50 M03;

Check the voltage across the black and red wires on the I/O PCB at this location:

* P32 if the machine has a Next Generation Control

The voltage should be 120 VAC. If no voltage is present, the I/O PCB is bad.

## Encoder Belt

**Corrective Action:**

Make sure the encoder belt is adjusted correctly and is not damaged. Replace a damaged or worn belt.

Make sure the encoder pulley is not damaged. Make sure the set screw is tight.

## Program/Application

**Corrective Action:**

Reduce the axis feed rate, or adjust the spindle rpm in the program.

Check for dull or damaged tooling.

## Coolant (TSC Only)

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/Spindle_Motor_TSG_TRP_Moves.png)

**Corrective Action:**

Remove the head cover and inspect the TSC union for leaks. A leaking coolant union may cause coolant to get into the motor and wash the grease out of the bearings.

## Bearings

**Corrective Action:**

Damaged bearings in the spindle motor can cause finish issues on the part. Contact your local HFO for a vibration analysis to see if the bearings are damaged.

## Electrical Diagrams: Spindle Encoder Feedback / Drive Command

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/spindle_motor_electrical_schematic.png)

![](https://www.haascnc.com/content/dam/haascnc/service/guides/troubleshooting/spindle-motor---troubleshooting-guide/spindle_motor_electrical_diagram.png)

# 10.3 Spindle Motor - Brand Identification - VMC

## **Spindle Motor Brand** - Identification

---

*Applies to machines built after August 2016*

## Introduction

This reference document demonstrates how to identify the spindle motor brand by inspecting the label on your spindle motor.

## Remove JBOX - VF/VM

**NOTE:** If it is necessary to remove (or partially disassemble) spindle motor assembly to access JBOX, refer to [40T Pin Drive Motor- Replacement](https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html) for more information.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/vmc---40-taper---inline-spindle---replacement/JBOXDisassembly.png)

### 1

Unbolt cover on JBOX [1]

Remove nuts securing terminal block and lift off of threads. [2]

Remove screw on the bronze bracket holding the thermal probe wire.

Remove screws securing JBOX to spindle motor. [3]

Lift JBOX and locate spindle motor label. [4]

## Identification

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/vmc---40-taper---inline-spindle---replacement/SpindleMotorLabel.png)

### 1

Identify motor brand name at the top or bottom of spindle motor label:

1. **HPB**
2. **HiGen**
3. **Yaskawa**

When identification is complete, reinstall JBOX and spindle motor.

**For Service Techs:** Log-in to HBC. Navigate to Service > Utilities > [Documents and Software](https://hbc.haascnc.com/service/utilities/documents-and-software) >  12 - Activation Codes and Configuation Files > 5 -  Spindle Motor - Brand Configuration - NGC to update spindle motor brand.

**Note:** Only Haas Certified Service Technicians can log into this site.

## Remove JBOX - VF/VM

**NOTE:** If it is necessary to remove (or partially disassemble) spindle motor assembly to access JBOX, refer to [40T Pin Drive Motor- Replacement](https://www.haascnc.com/service/online-manuals/vf-vm-series---service-manual/vf-vm---40t-spindle-motor.html) for more information.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/vmc---40-taper---inline-spindle---replacement/JBOXDisassembly.png)

### 1

Unbolt cover on JBOX [1]

Remove nuts securing terminal block and lift off of threads. [2]

Remove screw on the bronze bracket holding the thermal probe wire.

Remove screws securing JBOX to spindle motor. [3]

Lift JBOX and locate spindle motor label. [4]

## Identification

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/vmc---40-taper---inline-spindle---replacement/SpindleMotorLabel.png)

### 1

Identify motor brand name at the top or bottom of spindle motor label:

1. **HPB**
2. **HiGen**
3. **Yaskawa**

When identification is complete, reinstall JBOX and spindle motor.

**For Service Techs:** Log-in to HBC. Navigate to Service > Utilities > [Documents and Software](https://hbc.haascnc.com/service/utilities/documents-and-software) >  12 - Activation Codes and Configuation Files > 5 -  Spindle Motor - Brand Configuration - NGC to update spindle motor brand.

**Note:** Only Haas Certified Service Technicians can log into this site.

# 10.4 40T Spindle Motor - HDF Requirements

## **40T Spindle Motor** - HDF Requirements - NGC

---

Revision C - 3/2026

## Introduction

The Hardware Definition File (HDF) allows you to configure your machine to be compatible with multiple spindle brands.

In the event of a spindle motor replacement, a service tech may easily swap out the motor and update the spindle motor brand configuration.

The table below lists the 40T spindle motor service kits that currently require a Hardware Definition File (HDF). **If you have recently installed one of these kits, contact your local Haas Factory Outlet to update your spindle motor brand configuration on your machine.**

**For Service Techs:** To update your spindle motor brand configuration:

1. Log in to the [Dealer-only Content (DOC)](https://haas-sso.helloid.com/RelayService/Redirect/2001b686-aa42-44a8-9640-d2af01123553) portal.
2. Navigate to the [Spindle Motor - Brand Configuration - NGC](https://www.haascnc.com/content/haascnc/en/service/distributor-only/ad---procedures/spindle-motor---brand-configuration---ngc.html) page.

**Note:**Only Haas Certified Service Technicians can log into this site.

|  |  |  |
| --- | --- | --- |
| Kit Number | Kit Name | Valid Date |
| 93-30-12078 | SPNDL MTR 40T INLINE 12K PIN DRV | 6/1/2025 |
| 93-30-12078A | SPNDL MTR 40T INLINE 12K NCE GEN2 EC SVC | 6/1/2025 |
| 93-30-12117 | SPNDL MTR 40T INLINE 12K NCE GEN2 VF SVC | 12/1/2024 |
| 93-30-12117A | SPNDL MTR 40T INLINE 12K NCE GEN2 VF SVC | 12/1/2024 |
| 93-30-11973 | SPNDL MTR 40T 12K INLINE PIN DRIVE | 6/1/2025 |
| 93-30-14276 | SPINDL MTR 40T DC-2 | 3/1/2025 |
| 93-30-14275 | SPINDL MTR 40T DC-1 | 1/1/2025 |