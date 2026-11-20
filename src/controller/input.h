#pragma once
// Rotary encoder (interrupt driven, full quadrature decode) and push button.

#include <Arduino.h>

#include "config.h"

class Encoder {
 public:
  Encoder(uint8_t a, uint8_t b, bool reverse) : a_(a), b_(b), reverse_(reverse) {}

  void begin() {
    pinMode(a_, INPUT_PULLUP);
    pinMode(b_, INPUT_PULLUP);
    prev_ = readAB();
    attachInterruptArg(digitalPinToInterrupt(a_), isr, this, CHANGE);
    attachInterruptArg(digitalPinToInterrupt(b_), isr, this, CHANGE);
  }

  // Whole clicks turned since the last call (+ clockwise).
  int takeDetents(uint8_t stepsPerDetent) {
    noInterrupts();
    const int32_t raw = raw_;
    const int32_t d = raw / stepsPerDetent;
    raw_ -= d * stepsPerDetent;
    interrupts();
    return reverse_ ? -d : d;
  }

 private:
  uint8_t a_, b_;
  bool reverse_;
  volatile int32_t raw_ = 0;
  volatile uint8_t prev_ = 0;

  uint8_t readAB() const { return (digitalRead(a_) << 1) | digitalRead(b_); }

  static void IRAM_ATTR isr(void *arg) {
    // Valid Gray-code transitions give +1/-1, bounces and invalid jumps give 0.
    static const int8_t T[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};
    Encoder *e = static_cast<Encoder *>(arg);
    const uint8_t cur = e->readAB();
    e->raw_ += T[(e->prev_ << 2) | cur];
    e->prev_ = cur;
  }
};

class Button {
 public:
  enum Event : uint8_t { NONE, SHORT, LONG };

  explicit Button(uint8_t pin) : pin_(pin) {}
  void begin() { pinMode(pin_, INPUT_PULLUP); }

  // Call often. LONG fires while still held; SHORT fires on release.
  Event update(uint32_t now) {
    const bool down = digitalRead(pin_) == LOW;
    if (down != raw_) {
      raw_ = down;
      changedMs_ = now;
    }
    if (now - changedMs_ >= BUTTON_DEBOUNCE_MS && down != stable_) {
      stable_ = down;
      if (down) {
        pressedMs_ = now;
        longFired_ = false;
      } else if (!longFired_) {
        return SHORT;
      }
    }
    if (stable_ && !longFired_ && now - pressedMs_ >= LONG_PRESS_MS) {
      longFired_ = true;
      return LONG;
    }
    return NONE;
  }

 private:
  uint8_t pin_;
  bool raw_ = false, stable_ = false, longFired_ = false;
  uint32_t changedMs_ = 0, pressedMs_ = 0;
};
