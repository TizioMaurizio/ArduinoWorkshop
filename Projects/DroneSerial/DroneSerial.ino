const int pinUpDown = 6;
const int pinYaw = 5;
const int pinPitch = 10;
const int pinRoll = 11;

const int PWM_LOW = 0;
const int PWM_NEUTRAL = 87;
const int PWM_HIGH = 171;

unsigned long lastCommandTime = 0;
const unsigned long timeout = 300; // ms before returning to neutral

String inputLine = "";

void setup() {
  Serial.begin(115200);

  pinMode(pinUpDown, OUTPUT);
  pinMode(pinYaw, OUTPUT);
  pinMode(pinPitch, OUTPUT);
  pinMode(pinRoll, OUTPUT);

  setNeutral();
}

void setNeutral() {
  analogWrite(pinUpDown, PWM_NEUTRAL);
  analogWrite(pinYaw, PWM_NEUTRAL);
  analogWrite(pinPitch, PWM_NEUTRAL);
  analogWrite(pinRoll, PWM_NEUTRAL);
}

void setAxis(int pin, int value) {
  if (value > 0) analogWrite(pin, PWM_HIGH);
  else if (value < 0) analogWrite(pin, PWM_LOW);
  else analogWrite(pin, PWM_NEUTRAL);
}

void loop() {

  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {

      int ud, yaw, pitch, roll;

      sscanf(inputLine.c_str(), "%d %d %d %d", &ud, &yaw, &pitch, &roll);

      setAxis(pinUpDown, ud);
      setAxis(pinYaw, yaw);
      setAxis(pinPitch, pitch);
      setAxis(pinRoll, roll);

      lastCommandTime = millis();
      inputLine = "";
    }
    else {
      inputLine += c;
    }
  }

  // timeout safety
  if (millis() - lastCommandTime > timeout) {
    setNeutral();
  }
}