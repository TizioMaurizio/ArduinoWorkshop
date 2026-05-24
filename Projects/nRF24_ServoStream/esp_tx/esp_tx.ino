// ESP8266 nRF24 Servo Angle Transmitter
// Receives angle (0-180) via Serial from PC GUI, streams over nRF24 to Uno

#include <SPI.h>
#include <RF24.h>

// CE=D2(GPIO4), CSN=D8(GPIO15)
RF24 radio(4, 15);

const byte ADDR_TX[6] = "SRV01";
const byte ADDR_RX[6] = "SRV02";

uint8_t current_angle = 90;
uint32_t tx_count = 0;
uint32_t fail_count = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  if (!radio.begin()) {
    Serial.println(F("ERROR: nRF24 not detected!"));
    while (1) { delay(1000); }
  }

  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(100);
  radio.setPayloadSize(8);
  radio.setAutoAck(true);
  radio.setRetries(2, 5);  // fast retries for low latency
  radio.openWritingPipe(ADDR_TX);
  radio.openReadingPipe(1, ADDR_RX);
  radio.stopListening();

  Serial.println(F("ESP TX ready. Send angle 0-180 via Serial."));
}

void loop() {
  // Read angle from Serial (sent by Python GUI)
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    int val = line.toInt();
    if (val >= 0 && val <= 180) {
      current_angle = (uint8_t)val;
    }
  }

  // Stream current angle at ~50Hz
  static uint32_t last_tx = 0;
  if (millis() - last_tx >= 20) {
    last_tx = millis();

    uint8_t payload[8] = {0};
    payload[0] = current_angle;
    payload[1] = (uint8_t)(tx_count & 0xFF);  // sequence number

    bool ok = radio.write(payload, sizeof(payload));
    tx_count++;
    if (!ok) fail_count++;

    // Print stats every 50 packets (once per second)
    if (tx_count % 50 == 0) {
      Serial.print(F("TX #"));
      Serial.print(tx_count);
      Serial.print(F(" angle="));
      Serial.print(current_angle);
      Serial.print(F(" fail="));
      Serial.print(fail_count);
      Serial.print(F(" ("));
      Serial.print((fail_count * 100) / tx_count);
      Serial.println(F("%)"));
    }
  }
}
