// ============================================================================
// F8620 — Handshake Stream Capture
// Outputs EVERY packet with millisecond timestamp. No dedup.
// For capturing the TX-on → bind → connected sequence.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t target_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;
static uint32_t pkt_count = 0;

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

void setup() {
  Serial.begin(230400);  // faster baud for stream
  delay(500);
  
  Serial.println(F("=== HANDSHAKE CAPTURE ==="));
  Serial.println(F("Outputs ALL packets. Start with TX OFF, then turn ON."));
  Serial.println(F("Format: ms ch | hex_bytes"));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) {}
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
  
  Serial.println(F("READY"));
}

void loop() {
  // Fast channel hopping
  static uint8_t ch_idx = 0;
  static uint32_t last_hop = 0;
  
  if (millis() - last_hop > 1) {  // 1ms per channel = 6ms full cycle
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
    
    // Minimal filter: not all same byte
    bool all_same = true;
    for (uint8_t i = 1; i < 8; i++) {
      if (buf[i] != buf[0]) { all_same = false; break; }
    }
    if (all_same) return;
    
    pkt_count++;
    
    // Format: #count timestamp channel | bytes
    Serial.print('#');
    Serial.print(pkt_count);
    Serial.print(' ');
    Serial.print(millis());
    Serial.print(' ');
    Serial.print(target_channels[ch_idx]);
    Serial.print(F(" | "));
    
    for (uint8_t i = 0; i < 20; i++) {
      print_hex(buf[i]);
      Serial.print(' ');
    }
    Serial.println();
  }
}
