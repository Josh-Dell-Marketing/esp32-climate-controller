# Climate Controller: Project Plan

A temperature and humidity controller for a small climate unit. It uses two ESP32 boards, joined by a wire:

- **Mainboard** (ESP32 NodeMCU WROOM-32 DevKit) does all the control. It reads the AHT20 + BMP280 sensor board, switches the 4 relays (fan, heater, humidifier, compressor), sets the fan speed through a PWM to 0-10 V converter, and reads the fan's tach output. It holds a temperature set point and a humidity set point, and keeps the settings in its flash.
- **Controller** (ESP32-C3 SuperMini) is the user interface. It drives a DST-013 OLED display and reads two rotary encoders with push switches. It shows the measured temperature and humidity, the mode, what is running, and any fault. Set point changes, mode changes and configuration changes are made on the encoders and sent to the Mainboard as commands.

For testing there are 2 encoders. The final version will use one concentric (dual-shaft) rotary encoder.

There is no web page in the current scope. Everything is set on the Controller. (Phase 1 was built on an ESP8266 with a web page and a simulated sensor. That code is still in `src/` and is the starting point for the Mainboard firmware.)

Status, 20 Nov 2026: Phase 1 is built (on the ESP8266). The design has moved to the two-ESP32 layout above. Next is Phase 2: move the control firmware to the Mainboard.

## 1. Hardware

### System overview

```
                 wired link (UART, see "Controller link")
 Controller  <------------------------------------------->  Mainboard
 ESP32-C3 SuperMini                                          ESP32 WROOM-32 DevKit
   - DST-013 OLED (I2C)                                        - AHT20 + BMP280 sensor (I2C)
   - Encoder 1 (A, B, push)                                    - 4-relay board (fan, heater, humidifier, compressor)
   - Encoder 2 (A, B, push)                                    - PWM -> 0-10 V converter -> fan speed input
                                                               - fan tach input (open collector, 1 pulse/rev)
```

The Mainboard runs the control rules on its own. If the Controller is unplugged or the link fails, the Mainboard carries on with its saved settings, and the Controller shows a link fault.

### Mainboard pins (ESP32 WROOM-32, proposed)

| Function | GPIO | Notes |
|---|---|---|
| Relay IN1: Fan | 26 | Already used for the ESP32 build in `config.h` |
| Relay IN2: Heater | 27 | |
| Relay IN3: Humidifier | 32 | |
| Relay IN4: Compressor | 33 | |
| I2C SDA (sensor) | 21 | ESP32 default |
| I2C SCL (sensor) | 22 | ESP32 default |
| Fan speed PWM (to 0-10 V converter) | 25 | LEDC PWM |
| Fan tach input | 34 | Input only, no internal pull-up: fit an external pull-up (see "Fan tach") |
| Link TX (to Controller RX) | 17 | UART2 |
| Link RX (from Controller TX) | 16 | UART2 |

Avoid GPIO 0, 2, 5, 12 and 15 for outputs (boot strapping pins), and GPIO 6 to 11 (used by the flash chip). None of the relay pins above are strapping pins, so no relay can click on during boot.

The relay board also needs VCC (5 V) and GND. Most cheap 4-relay boards switch ON when IN is pulled LOW. Check the board you have, and set `RELAY_ACTIVE_LOW` in `config.h` to match.

### Controller pins (ESP32-C3 SuperMini, proposed)

The SuperMini has GPIO 0 to 10, 20 and 21 on its pins. USB (programming and serial monitor) uses the C3's built-in USB on GPIO 18 and 19, so GPIO 20 and 21 are free for the link. GPIO 2, 8 and 9 are strapping pins. GPIO 8 also drives the on-board LED, and GPIO 9 is the BOOT button.

| Function | GPIO | Notes |
|---|---|---|
| OLED SDA | 8 | The I2C pull-ups hold it high at boot, which this strapping pin needs |
| OLED SCL | 9 | As above. Do not hold it low at power-up, or the chip enters download mode |
| Encoder 1 A | 0 | |
| Encoder 1 B | 1 | |
| Encoder 1 push | 3 | |
| Encoder 2 A | 4 | |
| Encoder 2 B | 5 | |
| Encoder 2 push | 10 | |
| Link TX (to Mainboard RX) | 21 | UART1 |
| Link RX (from Mainboard TX) | 20 | UART1 |
| Spare | 2, 6, 7 | GPIO 2 is a strapping pin |

