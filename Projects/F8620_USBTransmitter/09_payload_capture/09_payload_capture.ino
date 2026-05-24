// ============================================================================
// F8620 USB Transmitter — Payload Capture with 0xAA Address
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Based on statistical analysis showing the TX signal has a long
//          0xAA preamble, we set address = {AA,AA,AA,AA,AA} and capture
//          the payload that follows. User moves sticks to confirm data changes.
//
// FINDING: Phase 3 stats showed positions 0-5 dominated by 0xAA (71-93%),
//          then transition to 0x00 at positions 7-9. This means the signal
//          is: [long preamble 0xAA...] [short payload/zeros]
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t target_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

// XN297 descramble
static const uint8_t xn297_scram[] = {
  0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
  0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
  0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
  0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F
};

static uint8_t last_payload[32];
static bool have_last = false;
static uint32_t pkt_count = 0;
static uint32_t unique_count = 0;

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

bool payload_changed(uint8_t* buf) {
  if (!have_last) return true;
  for (uint8_t i = 0; i < 32; i++) {
    if (buf[i] != last_payload[i]) return true;
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println(F("=== F8620 Payload Capture ==="));
  Serial.println(F("Address: {AA,AA,AA,AA,AA} (5-byte)"));
  Serial.println(F("Channels: 72-77 | CRC: disabled | Rate: 1Mbps"));
  Serial.println();
  Serial.println(F("INSTRUCTIONS:"));
  Serial.println(F("1. Turn TX ON, leave sticks centered"));
  Serial.println(F("2. After ~20 packets, move throttle up"));
  Serial.println(F("3. Then move yaw left/right"));
  Serial.println(F("4. Watch for byte changes = control data!"));
  Serial.println();
  
  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }
  
  radio.setChannel(target_channels[0]);
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(5);
  
  uint8_t addr[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
  radio.openReadingPipe(0, addr);
  radio.startListening();
  
  Serial.println(F("Listening... (printing only unique payloads)"));
  Serial.println(F("PKT# CH  | Payload (hex)"));
  Serial.println(F("---- --- | ------------------------------------------------"));
}

void loop() {
  // Fast channel hopping
  static uint8_t ch_idx = 0;
  static uint32_t last_hop = 0;
  
  if (millis() - last_hop > 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(target_channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }
  
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    pkt_count++;
    
    // Filter: not all same byte, not all FF
    bool all_same = true;
    for (uint8_t i = 1; i < 16; i++) {
      if (buf[i] != buf[0]) { all_same = false; break; }
    }
    if (all_same) return;
    
    // Only print if payload changed (reduces noise)
    if (payload_changed(buf)) {
      unique_count++;
      
      // Print packet
      Serial.print(F("#"));
      if (unique_count < 100) Serial.print(' ');
      if (unique_count < 10) Serial.print(' ');
      Serial.print(unique_count);
      Serial.print(F("  "));
      Serial.print(target_channels[ch_idx]);
      Serial.print(F(" | "));
      
      // Print first 20 bytes (key data)
      for (uint8_t i = 0; i < 20; i++) {
        print_hex(buf[i]);
        Serial.print(' ');
      }
      
      // Mark which bytes changed from last
      if (have_last) {
        Serial.print(F(" Δ["));
        bool first = true;
        for (uint8_t i = 0; i < 20; i++) {
          if (buf[i] != last_payload[i]) {
            if (!first) Serial.print(',');
            Serial.print(i);
            first = false;
          }
        }
        Serial.print(']');
      }
      Serial.println();
      
      // Also print XN297 descrambled version every 10 packets
      if (unique_count <= 5 || unique_count % 20 == 0) {
        Serial.print(F("     XN: "));
        for (uint8_t i = 0; i < 20; i++) {
          print_hex(buf[i] ^ xn297_scram[i]);
          Serial.print(' ');
        }
        Serial.println();
      }
      
      memcpy(last_payload, buf, 32);
      have_last = true;
    }
    
    // Periodic summary
    if (pkt_count % 200 == 0) {
      Serial.print(F("\n[Total: "));
      Serial.print(pkt_count);
      Serial.print(F(" pkts, "));
      Serial.print(unique_count);
      Serial.println(F(" unique]\n"));
    }
  }
}
