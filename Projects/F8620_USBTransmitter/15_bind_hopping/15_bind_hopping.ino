// ============================================================================
// F8620 — Binding Transmitter with Channel Hopping
// Sends all-zero payloads on CH72-77 in sequence, like the original TX.
// Tries to trigger binding by mimicking the TX's hop pattern.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

// Payload: all zeros (sticks centered = bind request)
static uint8_t payload[32];  // initialized to zero

static uint32_t tx_count = 0;
static uint8_t ch_idx = 0;

void setup() {
  Serial.begin(1000000);
  delay(500);
  
  memset(payload, 0x00, sizeof(payload));
  
  Serial.println(F("=== BINDING TRANSMITTER ==="));
  Serial.println(F("Hops CH72-77, sends zeros, CRC disabled"));
  Serial.println(F("Commands: 0=CRC_OFF, 1=CRC8, 2=CRC16, P=toggle PA"));
  Serial.println(F("          8/A/F/G = payload size 8/10/15/32"));
  Serial.println(F("---"));
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) {}
  }
  
  radio.setChannel(channels[0]);
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_MAX);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setRetries(0, 0);
  radio.setPayloadSize(32);
  radio.setAddressWidth(5);
  
  uint8_t addr[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
  radio.openWritingPipe(addr);
  radio.stopListening();
  
  Serial.println(F("TRANSMITTING..."));
}

void loop() {
  // Send one packet per channel, hop every ~4ms (matches observed timing)
  radio.setChannel(channels[ch_idx]);
  radio.writeFast(payload, 32, true);  // multicast (no ACK)
  
  tx_count++;
  ch_idx = (ch_idx + 1) % NUM_CH;
  
  // ~4ms per channel = ~24ms full hop cycle ≈ 42 pkt/s per channel
  delayMicroseconds(3800);
  
  // Status every 500 packets
  if (tx_count % 500 == 0) {
    Serial.print(F("TX: "));
    Serial.print(tx_count);
    Serial.print(F(" pkts, CRC="));
    Serial.println(radio.getCRCLength());
  }
  
  // Handle serial commands
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case '0':
        radio.setCRCLength(RF24_CRC_DISABLED);
        Serial.println(F("CRC: OFF"));
        break;
      case '1':
        radio.setCRCLength(RF24_CRC_8);
        Serial.println(F("CRC: 8-bit"));
        break;
      case '2':
        radio.setCRCLength(RF24_CRC_16);
        Serial.println(F("CRC: 16-bit"));
        break;
      case 'P': case 'p':
        // Toggle PA level
        {
          static bool pa_high = true;
          pa_high = !pa_high;
          radio.setPALevel(pa_high ? RF24_PA_MAX : RF24_PA_LOW);
          Serial.print(F("PA: "));
          Serial.println(pa_high ? F("MAX") : F("LOW"));
        }
        break;
      case '8':
        radio.setPayloadSize(8);
        Serial.println(F("Payload: 8 bytes"));
        break;
      case 'A': case 'a':
        radio.setPayloadSize(10);
        Serial.println(F("Payload: 10 bytes"));
        break;
      case 'F': case 'f':
        radio.setPayloadSize(15);
        Serial.println(F("Payload: 15 bytes"));
        break;
      case 'G': case 'g':
        radio.setPayloadSize(32);
        Serial.println(F("Payload: 32 bytes"));
        break;
      case '3':
        radio.setAddressWidth(3);
        {
          uint8_t a3[] = {0xAA, 0xAA, 0xAA};
          radio.openWritingPipe(a3);
        }
        Serial.println(F("Addr: 3-byte AA*3"));
        break;
      case '4':
        radio.setAddressWidth(4);
        {
          uint8_t a4[] = {0xAA, 0xAA, 0xAA, 0xAA};
          radio.openWritingPipe(a4);
        }
        Serial.println(F("Addr: 4-byte AA*4"));
        break;
      case '5':
        radio.setAddressWidth(5);
        {
          uint8_t a5[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
          radio.openWritingPipe(a5);
        }
        Serial.println(F("Addr: 5-byte AA*5"));
        break;
    }
  }
}
