// ============================================================================
// F8620 — XN297 Protocol Dump (based on Pascallanger multi-protocol technique)
//
// Uses the XN297 preamble as nRF24 RX address to capture raw XN297 packets,
// then verifies CRC in software to find valid packets and extract the real
// address + payload.
//
// Key insight: nRF24 address = {0x55, 0x0F, 0x71} matches XN297's preamble,
// so everything received after that is the XN297's address + payload + CRC.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// XN297 scramble table
static const uint8_t xn297_scramble[] PROGMEM = {
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
    0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F,
    0x8E, 0xC5, 0x2F, 0xAA, 0x16, 0xF3, 0x95
};

// CRC XOR-out tables (scrambled and unscrambled, standard mode)
// Index = addr_len - 3 + payload_len
static const uint16_t xn297_crc_xorout_scrambled[] PROGMEM = {
    0x0000, 0x3448, 0x9BA7, 0x8BBB, 0x85E1, 0x3E8C,
    0x451E, 0x18E6, 0x6B24, 0xE7AB, 0x3828, 0x814B,
    0xD461, 0xF494, 0x2503, 0x691D, 0xFE8B, 0x9BA7,
    0x8B17, 0x2920, 0x8B5F, 0x61B1, 0xD391, 0x7401,
    0x2138, 0x129F, 0xB3A0, 0x2988, 0x23CA, 0xC0CB,
    0x0C6C, 0xB329, 0xA0A1, 0x0A16, 0xA9D0
};

static const uint16_t xn297_crc_xorout[] PROGMEM = {
    0x0000, 0x3D5F, 0xA6F1, 0x3A23, 0xAA16, 0x1CAF,
    0x62B2, 0xE0EB, 0x0821, 0xBE07, 0x5F1A, 0xAF15,
    0x4F0A, 0xAD24, 0x5E48, 0xED34, 0x068C, 0xF2C9,
    0x1852, 0xDF36, 0x129D, 0xB17C, 0xD5F5, 0x70D7,
    0xB798, 0x5133, 0x67DB, 0xD94E, 0x0A5B, 0xE445,
    0xE6A5, 0x26E7, 0xBDAB, 0xC379, 0x8E20
};

static uint16_t crc;

void crc16_update(uint8_t val, uint8_t bits) {
  crc ^= ((uint16_t)val) << 8;
  while (bits--) {
    if (crc & 0x8000)
      crc = (crc << 1) ^ 0x8005;
    else
      crc = crc << 1;
  }
}

uint8_t bit_reverse(uint8_t b) {
  b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4);
  b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2);
  b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1);
  return b;
}

// Try to decode an XN297 packet from raw received bytes
// Returns true if valid CRC found, fills addr_out, payload_out, etc.
bool xn297_decode(uint8_t* raw, uint8_t raw_len,
                  uint8_t* addr_out, uint8_t* addr_len_out,
                  uint8_t* payload_out, uint8_t* payload_len_out,
                  bool* scrambled_out) {
  
  // Try address lengths 3, 4, 5
  for (uint8_t addr_len = 3; addr_len <= 5; addr_len++) {
    // CRC initial value
    crc = 0xB5D2;
    
    // Process address bytes into CRC
    for (uint8_t i = 0; i < addr_len; i++) {
      crc16_update(raw[i], 8);
    }
    
    // Now try each possible payload length
    uint16_t crc_after_addr = crc;
    
    for (uint8_t pay_len = 1; pay_len <= raw_len - addr_len - 2; pay_len++) {
      // Update CRC with this payload byte
      crc16_update(raw[addr_len + pay_len - 1], 8);
      
      // Check if next 2 bytes match CRC XOR'd with xorout
      uint8_t xorout_idx = addr_len - 3 + pay_len;
      if (xorout_idx >= 35) break;  // table limit
      
      uint16_t crc_check;
      uint16_t received_crc = ((uint16_t)raw[addr_len + pay_len] << 8) | raw[addr_len + pay_len + 1];
      
      // Try unscrambled
      crc_check = crc ^ pgm_read_word(&xn297_crc_xorout[xorout_idx]);
      if (crc_check == received_crc) {
        *addr_len_out = addr_len;
        *payload_len_out = pay_len;
        *scrambled_out = false;
        // Address: reverse byte order
        for (uint8_t i = 0; i < addr_len; i++)
          addr_out[i] = raw[addr_len - 1 - i];
        // Payload: bit-reverse each byte
        for (uint8_t i = 0; i < pay_len; i++)
          payload_out[i] = bit_reverse(raw[addr_len + i]);
        return true;
      }
      
      // Try scrambled
      crc_check = crc ^ pgm_read_word(&xn297_crc_xorout_scrambled[xorout_idx]);
      if (crc_check == received_crc) {
        *addr_len_out = addr_len;
        *payload_len_out = pay_len;
        *scrambled_out = true;
        // Address: reverse byte order, XOR with scramble
        for (uint8_t i = 0; i < addr_len; i++)
          addr_out[i] = raw[addr_len - 1 - i] ^ pgm_read_byte(&xn297_scramble[i]);
        // Payload: XOR with scramble then bit-reverse
        for (uint8_t i = 0; i < pay_len; i++)
          payload_out[i] = bit_reverse(raw[addr_len + i] ^ pgm_read_byte(&xn297_scramble[addr_len + i]));
        return true;
      }
    }
  }
  return false;
}

