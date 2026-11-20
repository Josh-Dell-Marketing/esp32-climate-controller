// Controller firmware (ESP32-C3 SuperMini). See PLAN.md.
//
// The user interface: a 1.3" OLED and two rotary encoders with push switches.
// It makes no control decisions. Every change is sent to the Mainboard over
// the serial link (include/link_protocol.h), and is shown as accepted only
// once the Mainboard has acknowledged it.
//
// Home screen
//   Encoder 1 turn      temperature set point
//   Encoder 1 push      next mode (Off -> Auto -> Manual)
//   Encoder 2 turn      humidity set point
//   Encoder 2 long push settings menu
// Settings menu
//   Encoder 2 turn      choose an item        Encoder 1 turn   change its value
//   Either push         run an action (Clear fan fault, Exit)
//   Encoder 2 long push back to the home screen
// Fault screen
//   Any push            acknowledge (the fault stays listed on the home screen)

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

#include "config.h"
#include "input.h"
#include "link_protocol.h"

#if defined(OLED_SSD1306)
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, OLED_SCL_PIN, OLED_SDA_PIN);
#else
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, OLED_SCL_PIN, OLED_SDA_PIN);
#endif

Encoder enc1(ENC1_A_PIN, ENC1_B_PIN, ENC1_REVERSE);
Encoder enc2(ENC2_A_PIN, ENC2_B_PIN, ENC2_REVERSE);
Button btn1(ENC1_SW_PIN);
Button btn2(ENC2_SW_PIN);

HardwareSerial linkPort(1);
LinkParser parser;

// ---------------------------------------------------------------------------
// What we know about the Mainboard
// ---------------------------------------------------------------------------
LinkStatus st = {};
LinkSettings cfg = {};
bool haveStatus = false, haveSettings = false;
uint8_t cfgRev = 0;
uint32_t lastStatusMs = 0;

bool linkUp(uint32_t now) { return haveStatus && now - lastStatusMs < LINK_TIMEOUT_MS; }

// ---------------------------------------------------------------------------
// Changes waiting to be sent / acknowledged
// ---------------------------------------------------------------------------
struct Pending {
  bool active = false;
  int16_t value = 0;
  uint32_t readyMs = 0;   // send once now >= readyMs
  bool inFlight = false;  // sent, waiting for the ACK
  uint8_t seq = 0;
  int16_t sentValue = 0;
  uint32_t sentMs = 0;
};
Pending pending[IT_COUNT];
Pending clearFault;  // IT_CLEAR_FAN_FAULT
uint8_t nextSeq = 1;

char toast[22] = "";
uint32_t toastUntil = 0;

void showToast(const char *msg, uint32_t now) {
  strlcpy(toast, msg, sizeof(toast));
  toastUntil = now + 2000;
}

Pending &pendingFor(uint8_t item) { return item < IT_COUNT ? pending[item] : clearFault; }

// The value to show: the change being made, otherwise the Mainboard's value.
int16_t shownValue(uint8_t item) {
  if (item < IT_COUNT && pending[item].active) return pending[item].value;
  if (item == IT_TEMP_SET) return st.tempSet10;
  if (item == IT_HUM_SET) return st.humSet10;
  if (item == IT_MODE) return st.mode;
  if (item == IT_SENSOR_SOURCE) return (st.flags & FL_SIM_SENSOR) ? 1 : 0;
  if (item >= IT_MANUAL_FAN && item <= IT_MANUAL_COMPRESSOR) return (st.manual >> (item - IT_MANUAL_FAN)) & 1;
  return item < IT_COUNT ? cfg.v[item] : 0;
}

void queueChange(uint8_t item, int16_t value, uint32_t now, uint32_t settleMs) {
  Pending &p = pendingFor(item);
  p.active = true;
  p.value = value;
  p.readyMs = now + settleMs;
}

void stepItem(uint8_t item, int detents, uint32_t now) {
  if (detents == 0 || item >= IT_COUNT) return;
  const LinkItemInfo &info = linkItemInfo(item);
  int32_t v = shownValue(item) + (int32_t)detents * info.step;
  if (v < info.min) v = info.min;
  if (v > info.max) v = info.max;
  queueChange(item, (int16_t)v, now, EDIT_SETTLE_MS);
}

