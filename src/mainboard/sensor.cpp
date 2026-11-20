#include "sensor.h"

#include <Adafruit_AHTX0.h>
#include <Adafruit_BMP280.h>
#include <Wire.h>

namespace {
Adafruit_AHTX0 aht;
Adafruit_BMP280 bmp(&Wire);
}  // namespace

void SensorBoard::begin() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ_HZ);
  tryStart();
}

void SensorBoard::tryStart() {
  if (!ahtOk_) {
    ahtOk_ = aht.begin(&Wire);
    Serial.printf("[sensor] AHT20 %s\n", ahtOk_ ? "found at 0x38" : "NOT found");
  }
  if (!bmpOk_) {
    bmpOk_ = bmp.begin(0x77) || bmp.begin(0x76);
    if (bmpOk_) {
      bmp.setSampling(Adafruit_BMP280::MODE_NORMAL, Adafruit_BMP280::SAMPLING_X2,
                      Adafruit_BMP280::SAMPLING_X16, Adafruit_BMP280::FILTER_X16,
                      Adafruit_BMP280::STANDBY_MS_500);
    }
    Serial.printf("[sensor] BMP280 %s\n", bmpOk_ ? "found" : "not found (pressure not shown)");
  }
}

// A slave stuck holding SDA low can lock the bus. Clock SCL until it lets go.
void SensorBoard::recoverBus() {
  Wire.end();
  pinMode(I2C_SDA_PIN, INPUT_PULLUP);
  pinMode(I2C_SCL_PIN, OUTPUT_OPEN_DRAIN);
  for (int i = 0; i < 9 && digitalRead(I2C_SDA_PIN) == LOW; i++) {
    digitalWrite(I2C_SCL_PIN, LOW);
    delayMicroseconds(5);
    digitalWrite(I2C_SCL_PIN, HIGH);
    delayMicroseconds(5);
  }
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ_HZ);
}

void SensorBoard::tick(uint32_t now) {
  if (now - lastReadMs_ < SENSOR_READ_INTERVAL_MS) return;
  lastReadMs_ = now;

  if (!ahtOk_) {
    if (now - lastRetryMs_ >= SENSOR_RETRY_MS) {
      lastRetryMs_ = now;
      recoverBus();
      tryStart();
    }
  }

  if (ahtOk_) {
    sensors_event_t hum, temp;
    const bool ok = aht.getEvent(&hum, &temp);
    const float T = temp.temperature, H = hum.relative_humidity;
    // Reject failed reads and values the AHT20 cannot produce.
    if (ok && T > -40.0f && T < 85.0f && H >= 0.0f && H <= 100.0f) {
      if (everGood_ && now - lastGoodMs_ >= SENSOR_FAULT_TIMEOUT_MS) n_ = 0;  // drop stale values
      t_[next_] = T;
      h_[next_] = H;
      next_ = (next_ + 1) % SENSOR_AVERAGE_COUNT;
      if (n_ < SENSOR_AVERAGE_COUNT) n_++;
      lastGoodMs_ = now;
      everGood_ = true;
    } else if (now - lastGoodMs_ >= SENSOR_FAULT_TIMEOUT_MS / 2) {
      // Reads keep failing: start again from scratch on the next retry.
      ahtOk_ = false;
      lastRetryMs_ = now - SENSOR_RETRY_MS;
    }
  }

  if (bmpOk_) {
    const float p = bmp.readPressure();
    if (p > 30000.0f && p < 120000.0f) pressureHpa_ = p / 100.0f;
  }
}

Reading SensorBoard::reading() const {
  Reading r;
  if (!everGood_ || n_ == 0) return r;
  if (millis() - lastGoodMs_ >= SENSOR_FAULT_TIMEOUT_MS) return r;  // stale: fault
  float ts = 0, hs = 0;
  for (uint8_t i = 0; i < n_; i++) {
    ts += t_[i];
    hs += h_[i];
  }
  r.temp = ts / n_;
  r.hum = hs / n_;
  r.valid = true;
  return r;
}
