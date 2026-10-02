# BetterHaasModel
In search of a more better Haas MTConnect information model.

https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/machine-data-collection---ngc.html

## TODO

- [ ] Pretty print SHDR
- [ ] Find unique SHDR DataItems
- [ ] Compare to existing MTConnect model
- [ ] Make better model
- [ ] Supplement with Q/E commands
- [ ] Supplement with existing Agent
- [ ] Implement heartbeat
- [ ] Tunnel SHDR to Agent

## Running Script

Terminate script by pressing 'x'.

```
pwsh ./get_shdr.ps1 -remote 127.0.0.1 -port 9998
```

```
^B2022-10-07 07:18:59.668|ANALOG_AIR_PRESSURE|2373|SPINDLE_MOTOR_TEMPERATURE|725|PLUS_5V_VOLTAGE|3089|ANALOG_REFERENCE_VOLTAGE|3101`n^C^B2022-10-07 07:18:59.675|AirPressure|90.0|DcVolt|321.0`n^C

^B2022-10-07 07:18:59.687|accelerometerX|-512|accelerometerY|256|accelerometerZ|384`n^C^B2022-10-07 07:18:59.693|Aload|1`n^C

^B2022-10-07 07:18:59.705|SpindleMotorTemp|31.1|DcVolt|320.0`n^C^B2022-10-07 07:18:59.718|twelveVoltPlusRail|2515|twelveVoltNegativeRail|1446|batteryVoltage|1537|dacTemp1|1299|dacTemp1|1299|dcBusVoltage|2625`n^C

^B2022-10-07 07:18:59.729|SPINDLE_MOTOR_TEMPERATURE|720|_12V_VOLTAGE|1846|CHIP_CONVEYOR_CURRENT|6|ANALOG_INPUT_38|1838|PLUS_5V_VOLTAGE|3088|ANALOG_REFERENCE_VOLTAGE|3100`n^C
```

## Installing Powershell

### Linux ARM

```
sudo apt-get install curl
curl -L -o /tmp/powershell.tar.gz https://github.com/PowerShell/PowerShell/releases/download/v7.2.5/powershell-7.2.5-linux-arm64.tar.gz
sudo mkdir -p /opt/microsoft/powershell/7
sudo tar zxf /tmp/powershell.tar.gz -C /opt/microsoft/powershell/7
sudo chmod +x /opt/microsoft/powershell/7/pwsh
sudo ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh
```

### Linux X86

```
sudo apt-get install -y wget apt-transport-https software-properties-common
wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y powershell
```