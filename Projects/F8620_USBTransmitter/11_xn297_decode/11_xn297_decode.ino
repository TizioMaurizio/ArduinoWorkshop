// ============================================================================
// F8620 USB Transmitter — XN297 Protocol Decoder
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Receive XN297 packets with CRC DISABLED on nRF24, then verify
//          XN297 CRC in software. This is the correct approach because
//          XN297 CRC (CRC-16/CCITT) ≠ nRF24 CRC.
//
// KEY INSIGHT: Previous sketch 07 failed because it used nRF24 CRC which
//          is incompatible with XN297 CRC. The correct method is:
//          1. Disable nRF24 CRC
//          2. Set address to XN297 scrambled address
//          3. Read payload + 2 CRC bytes
//          4. Descramble payload
//          5. Verify CRC-16/CCITT over descrambled data
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t target_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

// XN297 scramble tables
static const uint8_t xn297_scramble_data[] = {
  0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
  0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
  0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
  0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F
};

// XN297 CRC-16/CCITT (poly 0x1021, init depends on address)
static uint16_t xn297_crc16(uint8_t* data, uint8_t len, uint16_t init) {
  uint16_t crc = init;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= ((uint16_t)data[i]) << 8;
    for (uint8_t j = 0; j < 8; j++) {
      if (crc & 0x8000)
        crc = (crc << 1) ^ 0x1021;
      else
        crc = crc << 1;
    }
  }
  return crc;
}

// Bit reverse a byte
static uint8_t bit_reverse(uint8_t b) {
  b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4);
  b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2);
  b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1);
  return b;
}

// Addresses to try (what appears on air for XN297)
// Format: the actual bytes transmitted over the air by XN297
struct XN297Addr {
  uint8_t addr[5];
  uint8_t width;
  uint16_t crc_init;  // CRC initial value (derived from address)
  const char* label;
};

// CRC init is computed from the address bytes (non-scrambled, non-reversed)
// For zero address: crc_init from {0,0,0,0,0} → 0
// But XN297 CRC includes address in the CRC calculation
// CRC init = CRC16 of the address bytes with init=0x3443 (or other depending on variant)
static const XN297Addr xn297_addrs[] = {
  // XN297 address {0,0,0,0,0}: on-air = scramble = {E3,B1,4B,EA,85}
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, 5, 0x3443, "XN-Zero-5"},
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, 5, 0x0000, "XN-Zero-5-i0"},
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, 5, 0xFFFF, "XN-Zero-5-iF"},
  
  // Same but 4-byte address
  {{0xE3, 0xB1, 0x4B, 0xEA}, 4, 0x3443, "XN-Zero-4"},
  {{0xE3, 0xB1, 0x4B, 0xEA}, 4, 0x0000, "XN-Zero-4-i0"},
  
  // Bit-reversed version (some XN297 implementations are LSBit first)
  {{0xC7, 0x8D, 0xD2, 0x57, 0xA1}, 5, 0x3443, "XN-Zero-R5"},
  {{0xC7, 0x8D, 0xD2, 0x57, 0xA1}, 5, 0x0000, "XN-Zero-R5-i0"},
  
  // XN297 address {0xC4,0xC4,0xC4,0xC4,0xC4} (H8/common)
  // on-air = {C4^E3, C4^B1, C4^4B, C4^EA, C4^85} = {27,75,8F,2E,41}
  {{0x27, 0x75, 0x8F, 0x2E, 0x41}, 5, 0x3443, "XN-C4-5"},
  {{0x27, 0x75, 0x8F, 0x2E, 0x41}, 5, 0x0000, "XN-C4-5-i0"},
  
  // Some protocols use specific init values
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, 5, 0xB5D2, "XN-Zero-5-iB"},
  
  // Also try the statistical finding: e21eab appeared 90 times
  {{0xE2, 0x1E, 0xAB, 0x00, 0x00}, 3, 0x0000, "STAT-E21EAB"},
  {{0xE2, 0x1E, 0xAB, 0x00, 0x00}, 3, 0x3443, "STAT-E21EAB-i3"},
};
static const uint8_t NUM_ADDRS = sizeof(xn297_addrs) / sizeof(xn297_addrs[0]);

// State
static uint8_t addr_idx = 0;
static uint32_t config_start_ms = 0;
static const uint32_t DWELL_MS = 2000;
static uint32_t total_tested = 0;
static uint32_t crc_matches = 0;

