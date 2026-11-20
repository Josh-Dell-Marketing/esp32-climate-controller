#pragma once
// Fan speed (PWM into the PWM -> 0-10 V converter) and tach (RPM) input.

#include <stdint.h>

namespace fan {
void begin();                 // PWM output at 0 % (0 V), tach interrupt on
void setCommandPct(uint8_t pct);  // 0-100 % of 10 V
uint8_t commandPct();
void tick(uint32_t nowMs);    // updates the RPM once per FAN_RPM_WINDOW_MS
uint16_t rpm();
}  // namespace fan
