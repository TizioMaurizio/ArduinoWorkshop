// Blinking LED - Arduino Sketch
// Circuit: Arduino Uno pin D13 → 220Ω Resistor → LED → GND
//
// Wiring:
//   D13 ──[220Ω]──|>|── GND
//
// Components:
//   - Arduino Uno
//   - 220Ω resistor (current limiting)
//   - 5mm red LED
//
// The LED on pin 13 also maps to the built-in LED on most Arduino boards.

const int LED_PIN = 13;
const unsigned long BLINK_INTERVAL = 1000; // ms

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
  Serial.println("Blink LED started");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED ON");
  delay(BLINK_INTERVAL);

  digitalWrite(LED_PIN, LOW);
  Serial.println("LED OFF");
  delay(BLINK_INTERVAL);
}
