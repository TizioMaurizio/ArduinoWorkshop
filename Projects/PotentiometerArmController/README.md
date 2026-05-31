# PotentiometerArmController

Receiver sketch for a 16-DOF arm. Reads a packet of 16 × 3-digit angles (`S090180...\n`) on SoftwareSerial (D10 RX / D11 TX) and applies them to a PCA9685.

Sketch: `PotentiometerArmController.ino`. Libraries: `Servo`, `Adafruit_PWMServoDriver`, `SoftwareSerial`.
