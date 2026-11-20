#include "climate_control.h"

namespace {
template <typename T>
bool clampTo(T &v, T lo, T hi) {
  T old = v;
  if (!(v >= lo)) v = lo;  // also catches NaN for floats
  if (v > hi) v = hi;
  return v != old;
}
}  // namespace

bool sanitize(Settings &s) {
  bool changed = false;
  changed |= clampTo(s.tempSetpoint, 5.0f, 40.0f);
  changed |= clampTo(s.humSetpoint, 20.0f, 90.0f);
  changed |= clampTo(s.tempBand, 0.2f, 5.0f);
  changed |= clampTo(s.humBand, 1.0f, 15.0f);
  changed |= clampTo<uint16_t>(s.compMinOffSec, 0, 900);
  changed |= clampTo<uint16_t>(s.compMinOnSec, 0, 900);
  changed |= clampTo<uint16_t>(s.fanRunOnSec, 0, 600);
  changed |= clampTo<uint8_t>(s.fanSpeedPct, 10, 100);
  changed |= clampTo<uint16_t>(s.fanFaultRpm, 0, 5000);
  changed |= clampTo<uint16_t>(s.fanSpinupSec, 0, 120);
  changed |= clampTo<uint16_t>(s.fanFaultDelaySec, 5, 300);
  changed |= clampTo(s.tempOffset, -5.0f, 5.0f);
  changed |= clampTo(s.humOffset, -10.0f, 10.0f);
  if ((uint8_t)s.mode > (uint8_t)Mode::Manual) { s.mode = Mode::Off; changed = true; }
  if ((uint8_t)s.fanMode > (uint8_t)FanMode::AlwaysOn) { s.fanMode = FanMode::Auto; changed = true; }
  return changed;
}

void ClimateControl::begin(uint32_t nowMs) {
  compOn_ = false;
  compChangedMs_ = nowMs;
  resetDemands();
}

void ClimateControl::resetDemands() {
  cool_ = heat_ = humidify_ = dehum_ = reheat_ = false;
}

