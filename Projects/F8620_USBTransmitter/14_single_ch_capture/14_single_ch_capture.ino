// ============================================================================
// F8620 — Single Channel Capture (CH76) — 1Mbaud, compact output
// Stays on ONE channel to capture EVERY packet without hopping gaps.
// Output: binary frames for maximum throughput
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t CAPTURE_CHANNEL = 76;
static uint32_t pkt_count = 0;

// Compact text output: "T<ms> <hex_no_spaces>\n"  (~72 chars vs 116)
void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

void setup() {
  Serial.begin(1000000);  // 1 Mbaud — 0% error on 16MHz, ~862 pkt/s capacity
  delay(500);
  
  Serial.println(F("=== SINGLE CH CAPTURE ==="));
  Serial.print(F("CH="));
  Serial.print(CAPTURE_CHANNEL);
  Serial.println(F(" BAUD=1000000"));
  Serial.println(F("Format: #count ms ch | hex"));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) {}
  }
  
  radio.setChannel(CAPTURE_CHANNEL);
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
    
    // Keep compatible format with capture_replay.py parser
    Serial.print('#');
    Serial.print(pkt_count);
    Serial.print(' ');
    Serial.print(millis());
    Serial.print(' ');
    Serial.print(CAPTURE_CHANNEL);
    Serial.print(F(" | "));
    
    for (uint8_t i = 0; i < 32; i++) {
      print_hex(buf[i]);
      if (i < 31) Serial.print(' ');
    }
    Serial.println();
  }
}
