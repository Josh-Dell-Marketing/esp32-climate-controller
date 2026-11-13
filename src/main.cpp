// Climate controller: fan, heater, humidifier and compressor on 4 relays.
// Holds a temperature and a humidity set point. See PLAN.md.
//
// Web page at http://climate.local (or the IP address).
// API:
//   GET  /api/state
//   POST /api/settings  tempSet, humSet, tempBand, humBand, mode=off|auto|manual,
//                       fanMode=auto|on, compMinOff, compMinOn, fanRunOn
//   POST /api/sim       temp, hum, react=0|1, fault=0|1      (simulated sensor)
//   POST /api/manual    ch=1-4|all, state=on|off|toggle       (Manual mode only)
// Serial (115200): status | mode off|auto|manual | temp 23.5 | hum 60

#include <Arduino.h>
#include <ArduinoOTA.h>

#if defined(ESP8266)
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
using WebServerT = ESP8266WebServer;
#else
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <driver/gpio.h>
using WebServerT = WebServer;
#endif

#include "config.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#warning "include/secrets.h not found: using secrets.example.h. Copy it to secrets.h and add your WiFi details."
#include "secrets.example.h"
#endif
#include "web_ui.h"
#include "controller.h"
#include "sim_room.h"
#include "storage.h"

static const char *RELAY_NAMES[RELAY_TOTAL] = {"Fan", "Heater", "Humidifier", "Compressor"};

WebServerT server(80);
Settings settings;
Controller controller;
SimRoom sim;
bool manualReq[RELAY_TOTAL] = {};
bool applied[RELAY_TOTAL] = {};

uint32_t lastControlMs = 0;
bool apMode = false;
uint32_t apStartedMs = 0;
uint32_t lastWifiCheckMs = 0;

// ---------------------------------------------------------------------------
// Relays and control
// ---------------------------------------------------------------------------
uint8_t pinLevel(bool on) { return (on != RELAY_ACTIVE_LOW) ? HIGH : LOW; }

void initRelays() {
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    // Set the level before making the pin an output, so nothing clicks on at boot.
#if defined(ESP8266)
    digitalWrite(RELAY_PINS[i], pinLevel(false));
#else
    gpio_set_level((gpio_num_t)RELAY_PINS[i], pinLevel(false));
#endif
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

// Runs the controller and drives the relay pins to match.
void updateOutputs() {
  controller.update(settings, sim.reading(), manualReq, millis());
  const Status &st = controller.status();
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    if (st.relay[i] == applied[i]) continue;
    applied[i] = st.relay[i];
    digitalWrite(RELAY_PINS[i], pinLevel(applied[i]));
    Serial.printf("[relay] %-10s %s  %s\n", RELAY_NAMES[i], applied[i] ? "ON " : "OFF", st.reason[i]);
  }
}

void controlTick() {
  uint32_t now = millis();
  if (now - lastControlMs < CONTROL_INTERVAL_MS) return;
  float dt = (now - lastControlMs) / 1000.0f;
  lastControlMs = now;
  sim.step(applied, dt);
  updateOutputs();
}

void setMode(Mode m) {
  if (m != settings.mode) {
    for (bool &r : manualReq) r = false;  // manual switches always start off
  }
  settings.mode = m;
}

bool parseMode(String v, Mode &m) {
  v.toLowerCase();
  if (v == "off") m = Mode::Off;
  else if (v == "auto") m = Mode::Auto;
  else if (v == "manual") m = Mode::Manual;
  else return false;
  return true;
}

// ---------------------------------------------------------------------------
// JSON
// ---------------------------------------------------------------------------
String jsonEscape(const char *s) {
  String out;
  for (; *s; s++) {
    if (*s == '"' || *s == '\\') out += '\\';
    out += *s;
  }
  return out;
}

void addBool(String &j, const char *key, bool v, bool comma = true) {
  j += '"';
  j += key;
  j += "\":";
  j += v ? "true" : "false";
  if (comma) j += ',';
}

