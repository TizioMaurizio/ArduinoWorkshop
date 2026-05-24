// ============================================================================
// F8620 PC-Controlled Transmitter — XN297 Protocol
//
// Architecture: PC → USB Serial → Arduino Uno → SPI → nRF24L01+ → RF → Drone
//
// Protocol: Custom XN297-compatible (NOT standard Bayang)
//   - CRC-16/CCITT (poly=0x1021, init=0x0000, xorout=0x4358)
//   - XN297 scramble applied to address + payload
//   - Channels 72-77, 1 Mbps, no auto-ack, no nRF24 CRC
//
// Safety:
//   - Default throttle = SAFE (0x00)
//   - Failsafe activates if no PC command for >250 ms
//   - Motors never spin unless ARM 1 is received
//   - PROPELLERS MUST BE REMOVED FOR ALL TESTING
//
// Serial: 115200 baud, newline-delimited commands
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE=D9, CSN=D10

// ========================== PROTOCOL CONSTANTS ==============================

// RF channels
static const uint8_t RF_CHANNELS[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CHANNELS = 6;

// XN297 scramble table
static const uint8_t XN297_SCRAMBLE[] PROGMEM = {
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC
};

// Data address (scrambled on-air): B7 98 D8 58 EF
// Descrambled: 54 29 93 B2 6A
static const uint8_t DATA_ADDR_SCRAMBLED[] = {0xB7, 0x98, 0xD8, 0x58, 0xEF};

// Bind address (scrambled on-air): E3 B1 4B EA 85
// Descrambled: 00 00 00 00 00
static const uint8_t BIND_ADDR_SCRAMBLED[] = {0xE3, 0xB1, 0x4B, 0xEA, 0x85};

// nRF24 TX addresses (RF24 library byte order: LSByte first = last on-air byte first)
// Data: on-air 71 0F B7 98 D8 → RF24 {D8, 98, B7, 0F, 71}
static const uint8_t NRF_DATA_ADDR[] = {0xD8, 0x98, 0xB7, 0x0F, 0x71};
// Bind: on-air 71 0F E3 B1 4B → RF24 {4B, B1, E3, 0F, 71}
static const uint8_t NRF_BIND_ADDR[] = {0x4B, 0xB1, 0xE3, 0x0F, 0x71};

// CRC parameters
#define CRC_INIT   0x0000
#define CRC_POLY   0x1021
#define CRC_XOROUT 0x4358

// ========================== PAYLOAD DEFAULTS ================================
// Observed center values from original TX capture:
//   throttle ~0xF0, yaw ~0x05, pitch ~0x39, roll ~0x39
// SAFETY: We do NOT assume F0 is safe. We use 0x00 as safe throttle.

#define SAFE_THROTTLE  0x00
#define CENTER_YAW     0x05
#define CENTER_PITCH   0x39
#define CENTER_ROLL    0x39
#define DEFAULT_FLAGS1 0x00
#define DEFAULT_FLAGS2 0x40
#define DEFAULT_FLAGS3 0x00

// Failsafe timeout (ms)
#define FAILSAFE_TIMEOUT_MS 250

// Packet send interval (microseconds) — ~500 pps total
#define PACKET_INTERVAL_US 2000

// Bind duration (ms)
#define BIND_DURATION_MS 4000

// ========================== CAPTURED BIND FRAMES ============================
// Pattern A bind frames captured from original TX (raw 19 bytes each)
// These are the exact on-air bytes after XN297 preamble extension
static const uint8_t BIND_FRAMES[][19] PROGMEM = {
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x0F, 0x4D, 0x59, 0x7A, 0xEA, 0x9F, 0xCC, 0x70, 0xED, 0xE5},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0x5C, 0x99, 0x54, 0x0F, 0x5C, 0xAD, 0x49, 0x8D, 0x7C, 0xB1, 0x6A, 0x7A, 0x96},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0x4C, 0xB8, 0x54, 0x0F, 0x28, 0xDD, 0xC9, 0x5B, 0xB2, 0x10, 0xE2, 0xBA, 0x9E},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x0F, 0x9D, 0x68, 0x92, 0x24, 0x92, 0x51, 0x4B, 0x55, 0x4A},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0x4C, 0xB8, 0x54, 0x0E, 0xA5, 0x58, 0x1A, 0xA0, 0x2A, 0x69, 0x09, 0xAD, 0x2A},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x08, 0xF3, 0x29, 0xE9, 0x77, 0x4D, 0x59, 0x5E, 0x6C, 0xF9},
  {0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0xC4, 0xA8, 0xD4, 0x0A, 0xA2, 0x7D, 0xA1, 0x74, 0x55, 0xAC, 0xFE, 0x56, 0x9F},
};
#define NUM_BIND_FRAMES 7

