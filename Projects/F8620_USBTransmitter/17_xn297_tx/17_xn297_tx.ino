// ============================================================================
// F8620 USB Transmitter — XN297 Protocol Implementation
//
// Protocol decoded by RF analysis:
//   - XN297 compatible (scrambled)
//   - 5-byte address: {54, 29, 93, B2, 6A}
//   - 12-byte payload
//   - CRC-16/CCITT (poly=0x1021, init=0x0000, xorout=0x4358)
//   - Channels: 72-77 (hop)
//   - Data rate: 1 Mbps
//
// nRF24 emulation approach:
//   - nRF24 address (5 bytes) = XN297 preamble extension + first 3 addr bytes
//   - nRF24 payload = last 2 addr bytes + scrambled payload + CRC
//   - nRF24 CRC disabled (we compute our own)
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// XN297 scramble table (38 bytes needed for 5 addr + 12 payload + some margin)
static const uint8_t xn297_scramble[] PROGMEM = {
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC
};

// Scrambled address (on-air bytes): addr XOR scramble[0:5]
// Real address: {54, 29, 93, B2, 6A}
static const uint8_t ADDR_SCRAMBLED[] = {0xB7, 0x98, 0xD8, 0x58, 0xEF};

// nRF24 TX address: XN297 preamble ext (71 0F) + first 3 scrambled addr bytes
// On-air order: 71 0F B7 98 D8
// RF24 library byte order (LSByte = first on-air): reversed
static const uint8_t NRF_TX_ADDR[] = {0xD8, 0x98, 0xB7, 0x0F, 0x71};

// Channels to hop through
static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;
static uint8_t ch_idx = 0;

// Payload structure (descrambled)
// [0-1]  Header: 00 00
// [2]    Mode: 93
// [3]    Throttle (center ~F0)
// [4]    Yaw (center ~05)
// [5]    Pitch (center ~39)
// [6]    Roll (center ~39)
// [7]    Flags1: 00
// [8]    Flags2: 40
// [9]    Flags3: 00
// [10-11] Padding: AA AA
static uint8_t payload[12] = {0x00, 0x00, 0x93, 0xF0, 0x05, 0x39, 0x39, 0x00, 0x40, 0x00, 0xAA, 0xAA};

// CRC-16/CCITT parameters
#define CRC_INIT  0x0000
#define CRC_POLY  0x1021
#define CRC_XOROUT 0x4358

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

// Build the scrambled packet for transmission
// Returns total bytes written to tx_buf (should be 16: 2 addr + 12 payload + 2 CRC)
uint8_t build_packet(uint8_t* tx_buf) {
  // CRC is computed over full scrambled address (5) + scrambled payload (12) = 17 bytes
  uint8_t crc_data[17];
  
  // Copy scrambled address (5 bytes)
  memcpy(crc_data, ADDR_SCRAMBLED, 5);
  
  // Scramble payload: bit_reverse(payload[i]) XOR scramble[5+i]
  for (uint8_t i = 0; i < 12; i++) {
    crc_data[5 + i] = bit_reverse(payload[i]) ^ pgm_read_byte(&xn297_scramble[5 + i]);
  }
  
  // Compute CRC over all 17 raw bytes
  uint16_t crc = crc16_ccitt(crc_data, 17);
  
  // Build nRF24 payload:
  // [0-1] = last 2 scrambled address bytes (58 EF)
  // [2-13] = scrambled payload (12 bytes)
  // [14-15] = CRC (2 bytes, big-endian)
  tx_buf[0] = ADDR_SCRAMBLED[3];  // 0x58
  tx_buf[1] = ADDR_SCRAMBLED[4];  // 0xEF
  memcpy(&tx_buf[2], &crc_data[5], 12);  // scrambled payload
  tx_buf[14] = crc >> 8;     // CRC high byte
  tx_buf[15] = crc & 0xFF;   // CRC low byte
  
  return 16;
}

// Packet send counter
static uint32_t pkt_count = 0;
static uint32_t last_report = 0;

void setup() {
  Serial.begin(1000000);
  delay(500);
  
  Serial.println(F("=== F8620 XN297 TRANSMITTER ==="));
  Serial.println(F("Protocol: XN297 scrambled, CRC-CCITT"));
  Serial.println(F("Address: 54 29 93 B2 6A"));
  Serial.println(F("Channels: 72-77 (hop)"));
  Serial.println(F("Payload: 12 bytes"));
  
  if (!radio.begin()) {
    Serial.println(F("RADIO FAIL"));
    while (1) {}
  }
  
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setRetries(0, 0);
  radio.setPALevel(RF24_PA_MAX);
  radio.setPayloadSize(16);
  radio.setAddressWidth(5);
  
  // Set TX address (XN297 preamble ext + first 3 addr bytes)
  radio.openWritingPipe(NRF_TX_ADDR);
  radio.stopListening();
  radio.setChannel(channels[0]);
  
  Serial.println(F("Radio configured. Transmitting..."));
  Serial.println(F("Commands: T=throttle up, t=throttle down, L/R/F/B=roll/pitch"));
  Serial.println(F("          0=all center, 9=max throttle"));
  
  last_report = millis();
}

void loop() {
  // Channel hopping: switch channel every packet (or every few packets)
  ch_idx = (ch_idx + 1) % NUM_CH;
  radio.setChannel(channels[ch_idx]);
  
  // Build and send packet
  uint8_t tx_buf[16];
  build_packet(tx_buf);
  radio.writeFast(tx_buf, 16);
  pkt_count++;
  
  // Handle serial commands for joystick control
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'T': payload[3] = min(255, payload[3] + 10); break;  // throttle up
      case 't': payload[3] = max(0, payload[3] - 10); break;    // throttle down
      case '0': payload[3] = 0x00; payload[4] = 0x39; payload[5] = 0x39; payload[6] = 0x39; break; // zero throttle, center axes
      case '5': payload[3] = 0x80; break;  // half throttle
      case '9': payload[3] = 0xFF; break;  // max throttle
      case 'c': payload[3] = 0xF0; payload[4] = 0x05; payload[5] = 0x39; payload[6] = 0x39; break; // original center values
      case 'R': payload[6] = min(255, payload[6] + 5); break;   // roll right
      case 'L': payload[6] = max(0, payload[6] - 5); break;     // roll left
      case 'F': payload[5] = min(255, payload[5] + 5); break;   // pitch forward
      case 'B': payload[5] = max(0, payload[5] - 5); break;     // pitch back
      case '>': payload[4] = min(255, payload[4] + 5); break;   // yaw right
      case '<': payload[4] = max(0, payload[4] - 5); break;     // yaw left
      case '?':
        Serial.print(F("Thr="));
        Serial.print(payload[3], HEX);
        Serial.print(F(" Yaw="));
        Serial.print(payload[4], HEX);
        Serial.print(F(" Pit="));
        Serial.print(payload[5], HEX);
        Serial.print(F(" Rol="));
        Serial.println(payload[6], HEX);
        break;
    }
  }
  
  // Report every 2 seconds
  if (millis() - last_report > 2000) {
    Serial.print(F("TX: "));
    Serial.print(pkt_count);
    Serial.print(F(" pkts, CH"));
    Serial.print(channels[ch_idx]);
    Serial.print(F(" T="));
    Serial.println(payload[3], HEX);
    last_report = millis();
    pkt_count = 0;
  }
  
  // ~250 packets/second per channel = total ~1500 pps across 6 channels
  // Typical toy TX sends ~100-250 pps
  delayMicroseconds(800);  // ~1250 pps total
}