Use the internal pull-ups on the encoder pins, with the encoder common pin to GND. Check these pins against your SuperMini, because clones differ.

### Display

- **DST-013**: to be confirmed. It is assumed to be a 1.3-inch 128 × 64 monochrome OLED on I2C (usually an SH1106 driver at address 0x3C; some use an SSD1306). Check the driver before choosing the library. U8g2 (`olikraus/U8g2`) supports both.
- It shows: measured temperature and humidity, set points, mode, which loads are running, the compressor rest countdown, and fault messages.

### Encoders

Proposed use, to be confirmed:

- **Encoder 1:** turn to change the temperature set point. Push to change the mode (Off, Auto, Manual).
- **Encoder 2:** turn to change the humidity set point. Long push to open the settings menu, where encoder 2 picks an item and encoder 1 changes its value.
- With the final concentric encoder, the outer shaft does the job of encoder 1 and the inner shaft (with its push switch) the job of encoder 2.

A change is sent to the Mainboard when the knob has been still for about 1 s, so the Mainboard does not save to flash on every click.

### Controller link

A wired serial link. Proposed:

- UART at 115200 baud, 8N1. TX of each board to RX of the other, plus GND. The same cable can carry 5 V from the Mainboard side to power the Controller (4 cores: 5 V, GND, TX, RX).
- For a cable longer than about 1 m, or one that runs near the compressor or mains wiring, put an RS-485 transceiver at each end (for example a 3.3 V MAX3485 module), using a twisted pair.
- The Mainboard is in charge. It keeps the settings, and the Controller asks for them when it connects.
- Every message has a start byte, a type, a length, the data and a CRC. A message with a bad CRC is dropped.
- The Mainboard sends a status message every 1 s: temperature, humidity, pressure, mode, set points, each relay and why it is on, the fan speed command and measured RPM, the compressor rest time left, and the fault flags.
- The Controller sends commands: set point changes, mode changes, settings changes, manual relay switches, and "clear fault". The Mainboard answers each command with an accept or reject, and the Controller shows the value only after it is accepted.
- If the Controller hears no status message for 5 s, it shows "NO LINK TO MAINBOARD". The Mainboard keeps controlling with its saved settings.

The message layout goes in one shared header that both firmwares include, so they cannot drift apart.

### Sensor: AHT20 + BMP280 board

- One breakout board with two chips on the same I2C bus: the **AHT20** (temperature and humidity, I2C address 0x38) and the **BMP280** (pressure and temperature, address 0x76 or 0x77).
- The control uses the AHT20's temperature and humidity. The BMP280's pressure is shown for information. Its temperature can be used as a cross-check against the AHT20 (a big difference suggests a sensor problem).
- Wiring: VIN to 3V3, GND to GND, SDA to GPIO 21, SCL to GPIO 22. Run the bus at 100 kHz.
- Libraries: `adafruit/Adafruit AHTX0` and `adafruit/Adafruit BMP280 Library`.
- Put the sensor where it measures the room air, for example the return air. Keep it away from the humidifier outlet, the heater and the cold coil.

### Fan control

The fan has a 0-10 V speed input, referenced to its own control ground pin: 10 V is full speed and 0 V is stopped. The Mainboard makes this voltage with a PWM output and a PWM to 0-10 V converter board.

- **The 0-10 V command follows the fan relay.** It is 0 V whenever the fan relay is off, and the set speed whenever the fan relay is on. When the relay switches on, the speed command is applied after it. When the relay switches off, the command goes to 0 V first.
- Connect the converter's output ground to the fan's 0-10 V reference ground, and the converter's input ground to the Mainboard GND.
- Many PWM to 0-10 V converters want a PWM signal of 1 to 3 kHz and an amplitude of 5 V or more. Check the one you have. If it will not read the ESP32's 3.3 V signal, add a transistor or level shifter between them.
- The converter's output is not exactly linear. Calibrate it: set several duty cycles, measure the output with a meter, and store the result as a table or offset and scale.
- The fan's 0-10 V input and tach output must be SELV (isolated from mains inside the fan). Check the fan's datasheet before connecting them to the Mainboard.

