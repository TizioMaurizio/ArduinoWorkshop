// Arduino Uno nRF24 Servo Receiver
// Receives angle over nRF24 from ESP, drives servo on D3
// Runs standalone on powerbank (no serial needed)

#include <SPI.h>
#include <RF24.h>
#include <Servo.h>

// CE=D9, CSN=D10
RF24 radio(9, 10);
Servo myServo;

const byte ADDR_TX[6] = "SRV02";
const byte ADDR_RX[6] = "SRV01";

const int SERVO_PIN = 3;

uint8_t current_angle = 90;
uint32_t rx_count = 0;
uint32_t last_rx_time = 0;
bool signal_lost = false;

void setup() {
  Serial.begin(115200);

  myServo.attach(SERVO_PIN);
  myServo.write(90);  // center position

  if (!radio.begin()) {
    Serial.println(F("ERROR: nRF24 not detected!"));
    while (1) { delay(1000); }
  }

  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(100);
  radio.setPayloadSize(8);
  radio.setAutoAck(true);
  radio.setRetries(2, 5);
  radio.openWritingPipe(ADDR_TX);
  radio.openReadingPipe(1, ADDR_RX);
  radio.startListening();

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.println(F("Uno RX ready. Waiting for servo angles..."));
  last_rx_time = millis();
}

void loop() {
  if (radio.available()) {
    uint8_t payload[8];
    radio.read(payload, sizeof(payload));

    uint8_t angle = payload[0];
    if (angle <= 180) {
      current_angle = angle;
      myServo.write(current_angle);
    }

    rx_count++;
    last_rx_time = millis();
    signal_lost = false;

    // Blink LED on receive
    digitalWrite(LED_BUILTIN, HIGH);

    // Print every 50th packet
    if (rx_count % 50 == 0) {
      Serial.print(F("RX #"));
      Serial.print(rx_count);
      Serial.print(F(" angle="));
      Serial.println(current_angle);
    }
  } else {
    // Turn off LED when not receiving
    digitalWrite(LED_BUILTIN, LOW);
  }

  // Signal lost detection (no packet for 500ms)
  if (!signal_lost && (millis() - last_rx_time > 500)) {
    signal_lost = true;
    Serial.println(F("SIGNAL LOST - holding last angle"));
  }
}
