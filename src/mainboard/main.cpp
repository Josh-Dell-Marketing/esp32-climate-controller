// Mainboard firmware (ESP32 NodeMCU WROOM-32). See PLAN.md.
//
// Runs the climate control rules: reads the AHT20 + BMP280 sensor, switches
// the 4 relays (fan, heater, humidifier, compressor), sets the fan speed
// (PWM -> 0-10 V) and watches the fan tach. Takes its commands from the
// Controller over the serial link (include/link_protocol.h), and keeps
// controlling with its saved settings if the link is lost.
//
// USB serial (115200): type "help" for the commands.

#include <Arduino.h>
#include <driver/gpio.h>
#include <math.h>

#include "climate_control.h"
#include "config.h"
#include "fan.h"
#include "link_protocol.h"
#include "sensor.h"
#include "sim_room.h"
#include "storage.h"

static const char *RELAY_NAMES[RELAY_TOTAL] = {"Fan", "Heater", "Humidifier", "Compressor"};
static const uint8_t RELAY_BITS[RELAY_TOTAL] = {LB_FAN, LB_HEATER, LB_HUMIDIFIER, LB_COMPRESSOR};

Settings settings;
ClimateControl control;
FanMonitor fanMonitor;
SensorBoard sensor;
SimRoom sim;
bool useSim = false;  // never saved: the Mainboard always boots on the real sensor
bool manualReq[RELAY_TOTAL] = {};
bool applied[RELAY_TOTAL] = {};
Reading lastReading;
uint8_t settingsRev = 0;

uint32_t lastControlMs = 0;
uint32_t lastStatusMs = 0;
HardwareSerial &linkPort = Serial2;
LinkParser linkParser;

// ---------------------------------------------------------------------------
// Relays, fan and control
// ---------------------------------------------------------------------------
uint8_t pinLevel(bool on) { return (on != RELAY_ACTIVE_LOW) ? HIGH : LOW; }

void initRelays() {
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    // Set the level before making the pin an output, so nothing clicks on at boot.
    gpio_set_level((gpio_num_t)RELAY_PINS[i], pinLevel(false));
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], pinLevel(false));
  }
}

const char *modeName(Mode m) {
  switch (m) {
    case Mode::Auto: return "auto";
    case Mode::Manual: return "manual";
    default: return "off";
  }
}

Reading currentReading() {
  if (useSim) return sim.reading();
  Reading r = sensor.reading();
  if (r.valid) {
    r.temp += settings.tempOffset;
    r.hum += settings.humOffset;
    if (r.hum < 0) r.hum = 0;
    if (r.hum > 100) r.hum = 100;
  }
  return r;
}

void setRelay(uint8_t i, bool on) {
  applied[i] = on;
  digitalWrite(RELAY_PINS[i], pinLevel(on));
  Serial.printf("[relay] %-10s %s  %s\n", RELAY_NAMES[i], on ? "ON " : "OFF", control.status().reason[i]);
}

// Runs the control rules and drives the outputs to match.
// The 0-10 V command follows the fan relay: it goes to 0 before the relay
// opens, and to the speed setting after the relay closes.
void updateOutputs() {
  const uint32_t now = millis();
  lastReading = currentReading();
  control.update(settings, lastReading, fanMonitor.fault(), manualReq, now);
  const Status &st = control.status();

  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    if (i == FAN || st.relay[i] == applied[i]) continue;
    setRelay(i, st.relay[i]);
  }
  if (st.relay[FAN]) {
    if (!applied[FAN]) setRelay(FAN, true);
    fan::setCommandPct(settings.fanSpeedPct);
  } else {
    fan::setCommandPct(0);
    if (applied[FAN]) setRelay(FAN, false);
  }
}

void controlTick() {
  const uint32_t now = millis();
  if (now - lastControlMs < CONTROL_INTERVAL_MS) return;
  const float dt = (now - lastControlMs) / 1000.0f;
  lastControlMs = now;
  if (useSim) sim.step(applied, dt);

  const bool wasFault = fanMonitor.fault();
  fanMonitor.update(applied[FAN], fan::rpm(), settings, now);
  if (fanMonitor.fault() && !wasFault) {
    Serial.printf("[fan] FAN FAULT: %u rpm (threshold %u)\n", fan::rpm(), settings.fanFaultRpm);
  }
  updateOutputs();
}

