#pragma once
// Climate control logic. Plain C++ with no Arduino calls, so it can be
// unit-tested on a PC later. See PLAN.md section 2 for the rules.

#include <stdint.h>

enum Relay : uint8_t { FAN = 0, HEATER = 1, HUMIDIFIER = 2, COMPRESSOR = 3, RELAY_TOTAL = 4 };

enum class Mode : uint8_t { Off = 0, Auto = 1, Manual = 2 };
enum class FanMode : uint8_t { Auto = 0, AlwaysOn = 1 };

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
  bool compWaiting = false;      // compressor wanted but resting
  uint32_t compRestLeftSec = 0;  // seconds until the compressor may start
};

class Controller {
 public:
  // Call once at boot. The compressor counts as having just stopped,
  // so it rests for compMinOffSec after a power cut.
  void begin(uint32_t nowMs);

  // Call about once a second. manual[] is only used in Manual mode.
  void update(const Settings &s, const Reading &r, const bool manual[RELAY_TOTAL], uint32_t nowMs);

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
