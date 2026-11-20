#include "fan.h"

#include <Arduino.h>

#include "config.h"

namespace {
volatile uint32_t pulses = 0;
volatile uint32_t lastPulseUs = 0;
uint8_t cmdPct = 0;
uint16_t rpmNow = 0;
uint32_t windowStartMs = 0;
uint32_t windowStartPulses = 0;

void IRAM_ATTR onTach() {
  const uint32_t now = micros();
  if (now - lastPulseUs < FAN_TACH_MIN_PERIOD_US) return;  // glitch filter
  lastPulseUs = now;
  pulses++;
}

uint32_t dutyFor(uint8_t pct) {
  if (pct == 0) return 0;  // always truly 0 V when off
  const float duty = FAN_PWM_DUTY_AT_0V + (FAN_PWM_DUTY_AT_10V - FAN_PWM_DUTY_AT_0V) * pct / 100.0f;
  const uint32_t maxDuty = (1UL << FAN_PWM_BITS) - 1;
  float d = duty / 100.0f * maxDuty;
  if (d < 0) d = 0;
  if (d > maxDuty) d = maxDuty;
  return (uint32_t)(d + 0.5f);
}
}  // namespace

namespace fan {

void begin() {
  pinMode(FAN_PWM_PIN, OUTPUT);
  digitalWrite(FAN_PWM_PIN, LOW);
  ledcSetup(FAN_PWM_CHANNEL, FAN_PWM_FREQ_HZ, FAN_PWM_BITS);
  ledcAttachPin(FAN_PWM_PIN, FAN_PWM_CHANNEL);
  ledcWrite(FAN_PWM_CHANNEL, 0);
  cmdPct = 0;

  pinMode(FAN_TACH_PIN, INPUT);  // GPIO 34: external pull-up required
  attachInterrupt(digitalPinToInterrupt(FAN_TACH_PIN), onTach, FALLING);
  windowStartMs = millis();
}

void setCommandPct(uint8_t pct) {
  if (pct > 100) pct = 100;
  if (pct == cmdPct) return;
  cmdPct = pct;
  ledcWrite(FAN_PWM_CHANNEL, dutyFor(pct));
}

uint8_t commandPct() { return cmdPct; }

void tick(uint32_t now) {
  const uint32_t elapsed = now - windowStartMs;
  if (elapsed < FAN_RPM_WINDOW_MS) return;
  noInterrupts();
  const uint32_t p = pulses;
  interrupts();
  const uint32_t counted = p - windowStartPulses;
  rpmNow = (uint16_t)min<uint32_t>(counted * 60000UL / (elapsed * FAN_TACH_PULSES_PER_REV), 65535);
  windowStartPulses = p;
  windowStartMs = now;
}

uint16_t rpm() { return rpmNow; }

}  // namespace fan
