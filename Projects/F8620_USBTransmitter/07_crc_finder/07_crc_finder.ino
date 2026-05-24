// ============================================================================
// F8620 USB Transmitter — CRC-Filtered Address Finder
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Find the correct RX address by enabling CRC16 (noise rejection)
//          and cycling through candidate addresses on channels 72-77.
//          ANY packet that passes CRC is almost certainly genuine.
//
// APPROACH:
//   - CRC16 = 99.998% noise rejection
//   - Try 3-byte, 4-byte, and 5-byte address widths
//   - Try 1Mbps and 250kbps
//   - Cycle all 6 target channels per config
//   - Report immediately if CRC-valid packet received
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// Target channels identified by scanner
static const uint8_t target_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_TARGET_CH = 6;

// XN297 scramble table for address
static const uint8_t xn297_scramble[] = {0xE3, 0xB1, 0x4B, 0xEA, 0x85};

// Bit reversal lookup
static uint8_t bit_reverse(uint8_t b) {
  b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4);
  b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2);
  b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1);
  return b;
}

// Candidate addresses (5 bytes each, will be truncated for shorter widths)
// Format: {byte0, byte1, byte2, byte3, byte4}
struct AddrCandidate {
  uint8_t addr[5];
  const char* label;
};

// Both native nRF24 addresses AND XN297-scrambled equivalents
static const AddrCandidate candidates[] = {
  // --- Native nRF24 addresses (if drone uses nRF24 directly) ---
  {{0xCC, 0xCC, 0xCC, 0xCC, 0xCC}, "nRF-CC"},     // CX10/derivatives
  {{0xC4, 0xC4, 0xC4, 0xC4, 0xC4}, "nRF-C4"},     // H8 mini
  {{0xAA, 0xAA, 0xAA, 0xAA, 0xAA}, "nRF-AA"},     // preamble continuation
  {{0x55, 0x55, 0x55, 0x55, 0x55}, "nRF-55"},      // preamble continuation
  {{0xA1, 0xA1, 0xA1, 0xA1, 0xA1}, "nRF-A1"},     // some Syma variants
  {{0x3B, 0xB6, 0x00, 0x00, 0xA2}, "nRF-3B"},     // Eachine
  {{0x66, 0x88, 0x68, 0x68, 0x68}, "nRF-66"},     // MJX
  {{0x32, 0xAA, 0x45, 0x45, 0x78}, "nRF-32"},     // FQ777
  {{0x12, 0x34, 0x56, 0x78, 0x9A}, "nRF-12"},     // common test
  
  // --- XN297 scrambled addresses (real_addr XOR scramble, bit-reversed) ---
  // XN297 addr={0,0,0,0,0} → scrambled on air = {E3,B1,4B,EA,85}
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, "X-Zero"},
  // XN297 addr={0,0,0,0,0} bit-reversed then XOR → {C7,8D,D2,57,A1}
  {{0xC7, 0x8D, 0xD2, 0x57, 0xA1}, "X-Zero-R"},
  // XN297 addr={C4,C4,C4,C4,C4} → XOR scramble = {27,75,8F,2E,41}
  {{0x27, 0x75, 0x8F, 0x2E, 0x41}, "X-C4"},
  // XN297 addr={C4,C4,C4,C4,C4} bit-rev first = {23,23,23,23,23} XOR = {C0,92,68,C9,A6}
  {{0xC0, 0x92, 0x68, 0xC9, 0xA6}, "X-C4-R"},
  // Common Bayang bind (sometimes reversed)
  {{0xA8, 0x2D, 0x48, 0x00, 0x85}, "X-Bay-B"},
  // Eachine E010/E011 specific
  {{0x73, 0x73, 0x73, 0x73, 0x73}, "nRF-73"},
  {{0x90, 0xC2, 0x38, 0x99, 0xF6}, "X-73"},
  // JJRC H36 / Eachine E010 (common cheap quads)
  {{0x4B, 0x4B, 0x4B, 0x4B, 0x4B}, "nRF-4B"},
  {{0xA8, 0xFA, 0x00, 0xA1, 0xCE}, "X-4B"},
};
static const uint8_t NUM_CANDIDATES = sizeof(candidates) / sizeof(candidates[0]);

// State machine
static uint8_t cand_idx = 0;
static uint8_t rate_idx = 0;        // 0=1Mbps, 1=250kbps
static uint8_t addr_width_idx = 0;  // 0=5byte, 1=4byte, 2=3byte
static uint32_t config_start_ms = 0;
static const uint32_t DWELL_MS = 500;  // 500ms per config (fast cycling)
static uint32_t total_configs_tried = 0;
static uint32_t packets_found = 0;