// ---------------------------------------------------------------------------
// Link
// ---------------------------------------------------------------------------
void linkSend(uint8_t type, const void *payload, uint8_t len) {
  uint8_t frame[LINK_MAX_PAYLOAD + 5];
  const size_t n = linkEncode(type, payload, len, frame);
  digitalWrite(LINK_DE_PIN, HIGH);
  linkPort.write(frame, n);
  linkPort.flush();
  digitalWrite(LINK_DE_PIN, LOW);
}

bool sendPending(uint8_t item, uint32_t now) {
  Pending &p = pendingFor(item);
  if (!p.active || now < p.readyMs) return false;
  if (p.inFlight && now - p.sentMs < 1500) return false;  // still waiting for its ACK
  LinkSet m;
  m.seq = nextSeq++;
  m.item = item;
  m.value = p.value;
  p.inFlight = true;
  p.seq = m.seq;
  p.sentValue = p.value;
  p.sentMs = now;
  linkSend(MSG_SET, &m, sizeof(m));
  return true;
}

// Straight after each STATUS we may send one frame (see link_protocol.h).
void sendOneFrame(uint32_t now) {
  if (!haveSettings || cfgRev != st.settingsRev) {
    linkSend(MSG_GET_SETTINGS, nullptr, 0);
    return;
  }
  if (sendPending(IT_CLEAR_FAN_FAULT, now)) return;
  for (uint8_t i = 0; i < IT_COUNT; i++) {
    if (sendPending(i, now)) return;
  }
}

void onAck(const LinkAck &a, uint32_t now) {
  Pending &p = pendingFor(a.item);
  if (!p.inFlight || p.seq != a.seq) return;
  p.inFlight = false;
  if (a.item < IT_COUNT) cfg.v[a.item] = a.value;
  if (!a.ok) {
    showToast(a.item >= IT_MANUAL_FAN && a.item <= IT_MANUAL_COMPRESSOR ? "Manual mode only" : "Not accepted", now);
    p.active = false;
  } else if (p.value == p.sentValue) {
    p.active = false;  // done (unless the knob moved again meanwhile)
  }
}

