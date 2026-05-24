// Ping-Pong: Arduino Uno side (nRF24L01+)
// Sends "PING" every second, waits for "PONG" reply from ESP8266
// CE=D9, CSN=D10

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// Pipe addresses (must match ESP8266 side, reversed)
const uint8_t ADDR_TX[] = "UNO01";  // Uno writes here, ESP reads
const uint8_t ADDR_RX[] = "ESP01";  // ESP writes here, Uno reads

uint32_t ping_count = 0;
uint32_t pong_count = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F("=== nRF24 Ping-Pong: Arduino Uno ==="));

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not detected! Check wiring."));
    while (1);
  }

  radio.setPALevel(RF24_PA_LOW);  // LOW for bench testing
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(100);          // Channel 100 (away from WiFi)
  radio.setPayloadSize(8);
  radio.setAutoAck(true);
  radio.setRetries(5, 15);        // 5*250us delay, 15 retries
  radio.openWritingPipe(ADDR_TX);
  radio.openReadingPipe(1, ADDR_RX);
  radio.startListening();

  Serial.println(F("Radio OK. Sending PING every second..."));
  Serial.println(F("Waiting for PONG from ESP8266..."));
  Serial.println();
}

void loop() {
  // Send PING
  radio.stopListening();

  uint32_t payload = millis();
  bool ok = radio.write(&payload, sizeof(payload));
  ping_count++;

  if (ok) {
    Serial.print(F("PING #"));
    Serial.print(ping_count);
    Serial.print(F(" sent ("));
    Serial.print(payload);
    Serial.print(F("ms) → "));
  } else {
    Serial.print(F("PING #"));
    Serial.print(ping_count);
    Serial.println(F(" FAILED (no ACK)"));
    radio.startListening();
    delay(100);
    return;
  }

  // Switch to RX and wait for PONG
  radio.startListening();
  uint32_t wait_start = millis();

  while (!radio.available()) {
    if (millis() - wait_start > 500) {
      Serial.println(F("no PONG (timeout)"));
      delay(100);
      return;
    }
  }

  uint32_t reply;
  radio.read(&reply, sizeof(reply));
  pong_count++;

  uint32_t rtt = millis() - payload;
  Serial.print(F("PONG! RTT="));
  Serial.print(rtt);
  Serial.print(F("ms ("));
  Serial.print(pong_count);
  Serial.print('/');
  Serial.print(ping_count);
  Serial.println(F(" success)"));

  delay(100);
}
