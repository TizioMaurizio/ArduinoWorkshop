// ============================================================================
// F8620 USB Transmitter — Raw Bitstream Capture
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Stream raw demodulated bytes to PC at maximum rate.
//          Python script will find the real sync word via autocorrelation.
//
// OUTPUT FORMAT: Binary data stream with framing markers.
//   Each capture: 0xFF 0x00 [channel] [32 bytes payload]
//   (0xFF 0x00 can't appear in preamble-synced data easily)
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;
static uint8_t ch_idx = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) { delay(1000); }
  }
  
  // Minimal address, max payload, no CRC
  radio.setChannel(channels[0]);
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(3);
  
  uint8_t addr[] = {0xAA, 0xAA, 0xAA};
  radio.openReadingPipe(0, addr);
  radio.startListening();
  
  Serial.println(F("READY"));
}

void loop() {
  // Hop channels every 2ms
  static uint32_t last_hop = 0;
  if (millis() - last_hop > 2) {
    ch_idx = (ch_idx + 1) % NUM_CH;
    radio.stopListening();
    radio.setChannel(channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }
  
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    
    // Send frame marker + channel + data
    Serial.write(0xFF);
    Serial.write((uint8_t)0x00);
    Serial.write(channels[ch_idx]);
    Serial.write(buf, 32);
  }
}
