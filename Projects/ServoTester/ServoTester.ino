/*
 Control various servos one at a time using a potentiometer or serial input angle
*/

#include <Servo.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)
#define NONE -99

Servo myservo;  // for use without drive, signal on pin 9
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// MOTOR STARTING POSITIONS
int servos[16] = {109, 90, 60, 40, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};

// Potentiometer variables
int potpin = 0;  // analog pin used to connect the potentiometer
int offset = 0;  // motor - potpin
int offpot = 0;  // potpin + offset
int val = 0;    // variable to read the value from the analog pin

// General variables
int angle = NONE;
int input;
String buf;
char motor = NONE;
bool potMode = true;

// Time interval checker variables for potentiometer angle monitor
unsigned long previousMillis = 0;
const long interval = 1000;


void setup() {
  myservo.attach(9);  // attaches the single servo on pin 9 to the servo object
  val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
  val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
  myservo.write(val);
  pwm.begin();
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  Serial.begin(9600);
  Serial.setTimeout(10); // readString reads until this timeout
  Serial.println("Servo controller: input -1 to use potentiometer, -2 to print current angle");
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
  //  if there was an input
  if(Serial.available()){
    buf = Serial.readString();
    input = buf.toInt();
    
    // if input was a char (clamps strings)
    if(input==0 && buf[0]!='0'){  
      if(buf[0]<97 || buf[0]>97+15){  // 97 is ASCII 'a'
        if(buf[0] == 'q'){
          Serial.println("Viewing values of motor q (D9)");
          motor = NONE;
        }
        else{
          Serial.println("Selected motor out of bounds, insert a letter among");
          Serial.println("a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q.");
        }
      }
      else{
        motor = buf[0]-97;
        Serial.print("Now using ");
        Serial.println((char)(motor+97));
      }
      angle=NONE;
      potMode = false;
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
        Serial.print("Switched to potentiometer control of motor ");
        Serial.println((char)(motor+97));
      }

      //  Set motor angle
      if(angle>=0 && angle<=180){  // set servo angle
        if(potMode){
          Serial.println();
          Serial.println("Potentiometer control disabled");
        }
        potMode=false;
        Serial.print("Motor ");
        Serial.print((char)(motor+97));
        Serial.print(" -> ");
        Serial.println(angle);
        val = angle;
        myservo.write(val);
        servos[motor] = angle;
        pwm.setPWM(motor, 0, angleToPulse(servos[motor]));
      }
      if(angle>180)
        Serial.println("Insert angle value between 0 and 180");
        
      //  Print potentiometer angle
      if(angle==-2){
        Serial.print("Motor ");
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
    myservo.write(val);                  // sets the servo position according to the scaled value
    offpot = val + offset;  // offset updated when switching to potmode
    if(offpot>=0 && offpot<=180 && motor >= 0){
      servos[motor] = offpot;
      pwm.setPWM(motor, 0, angleToPulse(servos[motor]));
    }

    //  angle monitor
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
      Serial.print(" - ");
      if((motor == 'q'-97) || (motor == -99))
        Serial.print(val);
      else
        Serial.print(servos[motor]);
      previousMillis = currentMillis;
    }
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