void linkTick(uint32_t now) {
  while (linkPort.available()) {
    if (!parser.feed((uint8_t)linkPort.read())) continue;
    switch (parser.type()) {
      case MSG_STATUS: {
        LinkStatus s;
        if (parser.get(s) && s.version == LINK_PROTOCOL_VERSION) {
          st = s;
          haveStatus = true;
          lastStatusMs = now;
          sendOneFrame(now);
        }
        break;
      }
      case MSG_SETTINGS:
        if (parser.get(cfg)) {
          haveSettings = true;
          cfgRev = st.settingsRev;
        }
        break;
      case MSG_ACK: {
        LinkAck a;
        if (parser.get(a)) onAck(a, now);
        break;
      }
      default:
        break;
    }
  }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------
const char *MODE_NAMES[] = {"Off", "Auto", "Manual"};

void formatValue(uint8_t item, int16_t v, char *out, size_t n) {
  const LinkItemInfo &info = linkItemInfo(item);
  switch (item) {
    case IT_MODE: snprintf(out, n, "%s", MODE_NAMES[v % 3]); return;
    case IT_FAN_MODE: snprintf(out, n, "%s", v ? "Always on" : "Auto"); return;
    case IT_SENSOR_SOURCE: snprintf(out, n, "%s", v ? "Sim" : "Real"); return;
    case IT_FAN_FAULT_RPM:
      if (v == 0) { snprintf(out, n, "Off"); return; }
      break;
    default:
      if (info.min == 0 && info.max == 1) { snprintf(out, n, "%s", v ? "On" : "Off"); return; }
  }
  if (info.decimals) snprintf(out, n, "%.1f%s", v / 10.0f, info.unit);
  else snprintf(out, n, "%d%s", v, info.unit);
}

// ---------------------------------------------------------------------------
// Screens
// ---------------------------------------------------------------------------
enum class Screen : uint8_t { Home, Menu };
Screen screen = Screen::Home;
uint16_t ackedFaults = 0;  // fault bits the user has seen
uint32_t lastInputMs = 0;

// Settings menu: links items, plus two actions.
constexpr uint8_t ACT_CLEAR = 200, ACT_EXIT = 201;
const uint8_t MENU_ALL[] = {
    IT_TEMP_BAND, IT_HUM_BAND, IT_FAN_MODE, IT_FAN_SPEED, IT_FAN_RUN_ON, IT_COMP_MIN_OFF, IT_COMP_MIN_ON,
    IT_FAN_FAULT_RPM, IT_FAN_SPINUP, IT_FAN_FAULT_DELAY, IT_TEMP_OFFSET, IT_HUM_OFFSET,
    IT_MANUAL_FAN, IT_MANUAL_HEATER, IT_MANUAL_HUMIDIFIER, IT_MANUAL_COMPRESSOR,
    IT_SENSOR_SOURCE, IT_SIM_TEMP, IT_SIM_HUM, IT_SIM_REACT, IT_SIM_FAULT,
    ACT_CLEAR, ACT_EXIT};
uint8_t menuItems[sizeof(MENU_ALL)];
uint8_t menuCount = 0, menuSel = 0, menuTop = 0;

// Manual switches only appear in Manual mode, the simulation values only
// while the simulated sensor is in use.
void buildMenu() {
  const bool manual = shownValue(IT_MODE) == 2;
  const bool sim = shownValue(IT_SENSOR_SOURCE) == 1;
  const uint8_t selected = menuCount ? menuItems[menuSel] : MENU_ALL[0];
  menuCount = 0;
  for (uint8_t it : MENU_ALL) {
    if (it >= IT_MANUAL_FAN && it <= IT_MANUAL_COMPRESSOR && !manual) continue;
    if (it >= IT_SIM_TEMP && it <= IT_SIM_FAULT && !sim) continue;
    menuItems[menuCount++] = it;
  }
  menuSel = 0;
  for (uint8_t i = 0; i < menuCount; i++) {
    if (menuItems[i] == selected) menuSel = i;
  }
}

void drawCentered(const char *s, int y) {
  oled.drawUTF8((128 - oled.getUTF8Width(s)) / 2, y, s);
}

void drawNoLink() {
  oled.setFont(u8g2_font_7x14B_tf);
  drawCentered("NO LINK TO", 22);
  drawCentered("MAINBOARD", 38);
  oled.setFont(u8g2_font_6x10_tf);
  drawCentered("Check the cable", 58);
}

void drawFault(uint16_t faults) {
  oled.drawFrame(0, 0, 128, 64);
  oled.setFont(u8g2_font_7x14B_tf);
  char line[24];
  int y = 18;
  if (faults & FL_FAN_FAULT) {
    drawCentered("FAN FAULT", y);
    y += 16;
  }
  if (faults & FL_SENSOR_FAULT) {
    drawCentered("SENSOR FAULT", y);
    y += 16;
  }
  oled.setFont(u8g2_font_6x10_tf);
  if (faults & FL_FAN_FAULT) {
    snprintf(line, sizeof(line), "Fan %u rpm", st.fanRpm);
    drawCentered(line, y);
    y += 11;
  }
  drawCentered("Push to continue", 60);
}

void drawHome(uint32_t now) {
  char line[32];
  const bool valid = st.flags & FL_READING_VALID;

  // Measured values, large
  oled.setFont(u8g2_font_logisoso16_tf);
  if (valid) snprintf(line, sizeof(line), "%.1f\xC2\xB0", st.temp10 / 10.0f);
  else snprintf(line, sizeof(line), "--.-\xC2\xB0");
  oled.drawUTF8(0, 17, line);
  if (valid) snprintf(line, sizeof(line), "%.0f%%", st.hum10 / 10.0f);
  else snprintf(line, sizeof(line), "--%%");
  oled.drawUTF8(127 - oled.getUTF8Width(line), 17, line);

  oled.setFont(u8g2_font_6x10_tf);

  // Set points. A value being changed is shown inverted until the Mainboard accepts it.
  char t[12], h[12];
  formatValue(IT_TEMP_SET, shownValue(IT_TEMP_SET), t, sizeof(t));
  formatValue(IT_HUM_SET, shownValue(IT_HUM_SET), h, sizeof(h));
  oled.drawUTF8(0, 30, "Set");
  int x = 24;
  oled.setDrawColor(1);
  if (pending[IT_TEMP_SET].active) { oled.drawBox(x - 1, 21, oled.getUTF8Width(t) + 2, 11); oled.setDrawColor(0); }
  oled.drawUTF8(x, 30, t);
  oled.setDrawColor(1);
  x = 127 - oled.getUTF8Width(h);
  if (pending[IT_HUM_SET].active) { oled.drawBox(x - 1, 21, oled.getUTF8Width(h) + 2, 11); oled.setDrawColor(0); }
  oled.drawUTF8(x, 30, h);
  oled.setDrawColor(1);

  // Mode, sensor source, compressor countdown
  const int16_t mode = shownValue(IT_MODE);
  snprintf(line, sizeof(line), "%s%s", MODE_NAMES[mode % 3], pending[IT_MODE].active ? "?" : "");
  if (pending[IT_MODE].active) {
    oled.drawBox(0, 33, oled.getUTF8Width(line) + 2, 11);
    oled.setDrawColor(0);
  }
  oled.drawUTF8(1, 42, line);
  oled.setDrawColor(1);
  if (st.compRestLeftSec && (st.flags & FL_COMP_WAITING)) {
    snprintf(line, sizeof(line), "COMP WAIT %u:%02u", st.compRestLeftSec / 60, st.compRestLeftSec % 60);
    oled.drawUTF8(127 - oled.getUTF8Width(line), 42, line);
  } else if (st.flags & FL_SIM_SENSOR) {
    oled.drawUTF8(127 - oled.getUTF8Width("SIM"), 42, "SIM");
  }

  // What is running
  static const char *NAMES[4] = {"FAN", "HEAT", "HUM", "COMP"};
  x = 0;
  if (!st.relays) oled.drawUTF8(0, 53, "Idle");
  for (uint8_t i = 0; i < 4; i++) {
    if (!(st.relays & (1 << i))) continue;
    const int w = oled.getUTF8Width(NAMES[i]);
    oled.drawBox(x, 44, w + 3, 11);
    oled.setDrawColor(0);
    oled.drawUTF8(x + 1, 53, NAMES[i]);
    oled.setDrawColor(1);
    x += w + 6;
  }

  // Bottom line: toast, faults, or fan speed
  if (now < toastUntil) {
    snprintf(line, sizeof(line), "%s", toast);
  } else if (st.flags & (FL_FAN_FAULT | FL_SENSOR_FAULT)) {
    snprintf(line, sizeof(line), "%s%s", (st.flags & FL_FAN_FAULT) ? "FAN FAULT " : "",
             (st.flags & FL_SENSOR_FAULT) ? "SENSOR FAULT" : "");
  } else if (st.relays & LB_FAN) {
    snprintf(line, sizeof(line), "Fan %u%% %u rpm", st.fanCmdPct, st.fanRpm);
  } else if (st.flags & FL_PRESSURE_VALID) {
    snprintf(line, sizeof(line), "%.1f hPa", st.pressure10 / 10.0f);
  } else {
    line[0] = 0;
  }
  oled.drawUTF8(0, 64, line);
}

void drawMenu() {
  char val[16];
  oled.setFont(u8g2_font_6x10_tf);
  oled.drawUTF8(0, 9, "SETTINGS");
  oled.drawHLine(0, 11, 128);
  constexpr uint8_t ROWS = 5;
  if (menuSel < menuTop) menuTop = menuSel;
  if (menuSel >= menuTop + ROWS) menuTop = menuSel - ROWS + 1;
  for (uint8_t r = 0; r < ROWS && menuTop + r < menuCount; r++) {
    const uint8_t i = menuTop + r;
    const uint8_t it = menuItems[i];
    const int y = 22 + r * 10;
    if (i == menuSel) {
      oled.drawBox(0, y - 9, 128, 10);
      oled.setDrawColor(0);
    }
    if (it == ACT_CLEAR) {
      oled.drawUTF8(1, y, "Clear fan fault");
      if (clearFault.active) oled.drawUTF8(116, y, "..");
    } else if (it == ACT_EXIT) {
      oled.drawUTF8(1, y, "Exit");
    } else {
      oled.drawUTF8(1, y, linkItemInfo(it).label);
      formatValue(it, shownValue(it), val, sizeof(val));
      if (pending[it].active) strlcat(val, "*", sizeof(val));
      oled.drawUTF8(127 - oled.getUTF8Width(val), y, val);
    }
    oled.setDrawColor(1);
  }
}

void draw(uint32_t now) {
  oled.clearBuffer();
  const uint16_t faults = st.flags & (FL_FAN_FAULT | FL_SENSOR_FAULT);
  if (!linkUp(now)) drawNoLink();
  else if (faults & ~ackedFaults) drawFault(faults);
  else if (screen == Screen::Menu) drawMenu();
  else drawHome(now);
  oled.sendBuffer();
}

// ---------------------------------------------------------------------------
// Input
// ---------------------------------------------------------------------------
void handleInput(uint32_t now) {
  const int d1 = enc1.takeDetents(ENC_STEPS_PER_DETENT);
  const int d2 = enc2.takeDetents(ENC_STEPS_PER_DETENT);
  const Button::Event b1 = btn1.update(now);
  const Button::Event b2 = btn2.update(now);
  const bool any = d1 || d2 || b1 || b2;
  if (any) lastInputMs = now;

  if (!linkUp(now)) return;  // nothing to send changes to

  // A fault no longer active may be shown again if it comes back.
  const uint16_t faults = st.flags & (FL_FAN_FAULT | FL_SENSOR_FAULT);
  ackedFaults &= faults;
  if (faults & ~ackedFaults) {
    if (b1 || b2) ackedFaults = faults;
    return;
  }

  if (screen == Screen::Home) {
    stepItem(IT_TEMP_SET, d1, now);
    stepItem(IT_HUM_SET, d2, now);
    if (b1 == Button::SHORT) queueChange(IT_MODE, (shownValue(IT_MODE) + 1) % 3, now, EDIT_SETTLE_MS);
    if (b2 == Button::LONG) {
      screen = Screen::Menu;
      menuCount = 0;
      menuTop = 0;
      buildMenu();
    }
    return;
  }

  // Settings menu
  buildMenu();
  if (b2 == Button::LONG || now - lastInputMs > MENU_TIMEOUT_MS) {
    screen = Screen::Home;
    return;
  }
  if (d2) menuSel = (uint8_t)constrain((int)menuSel + d2, 0, (int)menuCount - 1);
  const uint8_t it = menuItems[menuSel];
  if (it == ACT_CLEAR || it == ACT_EXIT) {
    if (b1 == Button::SHORT || b2 == Button::SHORT) {
      if (it == ACT_EXIT) screen = Screen::Home;
      else queueChange(IT_CLEAR_FAN_FAULT, 0, now, 0);
    }
  } else {
    stepItem(it, d1, now);
  }
}

// ---------------------------------------------------------------------------
void setup() {
  pinMode(LINK_DE_PIN, OUTPUT);
  digitalWrite(LINK_DE_PIN, LOW);
  Serial.begin(115200);  // USB CDC, for debug messages
  linkPort.begin(LINK_BAUD, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN);

  oled.setBusClock(400000);
  oled.begin();
  oled.clearBuffer();
  oled.setFont(u8g2_font_7x14B_tf);
  drawCentered("Climate", 28);
  drawCentered("Controller", 46);
  oled.sendBuffer();

  enc1.begin();
  enc2.begin();
  btn1.begin();
  btn2.begin();
  Serial.println("=== Climate controller: Controller ===");
  delay(800);
}

void loop() {
  const uint32_t now = millis();
  linkTick(now);
  handleInput(now);

  static uint32_t lastDraw = 0;
  if (now - lastDraw >= 100) {
    lastDraw = now;
    draw(now);
  }

  static bool wasUp = false;
  if (linkUp(now) != wasUp) {
    wasUp = !wasUp;
    Serial.println(wasUp ? "[link] Mainboard connected" : "[link] NO LINK TO MAINBOARD");
    if (!wasUp) {
      haveSettings = false;  // fetch them again on reconnect
      for (Pending &p : pending) p = Pending();  // drop unsent changes: they could be stale
      clearFault = Pending();
    }
  }
  delay(2);
}
