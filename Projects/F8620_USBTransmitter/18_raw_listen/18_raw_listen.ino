// Raw listener — captures XN297 packets on channels 72-77
// Uses the XN297 "enhanced preamble" as nRF24 address (same technique as 16_xn297_dump)
// Prints timestamped hex. Toggle your TX on/off to see what appears.

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// XN297 enhanced preamble (used as nRF24 RX address)
// This captures ALL XN297 packets (both data and bind) from F8620
static const uint8_t ADDR_XN297[] = {0x55, 0x0F, 0x71};  // catches XN297 addr MSBit variant

static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

static uint8_t ch_idx = 0;
static uint32_t pkt_count = 0;
static uint32_t start_ms = 0;
static uint32_t last_hop = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println(F("=== RAW XN297 LISTENER ==="));
  Serial.println(F("Channels: 72-77, hopping every 2ms"));
  Serial.println(F("XN297 preamble capture mode"));
  Serial.println(F("Toggle TX on/off now. Listening 20s..."));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("RADIO FAIL"));
    while(1);
  }
  
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(3);
  radio.setPALevel(RF24_PA_MAX);
  
  radio.openReadingPipe(0, ADDR_XN297);
  
  radio.setChannel(channels[0]);
  radio.startListening();
  
  start_ms = millis();
  last_hop = millis();
  
  Serial.println(F("GO!"));
}

void loop() {
  uint32_t now = millis();
  
  // Stop after 20 seconds
  if (now - start_ms > 20000) {
    radio.stopListening();
    Serial.println(F("---"));
    Serial.print(F("DONE. Total packets: "));
    Serial.println(pkt_count);
    Serial.print(F("Rate: "));
    Serial.print(pkt_count * 1000UL / 20000UL);
    Serial.println(F(" pkt/s avg"));
    while(1);
  }
  
  // Hop channels every 2ms
  if (now - last_hop >= 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(channels[ch_idx]);
    radio.startListening();
    last_hop = now;
  }
  
  // Check for packets
  uint8_t pipe;
  while (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    pkt_count++;
    
    // Print: timestamp channel first_20_bytes
    uint32_t t = now - start_ms;
    Serial.print(t);
    Serial.print(F(" c"));
    Serial.print(channels[ch_idx]);
    Serial.print(F(" "));
    
    // Print first 20 bytes hex (compact)
    for (uint8_t i = 0; i < 20; i++) {
      if (buf[i] < 0x10) Serial.print('0');
      Serial.print(buf[i], HEX);
    }
    Serial.println();
    
    // After 200 packets, just count
    if (pkt_count == 200) {
      Serial.println(F("--- (limiting output, counting only) ---"));
    }
    if (pkt_count > 200 && pkt_count % 500 == 0) {
      Serial.print(F("["));
      Serial.print(now - start_ms);
      Serial.print(F("ms: "));
      Serial.print(pkt_count);
      Serial.println(F(" pkts]"));
    }
  }
}
