// ============================================================================
// F8620 USB Transmitter — Transmit Test
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Attempt to control the drone by transmitting the same pattern
//          observed from the original TX:
//          - Long 0xAA preamble (via address = AA*5)
//          - CRC disabled (raw output)
//          - Payload = zeros (neutral sticks)
//          - Hop channels 72-77
//
// SAFETY: This sends ZERO throttle only. Motors should NOT spin.
//         If drone LEDs change from fast-blink to solid/slow-blink = BOUND!
//
// SERIAL COMMANDS:
//   'a' = arm (set throttle byte to low value)
//   'd' = disarm (throttle back to zero)
//   't' = toggle TX on/off
//   'i' = info (print current state)
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static const uint8_t hop_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_CH = 6;

// Payload: 15 bytes (common for toy drone protocols)
// Try different payload sizes to see what the drone accepts
static uint8_t payload[15] = {0};
static const uint8_t PAYLOAD_SIZE = 15;

static bool tx_active = true;
static uint8_t ch_idx = 0;
static uint32_t last_send = 0;
static uint32_t pkt_count = 0;
static const uint16_t SEND_INTERVAL_US = 1500;  // ~667 pkts/sec total, ~111/channel

void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println(F("=== F8620 TRANSMIT TEST ==="));
  Serial.println(F("Sending: addr=AA*5, CRC off, payload=zeros"));
  Serial.println(F("Channels: 72-77, hopping every packet"));
  Serial.println(F(""));
  Serial.println(F("Commands:"));
  Serial.println(F("  t = toggle TX on/off"));
  Serial.println(F("  i = info"));
  Serial.println(F("  1-9 = set byte[0] to value (test)"));
  Serial.println(F("  0 = reset payload to zeros"));
  Serial.println(F(""));
  Serial.println(F("Watch drone LEDs for bind indication!"));
  Serial.println(F(""));
  
  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) {}
  }
  
  // Configure as transmitter
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setRetries(0, 0);
  radio.setPayloadSize(PAYLOAD_SIZE);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);
  
  uint8_t addr[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
  radio.openWritingPipe(addr);
  radio.setChannel(hop_channels[0]);
  radio.stopListening();
  
  Serial.println(F("TX active. Sending..."));
}

void send_packet() {
  // Hop to next channel
  ch_idx = (ch_idx + 1) % NUM_CH;
  radio.setChannel(hop_channels[ch_idx]);
  
  // Send without waiting for ACK
  radio.writeFast(payload, PAYLOAD_SIZE, true);  // multicast = no ACK
  pkt_count++;
}

void print_status() {
  Serial.print(F("TX: "));
  Serial.print(tx_active ? F("ON") : F("OFF"));
  Serial.print(F(" | Packets: "));
  Serial.print(pkt_count);
  Serial.print(F(" | Payload: "));
  for (uint8_t i = 0; i < PAYLOAD_SIZE; i++) {
    if (payload[i] < 0x10) Serial.print('0');
    Serial.print(payload[i], HEX);
    Serial.print(' ');
  }
  Serial.println();
}

void loop() {
  // Send packets at high rate
  if (tx_active && micros() - last_send >= SEND_INTERVAL_US) {
    send_packet();
    last_send = micros();
  }
  
  // Handle serial commands
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 't':
        tx_active = !tx_active;
        Serial.print(F("TX: "));
        Serial.println(tx_active ? F("ON") : F("OFF"));
        break;
      case 'i':
        print_status();
        break;
      case '0':
        memset(payload, 0, PAYLOAD_SIZE);
        Serial.println(F("Payload reset to zeros"));
        break;
      case '1': case '2': case '3': case '4':
      case '5': case '6': case '7': case '8': case '9':
        payload[0] = (c - '0') * 0x1C;  // scale 1-9 to 0x1C-0xFC
        Serial.print(F("Byte[0] = 0x"));
        Serial.println(payload[0], HEX);
        break;
      default:
        break;
    }
  }
  
  // Periodic status
  if (pkt_count > 0 && pkt_count % 5000 == 0) {
    static uint32_t last_report = 0;
    if (pkt_count != last_report) {
      last_report = pkt_count;
      Serial.print(F("."));  // heartbeat
    }
  }
}