### Fan tach

The fan's tach output is an open collector with 1 pulse per revolution. It can sink at most 10 mA, and it is SELV.

- Pull it up to 3.3 V with a resistor (4.7 kΩ to 10 kΩ, under 1 mA, well inside the 10 mA limit). Do not pull it up to 5 V or more, because the ESP32 input is not 5 V tolerant.
- Add a small RC filter (for example 1 kΩ in series and 10 nF to GND at the ESP32 pin) to remove noise from the fan cable.
- Count the pulses with the ESP32's pulse counter (PCNT) with its glitch filter on. At 1 pulse per revolution, RPM = pulses per second × 60. At low speed (a few pulses per second), measure the time between pulses instead, or average over a longer window.

### Before connecting real loads

- A compressor draws a high current for a moment when it starts. Do not switch it directly with a hobby relay module. Use the relay to drive a **contactor** rated for the compressor (motor rating AC-3), or a relay rated for the motor's start current.
- The heater needs its own thermal cut-out (a bimetal safety thermostat) that works even if the controller fails.
- Mains wiring must be done by a competent person, in an earthed enclosure, with suitable fusing.
- Keep the low-voltage wiring (sensor, link, 0-10 V, tach) away from mains wiring.

## 2. Control rules

The control rules are the same as in Phase 1. Default values are shown in brackets. All of them can be changed on the Controller.

- Temperature set point **Ts** (22.0 °C) and band **Tb** (0.5 °C).
- Humidity set point **Hs** (50 %RH) and band **Hb** (3 %RH).

The band stops the relays switching on and off rapidly around the set point. Each demand starts at the set point plus or minus the band, and stops at the set point.

| Demand | Starts when | Stops when | Runs |
|---|---|---|---|
| Cool | T ≥ Ts + Tb | T ≤ Ts | Compressor |
| Heat | T ≤ Ts − Tb | T ≥ Ts | Heater |
| Humidify | RH ≤ Hs − Hb | RH ≥ Hs | Humidifier |
| Dehumidify | RH ≥ Hs + Hb | RH ≤ Hs | Compressor |
| Reheat (only while dehumidifying and the compressor is running) | T ≤ Ts | T ≥ Ts + Tb | Heater |

- **Fan:** runs whenever the heater, humidifier or compressor runs. After they all stop, it keeps running for 30 s (the run-on time) to clear heat from the heater. It can also be set to run all the time. While the fan relay is on, the 0-10 V command is the fan speed setting (100 %). While it is off, the command is 0 V.
- **Dehumidifying:** the compressor dries the air, but it also cools it. When the temperature is at or below the set point, the heater runs as well to hold the temperature (reheat). As the temperature moves, the controller switches between running the compressor alone and running the compressor plus the heater. When the humidity reaches the set point, both stop.
- **Cool and heat** can never be on together, because of the bands.

### Compressor protection

- **Minimum off time** (180 s): once the compressor stops, it cannot start again until this time has passed. This also applies after a power cut or reboot. The display shows the time left.
- **Minimum run time** (60 s): once started in Auto, the compressor runs for at least this long.
- Choosing Off, choosing Manual, a sensor fault or a fan fault stops the compressor straight away. Both times can be set to 0 for bench testing.

### Modes

- **Off:** everything stops. The fan still does its run-on.
- **Auto:** the rules above.
- **Manual:** you switch each relay yourself from the Controller's menu, to test the wiring. The fan rule and the compressor minimum off time still apply.

The mode and the settings are saved on the Mainboard, so after a power cut the unit returns to its last mode.

### Sensor fault

If the sensor gives no valid reading for 30 s, Auto mode stops the heater, humidifier and compressor. The fan does its run-on. The display shows "SENSOR FAULT". The fault clears itself when valid readings come back. A simulated sensor fault can be switched on for testing.

### Fan fault

If the fan relay is on and the speed command is above a minimum, but the tach reads below the fault threshold (proposed 200 RPM) for 15 s, after a 10 s spin-up allowance, that is a fan fault. Running the heater, compressor or humidifier without airflow is unsafe, so:

