# Climate Controller (two ESP32 boards)

Holds a temperature set point and a humidity set point by switching 4 relays: **fan, heater, humidifier, compressor**. The fan speed is set with a 0-10 V signal, and the fan's tach output is watched for a fan fault.

There are two boards joined by a serial cable:

- **Mainboard**: ESP32 NodeMCU WROOM-32 DevKit. Runs the control rules. It reads the AHT20 + BMP280 sensor, switches the relay board, drives the PWM to 0-10 V converter for the fan speed, and reads the fan tach. It keeps the settings in flash, and carries on controlling if the Controller is unplugged.
- **Controller**: ESP32-C3 SuperMini. The user interface: a 1.3" OLED (DST-013) and two rotary encoders with push switches. It shows the readings, the set points, what is running and any fault, and sends your changes to the Mainboard.

More documents:

- The project plan, the control rules and the phases are in **[PLAN.md](PLAN.md)**.
- Picking up the project? Start with **[CLAUDE.md](CLAUDE.md)**.
- **[hardware/](hardware/README.md)** has the relay carrier PCB (KiCad 10), its simulations and a 3D-printable case. These are the Phase 1 **ESP8266** design and do not fit the new Mainboard. They are kept for reference.

**Mains:** a compressor needs a contactor, and a heater needs its own thermal cut-out. See PLAN.md section 1.

## Mainboard pinout (ESP32 NodeMCU WROOM-32)

```
                      +---------------------+
                  EN  | o                 o |  GPIO23
              GPIO36  | o                 o |  GPIO22 ------> sensor SCL
              GPIO39  | o                 o |  GPIO1 (TX0, USB)
 fan tach --> GPIO34  | o                 o |  GPIO3 (RX0, USB)
              GPIO35  | o                 o |  GPIO21 <-----> sensor SDA
 IN3 hum  <-- GPIO32  | o                 o |  GPIO19
 IN4 comp <-- GPIO33  | o                 o |  GPIO18
 fan PWM  <-- GPIO25  | o                 o |  GPIO5
 IN1 fan  <-- GPIO26  | o                 o |  GPIO17 (TX2) ---> Controller RX (GPIO20)
 IN2 heat <-- GPIO27  | o                 o |  GPIO16 (RX2) <--- Controller TX (GPIO21)
              GPIO14  | o                 o |  GPIO4 ----------> RS-485 DE/RE (later)
              GPIO12  | o                 o |  GPIO2
              GPIO13  | o                 o |  GPIO15
                 GND  | o                 o |  GND
 5 V in/out      VIN  | o                 o |  3V3 ------------> sensor VIN, tach pull-up
                      +-------[USB]---------+
```

This is the common 30-pin board. The 38-pin DevKitC has the same GPIOs in a different order, so wire by the GPIO numbers printed on your board.

| GPIO | Connects to | Notes |
|---|---|---|
| 26 | Relay board IN1: **Fan** | |
| 27 | Relay board IN2: **Heater** | |
| 32 | Relay board IN3: **Humidifier** | |
| 33 | Relay board IN4: **Compressor** | |
| VIN (5 V), GND | Relay board VCC, GND | |
| 21 | Sensor SDA | AHT20 (0x38) + BMP280 (0x76/0x77), I2C at 100 kHz |
| 22 | Sensor SCL | |
| 3V3, GND | Sensor VIN, GND | |
| 25 | PWM to 0-10 V converter: PWM input | 1 kHz. Converter GND to Mainboard GND |
| 34 | Fan tach | Input only. **Fit a 10 kΩ pull-up to 3V3** (never 5 V), plus 1 kΩ in series and 10 nF to GND at the pin |
| 17 (TX2) | Controller RX (GPIO 20) | Link, 115200 baud |
| 16 (RX2) | Controller TX (GPIO 21) | |
| 4 | MAX485 DE + /RE (when RS-485 is fitted) | High while sending. Driven even on plain UART, where it is harmless |
| VIN, GND | Controller 5V, GND (in the link cable) | Powers the Controller |

