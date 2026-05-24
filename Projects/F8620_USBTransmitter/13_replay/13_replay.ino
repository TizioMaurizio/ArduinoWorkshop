// ============================================================================
// F8620 — Replay Transmitter
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Receives packet data from PC via serial and transmits immediately.
//          Used to replay captured RF sequences.
//
// SERIAL PROTOCOL (binary):
//   PC → Arduino: [0xFF] [channel] [len] [payload bytes...]
//   Arduino → PC: 'R' after each transmitted packet (ACK)
//   Special: [0xFE] = start streaming mode
//            [0xFD] = stop streaming mode
//            'S' = status request (ASCII)
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

static uint32_t tx_count = 0;
static bool streaming = false;

enum RxState {
  WAIT_SYNC,
  READ_CHANNEL,
  READ_LEN,
  READ_PAYLOAD
};

static RxState state = WAIT_SYNC;
static uint8_t pkt_channel = 0;
static uint8_t pkt_len = 0;
static uint8_t pkt_buf[32];
static uint8_t pkt_idx = 0;

void setup() {
  Serial.begin(1000000);  // 1 Mbaud — matches capture_replay.py
  delay(500);
  
  if (!radio.begin()) {
    Serial.println(F("FAIL"));
    while (1) {}
  }
  
  // Configure as transmitter
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setRetries(0, 0);
  radio.setPayloadSize(32);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);
  
  uint8_t addr[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
  radio.openWritingPipe(addr);
  radio.setChannel(72);
  radio.stopListening();
  
  Serial.println(F("READY"));
}

void transmit_packet() {
  radio.setChannel(pkt_channel);
  radio.writeFast(pkt_buf, pkt_len, true);
  tx_count++;
  Serial.write('R');  // ACK back to PC
}

void loop() {
  while (Serial.available()) {
    uint8_t b = Serial.read();
    
    switch (state) {
      case WAIT_SYNC:
        if (b == 0xFF) {
          state = READ_CHANNEL;
        } else if (b == 0xFE) {
          streaming = true;
          Serial.println(F("STREAM_ON"));
        } else if (b == 0xFD) {
          streaming = false;
          Serial.println(F("STREAM_OFF"));
        } else if (b == 'S') {
          Serial.print(F("TX:"));
          Serial.println(tx_count);
        }
        break;
        
      case READ_CHANNEL:
        pkt_channel = b;
        state = READ_LEN;
        break;
        
      case READ_LEN:
        pkt_len = b;
        if (pkt_len > 32) pkt_len = 32;
        pkt_idx = 0;
        if (pkt_len == 0) {
          transmit_packet();
          state = WAIT_SYNC;
        } else {
          state = READ_PAYLOAD;
        }
        break;
        
      case READ_PAYLOAD:
        pkt_buf[pkt_idx++] = b;
        if (pkt_idx >= pkt_len) {
          transmit_packet();
          state = WAIT_SYNC;
        }
        break;
    }
  }
}
