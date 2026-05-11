// Servo Sweep - Arduino Sketch
// Circuit: Arduino Uno D9~ → Servo Signal, 5V → VCC, GND → GND

#include <Servo.h>

const int SERVO_PIN = 9;
Servo myServo;

void setup() {
  myServo.attach(SERVO_PIN);
  Serial.begin(9600);
  Serial.println("Servo sweep started");
}

void loop() {
  myServo.write(0);
  Serial.println("Angle: 0");
  delay(800);

  myServo.write(45);
  Serial.println("Angle: 45");
  delay(800);

  myServo.write(90);
  Serial.println("Angle: 90");
  delay(800);

  myServo.write(135);
  Serial.println("Angle: 135");
  delay(800);

  myServo.write(180);
  Serial.println("Angle: 180");
  delay(800);

  myServo.write(90);
  Serial.println("Angle: 90");
  delay(800);
}
