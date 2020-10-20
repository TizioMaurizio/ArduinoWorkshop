/*
 Control various servos one at a time using a potentiometer or serial input angle
*/

#include <Servo.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)
#define NONE -99
#define CW_START_CLK 0
#define CW_START_DT 0
#define CW_END_CLK 1
#define CW_END_DT 1
#define CCW_START_CLK 0
#define CCW_START_DT 1
#define CCW_END_CLK 1
#define CCW_END_DT 0

Servo myservo;  // for use without drive, signal on pin 9
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// MOTOR STARTING POSITIONS
int servos[16] = {90, 180, 150, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};
//SERVO ARM
//Hand 'a' >=30
//Swing 'd' >=80

// Potentiometer variables
int potpin = 0;  // analog pin used to connect the potentiometer
int offset = 0;  // motor - potpin
int offpot = 0;  // potpin + offset
int val = 0;    // variable to read the value from the analog pin

//Encoder variables
int CLK = 2;//CLK->D2
int DT = 3;//DT->D3
int SW = 4;//SW->D4
const int interrupt0 = 0;
int count = 18;
int lastCLK = 0;
int stage = -1; 
int encAngle = 90;
int precValue = 0;

// General variables
int angle = NONE;
int input;
String buf;
char motor = NONE;
bool potMode = true;
int newline = 0;

// Time interval checker variables for potentiometer angle monitor
unsigned long previousMillis = 0;
const long interval = 500;


void setup() {
  myservo.attach(9);  // attaches the single servo on pin 9 to the servo object
  val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
  val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
  myservo.write(encAngle);
  pinMode(SW, INPUT);
  digitalWrite(SW, HIGH);
  pinMode(CLK, INPUT);
  pinMode(DT, INPUT);
  attachInterrupt(interrupt0, ClockChanged, CHANGE);
  pwm.begin();
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  Serial.begin(9600);
  Serial.setTimeout(10); // readString reads until this timeout
  Serial.println("Servo controller: input -1 to use encoder, -2 to print current angle");
  Serial.println("else input a letter to choose the motor and an int to set angle");
  Serial.println("signal D9 is for use without servo drive (motor q)");
  Serial.println("Initializing motors to values ");
  for(int i=0; i<16; i++){  // power motors to starting position
    Serial.print((char)(97+i));
    Serial.print(":");
    Serial.print(servos[i]);
    Serial.print(' ');
    pwm.setPWM(i, 0, angleToPulse(servos[i]));
  }
  Serial.println();
}

void loop() {
  encAngle = count * 5;
  //  if there was an input
  if(Serial.available()){
    buf = Serial.readString();
    input = buf.toInt();
    
    // if input was a char (clamps strings)
    if(input==0 && buf[0]!='0'){  
      if(buf[0]<97 || buf[0]>97+15){  // 97 is ASCII 'a'
        if(buf[0] == 'q'){
          Serial.println("\nViewing values of motor q (D9)");
          motor = NONE;
        }
        else{
          Serial.println("Selected motor out of bounds, insert a letter among");
          Serial.println("a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q.");
        }
      }
      else{
        motor = buf[0]-97;
        Serial.print("\nNow using ");
        Serial.println((char)(motor+97));
      }
      angle=NONE;
      count = servos[motor] / 5;
    }

    // if input was integer
    else{
      angle = input;
      Serial.read();

      //  Start potentiometer control
      if(angle==-1){
        potMode=true;
        val = analogRead(potpin);  
        val = map(val, 0, 1023, 0, 180);
        offset = servos[motor] - val;  // update potentiometer offset
        count = servos[motor] / 5;
        Serial.print("Switched to potentiometer control of motor ");
        Serial.println((char)(motor+97));
      }

      //  Set motor angle
      if(angle>=0 && angle<=180){  // set servo angle
        if(potMode){
          Serial.println();
          Serial.println("\nPotentiometer control disabled");
        }
        potMode=false;
        Serial.print("\nMotor ");
        Serial.print((char)(motor+97));
        Serial.print(" -> ");
        Serial.println(angle);
        encAngle = angle;
        myservo.write(encAngle);
        servos[motor] = angle;
        pwm.setPWM(motor, 0, angleToPulse(servos[motor]));
      }
      if(angle>180)
        Serial.println("\nInsert angle value between 0 and 180");
        
      //  Print potentiometer angle
      if(angle==-2){
        Serial.print("\nMotor ");
        Serial.print((char)(motor+97));
        Serial.print(" -> ");
        Serial.println(servos[motor]);
        if(potMode)
          angle=-1;
      }
    }
  }

  //  if in potentiometer mode
  if(potMode){
    
    val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
    val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
    encAngle = count * 5;
    myservo.write(encAngle);                  // sets the servo position according to the scaled value
    offpot = val + offset;  // offset updated when switching to potmode
    if(encAngle>=0 && encAngle<=180 && motor >= 0){
      servos[motor] = encAngle;
      pwm.setPWM(motor, 0, angleToPulse(servos[motor]));
    }

    //  angle monitor
    unsigned long currentMillis = millis();
    if (precValue != encAngle) {
      newline++;
      if(newline > 20){
        Serial.print("\n");
        newline = 0;
      }
      Serial.print(" - ");
      if((motor == 'q'-97) || (motor == -99))
        Serial.print(encAngle);
      else
        Serial.print(servos[motor]);
      precValue = encAngle;
    }
  }

  if (!digitalRead(SW) && count != 0) 
  {
    count = 18;
    Serial.print("\nPOTENTIOMETER RESETTED TO 90 DEGREES");
  }
  
  delay(15);
}






/*
 * angleToPulse(int ang)
 * gets angle in degree and returns the pulse width
 * also prints the value on seial monitor
 * written by Ahmad Nejrabi for Robojax, Robojax.com
 */
int angleToPulse(int ang){
   int pulse = map(ang,0, 180, SERVOMIN,SERVOMAX);// map angle of 0 to 180 to Servo min and Servo max
   return pulse;
}

void ClockChanged()
{
int clkValue = digitalRead(CLK);
int dtValue = digitalRead(DT);

if ((clkValue == CW_START_CLK) && (dtValue == CW_START_DT))
{
if (stage == -1)
{
stage = 0;
}
else if (stage == 1)
{
stage = 0;
if(count < 36)
  count++;
}
}
else if ((clkValue == CW_END_CLK) && (dtValue == CW_END_DT))
{
if (stage == 0)
{
stage = 1;
}
}
else if ((clkValue == CW_START_CLK) && (dtValue == CCW_START_DT))
{
if (stage == -1)
{
stage = 0;
}
else if (stage == 1)
{
stage = 0;
if(count > 0)
  count--;
}
}
else if ((clkValue == CCW_END_CLK) && (dtValue == CCW_END_DT))
{
if (stage == 0)
{
stage = 1;
}
}
}