void addNum(String &j, const char *key, float v, int decimals, bool comma = true) {
  j += '"';
  j += key;
  j += "\":";
  j += String(v, decimals);
  if (comma) j += ',';
}

String stateJson() {
  const Status &st = controller.status();
  const Reading r = sim.reading();
  String j;
  j.reserve(1400);
  j += "{\"mode\":\"";
  j += modeName(settings.mode);
  j += "\",\"fanMode\":\"";
  j += settings.fanMode == FanMode::AlwaysOn ? "on" : "auto";
  j += "\",\"settings\":{";
  addNum(j, "tempSet", settings.tempSetpoint, 1);
  addNum(j, "humSet", settings.humSetpoint, 1);
  addNum(j, "tempBand", settings.tempBand, 1);
  addNum(j, "humBand", settings.humBand, 1);
  addNum(j, "compMinOff", settings.compMinOffSec, 0);
  addNum(j, "compMinOn", settings.compMinOnSec, 0);
  addNum(j, "fanRunOn", settings.fanRunOnSec, 0, false);
  j += "},\"reading\":{";
  addNum(j, "temp", r.temp, 2);
  addNum(j, "hum", r.hum, 2);
  addBool(j, "valid", r.valid);
  j += "\"source\":\"simulated\"},\"sim\":{";
  addBool(j, "react", sim.react);
  addBool(j, "fault", sim.fault, false);
  j += "},\"demand\":{";
  addBool(j, "cool", st.cool);
  addBool(j, "heat", st.heat);
  addBool(j, "humidify", st.humidify);
  addBool(j, "dehumidify", st.dehumidify);
  addBool(j, "reheat", st.reheat);
  addBool(j, "sensorFault", st.sensorFault, false);
  j += "},\"compRestLeft\":";
  j += (unsigned long)st.compRestLeftSec;
  j += ",\"relays\":[";
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    if (i) j += ',';
    j += "{\"id\":";
    j += (int)(i + 1);
    j += ",\"name\":\"";
    j += RELAY_NAMES[i];
    j += "\",";
    addBool(j, "on", st.relay[i]);
    addBool(j, "manual", manualReq[i]);
    j += "\"reason\":\"";
    j += jsonEscape(st.reason[i]);
    j += "\"}";
  }
  j += "],\"net\":{\"mode\":\"";
  j += apMode ? "ap" : "sta";
  j += "\",\"ip\":\"";
  j += apMode ? WiFi.softAPIP().toString() : WiFi.localIP().toString();
  j += "\",\"rssi\":";
  j += apMode ? 0 : (int)WiFi.RSSI();
  j += "},\"uptime\":";
  j += (unsigned long)(millis() / 1000);
  j += '}';
  return j;
}

// ---------------------------------------------------------------------------
// Web server
// ---------------------------------------------------------------------------
bool checkAuth() {
  if (strlen(WEB_PASSWORD) == 0) return true;
  if (server.authenticate(WEB_USER, WEB_PASSWORD)) return true;
  server.requestAuthentication();
  return false;
}

void sendState() { server.send(200, "application/json", stateJson()); }

void handleRoot() {
  if (!checkAuth()) return;
  server.send_P(200, "text/html", INDEX_HTML);
}

void handleState() {
  if (!checkAuth()) return;
  sendState();
}