void setMode(Mode m) {
  if (m != settings.mode) {
    for (bool &r : manualReq) r = false;  // manual switches always start off
  }
  settings.mode = m;
}

// ---------------------------------------------------------------------------
// Settings as link items
// ---------------------------------------------------------------------------
int16_t x10(float v) { return (int16_t)lroundf(v * 10.0f); }

int16_t getItem(uint8_t item) {
  const Settings &s = settings;
  switch (item) {
    case IT_TEMP_SET: return x10(s.tempSetpoint);
    case IT_HUM_SET: return x10(s.humSetpoint);
    case IT_TEMP_BAND: return x10(s.tempBand);
    case IT_HUM_BAND: return x10(s.humBand);
    case IT_MODE: return (int16_t)s.mode;
    case IT_FAN_MODE: return (int16_t)s.fanMode;
    case IT_FAN_SPEED: return s.fanSpeedPct;
    case IT_FAN_RUN_ON: return s.fanRunOnSec;
    case IT_COMP_MIN_OFF: return s.compMinOffSec;
    case IT_COMP_MIN_ON: return s.compMinOnSec;
    case IT_FAN_FAULT_RPM: return s.fanFaultRpm;
    case IT_FAN_SPINUP: return s.fanSpinupSec;
    case IT_FAN_FAULT_DELAY: return s.fanFaultDelaySec;
    case IT_TEMP_OFFSET: return x10(s.tempOffset);
    case IT_HUM_OFFSET: return x10(s.humOffset);
    case IT_SENSOR_SOURCE: return useSim ? 1 : 0;
    case IT_SIM_TEMP: return x10(sim.temp);
    case IT_SIM_HUM: return x10(sim.hum);
    case IT_SIM_REACT: return sim.react ? 1 : 0;
    case IT_SIM_FAULT: return sim.fault ? 1 : 0;
    case IT_MANUAL_FAN: return manualReq[FAN];
    case IT_MANUAL_HEATER: return manualReq[HEATER];
    case IT_MANUAL_HUMIDIFIER: return manualReq[HUMIDIFIER];
    case IT_MANUAL_COMPRESSOR: return manualReq[COMPRESSOR];
    default: return 0;
  }
}

