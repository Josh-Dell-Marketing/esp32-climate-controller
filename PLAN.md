# Climate Controller: Project Plan

An ESP8266 (NodeMCU) controls a temperature and humidity unit through 4 relays: fan, heater, humidifier and compressor. It holds a temperature set point and a humidity set point. A web page shows the readings and the relays, and lets you change the set points.

Status, 13 Nov 2026: Phase 1 is built. There is no sensor yet, so the web page has a simulated sensor.

## 1. Hardware

### Relays

| Relay | Load | NodeMCU pin | GPIO |
|---|---|---|---|
| IN1 | Fan | D0 | 16 |
| IN2 | Heater | D7 | 13 |
| IN3 | Humidifier | D5 | 14 |
| IN4 | Compressor | D6 | 12 |

The relay module also needs VCC to VIN (5 V) and GND to GND.

D1 and D2 are kept free for the I2C sensor. The compressor is on D6 because that pin stays quiet while the board boots, so the compressor cannot click on during a reset.

### Sensor (for development)

| Sensor | Approx. price | Accuracy | Notes |
|---|---|---|---|
| **SHT31-D breakout** (recommended) | £5-10 | ±0.3 °C, ±2 %RH | I2C. Reliable and well supported. Has a built-in heater to clear condensation. |
| SHT40 / SHT41 breakout | £5-10 | ±0.2 °C, ±1.8 %RH | I2C. Newer than the SHT31. Some boards have a PTFE filter cap, which is good near a humidifier. |
| AHT20 breakout (often sold with a BMP280) | £2-4 | ±0.3 °C, ±2 %RH | I2C. The cheapest usable option. Good as a spare or second sensor. |
| BME280 breakout | £4-8 | ±1 °C, ±3 %RH | I2C. Reads a little warm because it heats itself. Many listings are really a BMP280, which has **no humidity sensor**. |
| DHT22 / AM2302 | £3-5 | ±0.5 °C, ±2-5 %RH | Single-wire. Slow (one reading every 2 s), and drifts at high humidity. Usable but not recommended. |
| DHT11 | £1-2 | ±2 °C, ±5 %RH | Avoid: too inaccurate for control. |

Prices are rough UK hobby-shop and online-marketplace prices.

Suggestion: buy one SHT31-D or SHT41 as the main sensor, and an AHT20 as a cheap spare to compare against.

Sensor wiring (I2C): VIN to 3V3, GND to GND, SDA to D2, SCL to D1.

Put the sensor where it measures the room air, for example the return air. Keep it away from the humidifier outlet, the heater and the cold coil.

### Before connecting real loads

- A compressor draws a high current for a moment when it starts. Do not switch it directly with a hobby relay module. Use the relay to drive a **contactor** rated for the compressor (motor rating AC-3), or a relay rated for the motor's start current.
- The heater needs its own thermal cut-out (a bimetal safety thermostat) that works even if the controller fails.
- Mains wiring must be done by a competent person, in an earthed enclosure, with suitable fusing.

## 2. Control rules

Default values are shown in brackets. All of them can be changed on the web page.

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

- **Fan:** runs whenever the heater, humidifier or compressor runs. After they all stop, it keeps running for 30 s (the run-on time) to clear heat from the heater. It can also be set to run all the time.
- **Dehumidifying:** the compressor dries the air, but it also cools it. When the temperature is at or below the set point, the heater runs as well to hold the temperature (reheat). As the temperature moves, the controller switches between running the compressor alone and running the compressor plus the heater. When the humidity reaches the set point, both stop.
- **Cool and heat** can never be on together, because of the bands.

### Compressor protection

- **Minimum off time** (180 s): once the compressor stops, it cannot start again until this time has passed. This also applies after a power cut or reboot. The web page shows the time left.
- **Minimum run time** (60 s): once started in Auto, the compressor runs for at least this long.
- Choosing Off, choosing Manual or a sensor fault stops the compressor straight away. Both times can be set to 0 for bench testing.

### Modes

- **Off:** everything stops. The fan still does its run-on.
- **Auto:** the rules above.
- **Manual:** you switch each relay yourself, to test the wiring. The fan rule and the compressor minimum off time still apply.

The mode and the settings are saved, so after a power cut the unit returns to its last mode.

### Sensor fault

