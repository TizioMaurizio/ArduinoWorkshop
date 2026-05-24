// Pseudo-promiscuous listener — 2-byte address 0xAA to catch anything
// Will get noise but also any real packet on CH 72-77

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

// 2-byte "promiscuous" addresses that match common bit patterns
static const uint8_t ADDR_AA[] = {0xAA, 0xAA, 0x00, 0x00, 0x00};  // matches 10101010...
static const uint8_t ADDR_55[] = {0x55, 0x55, 0x00, 0x00, 0x00};  // matches 01010101...

static uint8_t ch_idx = 0;
static uint32_t pkt_count = 0;
static uint32_t start_ms = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println(F("=== PROMISCUOUS LISTENER ==="));
  Serial.println(F("2-byte addr, CH72-77, hop 2ms"));
  Serial.println(F("Toggle TX on/off. 20s capture."));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("RADIO FAIL"));
    while(1);
  }
  
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(2);
  radio.setPALevel(RF24_PA_MAX);
  
  // Two pipes with different "promiscuous" address prefixes
  radio.openReadingPipe(0, ADDR_AA);
  radio.openReadingPipe(1, ADDR_55);
  
  radio.setChannel(channels[0]);
  radio.startListening();
  
  start_ms = millis();
  Serial.println(F("GO!"));
}

void loop() {
  uint32_t now = millis();
  
  if (now - start_ms > 20000) {
    radio.stopListening();
    Serial.println(F("---"));
    Serial.print(F("DONE. Pkts: "));
    Serial.println(pkt_count);
    while(1);
  }
  
  // Hop every 2ms
  static uint32_t last_hop = 0;
  if (now - last_hop >= 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(channels[ch_idx]);
    radio.startListening();
    last_hop = now;
  }
  
  uint8_t pipe;
  while (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    pkt_count++;
    
    // Only print first 100 packets to avoid flooding
    if (pkt_count <= 100) {
      uint32_t t = now - start_ms;
      Serial.print(t);
      Serial.print(pipe == 0 ? F(" AA") : F(" 55"));
      Serial.print(F(" c"));
      Serial.print(channels[ch_idx]);
      Serial.print(' ');
      for (uint8_t i = 0; i < 22; i++) {
        if (buf[i] < 0x10) Serial.print('0');
        Serial.print(buf[i], HEX);
      }
      Serial.println();
    } else if (pkt_count % 500 == 0) {
      Serial.print(F("["));
      Serial.print(pkt_count);
      Serial.println(F(" pkts]"));
    }
  }
}