// Payload sizes to try (payload + 2 CRC bytes)
// Common sizes: 10+2=12, 12+2=14, 15+2=17
static const uint8_t payload_sizes[] = {10, 12, 15, 16, 8, 20};
static const uint8_t NUM_SIZES = 6;

void apply_config() {
  radio.stopListening();
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);  // CRITICAL: no nRF24 CRC
  radio.setAutoAck(false);
  radio.setPayloadSize(32);  // max, to capture payload + CRC
  radio.setAddressWidth(xn297_addrs[addr_idx].width);
  radio.openReadingPipe(0, xn297_addrs[addr_idx].addr);
  radio.setChannel(target_channels[0]);
  radio.startListening();
  config_start_ms = millis();
}

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

bool check_xn297_crc(uint8_t* raw, uint8_t payload_len, uint16_t init) {
  // Descramble the data first
  uint8_t descrambled[32];
  uint8_t total_len = payload_len + 2;  // payload + 2 CRC bytes
  
  for (uint8_t i = 0; i < total_len; i++) {
    descrambled[i] = raw[i] ^ xn297_scramble_data[i];
  }
  
  // CRC is over the descrambled payload
  uint16_t calc_crc = xn297_crc16(descrambled, payload_len, init);
  
  // Compare with received CRC (big-endian in packet)
  uint16_t rx_crc = ((uint16_t)descrambled[payload_len] << 8) | descrambled[payload_len + 1];
  
  return calc_crc == rx_crc;
}

void print_match(uint8_t* raw, uint8_t payload_len, uint8_t channel) {
  crc_matches++;
  
  Serial.println(F("\n**** XN297 CRC MATCH! ****"));
  Serial.print(F("Addr: "));
  Serial.print(xn297_addrs[addr_idx].label);
  Serial.print(F(" | CH: "));
  Serial.print(channel);
  Serial.print(F(" | PayloadLen: "));
  Serial.println(payload_len);
  
  Serial.print(F("Raw (scrambled): "));
  for (uint8_t i = 0; i < payload_len + 2; i++) {
    print_hex(raw[i]);
    Serial.print(' ');
  }
  Serial.println();
  
  // Descramble and print
  Serial.print(F("Descrambled:     "));
  for (uint8_t i = 0; i < payload_len + 2; i++) {
    print_hex(raw[i] ^ xn297_scramble_data[i]);
    Serial.print(' ');
  }
  Serial.println();
  Serial.println(F("****************************\n"));
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println(F("=== F8620 XN297 Decoder ==="));
  Serial.println(F("CRC DISABLED on nRF24 — software XN297 CRC verification"));
  Serial.println(F("Trying XN297 scrambled addresses on CH 72-77"));
  Serial.println(F("Turn ON the F8620 transmitter."));
  Serial.println();
  
  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }
  
  Serial.print(F("Configs: "));
  Serial.print(NUM_ADDRS);
  Serial.print(F(" addrs x "));
  Serial.print(NUM_SIZES);
  Serial.print(F(" sizes = "));
  Serial.println((uint16_t)(NUM_ADDRS * NUM_SIZES));
  Serial.println(F("Listening..."));
  
  apply_config();
}

void loop() {
  // Channel hopping
  static uint8_t ch_idx = 0;
  static uint32_t last_hop = 0;
  
  if (millis() - last_hop > 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(target_channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }
  
  // Check for data
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    total_tested++;
    
    // Try each payload size for XN297 CRC verification
    for (uint8_t s = 0; s < NUM_SIZES; s++) {
      uint8_t plen = payload_sizes[s];
      if (plen + 2 > 32) continue;
      
      if (check_xn297_crc(buf, plen, xn297_addrs[addr_idx].crc_init)) {
        print_match(buf, plen, target_channels[ch_idx]);
      }
    }
  }
  
  // Advance address config
  if (millis() - config_start_ms > DWELL_MS) {
    addr_idx = (addr_idx + 1) % NUM_ADDRS;
    
    if (addr_idx == 0) {
      Serial.print(F("\n[Cycle done. Tested: "));
      Serial.print(total_tested);
      Serial.print(F(" pkts, CRC matches: "));
      Serial.print(crc_matches);
      Serial.println(F("]\n"));
    }
    
    Serial.print(F("."));
    if (addr_idx % 6 == 0) {
      Serial.print(F(" "));
      Serial.print(xn297_addrs[addr_idx].label);
    }
    
    apply_config();
  }
}
