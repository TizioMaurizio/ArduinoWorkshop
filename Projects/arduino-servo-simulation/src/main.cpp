#include <Arduino.h>
#include <Servo.h>

// Wiring (from Circuit Designer):
//   Arduino D9~ → Servo Signal (Orange)
//   Arduino 5V  → Servo VCC   (Red)
//   Arduino GND → Servo GND   (Brown)

static const uint8_t SERVO_PIN = 9;

Servo servo;
char buf[8];
uint8_t buf_idx = 0;

void setup() {
  Serial.begin(115200);
  servo.attach(SERVO_PIN);
  servo.write(90);
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf_idx > 0) {
        buf[buf_idx] = '\0';
        int angle = atoi(buf);
        if (angle >= 0 && angle <= 180) {
          servo.write(angle);
          Serial.print("OK ");
          Serial.println(angle);
        }
        buf_idx = 0;
      }
    } else if (buf_idx < sizeof(buf) - 1) {
      buf[buf_idx++] = c;
    }
  }
}