- The heater, humidifier and compressor stop straight away (the compressor's minimum run time does not apply).
- The fan stays commanded on, so it can recover.
- The display shows "FAN FAULT" and the measured RPM.
- The fault is latched: it stays until it is cleared on the Controller, and it comes back if the fan still does not turn.

The threshold, the spin-up allowance and the delay can be changed in the settings. A fan fault also stops the other loads in Manual mode.

### Faults on the display

Faults are shown on the OLED in place of the normal screen until acknowledged, and then as a line on the normal screen while they last. If more than one is active, all of them are listed.

| Message | Cause |
|---|---|
| SENSOR FAULT | No valid AHT20 reading for 30 s |
| FAN FAULT | Fan on but tach too slow (see above) |
| NO LINK TO MAINBOARD | Controller has heard nothing from the Mainboard for 5 s |
| COMP WAIT mm:ss | Not a fault: compressor wanted but still in its minimum off time |

## 3. Phases

### Phase 1: control logic and simulated sensor (done, on the ESP8266)

- [x] Move relays to D0, D7, D5, D6. D1 and D2 are free for the sensor.
- [x] Control logic as in section 2, with bands, reheat, fan rule and compressor protection.
- [x] Settings saved to flash.
- [x] Web page: readings, set points, mode, the state of each relay and why it is on, manual relay switches.
- [x] Simulated sensor: type in the temperature and humidity. Optional "room reacts" mode: the heater warms, the compressor cools and dries, and the humidifier adds moisture, so you can watch the controller work.
- [x] Simulated sensor fault.

### Phase 2: Mainboard firmware (ESP32 WROOM-32)

- [ ] Build env for the Mainboard (`esp32dev`), with the pins from section 1.
- [ ] Keep `controller.cpp` as the control rules (plain C++). Add the fan fault to it.
- [ ] AHT20 + BMP280 driver. Read every 2 s, and average the last few readings.
- [ ] Sensor fault after 30 s with no valid reading. Try to restart the I2C bus.
- [ ] Optional temperature and humidity offset settings, for calibration against a reference.
- [ ] Fan speed: PWM output to the 0-10 V converter, following the fan relay. Fan speed setting. Calibration of the converter.
- [ ] Fan tach: RPM measurement with the pulse counter. Fan fault as in section 2.
- [ ] Link: Mainboard side of the protocol (status every 1 s, commands with accept/reject).
- [ ] Simulated sensor kept for testing, selectable from the Controller's settings menu and from the serial commands.
- [ ] Remove the web page, JSON API and WiFi from the build (or put them behind a build flag), and `tools/test-control.ps1`'s HTTP use with them. Decide whether to keep WiFi for OTA updates (section 5).
- [ ] Replace `tools/test-control.ps1` with a test that drives the Mainboard over its serial port, and run the section 4 test list.
- [ ] Bump `SETTINGS_VERSION` for the new settings (fan speed, fan fault, offsets).

### Phase 3: Controller firmware (ESP32-C3 SuperMini)

- [ ] Build env for the Controller (ESP32-C3 SuperMini).
- [ ] Confirm the DST-013 display driver (SH1106 or SSD1306) and get it working with U8g2.
- [ ] Read both encoders and their push switches, with debouncing.
- [ ] Main screen: temperature, humidity, set points, mode, running loads, compressor countdown.
- [ ] Set point and mode changes on the encoders, sent to the Mainboard.
- [ ] Settings menu: bands, fan mode, fan speed, run-on time, compressor times, fan fault settings, sensor offsets, real or simulated sensor, manual relay switches.
- [ ] Fault messages as in section 2, and "clear fault".
- [ ] Link: Controller side of the protocol, with the 5 s link timeout.
- [ ] Later: change to one concentric rotary encoder.

### Phase 4: safety and alarms

- [ ] High and low temperature alarms, shown on the display. Heater locked off above a maximum temperature.
- [ ] Compressor locked off below a minimum temperature, to stop the coil freezing.
- [ ] Maximum continuous heater run time.
- [ ] Hardware watchdog on the Mainboard. Check that every relay goes safe (and the 0-10 V command goes to 0) after a crash.
- [ ] Optional cross-check between the AHT20 and BMP280 temperatures.

### Phase 5: final hardware

- [x] Carrier PCB designed in KiCad 10 (`hardware/`): 4 × SRD-05VDC-SL-C relays, plug-in NodeMCU, SHT31-D connector, 5 V input. ERC and DRC are clean, the mains isolation rules are checked, and the circuit is simulated. See `hardware/README.md`. **This is the ESP8266 design. It does not fit the new Mainboard.**
- [x] 3D-printable case designed (`hardware/case/`), for the ESP8266 PCB.
- [ ] Decide: rework the PCB for the ESP32 WROOM-32 DevKit (with connectors for the AHT20 + BMP280 board, the 0-10 V converter, the fan tach and the Controller link), or use the off-the-shelf relay board.
- [ ] Controller enclosure, with the display and encoder(s) on the front.
- [ ] Contactor for the compressor. Thermal cut-out on the heater.
- [ ] Enclosure, power supply, cable glands, fusing.
- [ ] Mount the sensor in the air stream, away from the heater and humidifier.
- [ ] Long run test: 48 h at fixed set points.

### Later (not in the current scope)

- [ ] Keep the last 24 h of readings and relay states, and show them (on the display, or on a web page if one comes back).
- [ ] Optional MQTT or Home Assistant integration.
- [ ] Optional email or push alerts.

## 4. Test list

Use the simulated sensor, and set the compressor minimum off and run times to 0 so you don't have to wait. Phase 1 ran these through the web page. From Phase 2 on they run through the Controller (or the Mainboard's serial commands).