If the sensor gives no valid reading, Auto mode stops the heater, humidifier and compressor. In Phase 1 you can test this with a "sensor fault" switch on the web page. In Phase 2 a fault means no valid reading for 30 s.

## 3. Phases

### Phase 1: control logic and simulated sensor (done)

- [x] Move relays to D0, D7, D5, D6. D1 and D2 are free for the sensor.
- [x] Control logic as in section 2, with bands, reheat, fan rule and compressor protection.
- [x] Settings saved to flash.
- [x] Web page: readings, set points, mode, the state of each relay and why it is on, manual relay switches.
- [x] Simulated sensor: type in the temperature and humidity. Optional "room reacts" mode: the heater warms, the compressor cools and dries, and the humidifier adds moisture, so you can watch the controller work.
- [x] Simulated sensor fault.
- [ ] You: check each relay in Manual mode, then run through the test list below.

### Phase 2: real sensor

- [ ] Buy an SHT31-D or SHT41 (and an AHT20 spare).
- [ ] Driver for the chosen sensor. Read every 2 s, and average the last few readings.
- [ ] Sensor fault after 30 s with no valid reading. Try to restart the I2C bus.
- [ ] Optional temperature and humidity offset settings, for calibration against a reference.
- [ ] Choice of sensor on the web page: real or simulated.

### Phase 3: safety and alarms

- [ ] High and low temperature alarms. Heater locked off above a maximum temperature.
- [ ] Compressor locked off below a minimum temperature, to stop the coil freezing.
- [ ] Maximum continuous heater run time.
- [ ] Hardware watchdog. Check that every relay goes safe after a crash.
- [ ] Optional login on the web page (the setting already exists in `secrets.h`).

### Phase 4: history and remote access

- [ ] Keep the last 24 h of readings and relay states in memory, and show a chart on the web page.
- [ ] Optional MQTT or Home Assistant integration.
- [ ] Optional email or push alerts.

### Phase 5: final hardware

- [x] Carrier PCB designed in KiCad 10 (`hardware/`): 4 × SRD-05VDC-SL-C relays, plug-in NodeMCU, SHT31-D connector, 5 V input. ERC and DRC are clean, the mains isolation rules are checked, and the circuit is simulated. See `hardware/README.md`.
- [x] 3D-printable case designed (`hardware/case/`).
- [ ] Order the PCB and parts. Build it, run the bring-up checks, and flash with `pio run -e nodemcuv2-pcb` (on this board the relays are active HIGH).
- [ ] Contactor for the compressor. Thermal cut-out on the heater.
- [ ] Enclosure, power supply, cable glands, fusing.
- [ ] Mount the sensor in the air stream, away from the heater and humidifier.
- [ ] Long run test: 48 h at fixed set points, then check the history.
- [ ] Optional: move to an ESP32, which has more pins and memory. The code already builds for both.

## 4. Phase 1 test list

Use the simulated sensor, and set the compressor minimum off and run times to 0 so you don't have to wait.

1. Set Ts = 22.0, Tb = 0.5, Hs = 50, Hb = 3, and choose Auto.
2. Set the sensor to T 22.0, RH 50: everything is off.
3. T 22.6: the compressor and fan come on (cooling). T 22.2: they stay on. T 22.0: they stop, and the fan runs on.
4. T 21.4: the heater and fan come on. T 22.0: the heater stops.
5. T 22.0, RH 46: the humidifier and fan come on. RH 50: the humidifier stops.
6. T 22.0, RH 54: the compressor, heater (reheat) and fan come on. T 22.6: the heater stops and the compressor keeps running. RH 50: the compressor stops.
7. Turn on sensor fault: the compressor, heater and humidifier stop.
8. Set the compressor minimum off time back to 180 s. Make the compressor stop, then start it again: the page counts down before it restarts.

## 5. Open questions

1. When the humidity is too high, I read your rule as: run the compressor to dry the air, and also run the heater while the temperature is at or below the set point, so the room does not get cold. Is that right?
2. When the temperature is too high and the humidity is too low, the compressor and the humidifier both run. Is that acceptable, or should one of them take priority?
3. Does the fan need to blow over the heater whenever the heater is on? It does at the moment.
4. Should the unit always start in Off after a power cut, instead of returning to its last mode?
5. Will the final unit stay on the ESP8266, or move to an ESP32?
