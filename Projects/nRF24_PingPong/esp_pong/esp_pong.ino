// Ping-Pong: NodeMCU (ESP8266) side (nRF24L01+)
// Listens for "PING" from Uno, replies with "PONG"
// CE=D2 (GPIO4), CSN=D8 (GPIO15)
// SPI: SCK=D5(GPIO14), MOSI=D7(GPIO13), MISO=D6(GPIO12)

#include <SPI.h>
#include <RF24.h>

RF24 radio(4, 15);  // CE=GPIO4 (D2), CSN=GPIO15 (D8)

// Pipe addresses (must match Uno side)
const uint8_t ADDR_RX[] = "UNO01";  // Uno writes here, ESP reads
const uint8_t ADDR_TX[] = "ESP01";  // ESP writes here, Uno reads

uint32_t pong_count = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F("\n=== nRF24 Ping-Pong: NodeMCU ESP8266 ==="));

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not detected! Check wiring:"));
    Serial.println(F("  VCC  → 3V3 (NOT 5V!)"));
    Serial.println(F("  GND  → GND"));
    Serial.println(F("  CE   → D2 (GPIO4)"));
    Serial.println(F("  CSN  → D8 (GPIO15)"));
    Serial.println(F("  MOSI → D7 (GPIO13)"));
    Serial.println(F("  MISO → D6 (GPIO12)"));
    Serial.println(F("  SCK  → D5 (GPIO14)"));
    while (1) { delay(1000); }
  }

  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(100);
  radio.setPayloadSize(8);
  radio.setAutoAck(true);
  radio.setRetries(5, 15);
  radio.openWritingPipe(ADDR_TX);
  radio.openReadingPipe(1, ADDR_RX);
  radio.startListening();

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);  // OFF (NodeMCU LED is active-LOW)

  Serial.println(F("Radio OK. Listening for PING from Uno..."));
  Serial.println();
}

static uint32_t led_off_time = 0;

void loop() {
  // Turn off LED after blink duration
  if (led_off_time && millis() > led_off_time) {
    digitalWrite(LED_BUILTIN, HIGH);  // OFF (active-LOW)
    led_off_time = 0;
  }

  if (radio.available()) {
    uint32_t received;
    radio.read(&received, sizeof(received));
    pong_count++;

    // Blink LED on receive
    digitalWrite(LED_BUILTIN, LOW);  // ON (active-LOW)
    led_off_time = millis() + 100;

    Serial.print(F("PING received (#"));
    Serial.print(pong_count);
    Serial.print(F(", val="));
    Serial.print(received);
    Serial.print(F("ms) → sending PONG... "));

    // Send PONG reply
    radio.stopListening();
    uint32_t reply = received;  // echo back the timestamp
    bool ok = radio.write(&reply, sizeof(reply));
    radio.startListening();

    Serial.println(ok ? F("OK") : F("FAIL"));
  }
}
