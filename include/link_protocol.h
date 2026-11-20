#pragma once
// Serial link between the Mainboard and the Controller. Shared by both
// firmwares, so the two sides cannot drift apart. Plain C++, no Arduino calls.
// See PLAN.md section 1, "Controller link".
//
// Frame:  0xA5 | type | len | payload[len] | crc16 (lo, hi)
//         CRC-16/CCITT-FALSE over type, len and payload. Bad frames are dropped.
//
// Who talks when (works on plain UART and on half-duplex RS-485):
//   - The Mainboard sends STATUS every LINK_STATUS_INTERVAL_MS. It sends nothing
//     else unless asked.
//   - Straight after each STATUS, the Controller may send ONE frame:
//     GET_SETTINGS or SET.
//   - The Mainboard answers GET_SETTINGS with SETTINGS, and SET with ACK.
// So only one side ever transmits at a time.
//
// Both ends are ESP32 (little-endian), so payloads are packed structs.

#include <stddef.h>
#include <stdint.h>
#include <string.h>

constexpr uint8_t LINK_PROTOCOL_VERSION = 1;
constexpr uint32_t LINK_BAUD = 115200;
constexpr uint32_t LINK_STATUS_INTERVAL_MS = 500;
constexpr uint32_t LINK_TIMEOUT_MS = 5000;  // Controller shows NO LINK after this

constexpr uint8_t LINK_START = 0xA5;
constexpr uint8_t LINK_MAX_PAYLOAD = 96;

enum LinkType : uint8_t {
  MSG_STATUS = 1,        // Mainboard -> Controller, LinkStatus
  MSG_GET_SETTINGS = 2,  // Controller -> Mainboard, no payload
  MSG_SETTINGS = 3,      // Mainboard -> Controller, LinkSettings
  MSG_SET = 4,           // Controller -> Mainboard, LinkSet
  MSG_ACK = 5,           // Mainboard -> Controller, LinkAck
};

// Every value the Controller can read or change. Scaled integers:
// x10 means tenths (225 = 22.5).
enum LinkItem : uint8_t {
  // Saved in the Mainboard's flash
  IT_TEMP_SET = 0,      // x10 °C
  IT_HUM_SET,           // x10 %RH
  IT_TEMP_BAND,         // x10 °C
  IT_HUM_BAND,          // x10 %RH
  IT_MODE,              // 0 Off, 1 Auto, 2 Manual
  IT_FAN_MODE,          // 0 Auto, 1 Always on
  IT_FAN_SPEED,         // % (10-100)
  IT_FAN_RUN_ON,        // s
  IT_COMP_MIN_OFF,      // s
  IT_COMP_MIN_ON,       // s
  IT_FAN_FAULT_RPM,     // rpm, 0 = fan fault check off
  IT_FAN_SPINUP,        // s
  IT_FAN_FAULT_DELAY,   // s
  IT_TEMP_OFFSET,       // x10 °C, added to the sensor reading
  IT_HUM_OFFSET,        // x10 %RH
  // Not saved: back to the defaults at every boot
  IT_SENSOR_SOURCE,     // 0 real sensor, 1 simulated
  IT_SIM_TEMP,          // x10 °C
  IT_SIM_HUM,           // x10 %RH
  IT_SIM_REACT,         // 0/1: simulated room reacts to the relays
  IT_SIM_FAULT,         // 0/1: simulated sensor fault
  IT_MANUAL_FAN,        // 0/1, Manual mode only
  IT_MANUAL_HEATER,
  IT_MANUAL_HUMIDIFIER,
  IT_MANUAL_COMPRESSOR,
  IT_COUNT,             // number of values in LinkSettings
  // Actions (no stored value)
  IT_CLEAR_FAN_FAULT = 100,
};

// Bits in LinkStatus::relays and ::manual (same order as the relay board IN1..IN4)
enum : uint8_t { LB_FAN = 1, LB_HEATER = 2, LB_HUMIDIFIER = 4, LB_COMPRESSOR = 8 };
// Bits in LinkStatus::demand
enum : uint8_t { DM_COOL = 1, DM_HEAT = 2, DM_HUMIDIFY = 4, DM_DEHUMIDIFY = 8, DM_REHEAT = 16 };
// Bits in LinkStatus::flags
enum : uint16_t {
  FL_READING_VALID = 1,   // temp/hum are a valid reading
  FL_SENSOR_FAULT = 2,    // no valid reading: heater, humidifier, compressor stopped
  FL_FAN_FAULT = 4,       // fan on but tach too slow (latched)
  FL_SIM_SENSOR = 8,      // simulated sensor in use
  FL_COMP_WAITING = 16,   // compressor wanted but resting
  FL_PRESSURE_VALID = 32, // BMP280 found
};

#pragma pack(push, 1)
struct LinkStatus {
  uint8_t version;          // LINK_PROTOCOL_VERSION
  uint8_t settingsRev;      // changes whenever LinkSettings changes
  int16_t temp10;           // x10 °C (after offset)
  int16_t hum10;            // x10 %RH (after offset)
  uint16_t pressure10;      // x10 hPa
  int16_t tempSet10;
  int16_t humSet10;
  uint8_t mode;
  uint8_t relays;           // LB_* bits: relay outputs now
  uint8_t manual;           // LB_* bits: manual switch requests
  uint8_t demand;           // DM_* bits
  uint16_t flags;           // FL_* bits
  uint8_t fanCmdPct;        // 0-10 V command now, %
  uint16_t fanRpm;
  uint16_t compRestLeftSec;
  uint32_t uptimeSec;
};

struct LinkSettings {
  int16_t v[IT_COUNT];      // indexed by LinkItem
};

