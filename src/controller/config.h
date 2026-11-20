#pragma once
// Controller: ESP32-C3 SuperMini. Pin map from PLAN.md section 1.
// If you change a pin here, change PLAN.md and README.md too.
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Display: DST-013, 1.3" 128x64 OLED on I2C (pins VDD, GND, SCK, SDA)
// ---------------------------------------------------------------------------
constexpr uint8_t OLED_SDA_PIN = 8;  // strapping pin: the I2C pull-ups hold it high, as it needs
constexpr uint8_t OLED_SCL_PIN = 9;  // "SCK" on the display. Strapping pin (BOOT button)
// Most 1.3" OLEDs use an SH1106 driver. If the picture is shifted by 2 pixels
// or garbled, it is an SSD1306: uncomment the next line.
// #define OLED_SSD1306

// ---------------------------------------------------------------------------
// Rotary encoders (common pin to GND, internal pull-ups)
// ---------------------------------------------------------------------------
constexpr uint8_t ENC1_A_PIN = 0;
constexpr uint8_t ENC1_B_PIN = 1;
constexpr uint8_t ENC1_SW_PIN = 3;
constexpr uint8_t ENC2_A_PIN = 4;
constexpr uint8_t ENC2_B_PIN = 5;
constexpr uint8_t ENC2_SW_PIN = 10;
// Quadrature steps per click. Most encoders (e.g. KY-040, EC11) give 4.
// If one click moves the value by 2, set 2. If you need 2 clicks for 1 step, set 4.
constexpr uint8_t ENC_STEPS_PER_DETENT = 4;
// Set true if turning clockwise lowers the value.
constexpr bool ENC1_REVERSE = false;
constexpr bool ENC2_REVERSE = false;

constexpr uint32_t BUTTON_DEBOUNCE_MS = 30;
constexpr uint32_t LONG_PRESS_MS = 800;
constexpr uint32_t EDIT_SETTLE_MS = 1000;  // send a change once the knob has been still this long
constexpr uint32_t MENU_TIMEOUT_MS = 60000;

// ---------------------------------------------------------------------------
// Link to the Mainboard (UART1). See include/link_protocol.h
// ---------------------------------------------------------------------------
constexpr uint8_t LINK_TX_PIN = 21;
constexpr uint8_t LINK_RX_PIN = 20;
// RS-485 driver enable (MAX485 DE + /RE tied together). High while sending.
// Harmless on a plain UART link, so it is always driven.
constexpr uint8_t LINK_DE_PIN = 7;