1. Set Ts = 22.0, Tb = 0.5, Hs = 50, Hb = 3, and choose Auto.
2. Set the sensor to T 22.0, RH 50: everything is off. The 0-10 V output is 0 V.
3. T 22.6: the compressor and fan come on (cooling), and the 0-10 V output goes to the fan speed. T 22.2: they stay on. T 22.0: they stop, and the fan runs on, then the 0-10 V output goes to 0 V.
4. T 21.4: the heater and fan come on. T 22.0: the heater stops.
5. T 22.0, RH 46: the humidifier and fan come on. RH 50: the humidifier stops.
6. T 22.0, RH 54: the compressor, heater (reheat) and fan come on. T 22.6: the heater stops and the compressor keeps running. RH 50: the compressor stops.
7. Turn on sensor fault: the compressor, heater and humidifier stop. The display shows SENSOR FAULT.
8. Set the compressor minimum off time back to 180 s. Make the compressor stop, then start it again: the display counts down before it restarts.
9. With the fan running, stop it turning (disconnect the tach, or hold the input low): after the spin-up allowance and delay, the heater, humidifier and compressor stop and the display shows FAN FAULT. Reconnect it and clear the fault on the Controller: normal control resumes.
10. Unplug the link cable: the Controller shows NO LINK TO MAINBOARD within 5 s, and the Mainboard keeps controlling. Plug it back in: the display recovers and shows the Mainboard's settings.
11. Change a set point on the Controller and power-cycle the Mainboard: the new set point is kept.

## 5. Open questions

1. When the humidity is too high, I read your rule as: run the compressor to dry the air, and also run the heater while the temperature is at or below the set point, so the room does not get cold. Is that right?
2. When the temperature is too high and the humidity is too low, the compressor and the humidifier both run. Is that acceptable, or should one of them take priority?
3. Does the fan need to blow over the heater whenever the heater is on? It does at the moment.
4. Should the unit always start in Off after a power cut, instead of returning to its last mode?
5. Fan speed: is one fixed speed setting enough, or should the speed depend on the demand (for example lower when dehumidifying)? Is there a minimum speed the fan needs?
6. Fan fault: is the proposed behaviour right (other loads stop, fan stays on, latched until cleared)? What RPM does the fan reach at full speed, so the threshold can be set sensibly?
7. Is the DST-013 an SH1106 or SSD1306 OLED, and is it 1.3-inch 128 × 64 on I2C?
8. How long will the cable between the Controller and the Mainboard be? Over about 1 m, RS-485 is safer than plain UART.
9. With no web page, should the Mainboard keep WiFi only for over-the-air firmware updates, or be USB-only?
10. Is the proposed encoder layout (encoder 1 for temperature and mode, encoder 2 for humidity and the menu) what you want?
