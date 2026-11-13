#pragma once
// Saves the settings to flash (LittleFS on ESP8266, NVS on ESP32).
// Both are wear-levelled. Settings are only written when they change.

#include "controller.h"

void storageBegin();
// Returns false (and leaves s at its defaults) if nothing valid is saved.
bool loadSettings(Settings &s);
void saveSettings(const Settings &s);