// ========================== STATE MACHINE ===================================

enum State {
  STATE_SAFE_IDLE,
  STATE_BIND,
  STATE_DATA_SAFE,
  STATE_ARMED,
  STATE_FAILSAFE
};

enum TxMode {
  MODE_BIND_REPLAY,       // Replay captured bind frames
  MODE_DATA_ONLY,         // Send data packets only (skip bind)
  MODE_BIND_THEN_DATA,    // Bind then data
  MODE_REPEATED_BIND_DATA // Alternate bind and data
};

static State state = STATE_SAFE_IDLE;
static TxMode tx_mode = MODE_BIND_THEN_DATA;
static bool armed = false;

// Channel hopping
static uint8_t ch_idx = 0;
static uint8_t ch_mode = 0;  // 0=hop all, 1=single 72, 2=single 76

// Payload (plaintext, before scramble)
static uint8_t payload[12] = {
  0x00, 0x00, 0x93,
  SAFE_THROTTLE, CENTER_YAW, CENTER_PITCH, CENTER_ROLL,
  DEFAULT_FLAGS1, DEFAULT_FLAGS2, DEFAULT_FLAGS3,
  0xAA, 0xAA
};

// PC-commanded values (only applied when armed)
static uint8_t cmd_throttle = SAFE_THROTTLE;
static uint8_t cmd_yaw = CENTER_YAW;
static uint8_t cmd_pitch = CENTER_PITCH;
static uint8_t cmd_roll = CENTER_ROLL;
static uint8_t cmd_flags1 = DEFAULT_FLAGS1;
static uint8_t cmd_flags2 = DEFAULT_FLAGS2;
static uint8_t cmd_flags3 = DEFAULT_FLAGS3;

// Timing
static uint32_t last_cmd_time = 0;
static uint32_t bind_start_time = 0;
static uint32_t last_packet_time = 0;
static uint32_t last_status_time = 0;
static uint32_t pkt_count = 0;
static uint8_t bind_frame_idx = 0;

// Serial input buffer
static char cmd_buf[64];
static uint8_t cmd_buf_pos = 0;

// ========================== UTILITY FUNCTIONS ===============================

uint8_t bit_reverse(uint8_t b) {
  b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4);
  b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2);
  b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1);
  return b;
}

uint16_t crc16_ccitt(const uint8_t* data, uint8_t len) {
  uint16_t crc = CRC_INIT;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t j = 0; j < 8; j++) {
      if (crc & 0x8000)
        crc = (crc << 1) ^ CRC_POLY;
      else
        crc = crc << 1;
    }
  }
  return crc ^ CRC_XOROUT;
}

// ========================== XN297 TX FUNCTIONS ==============================

// Send a raw 19-byte XN297 frame via nRF24
// raw[0..4]  = scrambled address
// raw[5..16] = scrambled payload
// raw[17..18] = CRC
void send_xn297_raw_frame(const uint8_t* raw) {
  // nRF24 address (on-air: 71 0F raw[0] raw[1] raw[2])
  // RF24 library byte order: {raw[2], raw[1], raw[0], 0x0F, 0x71}
  uint8_t nrf_addr[5] = {raw[2], raw[1], raw[0], 0x0F, 0x71};
  radio.openWritingPipe(nrf_addr);

  // nRF24 payload: raw[3..4] + raw[5..16] + raw[17..18] = 16 bytes
  uint8_t nrf_payload[16];
  memcpy(nrf_payload, &raw[3], 16);

  radio.writeFast(nrf_payload, 16);
}

// Build a 19-byte raw XN297 data frame from current payload
void build_data_raw_frame(uint8_t* raw19) {
  // Bytes 0-4: scrambled address
  memcpy(raw19, DATA_ADDR_SCRAMBLED, 5);

  // Bytes 5-16: scrambled payload
  for (uint8_t i = 0; i < 12; i++) {
    raw19[5 + i] = bit_reverse(payload[i]) ^ pgm_read_byte(&XN297_SCRAMBLE[5 + i]);
  }

  // Bytes 17-18: CRC over raw[0..16]
  uint16_t crc = crc16_ccitt(raw19, 17);
  raw19[17] = crc >> 8;
  raw19[18] = crc & 0xFF;
}

