/*
 Receives "<channel>,<angle>\n" from ESP32-CAM via SoftwareSerial (pin 10 RX, 4800 baud).
 Gradually moves each servo toward its target angle using PCA9685 driver (SDA -> A4, SCL -> A5).
*/
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <SoftwareSerial.h>

#define SERVOMIN  125 // 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // 'maximum' pulse length count (out of 4096)

static const int SERVONUM = 16;
SoftwareSerial linkSerial(10, 11); // RX from ESP32-CAM GPIO 13, TX unused
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Current and target positions for all 16 channels
int servos[SERVONUM]      = {90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};
int targetPoses[SERVONUM] = {90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};

// Gradual movement timing
unsigned long previousMillis = 0;
const long INTERVAL = 20;    // ms between steps
int increment = 3;           // degrees per step (~150 deg/s at 20ms interval)

// Serial parse buffer
char parseBuf[32];
int parseIdx = 0;

void setup() {
  pwm.begin();
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates

  Serial.begin(115200);          // USB debug
  linkSerial.begin(4800);        // ESP32-CAM link (matches ARDUINO_BAUD in main.cpp)

  // Power all servos to starting position
  for (int i = 0; i < SERVONUM; i++) {
    pwm.setPWM(i, 0, angleToPulse(servos[i]));
    targetPoses[i] = servos[i];
  }
  Serial.println(F("[SpotController] Ready — waiting for <ch>,<angle> on linkSerial@4800"));
}

// Parse "<channel>,<angle>\n" from linkSerial, update targetPoses[]
void readLink() {
  while (linkSerial.available()) {
    char c = linkSerial.read();
    if (c == '\n' || c == '\r') {
      if (parseIdx > 0) {
        parseBuf[parseIdx] = '\0';
        // Find comma separator
        char* comma = strchr(parseBuf, ',');
        if (comma) {
          *comma = '\0';
          int ch = atoi(parseBuf);
          int ang = atoi(comma + 1);
          if (ch >= 0 && ch < SERVONUM && ang >= 0 && ang <= 180) {
            targetPoses[ch] = ang;
            Serial.print(F("[RX] ch="));
            Serial.print(ch);
            Serial.print(F(" target="));
            Serial.println(ang);
          }
        }
        parseIdx = 0;
      }
    } else if (parseIdx < (int)sizeof(parseBuf) - 1) {
      parseBuf[parseIdx++] = c;
    } else {
      parseIdx = 0;  // overflow — discard
    }
  }
}

void loop() {
  unsigned long now = millis();

  // Read incoming target angles from ESP32-CAM
  readLink();

  // Gradually move servos toward targets every INTERVAL ms
  if (now - previousMillis >= (unsigned long)INTERVAL) {
    previousMillis = now;
    for (int i = 0; i < SERVONUM; i++) {
      if (servos[i] != targetPoses[i]) {
        int delta = targetPoses[i] - servos[i];
        if (abs(delta) <= increment)
          servos[i] = targetPoses[i];
        else
          servos[i] += (delta > 0) ? increment : -increment;
        pwm.setPWM(i, 0, angleToPulse(servos[i]));
      }
    }
  }
}



int angleToPulse(int ang) {
  return map(ang, 0, 180, SERVOMIN, SERVOMAX);
}