// Applies one change. Returns false (and changes nothing) if it is not allowed.
// Out-of-range values are clamped by sanitize().
bool setItem(uint8_t item, int16_t v, const char **why = nullptr) {
  const char *dummy;
  if (!why) why = &dummy;
  *why = "";
  Settings n = settings;
  const float f = v / 10.0f;
  bool saved = true;

  switch (item) {
    case IT_TEMP_SET: n.tempSetpoint = f; break;
    case IT_HUM_SET: n.humSetpoint = f; break;
    case IT_TEMP_BAND: n.tempBand = f; break;
    case IT_HUM_BAND: n.humBand = f; break;
    case IT_MODE:
      if (v < 0 || v > 2) { *why = "mode must be 0, 1 or 2"; return false; }
      break;
    case IT_FAN_MODE:
      if (v < 0 || v > 1) { *why = "fan mode must be 0 or 1"; return false; }
      n.fanMode = (FanMode)v;
      break;
    case IT_FAN_SPEED: n.fanSpeedPct = (uint8_t)constrain(v, 0, 100); break;
    case IT_FAN_RUN_ON: n.fanRunOnSec = (uint16_t)max<int16_t>(v, 0); break;
    case IT_COMP_MIN_OFF: n.compMinOffSec = (uint16_t)max<int16_t>(v, 0); break;
    case IT_COMP_MIN_ON: n.compMinOnSec = (uint16_t)max<int16_t>(v, 0); break;
    case IT_FAN_FAULT_RPM: n.fanFaultRpm = (uint16_t)max<int16_t>(v, 0); break;
    case IT_FAN_SPINUP: n.fanSpinupSec = (uint16_t)max<int16_t>(v, 0); break;
    case IT_FAN_FAULT_DELAY: n.fanFaultDelaySec = (uint16_t)max<int16_t>(v, 0); break;
    case IT_TEMP_OFFSET: n.tempOffset = f; break;
    case IT_HUM_OFFSET: n.humOffset = f; break;

    // Not saved
    case IT_SENSOR_SOURCE:
      saved = false;
      if (v && !useSim) {
        // Start the simulation from the real reading, or the set points.
        sim.temp = lastReading.valid ? lastReading.temp : settings.tempSetpoint;
        sim.hum = lastReading.valid ? lastReading.hum : settings.humSetpoint;
      }
      useSim = v != 0;
      Serial.printf("[sensor] using the %s sensor\n", useSim ? "SIMULATED" : "real");
      break;
    case IT_SIM_TEMP: saved = false; sim.temp = constrain(f, -20.0f, 60.0f); break;
    case IT_SIM_HUM: saved = false; sim.hum = constrain(f, 0.0f, 100.0f); break;
    case IT_SIM_REACT: saved = false; sim.react = v != 0; break;
    case IT_SIM_FAULT: saved = false; sim.fault = v != 0; break;
    case IT_MANUAL_FAN:
    case IT_MANUAL_HEATER:
    case IT_MANUAL_HUMIDIFIER:
    case IT_MANUAL_COMPRESSOR:
      if (settings.mode != Mode::Manual) { *why = "switch to Manual mode first"; return false; }
      saved = false;
      manualReq[item - IT_MANUAL_FAN] = v != 0;
      break;
    case IT_CLEAR_FAN_FAULT:
      saved = false;
      fanMonitor.clear();
      Serial.println("[fan] fault cleared");
      break;
    default:
      *why = "unknown item";
      return false;
  }

  if (saved) {
    sanitize(n);
    n.mode = settings.mode;  // setMode handles a mode change
    settings = n;
    if (item == IT_MODE) setMode((Mode)v);
    saveSettings(settings);
  }
  settingsRev++;
  updateOutputs();
  return true;
}

// ---------------------------------------------------------------------------
// Link to the Controller
// ---------------------------------------------------------------------------
void linkSend(uint8_t type, const void *payload, uint8_t len) {
  uint8_t frame[LINK_MAX_PAYLOAD + 5];
  const size_t n = linkEncode(type, payload, len, frame);
  digitalWrite(LINK_DE_PIN, HIGH);  // RS-485: take the bus
  linkPort.write(frame, n);
  linkPort.flush();                     // wait until the last bit is out
  digitalWrite(LINK_DE_PIN, LOW);   // release the bus so the Controller can answer
}

void sendStatus() {
  const Status &st = control.status();
  LinkStatus m = {};
  m.version = LINK_PROTOCOL_VERSION;
  m.settingsRev = settingsRev;
  m.temp10 = lastReading.valid ? x10(lastReading.temp) : 0;
  m.hum10 = lastReading.valid ? x10(lastReading.hum) : 0;
  m.pressure10 = (!useSim && sensor.pressureValid()) ? (uint16_t)lroundf(sensor.pressureHpa() * 10) : 0;
  m.tempSet10 = x10(settings.tempSetpoint);
  m.humSet10 = x10(settings.humSetpoint);
  m.mode = (uint8_t)settings.mode;
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    if (applied[i]) m.relays |= RELAY_BITS[i];
    if (manualReq[i]) m.manual |= RELAY_BITS[i];
  }
  if (st.cool) m.demand |= DM_COOL;
  if (st.heat) m.demand |= DM_HEAT;
  if (st.humidify) m.demand |= DM_HUMIDIFY;
  if (st.dehumidify) m.demand |= DM_DEHUMIDIFY;
  if (st.reheat) m.demand |= DM_REHEAT;
  if (lastReading.valid) m.flags |= FL_READING_VALID;
  // Sensor fault: no valid reading (the real sensor gets SENSOR_FAULT_TIMEOUT_MS
  // after boot to give its first one).
  if (!lastReading.valid && (useSim || millis() >= SENSOR_FAULT_TIMEOUT_MS)) m.flags |= FL_SENSOR_FAULT;
  if (fanMonitor.fault()) m.flags |= FL_FAN_FAULT;
  if (useSim) m.flags |= FL_SIM_SENSOR;
  if (st.compWaiting) m.flags |= FL_COMP_WAITING;
  if (!useSim && sensor.pressureValid()) m.flags |= FL_PRESSURE_VALID;
  m.fanCmdPct = fan::commandPct();
  m.fanRpm = fan::rpm();
  m.compRestLeftSec = (uint16_t)min<uint32_t>(st.compRestLeftSec, 65535);
  m.uptimeSec = millis() / 1000;
  linkSend(MSG_STATUS, &m, sizeof(m));
}