void handleSettings() {
  if (!checkAuth()) return;
  Settings n = settings;
  if (server.hasArg("tempSet")) n.tempSetpoint = server.arg("tempSet").toFloat();
  if (server.hasArg("humSet")) n.humSetpoint = server.arg("humSet").toFloat();
  if (server.hasArg("tempBand")) n.tempBand = server.arg("tempBand").toFloat();
  if (server.hasArg("humBand")) n.humBand = server.arg("humBand").toFloat();
  if (server.hasArg("compMinOff")) n.compMinOffSec = constrain(server.arg("compMinOff").toInt(), 0L, 900L);
  if (server.hasArg("compMinOn")) n.compMinOnSec = constrain(server.arg("compMinOn").toInt(), 0L, 900L);
  if (server.hasArg("fanRunOn")) n.fanRunOnSec = constrain(server.arg("fanRunOn").toInt(), 0L, 600L);
  if (server.hasArg("fanMode")) {
    String f = server.arg("fanMode");
    if (f == "on") n.fanMode = FanMode::AlwaysOn;
    else if (f == "auto") n.fanMode = FanMode::Auto;
    else return server.send(400, "text/plain", "fanMode must be auto or on");
  }
  Mode m = n.mode;
  if (server.hasArg("mode") && !parseMode(server.arg("mode"), m)) {
    return server.send(400, "text/plain", "mode must be off, auto or manual");
  }
  sanitize(n);
  n.mode = settings.mode;  // setMode handles the change below
  settings = n;
  setMode(m);
  saveSettings(settings);
  Serial.printf("[settings] mode %s, %.1f C / %.1f %%RH\n", modeName(settings.mode),
                settings.tempSetpoint, settings.humSetpoint);
  updateOutputs();
  sendState();
}

void handleSim() {
  if (!checkAuth()) return;
  if (server.hasArg("temp")) sim.temp = constrain(server.arg("temp").toFloat(), -20.0f, 60.0f);
  if (server.hasArg("hum")) sim.hum = constrain(server.arg("hum").toFloat(), 0.0f, 100.0f);
  if (server.hasArg("react")) sim.react = server.arg("react") == "1" || server.arg("react") == "true";
  if (server.hasArg("fault")) sim.fault = server.arg("fault") == "1" || server.arg("fault") == "true";
  updateOutputs();
  sendState();
}

void handleManual() {
  if (!checkAuth()) return;
  if (settings.mode != Mode::Manual) {
    return server.send(409, "text/plain", "Switch to Manual mode first");
  }
  String ch = server.arg("ch");
  String state = server.arg("state");
  state.toLowerCase();
  int first, last;
  if (ch.equalsIgnoreCase("all")) {
    first = 0;
    last = RELAY_TOTAL - 1;
  } else {
    long n = ch.toInt();
    if (n < 1 || n > RELAY_TOTAL) return server.send(400, "text/plain", "ch must be 1-4 or all");
    first = last = n - 1;
  }
  if (state != "on" && state != "off" && state != "toggle") {
    return server.send(400, "text/plain", "state must be on, off or toggle");
  }
  for (int i = first; i <= last; i++) {
    manualReq[i] = state == "toggle" ? !manualReq[i] : state == "on";
  }
  updateOutputs();
  sendState();
}

void startWebServer() {
  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/state", HTTP_GET, handleState);
  server.on("/api/settings", HTTP_POST, handleSettings);
  server.on("/api/sim", HTTP_POST, handleSim);
  server.on("/api/manual", HTTP_POST, handleManual);
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
  Serial.println("[web] server started on port 80");
}

// ---------------------------------------------------------------------------
// WiFi, mDNS, OTA
// ---------------------------------------------------------------------------
void startWiFi() {
  // WiFi power saving is turned off: it makes the board slow to answer.
#if defined(ESP8266)
  WiFi.mode(WIFI_STA);
  WiFi.hostname(HOSTNAME);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);
#else
  WiFi.setHostname(HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
#endif
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[wifi] connecting to \"%s\"", WIFI_SSID);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    apMode = false;
    Serial.printf("[wifi] connected, IP %s, RSSI %d dBm\n",
                  WiFi.localIP().toString().c_str(), (int)WiFi.RSSI());
  } else {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    apMode = true;
    apStartedMs = millis();
    Serial.printf("[wifi] could not connect. Started access point \"%s\" (password \"%s\"), open http://%s\n",
                  AP_SSID, AP_PASSWORD, WiFi.softAPIP().toString().c_str());
  }
}