Pins to leave alone: GPIO 0, 2, 5, 12 and 15 (they decide how the chip boots), 6 to 11 (flash), 1 and 3 (USB serial).

**Relay board:** most cheap 4-relay boards switch on when IN is LOW (`RELAY_ACTIVE_LOW = true` in `src/mainboard/config.h`). If a relay will not switch off, or its LED glows faintly, the 3.3 V signal is not quite high enough for the 5 V board. Remove the JD-VCC jumper, power JD-VCC from 5 V, and power VCC from the ESP32's 3V3.

**Fan:** the converter output goes to the fan's 0-10 V input, and its output ground to the fan's 0-10 V reference ground. Check that the fan's 0-10 V input and tach are SELV (isolated from mains) before connecting them. Some converters need a PWM signal of 5 V or more: if yours does not respond to 3.3 V, add a transistor or level shifter. Calibrate it with a meter and set `FAN_PWM_DUTY_AT_0V` / `FAN_PWM_DUTY_AT_10V` in `src/mainboard/config.h`.

## Controller pinout (ESP32-C3 SuperMini)

| GPIO | Connects to | Notes |
|---|---|---|
| 8 | OLED SDA | Strapping pin, held high by the I2C pull-ups |
| 9 | OLED SCK | Strapping pin (BOOT button) |
| 3V3, GND | OLED VDD, GND | |
| 0 | Encoder 1 A (CLK) | Encoder 1: temperature, mode |
| 1 | Encoder 1 B (DT) | |
| 3 | Encoder 1 push (SW) | |
| 4 | Encoder 2 A (CLK) | Encoder 2: humidity, menu |
| 5 | Encoder 2 B (DT) | |
| 10 | Encoder 2 push (SW) | |
| GND | Encoder common (and the switch's other side) | Internal pull-ups are used |
| 21 | Mainboard RX2 (GPIO 16) | Link |
| 20 | Mainboard TX2 (GPIO 17) | |
| 7 | MAX485 DE + /RE (when RS-485 is fitted) | |
| 5V, GND | Mainboard VIN, GND (in the link cable) | |

If your encoders are on a module with a "+" pin (such as the KY-040), connect "+" to **3V3**, not 5 V. GPIO 18/19 are the USB port. GPIO 2 and 6 are spare.

## Link cable

For now this is plain UART over a short cable (4 cores: 5 V, GND, TX, RX, with TX and RX crossed over). For the planned ~10 m run, fit a MAX485-type RS-485 module at each end and use a twisted pair for A/B:

- Each ESP32's TX goes to DI, RX to RO, and the DE and /RE pins (tied together) to GPIO 4 on the Mainboard and GPIO 7 on the Controller. A to A, B to B.
- **The MAX485 is a 5 V chip, and its RO output is 5 V, which the ESP32 inputs cannot take.** Use a 3.3 V part (MAX3485, SP3485) powered from 3V3, or put a divider (for example 1 kΩ / 2 kΩ) between RO and the ESP32 RX pin.
- Fit 120 Ω termination across A/B at both ends of a long cable. Most modules have it on board.
- No firmware change is needed: the link only ever has one side sending at a time, and the DE pin is already driven.

## Build and upload

1. Open this folder in VS Code with the PlatformIO extension.
2. Plug in one board, and pick its environment:
   - Mainboard: `pio run -e mainboard -t upload`
   - Controller: `pio run -e controller -t upload`
3. `pio run` (no `-e`) builds both.
4. Serial monitor at 115200: `pio device monitor -e mainboard` (or `-e controller`).

With both boards plugged in at once, say which port to use. For example, on Windows:

```bash
pio run -e mainboard -t upload --upload-port COM5
```

On Linux the ports are names like `/dev/ttyUSB0` (Mainboard) and `/dev/ttyACM0` (Controller).

The SuperMini flashes over its own USB port. If it will not connect, hold **BOOT**, tap **RESET**, release BOOT and upload again. After that, press RESET to start the new firmware.

The WROOM-32 DevKit needs a CP210x or CH340 USB driver on Windows, depending on the board. If an upload hangs at "Connecting...", hold its **BOOT** button until the upload starts.

## Using the Controller

**Home screen:** temperature and humidity (large), the set points, the mode, the loads that are running, and a bottom line with the fan speed and RPM, the pressure, or a fault.

| Control | What it does |
|---|---|
| Turn encoder 1 | Temperature set point (0.1 °C steps) |
| Push encoder 1 | Next mode: Off, Auto, Manual |
| Turn encoder 2 | Humidity set point (1 % steps) |
| Long-push encoder 2 | Settings menu |

A value you are changing is shown inverted. It is sent to the Mainboard once the knob has been still for 1 s, and goes back to normal when the Mainboard accepts it.

**Settings menu:** turn encoder 2 to choose an item, and turn encoder 1 to change it. Push either encoder on **Clear fan fault** or **Exit**. Long-push encoder 2 to go back, or leave it alone for 60 s. The items are:

- Bands and the fan settings: fan mode, speed, run-on, and the fan fault RPM (0 turns the check off), spin-up and delay.
- Compressor times and sensor offsets.
- The manual relay switches (only shown in Manual mode).
- Real or simulated sensor. In Sim, the simulated temperature, humidity, "room reacts" and sensor fault are shown too.

**Faults:** SENSOR FAULT and FAN FAULT take over the screen until you push either encoder. They then stay on the bottom line while they last. A fan fault is latched: clear it from the menu once the fan is working again. If the Controller hears nothing from the Mainboard for 5 s it shows **NO LINK TO MAINBOARD**. The Mainboard keeps controlling with its saved settings.

The simulated sensor is never saved: the Mainboard always starts on the real sensor after a reset.

## Mainboard serial commands (115200 baud, USB)

For bench testing without the Controller. Type `help` for the list.

```
status | settings | help
mode off|auto|manual
sensor real|sim
temp <C> | hum <%RH>        simulated reading (switches to the simulated sensor)
react on|off | fault on|off
relay <1-4> on|off           Manual mode only
clearfault
set <name> <value>           any name from "settings", e.g. set tempset 21.5
```

## Files

```
PLAN.md                        Project plan, control rules, pin plan, phases
platformio.ini                 Build environments: mainboard, controller
include/link_protocol.h        Link messages, shared by both firmwares
src/mainboard/main.cpp         Mainboard: relays, fan, link, serial commands
src/mainboard/climate_control.*  Control rules and fan fault (plain C++, no Arduino code)
src/mainboard/sensor.*         AHT20 + BMP280
src/mainboard/fan.*            Fan PWM (0-10 V) and tach
src/mainboard/storage.*        Saves settings to flash
src/mainboard/sim_room.h       Simulated sensor and room
src/mainboard/config.h         Mainboard pins and timings
src/controller/main.cpp        Controller: display, menus, link
src/controller/input.h         Encoders and push buttons
src/controller/config.h        Controller pins and timings
tools/host-test/               Tests of the control rules and link framing, run on a PC
```

The control rules can be tested on a PC without a board (needs `g++`):

```bash
g++ -std=c++17 -Isrc/mainboard -Iinclude tools/host-test/test_control.cpp src/mainboard/climate_control.cpp -o test_control && ./test_control
```

The Phase 1 firmware (ESP8266, web page, WiFi, OTA) was removed. The last commit with it is `65d825e`.

## License

- Firmware, scripts and documentation: [MIT](LICENSE).
- Hardware (everything in `hardware/`: the KiCad design files, generator scripts, simulations and case CAD): [CERN-OHL-P-2.0](hardware/LICENSE), the permissive CERN Open Hardware Licence. You may use, change, make and sell it. Keep the licence notice with any copies of the design files.