void sendSettings() {
  LinkSettings m;
  for (uint8_t i = 0; i < IT_COUNT; i++) m.v[i] = getItem(i);
  linkSend(MSG_SETTINGS, &m, sizeof(m));
}

void handleLinkFrame() {
  switch (linkParser.type()) {
    case MSG_GET_SETTINGS:
      sendSettings();
      break;
    case MSG_SET: {
      LinkSet req;
      if (!linkParser.get(req)) return;
      const char *why;
      LinkAck ack;
      ack.seq = req.seq;
      ack.item = req.item;
      ack.ok = setItem(req.item, req.value, &why) ? 1 : 0;
      ack.value = getItem(req.item);
      linkSend(MSG_ACK, &ack, sizeof(ack));
      Serial.printf("[link] set %s = %d: %s%s\n", linkItemInfo(req.item).key, req.value,
                    ack.ok ? "ok" : "rejected, ", why);
      break;
    }
    default:
      break;
  }
}

void linkTick() {
  while (linkPort.available()) {
    if (linkParser.feed((uint8_t)linkPort.read())) handleLinkFrame();
  }
  const uint32_t now = millis();
  if (now - lastStatusMs >= LINK_STATUS_INTERVAL_MS) {
    lastStatusMs = now;
    sendStatus();
  }
}

// ---------------------------------------------------------------------------
// USB serial commands (for bench testing)
// ---------------------------------------------------------------------------
void printStatus() {
  const Status &st = control.status();
  const Reading &r = lastReading;
  Serial.printf("  mode %s | sensor %s | ", modeName(settings.mode), useSim ? "SIMULATED" : "real");
  if (r.valid) Serial.printf("%.2f C (set %.1f) | %.1f %%RH (set %.1f)", r.temp, settings.tempSetpoint, r.hum,
                             settings.humSetpoint);
  else Serial.print("NO VALID READING");
  if (!useSim && sensor.pressureValid()) Serial.printf(" | %.1f hPa", sensor.pressureHpa());
  Serial.println();
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    Serial.printf("  %-10s %s  %s\n", RELAY_NAMES[i], st.relay[i] ? "ON " : "OFF", st.reason[i]);
  }
  Serial.printf("  fan command %u %% | %u rpm%s\n", fan::commandPct(), fan::rpm(),
                fanMonitor.fault() ? " | FAN FAULT" : "");
  if (st.compRestLeftSec) Serial.printf("  compressor resting, %lus left\n", (unsigned long)st.compRestLeftSec);
}

void printSettings() {
  for (uint8_t i = 0; i < IT_COUNT; i++) {
    const LinkItemInfo &info = linkItemInfo(i);
    const int16_t v = getItem(i);
    if (info.decimals) Serial.printf("  %-14s %.1f\n", info.key, v / 10.0f);
    else Serial.printf("  %-14s %d\n", info.key, v);
  }
}

void printHelp() {
  Serial.println(
      "Commands:\n"
      "  status | settings | help\n"
      "  mode off|auto|manual\n"
      "  sensor real|sim        simulated sensor (not saved)\n"
      "  temp <C> | hum <%RH>   set the simulated reading (switches to the simulated sensor)\n"
      "  react on|off           simulated room reacts to the relays\n"
      "  fault on|off           simulated sensor fault\n"
      "  relay <1-4> on|off     Manual mode only (1 fan, 2 heater, 3 humidifier, 4 compressor)\n"
      "  clearfault             clear a fan fault\n"
      "  set <name> <value>     any value from \"settings\", in real units (e.g. set tempset 21.5)");
}