static const rf24_datarate_e rates[] = {RF24_1MBPS, RF24_250KBPS};
static const char* rate_names[] = {"1M", "250k"};
static const uint8_t addr_widths[] = {5, 4, 3};

void apply_config() {
  radio.stopListening();
  
  uint8_t width = addr_widths[addr_width_idx];
  radio.setAddressWidth(width);
  radio.setDataRate(rates[rate_idx]);
  radio.setCRCLength(RF24_CRC_16);  // KEY: strong noise filter
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  
  // Apply address (use first 'width' bytes)
  radio.openReadingPipe(0, candidates[cand_idx].addr);
  radio.setChannel(target_channels[0]);
  radio.startListening();
  
  config_start_ms = millis();
  total_configs_tried++;
}

void advance_config() {
  cand_idx++;
  if (cand_idx >= NUM_CANDIDATES) {
    cand_idx = 0;
    rate_idx++;
    if (rate_idx >= 2) {
      rate_idx = 0;
      addr_width_idx++;
      if (addr_width_idx >= 3) {
        addr_width_idx = 0;
        Serial.println(F("\n=== Full cycle complete. Restarting... ==="));
        Serial.print(F("Configs tried: "));
        Serial.print(total_configs_tried);
        Serial.print(F(" | Packets found: "));
        Serial.println(packets_found);
      }
    }
  }
  apply_config();
  
  // Progress indicator every 10 configs
  if (total_configs_tried % 10 == 0) {
    Serial.print('.');
  }
}

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println(F("=== F8620 CRC-Filtered Address Finder ==="));
  Serial.println(F("Channels: 72-77 | CRC16 enabled (noise rejection)"));
  Serial.println(F("Any packet that passes CRC = REAL SIGNAL"));
  Serial.println(F("Turn ON the F8620 transmitter now."));
  Serial.println();
  
  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }
  
  Serial.println(F("nRF24 OK. Scanning addresses..."));
  Serial.print(F("Candidates: "));
  Serial.print(NUM_CANDIDATES);
  Serial.print(F(" x 2 rates x 3 widths = "));
  Serial.print((uint16_t)(NUM_CANDIDATES * 2 * 3));
  Serial.println(F(" configs"));
  Serial.println(F("Each config: 500ms dwell, hopping 72-77"));
  Serial.println();
  
  apply_config();
}

void loop() {
  // Fast channel hopping within current config
  static uint8_t ch_idx = 0;
  static uint32_t last_hop = 0;
  
  if (millis() - last_hop > 2) {  // hop every 2ms
    ch_idx = (ch_idx + 1) % NUM_TARGET_CH;
    radio.stopListening();
    radio.setChannel(target_channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }
  
  // Check for CRC-valid packets
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    packets_found++;
    
    Serial.println(F("\n\n**** CRC-VALID PACKET FOUND! ****"));
    Serial.print(F("Address: "));
    Serial.print(candidates[cand_idx].label);
    Serial.print(F(" ["));
    uint8_t w = addr_widths[addr_width_idx];
    for (uint8_t i = 0; i < w; i++) {
      print_hex(candidates[cand_idx].addr[i]);
      if (i < w - 1) Serial.print(':');
    }
    Serial.println(F("]"));
    Serial.print(F("Width: "));
    Serial.print(w);
    Serial.print(F(" | Rate: "));
    Serial.print(rate_names[rate_idx]);
    Serial.print(F(" | Channel: "));
    Serial.println(target_channels[ch_idx]);
    
    Serial.print(F("Payload: "));
    for (uint8_t i = 0; i < 32; i++) {
      print_hex(buf[i]);
      Serial.print(' ');
    }
    Serial.println();
    
    // Try XN297 descramble on payload
    Serial.print(F("XN297 descrambled: "));
    for (uint8_t i = 0; i < 32; i++) {
      uint8_t descrambled = buf[i] ^ (i < sizeof(xn297_scramble) ? 
                            xn297_scramble[i % 5] : 0x00);
      print_hex(descrambled);
      Serial.print(' ');
    }
    Serial.println();
    Serial.println(F("***********************************\n"));
    
    // Don't advance — keep listening on this config to capture more
    config_start_ms = millis();  // reset dwell timer
  }
  
  // Advance to next config after dwell time
  if (millis() - config_start_ms > DWELL_MS) {
    advance_config();
  }
}
