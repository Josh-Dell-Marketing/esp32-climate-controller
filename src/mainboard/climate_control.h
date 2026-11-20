#pragma once
// Climate control rules. Plain C++ with no Arduino calls, so it can be
// unit-tested on a PC. See PLAN.md section 2 for the rules.

#include <stdint.h>

enum Relay : uint8_t { FAN = 0, HEATER = 1, HUMIDIFIER = 2, COMPRESSOR = 3, RELAY_TOTAL = 4 };

enum class Mode : uint8_t { Off = 0, Auto = 1, Manual = 2 };
enum class FanMode : uint8_t { Auto = 0, AlwaysOn = 1 };

// Saved to flash as a raw struct: bump SETTINGS_VERSION in storage.cpp when this changes.
struct Settings {
  float tempSetpoint = 22.0f;   // °C
  float humSetpoint = 50.0f;    // %RH
  float tempBand = 0.5f;        // °C either side of the set point before acting
  float humBand = 3.0f;         // %RH
  Mode mode = Mode::Off;
  FanMode fanMode = FanMode::Auto;
  uint16_t compMinOffSec = 180; // compressor rest time before it may restart
  uint16_t compMinOnSec = 60;   // compressor minimum run time (Auto mode)
  uint16_t fanRunOnSec = 30;    // fan keeps running after everything else stops
  uint8_t fanSpeedPct = 100;    // 0-10 V command while the fan relay is on (10-100 %)
  uint16_t fanFaultRpm = 200;   // tach below this = fan fault. 0 turns the check off
  uint16_t fanSpinupSec = 10;   // allowance after the fan starts before checking
  uint16_t fanFaultDelaySec = 15; // RPM must be low this long to raise the fault
  float tempOffset = 0.0f;      // added to the sensor reading (calibration)
  float humOffset = 0.0f;
};

// Clamps every setting to a safe range. Returns true if anything changed.
bool sanitize(Settings &s);

struct Reading {
  float temp = 0;
  float hum = 0;
  bool valid = false;
};

struct Status {
  bool relay[RELAY_TOTAL] = {};
  const char *reason[RELAY_TOTAL] = {"", "", "", ""};  // why each relay is on (or held off)
  bool cool = false, heat = false, humidify = false, dehumidify = false, reheat = false;
  bool sensorFault = false;
  bool fanFault = false;
  bool compWaiting = false;      // compressor wanted but resting
  uint32_t compRestLeftSec = 0;  // seconds until the compressor may start
};

class ClimateControl {
 public:
  // Call once at boot. The compressor counts as having just stopped,
  // so it rests for compMinOffSec after a power cut.
  void begin(uint32_t nowMs);

  // Call about once a second. manual[] is only used in Manual mode.
  // fanFault comes from FanMonitor: it stops the heater, humidifier and compressor.
  void update(const Settings &s, const Reading &r, bool fanFault, const bool manual[RELAY_TOTAL],
              uint32_t nowMs);

  const Status &status() const { return st_; }

 private:
  Status st_;
  bool cool_ = false, heat_ = false, humidify_ = false, dehum_ = false, reheat_ = false;
  bool compOn_ = false;
  uint32_t compChangedMs_ = 0;
  bool othersEverOn_ = false;
  uint32_t othersLastOnMs_ = 0;

  void resetDemands();
};

// Fan fault detection from the tach. Plain C++.
// A fault is raised when the fan relay has been on for longer than the spin-up
// allowance and the RPM has stayed below the threshold for the fault delay.
// It is latched until clear() is called.
class FanMonitor {
 public:
  void update(bool fanOn, uint16_t rpm, const Settings &s, uint32_t nowMs) {
    if (!fanOn || s.fanFaultRpm == 0) {
      running_ = false;
      lowSince_ = 0;
      return;
    }
    if (!running_) {
      running_ = true;
      startMs_ = nowMs;
      lowSince_ = 0;
    }
    if ((uint32_t)(nowMs - startMs_) < (uint32_t)s.fanSpinupSec * 1000UL) return;
    if (rpm >= s.fanFaultRpm) {
      lowSince_ = 0;
      return;
    }
    if (lowSince_ == 0) lowSince_ = nowMs ? nowMs : 1;
    if ((uint32_t)(nowMs - lowSince_) >= (uint32_t)s.fanFaultDelaySec * 1000UL) fault_ = true;
  }

  // Clears the latch. The spin-up allowance starts again, so a fan that is
  // still not turning raises the fault again after spin-up + delay.
  void clear() {
    fault_ = false;
    running_ = false;
    lowSince_ = 0;
  }

  bool fault() const { return fault_; }

 private:
  bool fault_ = false;
  bool running_ = false;
  uint32_t startMs_ = 0;
  uint32_t lowSince_ = 0;
};
