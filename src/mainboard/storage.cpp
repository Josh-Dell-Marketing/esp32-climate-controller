#include "storage.h"

#include <Arduino.h>
#include <Preferences.h>

namespace {
// Bump SETTINGS_VERSION whenever the Settings struct changes, so old saved
// data is ignored instead of being misread.
constexpr uint32_t SETTINGS_MAGIC = 0x434C494D;  // "CLIM"
constexpr uint8_t SETTINGS_VERSION = 2;          // 2: fan speed, fan fault, sensor offsets

struct Blob {
  uint32_t magic;
  uint8_t version;
  Settings settings;
};

Preferences prefs;
}  // namespace

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
