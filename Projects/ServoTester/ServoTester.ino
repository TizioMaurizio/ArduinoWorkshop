/*
 Control various servos one at a time using a potentiometer or serial input angle
*/

#include <Servo.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)

Servo myservo;  // create servo object to control a servo
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

int potpin = 0;  // analog pin used to connect the potentiometer
int val=0;    // variable to read the value from the analog pin
int angle=-1;
int check;
String buf;
char motor = 'a';
int servos[16];


void setup() {
  myservo.attach(9);  // attaches the servo on pin 9 to the servo object
  pwm.begin();
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  Serial.begin(9600);
  Serial.setTimeout(10); // readString reads until this timeout
  Serial.println("Servo controller: input -1 to use potentiometer, -2 to print current angle");
  Serial.println("else input a letter to choose the motor and an int to set angle");
  Serial.println("signal D9 is for use without servo drive");
}

void loop() {
  if(Serial.available()){
    buf = Serial.readString();
    check = buf.toInt();
    
    if(check==0 && buf[0]!='0'){  // if input was a char (clamps strings)
      motor=buf[0];
      Serial.print("Now using ");
      Serial.println(motor);
    }
    else{ // if input was integer
      angle = check;
      if(check>=0){
        Serial.print("Motor ");
        Serial.print(motor);
        Serial.print(" -> ");
        Serial.println(angle);
      }
      Serial.read();
      if(angle>=0 && angle<=180){ // set servo angle
        val = angle;
        myservo.write(val);
        servos[motor-97] = angle;
        pwm.setPWM(motor-97, 0, angleToPulse(servos[motor-97]));
      }
      if(angle==-2){  // print potentiometer angle
        Serial.print("Motor ");
        Serial.print(motor);
        Serial.print(" -> ");
        Serial.println(val);
        angle=-1;
      }
    }
  }
  if(angle==-1){
    val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
    val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
    myservo.write(val);                  // sets the servo position according to the scaled value
    pwm.setPWM((char)motor - 97, 0, angleToPulse(val));
    //Serial.println(val);
  }
  delay(15);                           // waits for the servo to get there
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
