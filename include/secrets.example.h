#pragma once
// Copy this file to secrets.h (same folder) and fill in your details.
// secrets.h is git-ignored so your passwords stay out of version control.

#define WIFI_SSID "your-wifi-name"
#define WIFI_PASSWORD "your-wifi-password"

// Web page / API login. Leave WEB_PASSWORD empty ("") to turn login off.
#define WEB_USER "admin"
#define WEB_PASSWORD ""

// Password for over-the-air firmware updates. Must match upload_flags in platformio.ini.
#define OTA_PASSWORD "change-me"