void maintainWiFi() {
  if (millis() - lastWifiCheckMs < 10000) return;
  lastWifiCheckMs = millis();

  if (apMode) {
    // Nobody is using the setup AP: reboot and try the real network again.
    // Not while the compressor runs, so a reboot never cuts it mid-cycle.
    if (millis() - apStartedMs > AP_RETRY_MS && WiFi.softAPgetStationNum() == 0 &&
        !applied[COMPRESSOR]) {
      Serial.println("[wifi] retrying WiFi, restarting");
      delay(100);
      ESP.restart();
    }
  } else if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[wifi] connection lost, reconnecting");
    WiFi.reconnect();
  }
}

void startOta() {
  ArduinoOTA.setHostname(HOSTNAME);  // also starts mDNS as <HOSTNAME>.local
  if (strlen(OTA_PASSWORD) > 0) ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() {
    // Make everything safe before the update takes over.
    for (uint8_t i = 0; i < RELAY_TOTAL; i++) digitalWrite(RELAY_PINS[i], pinLevel(false));
    Serial.println("[ota] update starting, relays off");
  });
  ArduinoOTA.onEnd([]() { Serial.println("[ota] update done, rebooting"); });
  ArduinoOTA.onError([](ota_error_t e) { Serial.printf("[ota] error %u\n", (unsigned)e); });
  ArduinoOTA.begin();
  MDNS.addService("http", "tcp", 80);
  Serial.printf("[mdns] http://%s.local\n", HOSTNAME);
}

// ---------------------------------------------------------------------------
// Serial commands
// ---------------------------------------------------------------------------
void printStatus() {
  const Status &st = controller.status();
  const Reading r = sim.reading();
  Serial.printf("  mode %s | %.2f C (set %.1f) | %.2f %%RH (set %.1f)%s\n", modeName(settings.mode),
                r.temp, settings.tempSetpoint, r.hum, settings.humSetpoint,
                r.valid ? "" : " | SENSOR FAULT");
  for (uint8_t i = 0; i < RELAY_TOTAL; i++) {
    Serial.printf("  %-10s %s  %s\n", RELAY_NAMES[i], st.relay[i] ? "ON " : "OFF", st.reason[i]);
  }
  if (st.compRestLeftSec) Serial.printf("  compressor resting, %lus left\n", (unsigned long)st.compRestLeftSec);
  Serial.printf("  IP %s\n", (apMode ? WiFi.softAPIP() : WiFi.localIP()).toString().c_str());
}

void runSerialCommand(String line) {
  line.trim();
  if (line.length() == 0) return;
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String arg = sp < 0 ? "" : line.substring(sp + 1);
  cmd.toLowerCase();

  if (cmd == "status" || cmd == "?") {
    printStatus();
    return;
  }
  if (cmd == "mode") {
    Mode m;
    if (parseMode(arg, m)) {
      setMode(m);
      saveSettings(settings);
      updateOutputs();
      printStatus();
      return;
    }
  } else if (cmd == "temp" && arg.length()) {
    sim.temp = arg.toFloat();
    updateOutputs();
    printStatus();
    return;
  } else if (cmd == "hum" && arg.length()) {
    sim.hum = constrain(arg.toFloat(), 0.0f, 100.0f);
    updateOutputs();
    printStatus();
    return;
  }
  Serial.println("Commands: status | mode off|auto|manual | temp <C> | hum <%RH>");
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
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== Climate controller ===");

  storageBegin();
  if (!loadSettings(settings)) Serial.println("[settings] none saved, using defaults");
  sanitize(settings);
  // The simulated sensor starts at the set points, so nothing runs at boot.
  sim.temp = settings.tempSetpoint;
  sim.hum = settings.humSetpoint;

  controller.begin(millis());
  updateOutputs();
  printStatus();

  startWiFi();
  startOta();
  startWebServer();
  lastControlMs = millis();
  Serial.println("Type \"status\", \"mode auto\", \"temp 23.5\" or \"hum 60\"");
}

void loop() {
  server.handleClient();
  ArduinoOTA.handle();
  controlTick();
  handleSerial();
  maintainWiFi();
  delay(2);
}
