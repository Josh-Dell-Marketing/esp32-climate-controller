#pragma once
// AHT20 (temperature + humidity) and BMP280 (pressure) on one I2C board.
// Reads every SENSOR_READ_INTERVAL_MS, averages the last few good readings,
// and reports invalid after SENSOR_FAULT_TIMEOUT_MS with no good reading.

#include "climate_control.h"
#include "config.h"

class SensorBoard {
 public:
  void begin();
  void tick(uint32_t nowMs);  // call often; reads when due

  Reading reading() const;     // averaged, before offsets
  bool pressureValid() const { return bmpOk_; }
  float pressureHpa() const { return pressureHpa_; }
  bool ahtFound() const { return ahtOk_; }

 private:
  bool ahtOk_ = false, bmpOk_ = false;
  uint32_t lastReadMs_ = 0, lastGoodMs_ = 0, lastRetryMs_ = 0;
  bool everGood_ = false;
  float t_[SENSOR_AVERAGE_COUNT] = {}, h_[SENSOR_AVERAGE_COUNT] = {};
  uint8_t n_ = 0, next_ = 0;
  float pressureHpa_ = 0;

  void tryStart();
  void recoverBus();
};
