#include "storage.h"

#include <Arduino.h>

namespace {
// Bump SETTINGS_VERSION whenever the Settings struct changes, so old saved
// data is ignored instead of being misread.
constexpr uint32_t SETTINGS_MAGIC = 0x434C494D;  // "CLIM"
constexpr uint8_t SETTINGS_VERSION = 1;

struct Blob {
  uint32_t magic;
  uint8_t version;
  Settings settings;
};
}  // namespace

#if defined(ESP8266)
#include <LittleFS.h>

static bool fsOk = false;
static const char *PATH = "/settings.bin";

void storageBegin() {
  fsOk = LittleFS.begin();  // formats the filesystem on first use
  if (!fsOk) Serial.println("[store] LittleFS failed, settings will not be saved");
}

bool loadSettings(Settings &s) {
  if (!fsOk) return false;
  File f = LittleFS.open(PATH, "r");
  if (!f) return false;
  Blob b;
  size_t n = f.read((uint8_t *)&b, sizeof(b));
  f.close();
  if (n != sizeof(b) || b.magic != SETTINGS_MAGIC || b.version != SETTINGS_VERSION) return false;
  s = b.settings;
  return true;
}

void saveSettings(const Settings &s) {
  if (!fsOk) return;
  Blob b{SETTINGS_MAGIC, SETTINGS_VERSION, s};
  File f = LittleFS.open(PATH, "w");
  if (!f) return;
  f.write((const uint8_t *)&b, sizeof(b));
  f.close();
}

#else
#include <Preferences.h>

static Preferences prefs;

void storageBegin() { prefs.begin("climate", false); }

bool loadSettings(Settings &s) {
  Blob b;
  if (prefs.getBytes("settings", &b, sizeof(b)) != sizeof(b)) return false;
  if (b.magic != SETTINGS_MAGIC || b.version != SETTINGS_VERSION) return false;
  s = b.settings;
  return true;
}

void saveSettings(const Settings &s) {
  Blob b{SETTINGS_MAGIC, SETTINGS_VERSION, s};
  prefs.putBytes("settings", &b, sizeof(b));
}
#endif
