#pragma once
// Stand-in for a real sensor until one is wired in (PLAN.md Phase 1).
// Values are typed in on the web page. With "react" on, the relays move the
// values, so you can watch the controller work. The rates are much faster
// than a real room so a full cycle takes a minute or two.

#include "controller.h"

struct SimRoom {
  float temp = 22.0f;
  float hum = 50.0f;
  bool react = false;  // relays change temp/humidity
  bool fault = false;  // pretend the sensor has failed

  // Per-second effect of each load.
  static constexpr float HEATER_C_PER_S = 0.05f;
  static constexpr float COMP_C_PER_S = -0.04f;
  static constexpr float COMP_RH_PER_S = -0.15f;
  static constexpr float HUMIDIFIER_RH_PER_S = 0.20f;

  void step(const bool relay[RELAY_TOTAL], float dtSec) {
    if (!react) return;
    if (relay[HEATER]) temp += HEATER_C_PER_S * dtSec;
    if (relay[COMPRESSOR]) {
      temp += COMP_C_PER_S * dtSec;
      hum += COMP_RH_PER_S * dtSec;
    }
    if (relay[HUMIDIFIER]) hum += HUMIDIFIER_RH_PER_S * dtSec;
    if (hum < 0) hum = 0;
    if (hum > 100) hum = 100;
  }

  Reading reading() const {
    Reading r;
    r.temp = temp;
    r.hum = hum;
    r.valid = !fault;
    return r;
  }
};