struct LinkSet {
  uint8_t seq;              // echoed in the ACK
  uint8_t item;             // LinkItem
  int16_t value;
};

struct LinkAck {
  uint8_t seq;
  uint8_t item;
  uint8_t ok;               // 1 accepted, 0 rejected
  int16_t value;            // value now in force (may be clamped)
};
#pragma pack(pop)

static_assert(sizeof(LinkStatus) <= LINK_MAX_PAYLOAD, "LinkStatus too big");
static_assert(sizeof(LinkSettings) <= LINK_MAX_PAYLOAD, "LinkSettings too big");

// Name, limits and step of each LinkItem. Limits match sanitize() on the
// Mainboard (which clamps anyway). Values are in the scaled units above.
struct LinkItemInfo {
  const char *key;     // serial command name on the Mainboard ("set <key> <value>")
  const char *label;   // menu label on the Controller (max 13 chars)
  uint8_t decimals;    // 1 = value is x10
  int16_t min, max, step;
  const char *unit;
};

inline const LinkItemInfo &linkItemInfo(uint8_t item) {
  static const LinkItemInfo T[IT_COUNT] = {
      {"tempset", "Temp set", 1, 50, 400, 1, "\xC2\xB0" "C"},
      {"humset", "Hum set", 1, 200, 900, 10, "%"},
      {"tempband", "Temp band", 1, 2, 50, 1, "\xC2\xB0" "C"},
      {"humband", "Hum band", 1, 10, 150, 5, "%"},
      {"mode", "Mode", 0, 0, 2, 1, ""},
      {"fanmode", "Fan mode", 0, 0, 1, 1, ""},
      {"fanspeed", "Fan speed", 0, 10, 100, 5, "%"},
      {"fanrunon", "Fan run-on", 0, 0, 600, 5, "s"},
      {"compminoff", "Comp min off", 0, 0, 900, 10, "s"},
      {"compminon", "Comp min on", 0, 0, 900, 10, "s"},
      {"fanfaultrpm", "Fan flt rpm", 0, 0, 5000, 50, ""},
      {"fanspinup", "Fan spin-up", 0, 0, 120, 1, "s"},
      {"fanfaultdelay", "Fan flt delay", 0, 5, 300, 5, "s"},
      {"tempoffset", "Temp offset", 1, -50, 50, 1, "\xC2\xB0" "C"},
      {"humoffset", "Hum offset", 1, -100, 100, 5, "%"},
      {"sensor", "Sensor", 0, 0, 1, 1, ""},
      {"simtemp", "Sim temp", 1, -200, 600, 1, "\xC2\xB0" "C"},
      {"simhum", "Sim hum", 1, 0, 1000, 10, "%"},
      {"simreact", "Sim reacts", 0, 0, 1, 1, ""},
      {"simfault", "Sim fault", 0, 0, 1, 1, ""},
      {"manfan", "Man: fan", 0, 0, 1, 1, ""},
      {"manheater", "Man: heater", 0, 0, 1, 1, ""},
      {"manhum", "Man: humid.", 0, 0, 1, 1, ""},
      {"mancomp", "Man: compr.", 0, 0, 1, 1, ""},
  };
  static const LinkItemInfo NONE = {"", "", 0, 0, 0, 0, ""};
  return item < IT_COUNT ? T[item] : NONE;
}

inline uint16_t linkCrc16(const uint8_t *d, size_t n, uint16_t crc = 0xFFFF) {
  while (n--) {
    crc ^= (uint16_t)(*d++) << 8;
    for (uint8_t i = 0; i < 8; i++) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
  }
  return crc;
}

// Builds a frame into out (needs len + 5 bytes). Returns the frame length.
inline size_t linkEncode(uint8_t type, const void *payload, uint8_t len, uint8_t *out) {
  out[0] = LINK_START;
  out[1] = type;
  out[2] = len;
  if (len) memcpy(out + 3, payload, len);
  const uint16_t crc = linkCrc16(out + 1, (size_t)len + 2);
  out[3 + len] = (uint8_t)(crc & 0xFF);
  out[4 + len] = (uint8_t)(crc >> 8);
  return (size_t)len + 5;
}

// Byte-at-a-time frame decoder. feed() returns true when a whole, valid frame
// has arrived; then read type(), len() and payload().
class LinkParser {
 public:
  bool feed(uint8_t b) {
    switch (state_) {
      case 0:
        if (b == LINK_START) state_ = 1;
        return false;
      case 1:
        type_ = b;
        state_ = 2;
        return false;
      case 2:
        if (b > LINK_MAX_PAYLOAD) { state_ = 0; return false; }
        len_ = b;
        pos_ = 0;
        state_ = len_ ? 3 : 4;
        return false;
      case 3:
        buf_[pos_++] = b;
        if (pos_ >= len_) state_ = 4;
        return false;
      case 4:
        crcLo_ = b;
        state_ = 5;
        return false;
      default: {
        state_ = 0;
        uint8_t hdr[2] = {type_, len_};
        uint16_t crc = linkCrc16(hdr, 2);
        crc = linkCrc16(buf_, len_, crc);
        return crc == (uint16_t)(crcLo_ | (b << 8));
      }
    }
  }
  uint8_t type() const { return type_; }
  uint8_t len() const { return len_; }
  const uint8_t *payload() const { return buf_; }

  // Copies the payload into a struct if the length matches exactly.
  template <typename T>
  bool get(T &out) const {
    if (len_ != sizeof(T)) return false;
    memcpy(&out, buf_, sizeof(T));
    return true;
  }

 private:
  uint8_t state_ = 0, type_ = 0, len_ = 0, pos_ = 0, crcLo_ = 0;
  uint8_t buf_[LINK_MAX_PAYLOAD];
};
