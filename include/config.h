#pragma once
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Relays (order: fan, heater, humidifier, compressor, matching IN1..IN4)
// ---------------------------------------------------------------------------
#if defined(ESP8266)
// NodeMCU D0, D7, D5, D6 = GPIO 16, 13, 14, 12.
// D1/D2 (GPIO 5/4) are kept free for the I2C sensor (SCL/SDA).
// The compressor is on GPIO 12, which stays quiet while the chip boots.
// Avoid D3, D4, D8: they decide how the chip boots.
constexpr uint8_t RELAY_PINS[4] = {16, 13, 14, 12};
#else
// ESP32 DevKit. I2C sensor on the default pins: SDA 21, SCL 22.
constexpr uint8_t RELAY_PINS[4] = {26, 27, 32, 33};
#endif

// Most cheap opto-isolated relay boards switch ON when IN is pulled LOW.
// The project's own carrier PCB (hardware/) uses NPN drivers, so a GPIO HIGH
// switches the relay ON. Build the "nodemcuv2-pcb" environment for that board.
#if defined(CLIMATE_PCB)
constexpr bool RELAY_ACTIVE_LOW = false;
#else
constexpr bool RELAY_ACTIVE_LOW = true;
#endif

// ---------------------------------------------------------------------------
// Control loop
// ---------------------------------------------------------------------------
constexpr uint32_t CONTROL_INTERVAL_MS = 1000;

// ---------------------------------------------------------------------------
// Network
// ---------------------------------------------------------------------------
// Reach the board at http://<HOSTNAME>.local (mDNS) or by its IP address.
// If you change this, change upload_port in platformio.ini too.
constexpr const char *HOSTNAME = "climate";

// How long to try your WiFi before falling back to the board's own access point.
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;

// Fallback access point. Join it and open http://192.168.4.1
// The password must be at least 8 characters.
constexpr const char *AP_SSID = "Climate-Setup";
constexpr const char *AP_PASSWORD = "climate1234";

// In fallback AP mode, reboot and retry your WiFi after this long if nobody
// is connected to the AP. The control loop keeps running in AP mode.
constexpr uint32_t AP_RETRY_MS = 5UL * 60UL * 1000UL;