// Send one data packet with channel hop
void send_data_packet() {
  uint8_t raw[19];
  build_data_raw_frame(raw);

  // Hop channel
  advance_channel();
  radio.setChannel(RF_CHANNELS[ch_idx]);

  send_xn297_raw_frame(raw);
  pkt_count++;
}

// Send one captured bind frame with channel hop
void send_bind_packet() {
  uint8_t raw[19];
  for (uint8_t i = 0; i < 19; i++) {
    raw[i] = pgm_read_byte(&BIND_FRAMES[bind_frame_idx][i]);
  }
  bind_frame_idx = (bind_frame_idx + 1) % NUM_BIND_FRAMES;

  // Hop channel
  advance_channel();
  radio.setChannel(RF_CHANNELS[ch_idx]);

  send_xn297_raw_frame(raw);
  pkt_count++;
}

void advance_channel() {
  switch (ch_mode) {
    case 0: ch_idx = (ch_idx + 1) % NUM_CHANNELS; break;
    case 1: ch_idx = 0; break;  // CH72 only
    case 2: ch_idx = 4; break;  // CH76 only
    default: ch_idx = (ch_idx + 1) % NUM_CHANNELS; break;
  }
}

// ========================== FAILSAFE =======================================

void apply_failsafe() {
  payload[3] = SAFE_THROTTLE;
  payload[4] = CENTER_YAW;
  payload[5] = CENTER_PITCH;
  payload[6] = CENTER_ROLL;
  armed = false;
}

void apply_safe() {
  apply_failsafe();
  cmd_throttle = SAFE_THROTTLE;
  cmd_yaw = CENTER_YAW;
  cmd_pitch = CENTER_PITCH;
  cmd_roll = CENTER_ROLL;
}

// ========================== SERIAL COMMAND PARSER ===========================

void parse_serial_command(const char* cmd) {
  last_cmd_time = millis();

  if (strncmp(cmd, "STATUS", 6) == 0) {
    print_status();
  }
  else if (strncmp(cmd, "SAFE", 4) == 0) {
    apply_safe();
    state = STATE_SAFE_IDLE;
    Serial.println(F("OK SAFE"));
  }
  else if (strncmp(cmd, "BIND", 4) == 0) {
    start_bind();
    Serial.println(F("OK BIND started"));
  }
  else if (strncmp(cmd, "ARM ", 4) == 0) {
    int val = atoi(cmd + 4);
    if (val == 1) {
      armed = true;
      if (state == STATE_SAFE_IDLE || state == STATE_DATA_SAFE || state == STATE_FAILSAFE) {
        state = STATE_ARMED;
      }
      Serial.println(F("OK ARMED"));
    } else {
      armed = false;
      apply_failsafe();
      state = STATE_DATA_SAFE;
      Serial.println(F("OK DISARMED"));
    }
  }
  else if (strncmp(cmd, "SET ", 4) == 0) {
    // SET T Y P R — normalized values
    // T: 0..100 (throttle percent)
    // Y: -100..100 (yaw)
    // P: -100..100 (pitch)
    // R: -100..100 (roll)
    int t, y, p, r;
    if (sscanf(cmd + 4, "%d %d %d %d", &t, &y, &p, &r) == 4) {
      // Map throttle 0..100 → 0x00..0xFF
      cmd_throttle = constrain(t, 0, 100) * 255 / 100;
      // Map yaw -100..100 → 0x00..0xFF (center 0x05 is odd; use linear for now)
      cmd_yaw = map(constrain(y, -100, 100), -100, 100, 0, 255);
      // Map pitch -100..100 → 0x00..0xFF
      cmd_pitch = map(constrain(p, -100, 100), -100, 100, 0, 255);
      // Map roll -100..100 → 0x00..0xFF
      cmd_roll = map(constrain(r, -100, 100), -100, 100, 0, 255);

      if (armed && state == STATE_ARMED) {
        payload[3] = cmd_throttle;
        payload[4] = cmd_yaw;
        payload[5] = cmd_pitch;
        payload[6] = cmd_roll;
      }
      // No echo for SET to avoid serial flooding
    } else {
      Serial.println(F("ERR SET format: SET T Y P R"));
    }
  }
  else if (strncmp(cmd, "RAW ", 4) == 0) {
    // RAW t y p r f1 f2 f3 — raw protocol byte values
    unsigned int t, y, p, r, f1, f2, f3;
    if (sscanf(cmd + 4, "%u %u %u %u %u %u %u", &t, &y, &p, &r, &f1, &f2, &f3) == 7) {
      cmd_throttle = t & 0xFF;
      cmd_yaw = y & 0xFF;
      cmd_pitch = p & 0xFF;
      cmd_roll = r & 0xFF;
      cmd_flags1 = f1 & 0xFF;
      cmd_flags2 = f2 & 0xFF;
      cmd_flags3 = f3 & 0xFF;

      if (armed && state == STATE_ARMED) {
        payload[3] = cmd_throttle;
        payload[4] = cmd_yaw;
        payload[5] = cmd_pitch;
        payload[6] = cmd_roll;
        payload[7] = cmd_flags1;
        payload[8] = cmd_flags2;
        payload[9] = cmd_flags3;
      }
    } else {
      Serial.println(F("ERR RAW format: RAW t y p r f1 f2 f3"));
    }
  }
  else if (strncmp(cmd, "MODE ", 5) == 0) {
    const char* m = cmd + 5;
    if (strncmp(m, "BIND_REPLAY", 11) == 0) {
      tx_mode = MODE_BIND_REPLAY;
      Serial.println(F("OK MODE BIND_REPLAY"));
    } else if (strncmp(m, "DATA_ONLY", 9) == 0) {
      tx_mode = MODE_DATA_ONLY;
      Serial.println(F("OK MODE DATA_ONLY"));
    } else if (strncmp(m, "BIND_THEN_DATA", 14) == 0) {
      tx_mode = MODE_BIND_THEN_DATA;
      Serial.println(F("OK MODE BIND_THEN_DATA"));
    } else if (strncmp(m, "REPEATED", 8) == 0) {
      tx_mode = MODE_REPEATED_BIND_DATA;
      Serial.println(F("OK MODE REPEATED_BIND_DATA"));
    } else {
      Serial.println(F("ERR unknown mode"));
    }
  }
  else if (strncmp(cmd, "CH ", 3) == 0) {
    const char* c = cmd + 3;
    if (strncmp(c, "HOP", 3) == 0) {
      ch_mode = 0;
      Serial.println(F("OK CH HOP"));
    } else if (strncmp(c, "72", 2) == 0) {
      ch_mode = 1;
      Serial.println(F("OK CH 72"));
    } else if (strncmp(c, "76", 2) == 0) {
      ch_mode = 2;
      Serial.println(F("OK CH 76"));
    } else {
      Serial.println(F("ERR CH: HOP|72|76"));
    }
  }
  else {
    Serial.print(F("ERR unknown: "));
    Serial.println(cmd);
  }
}

