#pragma once
// Mainboard: ESP32 NodeMCU WROOM-32 DevKit. Pin map from PLAN.md section 1.
// If you change a pin here, change PLAN.md and README.md too.
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Relays (order: fan, heater, humidifier, compressor = relay board IN1..IN4)
// ---------------------------------------------------------------------------
// None of these are boot strapping pins, so no relay clicks on during boot.
constexpr uint8_t RELAY_PINS[4] = {26, 27, 32, 33};

// Most cheap opto-isolated 4-relay boards switch ON when IN is pulled LOW.
// Set this to false for a board that switches ON with IN HIGH.
constexpr bool RELAY_ACTIVE_LOW = true;

// ---------------------------------------------------------------------------
// Sensor: AHT20 + BMP280 board on I2C
// ---------------------------------------------------------------------------
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;
constexpr uint32_t I2C_FREQ_HZ = 100000;
constexpr uint32_t SENSOR_READ_INTERVAL_MS = 2000;
constexpr uint8_t SENSOR_AVERAGE_COUNT = 4;        // average of the last N good readings
constexpr uint32_t SENSOR_FAULT_TIMEOUT_MS = 30000; // no valid reading this long = sensor fault
constexpr uint32_t SENSOR_RETRY_MS = 10000;         // how often to re-try a missing sensor

// ---------------------------------------------------------------------------
// Fan: PWM to the PWM -> 0-10 V converter, and the tach input
// ---------------------------------------------------------------------------
constexpr uint8_t FAN_PWM_PIN = 25;
constexpr uint8_t FAN_PWM_CHANNEL = 0;      // LEDC channel
constexpr uint32_t FAN_PWM_FREQ_HZ = 1000;  // check your converter's datasheet (often 1-3 kHz)
constexpr uint8_t FAN_PWM_BITS = 10;
// Converter calibration: the duty cycle (%) that gives 0 V and 10 V out.
// Measure with a meter and adjust (PLAN.md section 1, "Fan control").
constexpr float FAN_PWM_DUTY_AT_0V = 0.0f;
constexpr float FAN_PWM_DUTY_AT_10V = 100.0f;

// Input only, no internal pull-up: fit a 4.7-10 k pull-up to 3V3 (never 5 V).
constexpr uint8_t FAN_TACH_PIN = 34;
constexpr uint8_t FAN_TACH_PULSES_PER_REV = 1;
constexpr uint32_t FAN_TACH_MIN_PERIOD_US = 2000;  // ignore pulses closer than this (glitches)
constexpr uint32_t FAN_RPM_WINDOW_MS = 2000;       // RPM is measured over this window

// ---------------------------------------------------------------------------
// Link to the Controller (UART2). See include/link_protocol.h
// ---------------------------------------------------------------------------
constexpr uint8_t LINK_TX_PIN = 17;
constexpr uint8_t LINK_RX_PIN = 16;
// RS-485 driver enable (MAX485 DE + /RE tied together). High while sending.
// Harmless on a plain UART link, so it is always driven.
constexpr uint8_t LINK_DE_PIN = 4;

// ---------------------------------------------------------------------------
// Control loop
// ---------------------------------------------------------------------------
constexpr uint32_t CONTROL_INTERVAL_MS = 1000;