bool parseOnOff(String v, int16_t &out) {
  v.toLowerCase();
  if (v == "on" || v == "1") out = 1;
  else if (v == "off" || v == "0") out = 0;
  else return false;
  return true;
}

void runSerialCommand(String line) {
  line.trim();
  if (line.length() == 0) return;
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String arg = sp < 0 ? "" : line.substring(sp + 1);
  arg.trim();
  cmd.toLowerCase();
  const char *why = "";
  int16_t b;
  bool ok = false, known = true;

  if (cmd == "status" || cmd == "?") {
    printStatus();
    return;
  } else if (cmd == "settings") {
    printSettings();
    return;
  } else if (cmd == "help") {
    printHelp();
    return;
  } else if (cmd == "mode") {
    arg.toLowerCase();
    int16_t m = arg == "off" ? 0 : arg == "auto" ? 1 : arg == "manual" ? 2 : -1;
    ok = m >= 0 && setItem(IT_MODE, m, &why);
  } else if (cmd == "sensor") {
    arg.toLowerCase();
    ok = (arg == "sim" || arg == "real") && setItem(IT_SENSOR_SOURCE, arg == "sim", &why);
  } else if ((cmd == "temp" || cmd == "hum") && arg.length()) {
    if (!useSim) setItem(IT_SENSOR_SOURCE, 1);
    ok = setItem(cmd == "temp" ? IT_SIM_TEMP : IT_SIM_HUM, x10(arg.toFloat()), &why);
  } else if (cmd == "react" && parseOnOff(arg, b)) {
    ok = setItem(IT_SIM_REACT, b, &why);
  } else if (cmd == "fault" && parseOnOff(arg, b)) {
    ok = setItem(IT_SIM_FAULT, b, &why);
  } else if (cmd == "relay") {
    int sp2 = arg.indexOf(' ');
    long ch = arg.substring(0, sp2).toInt();
    ok = sp2 > 0 && ch >= 1 && ch <= 4 && parseOnOff(arg.substring(sp2 + 1), b) &&
         setItem(IT_MANUAL_FAN + ch - 1, b, &why);
  } else if (cmd == "clearfault") {
    ok = setItem(IT_CLEAR_FAN_FAULT, 0, &why);
  } else if (cmd == "set") {
    int sp2 = arg.indexOf(' ');
    String key = arg.substring(0, sp2);
    key.toLowerCase();
    for (uint8_t i = 0; i < IT_COUNT && sp2 > 0; i++) {
      const LinkItemInfo &info = linkItemInfo(i);
      if (key != info.key) continue;
      const float f = arg.substring(sp2 + 1).toFloat();
      ok = setItem(i, info.decimals ? x10(f) : (int16_t)lroundf(f), &why);
      break;
    }
  } else {
    known = false;
  }

  if (ok) printStatus();
  else if (known) Serial.printf("Not accepted%s%s. Type \"help\".\n", *why ? ": " : "", why);
  else printHelp();
}

void handleSerial() {
  static String buf;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      runSerialCommand(buf);
      buf = "";
    } else if (buf.length() < 64) {
      buf += c;
    }
  }
}

// ---------------------------------------------------------------------------
void setup() {
  initRelays();  // first, so every relay is off as early as possible
  fan::begin();  // 0-10 V command at 0
  pinMode(LINK_DE_PIN, OUTPUT);
  digitalWrite(LINK_DE_PIN, LOW);

  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== Climate controller: Mainboard ===");

  storageBegin();
  if (!loadSettings(settings)) Serial.println("[settings] none saved, using defaults");
  sanitize(settings);
  sim.temp = settings.tempSetpoint;  // the simulated sensor starts at the set points
  sim.hum = settings.humSetpoint;

  sensor.begin();
  linkPort.begin(LINK_BAUD, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN);

  control.begin(millis());
  updateOutputs();
  lastControlMs = millis();
  printStatus();
  Serial.println("Type \"help\" for commands.");
}

void loop() {
  const uint32_t now = millis();
  sensor.tick(now);
  fan::tick(now);
  controlTick();
  linkTick();
  handleSerial();
  delay(2);
}