void start_bind() {
  state = STATE_BIND;
  bind_start_time = millis();
  bind_frame_idx = 0;
  Serial.print(F("BIND for "));
  Serial.print(BIND_DURATION_MS / 1000);
  Serial.println(F("s..."));
}

void print_status() {
  Serial.print(F("STATE="));
  switch (state) {
    case STATE_SAFE_IDLE: Serial.print(F("SAFE_IDLE")); break;
    case STATE_BIND:      Serial.print(F("BIND")); break;
    case STATE_DATA_SAFE: Serial.print(F("DATA_SAFE")); break;
    case STATE_ARMED:     Serial.print(F("ARMED")); break;
    case STATE_FAILSAFE:  Serial.print(F("FAILSAFE")); break;
  }
  Serial.print(F(" ARM="));
  Serial.print(armed ? '1' : '0');
  Serial.print(F(" MODE="));
  switch (tx_mode) {
    case MODE_BIND_REPLAY:       Serial.print(F("BIND_REPLAY")); break;
    case MODE_DATA_ONLY:         Serial.print(F("DATA_ONLY")); break;
    case MODE_BIND_THEN_DATA:    Serial.print(F("BIND_THEN_DATA")); break;
    case MODE_REPEATED_BIND_DATA:Serial.print(F("REPEATED")); break;
  }
  Serial.print(F(" CH="));
  switch (ch_mode) {
    case 0: Serial.print(F("HOP")); break;
    case 1: Serial.print(F("72")); break;
    case 2: Serial.print(F("76")); break;
  }
  Serial.print(F(" T="));
  Serial.print(payload[3], HEX);
  Serial.print(F(" Y="));
  Serial.print(payload[4], HEX);
  Serial.print(F(" P="));
  Serial.print(payload[5], HEX);
  Serial.print(F(" R="));
  Serial.print(payload[6], HEX);
  Serial.print(F(" pps="));
  Serial.println(pkt_count);
  pkt_count = 0;
}