void ClimateControl::update(const Settings &s, const Reading &r, bool fanFault,
                            const bool manual[RELAY_TOTAL], uint32_t now) {
  Status st;
  bool want[RELAY_TOTAL] = {};
  st.fanFault = fanFault;

  // ---- 1. Work out what each load should do -------------------------------
  if (fanFault && s.mode != Mode::Off) {
    // No airflow: running the heater, humidifier or compressor is unsafe.
    resetDemands();
    st.sensorFault = s.mode == Mode::Auto && !r.valid;
    st.reason[HEATER] = st.reason[HUMIDIFIER] = st.reason[COMPRESSOR] = "Fan fault";
  } else if (s.mode == Mode::Auto) {
    if (!r.valid) {
      resetDemands();
      st.sensorFault = true;
      st.reason[HEATER] = st.reason[HUMIDIFIER] = st.reason[COMPRESSOR] = "Sensor fault";
    } else {
      const float T = r.temp, H = r.hum;
      const float Ts = s.tempSetpoint, Hs = s.humSetpoint;

      // Each demand starts outside the band and stops at the set point.
      if (cool_) { if (T <= Ts) cool_ = false; }
      else if (T >= Ts + s.tempBand) cool_ = true;

      if (heat_) { if (T >= Ts) heat_ = false; }
      else if (T <= Ts - s.tempBand) heat_ = true;

      if (humidify_) { if (H >= Hs) humidify_ = false; }
      else if (H <= Hs - s.humBand) humidify_ = true;

      if (dehum_) { if (H <= Hs) dehum_ = false; }
      else if (H >= Hs + s.humBand) dehum_ = true;

      // Reheat: while dehumidifying, the compressor also cools the room, so
      // the heater runs whenever the temperature is at or below the set point.
      if (!dehum_) reheat_ = false;
      else if (reheat_) { if (T >= Ts + s.tempBand) reheat_ = false; }
      else if (T <= Ts) reheat_ = true;
    }

    if (cool_ || dehum_) {
      want[COMPRESSOR] = true;
      st.reason[COMPRESSOR] = (cool_ && dehum_) ? "Cooling and dehumidifying"
                              : cool_          ? "Cooling"
                                               : "Dehumidifying";
    }
    if (heat_) {
      want[HEATER] = true;
      st.reason[HEATER] = "Heating";
    }
    if (humidify_) {
      want[HUMIDIFIER] = true;
      st.reason[HUMIDIFIER] = "Humidifying";
    }
  } else {
    resetDemands();
    if (s.mode == Mode::Manual) {
      for (uint8_t i = HEATER; i < RELAY_TOTAL; i++) {
        want[i] = manual[i];
        if (want[i]) st.reason[i] = "Manual";
      }
    }
  }

  // ---- 2. Compressor protection -------------------------------------------
  const uint32_t compElapsedSec = (uint32_t)(now - compChangedMs_) / 1000;
  if (want[COMPRESSOR] && !compOn_) {
    if (compElapsedSec >= s.compMinOffSec) {
      compOn_ = true;
      compChangedMs_ = now;
    } else {
      st.compWaiting = true;
      st.compRestLeftSec = s.compMinOffSec - compElapsedSec;
      st.reason[COMPRESSOR] = "Waiting: compressor resting";
    }
  } else if (!want[COMPRESSOR] && compOn_) {
    // Minimum run time only applies to normal Auto control. Off, Manual, a
    // sensor fault and a fan fault stop the compressor straight away.
    const bool holdOn = s.mode == Mode::Auto && !st.sensorFault && !fanFault &&
                        compElapsedSec < s.compMinOnSec;
    if (holdOn) {
      st.reason[COMPRESSOR] = "Minimum run time";
    } else {
      compOn_ = false;
      compChangedMs_ = now;
    }
  }
  if (!compOn_ && !st.compWaiting) {
    const uint32_t sinceOff = (uint32_t)(now - compChangedMs_) / 1000;
    if (sinceOff < s.compMinOffSec) st.compRestLeftSec = s.compMinOffSec - sinceOff;
  }
  st.relay[COMPRESSOR] = compOn_;

  // Reheat only makes sense while the compressor is actually running.
  if (reheat_ && compOn_ && !heat_) {
    want[HEATER] = true;
    st.reason[HEATER] = "Reheat (holding temperature while dehumidifying)";
  }
  st.relay[HEATER] = want[HEATER];
  st.relay[HUMIDIFIER] = want[HUMIDIFIER];

  // ---- 3. Fan --------------------------------------------------------------
  const bool othersOn = st.relay[HEATER] || st.relay[HUMIDIFIER] || st.relay[COMPRESSOR];
  if (othersOn) {
    othersEverOn_ = true;
    othersLastOnMs_ = now;
  }
  const bool runOn = !othersOn && othersEverOn_ &&
                     (uint32_t)(now - othersLastOnMs_) < (uint32_t)s.fanRunOnSec * 1000UL;

  if (fanFault && s.mode != Mode::Off) {
    st.relay[FAN] = true;  // keep trying, so the fan can recover
    st.reason[FAN] = "Fan fault: tach too slow";
  } else if (othersOn) {
    st.relay[FAN] = true;
    st.reason[FAN] = "Other equipment running";
  } else if (runOn) {
    st.relay[FAN] = true;
    st.reason[FAN] = "Run-on after equipment stopped";
  } else if (s.mode == Mode::Manual && manual[FAN]) {
    st.relay[FAN] = true;
    st.reason[FAN] = "Manual";
  } else if (s.mode == Mode::Auto && s.fanMode == FanMode::AlwaysOn) {
    st.relay[FAN] = true;
    st.reason[FAN] = "Fan set to always on";
  }

  st.cool = cool_;
  st.heat = heat_;
  st.humidify = humidify_;
  st.dehumidify = dehum_;
  st.reheat = reheat_ && compOn_;
  st_ = st;
}