static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;
static uint8_t ch_idx = 0;
static uint32_t pkt_count = 0;
static uint32_t valid_count = 0;

// Alternate between XN297 preamble and AA*5 to verify signal present
static uint8_t mode = 0;  // 0=XN297 preamble1, 1=XN297 preamble2, 2=AA*5 verify

void set_rx_mode(uint8_t m) {
  radio.stopListening();
  switch (m) {
    case 0:  // XN297 preamble variant 1 (addr MSBit=0)
      radio.setAddressWidth(3);
      { uint8_t a[] = {0x55, 0x0F, 0x71}; radio.openReadingPipe(0, a); }
      break;
    case 1:  // XN297 preamble variant 2 (addr MSBit=1)
      radio.setAddressWidth(3);
      { uint8_t a[] = {0xAA, 0xF0, 0x8E}; radio.openReadingPipe(0, a); }
      break;
    case 2:  // Standard AA*5 (verify signal present)
      radio.setAddressWidth(5);
      { uint8_t a[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA}; radio.openReadingPipe(0, a); }
      break;
  }
  radio.startListening();
}

void setup() {
  Serial.begin(1000000);
  delay(500);
  
  Serial.println(F("=== XN297 PROTOCOL DUMP v2 ==="));
  Serial.println(F("Scanning CH72-77, cycling address modes"));
  Serial.println(F("Mode 0: XN297 preamble {55 0F 71}"));
  Serial.println(F("Mode 1: XN297 preamble {AA F0 8E}"));
  Serial.println(F("Mode 2: Standard AA*5 (signal check)"));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) {}
  }
  
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setChannel(channels[0]);
  
  set_rx_mode(0);
  Serial.println(F("LISTENING... (TX must be ON)"));
}

void loop() {
  // Channel hopping: 2ms per channel
  static uint32_t last_hop = 0;
  if (millis() - last_hop > 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }
  
  // Switch RX mode every 3 seconds
  static uint32_t last_mode_switch = 0;
  static uint32_t mode_pkt_count = 0;
  if (millis() - last_mode_switch > 3000) {
    Serial.print(F("\n[Mode "));
    Serial.print(mode);
    Serial.print(F(" got "));
    Serial.print(mode_pkt_count);
    Serial.println(F(" raw pkts]"));
    
    mode = (mode + 1) % 3;
    set_rx_mode(mode);
    mode_pkt_count = 0;
    last_mode_switch = millis();
    
    Serial.print(F("Switching to mode "));
    Serial.println(mode);
  }
  
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t raw[32];
    radio.read(raw, 32);
    pkt_count++;
    mode_pkt_count++;
    
    // Only try XN297 decode in modes 0 and 1
    if (mode < 2) {
      uint8_t addr[5], payload[32];
      uint8_t addr_len, payload_len;
      bool scrambled;
      
      if (xn297_decode(raw, 32, addr, &addr_len, payload, &payload_len, &scrambled)) {
        valid_count++;
        
        Serial.print(F("*** FOUND! M="));
        Serial.print(mode);
        Serial.print(F(" CH="));
        Serial.print(channels[ch_idx]);
        Serial.print(F(" S="));
        Serial.print(scrambled ? 'Y' : 'N');
        Serial.print(F(" A("));
        Serial.print(addr_len);
        Serial.print(F(")="));
        for (uint8_t i = 0; i < addr_len; i++) {
          if (addr[i] < 0x10) Serial.print('0');
          Serial.print(addr[i], HEX);
          if (i < addr_len - 1) Serial.print(' ');
        }
        Serial.print(F(" P("));
        Serial.print(payload_len);
        Serial.print(F(")="));
        for (uint8_t i = 0; i < payload_len && i < 16; i++) {
          if (payload[i] < 0x10) Serial.print('0');
          Serial.print(payload[i], HEX);
          if (i < payload_len - 1 && i < 15) Serial.print(' ');
        }
        Serial.println(F(" ***"));
      } else if (mode_pkt_count <= 5) {
        // Dump raw bytes for first 5 packets (debug)
        Serial.print(F("RAW M"));
        Serial.print(mode);
        Serial.print(F(": "));
        for (uint8_t i = 0; i < 20; i++) {
          if (raw[i] < 0x10) Serial.print('0');
          Serial.print(raw[i], HEX);
          Serial.print(' ');
        }
        Serial.println();
      }
    } else {
      // Mode 2: just report raw first bytes as signal check
      if (mode_pkt_count <= 3) {
        Serial.print(F("SIG: "));
        for (uint8_t i = 0; i < 8; i++) {
          if (raw[i] < 0x10) Serial.print('0');
          Serial.print(raw[i], HEX);
          Serial.print(' ');
        }
        Serial.println();
      }
    }
    
    // Status every 2000 packets
    if (pkt_count % 2000 == 0) {
      Serial.print(F("Total: "));
      Serial.print(pkt_count);
      Serial.print(F(" raw, "));
      Serial.print(valid_count);
      Serial.println(F(" valid XN297"));
    }
  }
}