// ========================== SETUP ==========================================

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println(F("=== F8620 PC TX — XN297 Protocol ==="));
  Serial.println(F("*** REMOVE PROPELLERS BEFORE TESTING ***"));
  Serial.println(F("Serial: 115200 baud, newline-delimited"));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("ERROR: nRF24 not detected! Check wiring."));
    while (1) { delay(1000); }
  }
  if (!radio.isChipConnected()) {
    Serial.println(F("ERROR: nRF24 not responding on SPI!"));
    while (1) { delay(1000); }
  }

  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setRetries(0, 0);
  radio.setPALevel(RF24_PA_LOW);  // Start LOW for bench; use PA_MAX for range
  radio.setPayloadSize(16);
  radio.setAddressWidth(5);
  radio.openWritingPipe(NRF_DATA_ADDR);
  radio.stopListening();
  radio.setChannel(RF_CHANNELS[0]);

  Serial.println(F("Radio OK. PA=LOW. Channels 72-77."));
  Serial.println(F("Commands: STATUS SAFE BIND ARM SET RAW MODE CH"));
  Serial.println(F("State: SAFE_IDLE (no TX until BIND or MODE DATA_ONLY)"));
  Serial.println();

  last_cmd_time = millis();
  last_status_time = millis();
  state = STATE_SAFE_IDLE;
}

// ========================== MAIN LOOP ======================================

void loop() {
  uint32_t now = millis();

  // --- Read serial commands ---
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_buf_pos > 0) {
        cmd_buf[cmd_buf_pos] = '\0';
        parse_serial_command(cmd_buf);
        cmd_buf_pos = 0;
      }
    } else if (cmd_buf_pos < sizeof(cmd_buf) - 1) {
      cmd_buf[cmd_buf_pos++] = c;
    }
  }

  // --- Failsafe check ---
  if (state == STATE_ARMED && (now - last_cmd_time > FAILSAFE_TIMEOUT_MS)) {
    apply_failsafe();
    state = STATE_FAILSAFE;
    Serial.println(F("!!! FAILSAFE: no command for 250ms"));
  }

  // --- State machine ---
  switch (state) {
    case STATE_SAFE_IDLE:
      // Send safe data packets so drone sees us (helps maintain link)
      if (now - last_packet_time >= (PACKET_INTERVAL_US / 1000 + 1)) {
        payload[3] = SAFE_THROTTLE;
        payload[4] = CENTER_YAW;
        payload[5] = CENTER_PITCH;
        payload[6] = CENTER_ROLL;
        send_data_packet();
        last_packet_time = now;
      }
      break;

    case STATE_BIND:
      // Send bind packets for BIND_DURATION_MS
      if (now - bind_start_time < BIND_DURATION_MS) {
        if (now - last_packet_time >= (PACKET_INTERVAL_US / 1000 + 1)) {
          send_bind_packet();
          last_packet_time = now;
        }
      } else {
        // Bind done, transition to data
        Serial.println(F("BIND complete → DATA_SAFE"));
        state = STATE_DATA_SAFE;
      }
      break;

    case STATE_DATA_SAFE:
      // Send safe data packets
      if (now - last_packet_time >= (PACKET_INTERVAL_US / 1000 + 1)) {
        payload[3] = SAFE_THROTTLE;
        payload[4] = CENTER_YAW;
        payload[5] = CENTER_PITCH;
        payload[6] = CENTER_ROLL;
        send_data_packet();
        last_packet_time = now;
      }
      break;

    case STATE_ARMED:
      // Send PC-commanded data packets
      if (now - last_packet_time >= (PACKET_INTERVAL_US / 1000 + 1)) {
        payload[3] = cmd_throttle;
        payload[4] = cmd_yaw;
        payload[5] = cmd_pitch;
        payload[6] = cmd_roll;
        payload[7] = cmd_flags1;
        payload[8] = cmd_flags2;
        payload[9] = cmd_flags3;
        send_data_packet();
        last_packet_time = now;
      }
      break;

    case STATE_FAILSAFE:
      // Keep sending safe packets
      if (now - last_packet_time >= (PACKET_INTERVAL_US / 1000 + 1)) {
        payload[3] = SAFE_THROTTLE;
        payload[4] = CENTER_YAW;
        payload[5] = CENTER_PITCH;
        payload[6] = CENTER_ROLL;
        send_data_packet();
        last_packet_time = now;
      }
      // Allow recovery via new command (last_cmd_time updates on any command)
      if (now - last_cmd_time < FAILSAFE_TIMEOUT_MS) {
        state = STATE_DATA_SAFE;
        Serial.println(F("FAILSAFE cleared → DATA_SAFE"));
      }
      break;
  }

  // --- Periodic status ---
  if (now - last_status_time > 2000) {
    print_status();
    last_status_time = now;
  }
}
