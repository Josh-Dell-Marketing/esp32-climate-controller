#pragma once
// Saves the settings to the ESP32's NVS flash (wear-levelled).
// Settings are only written when they change.

#include "climate_control.h"

void storageBegin();
// Returns false (and leaves s at its defaults) if nothing valid is saved.
bool loadSettings(Settings &s);
void saveSettings(const Settings &s);
