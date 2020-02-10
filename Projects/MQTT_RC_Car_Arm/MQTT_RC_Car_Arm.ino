/*
  Serial Event example

  When new serial data arrives, this sketch adds it to a String.
  When a newline is received, the loop prints the string and clears it.

  A good test for this is to try it with a GPS receiver that sends out
  NMEA 0183 sentences.

  NOTE: The serialEvent() feature is not available on the Leonardo, Micro, or
  other ATmega32U4 based boards.

  created 9 May 2011
  by Tom Igoe

  This example code is in the public domain.

  http://www.arduino.cc/en/Tutorial/SerialEvent
*/
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)

char receivedChar;
int potpin = 0;  // analog pin used to connect the potentiometer
int val;    // variable to read the value from the analog pin
boolean newData = false;
boolean incoming = false;
uint8_t servonum = 0;
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

const int A1A = 2;//define pin 2 for A1A
const int A1B = 3;//define pin 3 for A1B

const int B1A = 8;//define pin 8 for B1A
const int B1B = 9;//define pin 10 for B1B
int rotate = 90;
int joint1 = 90;
int joint2 = 90;
int hand = 180;

void setup() {
  // initialize serial:
  Serial.begin(115200);
  pinMode(B1A,OUTPUT);// define pin as output
  pinMode(B1B,OUTPUT);
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  pinMode(A1A,OUTPUT);
  pinMode(A1B,OUTPUT);  
  Serial.println("16 channel Servo test!");

  pwm.begin();
  
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates

  //yield();
}

void loop() {
 recvOneChar();
 showNewData();
 val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
  val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
  pwm.setPWM(15, 0, angleToPulse(180 - val) );
  pwm.setPWM(7, 0, angleToPulse(val) ); 
}

void recvOneChar() {
 if (Serial.available() > 0) {
 receivedChar = Serial.read();
 if(receivedChar == '&' || incoming){
  if(receivedChar == '&' && incoming)
    incoming = false;
  else{
    incoming = true;
    newData = true;
  }
 }
 }
}

/*
 * angleToPulse(int ang)
 * gets angle in degree and returns the pulse width
 * also prints the value on seial monitor
 * written by Ahmad Nejrabi for Robojax, Robojax.com
 */
int angleToPulse(int ang){
   int pulse = map(ang,0, 180, SERVOMIN,SERVOMAX);// map angle of 0 to 180 to Servo min and Servo max 
   Serial.print("Angle: ");Serial.print(ang);
   Serial.print(" pulse: ");Serial.println(pulse);
   return pulse;
}


void showNewData() {
 if (newData == true) {
 Serial.print(receivedChar);
         if(receivedChar == 'u'){
          motorA('L');
                      motorB('L');
                      Serial.println("Going Forward");
         }
         if(receivedChar == 'l'){
          motorA('L');
                  motorB('R');
                  Serial.println("Turning Right");
         }
         if(receivedChar == 'r'){
          motorA('R');
                  motorB('L');
                  Serial.println("Turning Left");
         }
         if(receivedChar == 's'){
          motorA('O');
                  motorB('O');
                  Serial.println("Stopping");
         }
         if(receivedChar == '0'){
          pwm.setPWM(0, 0, angleToPulse(rotate-=10) );
         }
         if(receivedChar == '1'){
          pwm.setPWM(0, 0, angleToPulse(rotate+=10) );
         }
         /*if(receivedChar == '2'){
          pwm.setPWM(7, 0, angleToPulse(joint1-=20) );
          pwm.setPWM(15, 0, angleToPulse(joint1-=20) );
         }
         if(receivedChar == '3'){
          pwm.setPWM(7, 0, angleToPulse(joint1+=20) );
          pwm.setPWM(15, 0, angleToPulse(joint1+=20) );
         }*/
         if(receivedChar == '4'){
          pwm.setPWM(13, 0, angleToPulse(joint2-=10) );
         }
         if(receivedChar == '5'){
          pwm.setPWM(13, 0, angleToPulse(joint2+=10) );
         }
         if(receivedChar == '6'){
          pwm.setPWM(12, 0, angleToPulse(hand-=10) );
         }
         if(receivedChar == '7'){
          pwm.setPWM(12, 0, angleToPulse(hand+=10) );
         }
 newData = false;
 }
}


/*
 * @motorA
 * activation rotation of motor A
 * d is the direction
 * R = Right
 * L = Left
 */
void motorA(char d)
{
  if(d =='R'){
    digitalWrite(A1A,LOW);
    digitalWrite(A1B,HIGH); 
  }else if (d =='L'){
    digitalWrite(A1A,HIGH);
    digitalWrite(A1B,LOW);    
  }else{
    //Robojax.com L9110 Motor Tutorial
    // Turn motor OFF
    digitalWrite(A1A,LOW);
    digitalWrite(A1B,LOW);    
  }
}// motorA end


/*
 * @motorB
 * activation rotation of motor B
 * d is the direction
 * R = Right
 * L = Left
 */
void motorB(char d)
{

    if(d =='R'){
      digitalWrite(B1A,LOW);
      digitalWrite(B1B,HIGH); 
    }else if(d =='L'){
      digitalWrite(B1A,HIGH);
      digitalWrite(B1B,LOW);    
    }else{
    //Robojax.com L9110 Motor Tutorial
    // Turn motor OFF      
      digitalWrite(B1A,LOW);
      digitalWrite(B1B,LOW);     
    }

}// motorB end 
