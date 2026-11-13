# Climate Controller (ESP8266 / ESP32)

Holds a temperature set point and a humidity set point by switching 4 relays: **fan, heater, humidifier, compressor**. A web page shows the readings, the state of each relay and why it is on, and lets you change the set points.

- The project plan, the control rules and the sensor choice are in **[PLAN.md](PLAN.md)**.
- The custom relay carrier PCB (KiCad 10), its simulations and the 3D-printable case are in **[hardware/](hardware/README.md)**.
- Picking up the project? Start with **[CLAUDE.md](CLAUDE.md)**.
- There is no sensor yet. The web page has a **simulated sensor**: type in a temperature and humidity, or let the simulated room react to the relays.

## Wiring (NodeMCU ESP8266)

```
     +-----------------------------+
 A0  | o                         o | D0 --------> IN1  Fan
 RSV | o                         o | D1 ........  (sensor SCL, Phase 2)
 RSV | o                         o | D2 ........  (sensor SDA, Phase 2)
 SD3 | o                         o | D3
 SD2 | o                         o | D4
 SD1 | o                         o | 3V3 .......  (sensor VIN, Phase 2)
 CMD | o                         o | GND
 SD0 | o                         o | D5 --------> IN3  Humidifier
 CLK | o                         o | D6 --------> IN4  Compressor
 GND | o ---------------------------------------> GND  relay module
 3V3 | o                         o | D7 --------> IN2  Heater
 EN  | o                         o | D8
 RST | o                         o | RX
 GND | o                         o | TX
 VIN | o ---------------------------------------> VCC  relay module
     +-------------[USB]-----------+
```

| Relay module | NodeMCU | GPIO | Load |
|---|---|---|---|
| VCC | VIN (5 V) | - | - |
| GND | GND | - | - |
| IN1 | D0 | 16 | Fan |
| IN2 | D7 | 13 | Heater |
| IN3 | D5 | 14 | Humidifier |
| IN4 | D6 | 12 | Compressor |

D1 and D2 are kept free for the I2C sensor. Do not use D3, D4 or D8 for relays: they decide how the chip boots.

Most relay boards switch on when IN is LOW (`RELAY_ACTIVE_LOW = true` in `include/config.h`). If a relay will not switch off, or its LED glows faintly, the 3.3 V signal is not quite high enough for the 5 V board. Remove the JD-VCC jumper, power JD-VCC from 5 V, and power VCC from the NodeMCU's 3V3.

**Mains:** a compressor needs a contactor, and a heater needs its own thermal cut-out. See PLAN.md section 1.

## Build and upload

1. Open this folder in VS Code with the PlatformIO extension.
2. Put your WiFi details in `include/secrets.h` (copy it from `secrets.example.h`).
3. Plug in the NodeMCU and click **Upload**, or run `pio run -t upload`.
4. Open `http://climate.local`, or the IP address printed in the Serial Monitor (115200 baud).

If the board cannot join your WiFi, it starts an access point called **Climate-Setup** (password `climate1234`). Join it and open `http://192.168.4.1`.

After the first USB upload you can update over WiFi with `pio run -e ota -t upload`. Set the same password in `OTA_PASSWORD` (`secrets.h`) and `upload_flags` (`platformio.ini`).

For an ESP32 DevKit, use `pio run -e esp32dev -t upload`. The ESP32 pins are listed in `include/config.h`.

## Using the web page

- **Mode:**
  - **Off** stops everything.
  - **Auto** follows the set points.
  - **Manual** shows a switch for each relay, so you can check the wiring.
- **Equipment:** each relay, whether it is on, and why. The compressor shows a countdown while it rests.
- **Set points:** change the values, then click **Save**. **Advanced** has the bands, the compressor rest and minimum run times, the fan run-on, and "fan always on".
- **Simulated sensor:**
  - The − and + buttons change the reading straight away.
  - **Room reacts** lets the relays move the readings, so you can watch a full cycle in a minute or two.
  - **Sensor fault** tests the safe shutdown.

## Testing the control rules

`tools/test-control.ps1` runs the test list from PLAN.md against the board through the API. It takes about 40 s, the relays will click, and it leaves the unit in Off mode with the default settings.

```
powershell -ExecutionPolicy Bypass -File tools\test-control.ps1 -Base http://192.168.0.133
```

## API

```
GET  /api/state
POST /api/settings  tempSet, humSet, tempBand, humBand, mode=off|auto|manual,
                    fanMode=auto|on, compMinOff, compMinOn, fanRunOn
POST /api/sim       temp, hum, react=0|1, fault=0|1
POST /api/manual    ch=1-4|all, state=on|off|toggle     (Manual mode only)
```

Example: `curl -X POST http://climate.local/api/settings -d "mode=auto&tempSet=21.5&humSet=55"`

## Serial commands (115200 baud)

`status`, `mode off|auto|manual`, `temp 23.5`, `hum 60`

## Files

```
PLAN.md                Project plan, control rules, sensors, phases
platformio.ini         Build settings (NodeMCU default, ESP32, OTA)
include/config.h       Relay pins, network names
include/secrets.h      Your WiFi and passwords (git-ignored)
include/web_ui.h       The web page
src/controller.*       Control rules (no Arduino code, so it can be unit-tested later)
src/sim_room.h         Simulated sensor and room
src/storage.*          Saves settings to flash
src/main.cpp           Relays, web server, WiFi, serial commands
tools/test-control.ps1 Control-rule test against a running board
```
