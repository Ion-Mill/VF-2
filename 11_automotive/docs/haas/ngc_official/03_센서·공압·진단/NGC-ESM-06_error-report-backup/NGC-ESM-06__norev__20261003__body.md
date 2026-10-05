<!-- doc_id: NGC-ESM-06 | title: NGC - Error Report and Backup - Haas Service Manual | revision: 표기 없음 | last_updated: 표기 없음 | source_url: https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---error-report-and-backup.html | retrieved_at: 2026-10-03T18:03:02 | retrieved_via: direct | original_file: NGC-ESM-06__norev__20261003.html | original_sha256: 3b4947211b4eef5fb6e8f0cdaa6bd61874b312c6722a61a98680a838a0ebb45b | extraction: div.print-only · scripts/extract_ngc_body.py | license: Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 -->

**본문 추출본 (원본 아님)** — 사실 확인은 같은 폴더의 원본 HTML과 공식 URL로 한다. 그림은 Haas 공식 주소에서 불러오므로 인터넷 연결 시에만 보인다.

|  |  |
| --- | --- |
| doc\_id | NGC-ESM-06 |
| title | NGC - Error Report and Backup - Haas Service Manual |
| revision | 표기 없음 |
| last\_updated | 표기 없음 |
| source\_url | https://www.haascnc.com/service/online-manuals/next-gen-control-electrical---service-manual/ngc---error-report-and-backup.html |
| retrieved\_at | 2026-10-03T18:03:02 |
| retrieved\_via | direct |
| original\_file | NGC-ESM-06\_\_norev\_\_20261003.html |
| original\_sha256 | 3b4947211b4eef5fb6e8f0cdaa6bd61874b312c6722a61a98680a838a0ebb45b |
| extraction | div.print-only · scripts/extract\_ngc\_body.py |
| license | Haas 저작물: 사이트 약관상 서면 허가 없는 사용 불가 표기. 내부 참고용 사본, 재배포 금지 |

Next Gen Control Electrical - Service Manual

---

Go To :

* [6.1 Error Report](#tab_error-report_0)
* [6.2 Machine Data Backup](#tab_data-backup_0)

# 6.1 Error Report

## **Error Report** - Next Generation Control

---

**RD0102**

Revision A - 08/2026

## Introduction

The following document will show you how to generate and Error Report and what is used for.

## Alarm History - Alarms & Notifications

The following service video shows how to view alarm history and system notifications.

**Note:**  This service video is for reference only and does not replace the written procedure.

## Error Reports

Haas machines with the Next Generation Control (NGC) can create an error report that saves the state of the machine for analysis. The error report is a ZIP file that includes a screenshot, the active program, and other information for diagnostics and system debugging. Train your customers to create this file immediately after a crash, a control freeze, an alarm, or when an apparent software bug appears.

Be sure always to generate the error report with the alarm active.

If the control freezes and does not respond to input:

1. Take a digital photograph of the control screen.
2. Cycle power.
3. Immediately generate an error report.

Use these steps to generate an error report:

1. Put a USB memory device into the USB port. The USB memory device is not required to generate an error report; without it, the control saves the error report in User Data, and you can retrieve it over Net Share or with a USB memory device.
2. Press **[SHIFT]**.
3. Press **[F3]**.

Send the ZIP file and digital photo to [[email protected]](https://www.haascnc.com/cdn-cgi/l/email-protection) for analysis.

## Auto Error Report

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---how-to-read-an-error-report/Auto-Save-Error-Report.jpg)

**This feature is only available in Software Version 100.23.000.1200 or higher:**

Haas machines with Next Generation Control (NGC) can automatically create an error report that saves the machine's state for analysis whenever a specific alarm is triggered.

Go to the Alarm Viewer tab.

Highlight the desired alarm and press **[ENTER]** [1] to check it for auto error report.

Multiple alarms can be set for an automatic error report. Press **[ALTER]** [2] to filter all set alarms.

**Important:**This feature disarms at every power up. For continuous monitoring, it is necessary to re-arm the feature after a power cycle.

**Important:** If a USB is inserted, auto error reports are saved in the USB folder on the Haas pendant. If no USB is inserted, auto error reports are saved in the **List Program** > **User Data** tab within a folder called **AutoSavedErrorReports**. Only five error reports can be saved in this folder at a time.

## Error Report Screenshot

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/next-generation-control---how-to-read-an-error-report/ngc_error_report_snapshot.png)

The screenshot of the error report contains useful information if it is taken at the correct time.

* Always generate the error report with the alarm active.
* The screenshot is an example of a correctly generated error report.
* You can see the active alarm, the program that was running, and the line of the program where the alarm occurred.

# 6.1 Machine Data Backup

## **Machine Data Backup** - NGC

---

*Applies to machines built from: September, 2015*

## Back Up Machine

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/ngc---backup-machine/Storm_Backup_List_Programs.png)

### 1

Use this procedure to backup all of the machine files on your Next Generation Control machine.

Set Setting 155, Load Pocket Tables, to ON.

**Note:** Make sure the memory lock key switch is in the unlocked position.

Push **[LIST PROGRAM]**.

Use the cursor arrows to select the USB tab [1].

Push **[F4]**, System [2].

Use the up and down cursor to select Back Up Machine [3].

Push **[ENTER]**.

### 2

**<u>Important Information</u>**

* The next step puts the copies of the machine data files in the open directory on the USB memory device.
* The backup makes a .zip file. You can open this .zip file on the control or on a PC.
* The name of the .zip file that contains the backup data has this structure: "HaasBackup", then the date. For example, HaasBackup(xx-xx-xxxx).zip.
* You cannot make a backup file if the control is in MEMORY or USER DATA modes.

![](https://www.haascnc.com/content/dam/haascnc/service/guides/how-to/ngc---backup-machine/backup_machine_AI_pic_001_RevA.png)

### 3

This screen lets you select the data files to make copies of.

**Caution:** If the machine has software version 100.15.000.1011, DO NOT select User Data [2] when you make a backup. Go to the User Data tab [1]. Select the User Data files to backup. Push **[F2]** to copy the files to the USB memory device.

Use the up and down cursors to make a selection.

Push **[ENTER]** to select or deselect what you must backup.

Push **[F4]** to make the backup.

### 4

Know this information about the stored data.

* System Data makes copies of these data files:
  + settings
  + offsets
  + macro variables
  + advanced tool management (ATM)
  + alarm history
  + key history
  + linear screw compensation (LSC)
  + network configurations
* User Data makes copies of all the files in the User Data folder.
* Programs makes copies of all the files in the Memory folder.
* The approximate size of each selection shows on the right side of the display. The total Estimated size shows at the bottom.
* If a selection is too large for the USB memory device, it is grey.