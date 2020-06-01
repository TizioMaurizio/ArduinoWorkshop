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

#include <boarddefs.h>
#include <IRremote.h>
#include <IRremoteInt.h>
#include <ir_Lego_PF_BitStreamEncoder.h>

#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)

const int irReceiverPin = 7;

char receivedChar;
int potpin = 0;  // analog pin used to connect the potentiometer
int val;    // variable to read the value from the analog pin
boolean newData = false;
boolean incoming = false;
boolean newIr = false;
boolean IRmode = true;
uint8_t servonum = 0;
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();
IRrecv irrecv(irReceiverPin);  
decode_results results;   

const int A1A = 2;//define pin 2 for A1A
const int A1B = 3;//define pin 3 for A1B

const int B1A = 8;//define pin 8 for B1A
const int B1B = 9;//define pin 10 for B1B
int rotate = 90;
int joint1 = 90;
int joint2 = 30;
int hand = 150;
int camVer = 160;
int camHor = 200;

bool potMode = false;


void setup() {
  // initialize serial:
  Serial.begin(115200);
  Serial.println("Begin");
  pinMode(B1A,OUTPUT);// define pin as output
  pinMode(B1B,OUTPUT);
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  pinMode(A1A,OUTPUT);
  pinMode(A1B,OUTPUT);  
  Serial.println("16 channel Servo test!");

  pwm.begin();
  
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates

  irrecv.enableIRIn();
  //yield();
}

void loop() {
 recvOneChar();
 showNewData();
 if (IRmode && irrecv.decode(&results) && results.value != 0xFFFFFFFF) {
    newIr = true;
    delay(100);
    irrecv.resume();
    Serial.print("Received IR: 0x");
    Serial.print(results.value, HEX);
    Serial.println();
    switch(results.value){
          case 0xFF40BF:  // DX
          receivedChar = 'r';
          break;
          case 0xFF00FF:  // SX
          receivedChar = 'l';
          break;
          case 0xFF08F7:  //UP
          receivedChar = 'u';
          break;
          case 0xFF50AF:  //DOWN
          receivedChar = 'b';
          break;
          case 0xFFE01F:  //STOP
            receivedChar = 's';
          break;
          case 0xFF6897:  //ROTATE+
            receivedChar = '1';
          break;
          case 0xFF28D7:  //ROTATE-
            receivedChar = '0';
          break;
          case 0xFF906F:  //JOINT1+
            receivedChar = '3';
          break;
          case 0xFF18E7:  //JOINT1-
            receivedChar = '2';
          break;
          case 0xFF10EF:  //JOINT2+
            receivedChar = '5';
          break;
          case 0xFF30CF:  //JOINT2-
            receivedChar = '4';
          break;
          case 0xFFB04F:  //HAND+
            receivedChar = '7';
          break;
          case 0xFF58A7:  //HAND-
            receivedChar = '6';
          break;
    }
    showNewData();
    newIr = false;
  }
 delay(10);
}

/* Potentiometer mode for testing, put in loop() to use
if(potMode){
  val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
  val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
  pwm.setPWM(15, 0, angleToPulse(180 - val) );
  pwm.setPWM(7, 0, angleToPulse(val) );
  pwm.setPWM(1, 0, angleToPulse(val) );
 }
*/

void recvOneChar() { //Checks if a '&' was received, if yes next character on serial will be stored
 IRmode = false;
 if (Serial.available() > 0) {
 receivedChar = Serial.read();
 if(receivedChar == '&' || incoming){
  if(incoming)
    incoming = false;
  else{
    incoming = true;
  }
  newData = true;
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
   /*Serial.print("Angle: ");Serial.print(ang);
   Serial.print(" pulse: ");Serial.println(pulse);*/
   return pulse;
}


void showNewData() {
 if (newData == true || newIr == true) {
 Serial.print(receivedChar);

         //MOVEMENT
         if(receivedChar == 'u'){
            forward();
            Serial.println("Going Forward");
         }
         if(receivedChar == 'l'){
            left();
            Serial.println("Turning Left");
         }
         if(receivedChar == 'r'){
            right();
            Serial.println("Turning Right");
         }
         if(receivedChar == 's'){
            coast();
            Serial.println("Stopping");
         }
         if(receivedChar == 'b'){
            back();
            Serial.println("Going back");
         }

         //ROTATE
         //start 90, max 150, min 30
         if(receivedChar == '0'){ 
          if(rotate > 10)
            pwm.setPWM(14, 0, angleToPulse(rotate-=20) );
          Serial.println(rotate);
         }
         if(receivedChar == '1'){
          if(rotate < 170)
            pwm.setPWM(14, 0, angleToPulse(rotate+=20) );
          Serial.println(rotate);
         }

         //JOINT 1
         //start 90, max 105, min 15
         if(receivedChar == '2'){
          if(joint1 > 0){
            joint1-=15;
            pwm.setPWM(7, 0, angleToPulse(joint1) );
            pwm.setPWM(15, 0, angleToPulse(180-joint1) );
          }
          Serial.println(joint1);
         }
         if(receivedChar == '3'){
          if(joint1 < 105){
            joint1+=15;
            pwm.setPWM(7, 0, angleToPulse(joint1) );
            pwm.setPWM(15, 0, angleToPulse(180-joint1) );
          }
          Serial.println(joint1);
         }

         //JOINT 2
         //start 30, max 240, min 0
         if(receivedChar == '4'){
          if(joint2 > 0)
            pwm.setPWM(13, 0, angleToPulse(joint2-=15) );
          Serial.println(joint2);
         }
         if(receivedChar == '5'){
          if(joint2 < 240)
            pwm.setPWM(13, 0, angleToPulse(joint2+=15) );
          Serial.println(joint2); 
         }
         
         //HAND
         //start 150, max 180, min 100
         if(receivedChar == '6'){ 
          if(hand > 100)
            pwm.setPWM(12, 0, angleToPulse(hand-=10) ); //OPEN
          Serial.println(hand);
         }
         if(receivedChar == '7'){
          if(hand < 180)
            pwm.setPWM(12, 0, angleToPulse(hand+=10) ); //CLOSE
          Serial.println(hand);
         }
         
         //CAMERA VERTICAL
         //start 160, max 230, min 70
         if(receivedChar == 'm'){
          if(camVer > 70)
            pwm.setPWM(0, 0, angleToPulse(camVer-=10) ); //UP
          Serial.println(camVer);
         }
         if(receivedChar == 'n'){
          if(camVer < 230)
            pwm.setPWM(0, 0, angleToPulse(camVer+=10) ); //DOWN
          Serial.println(camVer);
         }
         
         //CAMERA HORIZONTAL
         //start 200, max 250, min 150
         if(receivedChar == 'j'){ 
          if(camHor > 150)
            pwm.setPWM(1, 0, angleToPulse(camHor-=10) ); //LEFT
          Serial.println(camHor);
         }
         if(receivedChar == 'k'){
          if(camHor < 250)
            pwm.setPWM(1, 0, angleToPulse(camHor+=10) ); //RIGHT
          Serial.println(camHor);
         }

         //UNUSED
         /*if(receivedChar == 'y'){
          pwm.setPWM(10, 0, angleToPulse(hand-=15) );
         }
         if(receivedChar == 'y'){
          pwm.setPWM(10, 0, angleToPulse(hand+=15) );
         }*/
 newData = false;
 }
}


//MOVEMENT functions
void coast()
{
  motorA('O');
  motorB('O');
  delay(50);
}

void forward()
{
  coast();
  motorA('L');
  motorB('L');
}

void back()
{
  coast();
  motorA('R');
  motorB('R');
}

void right()
{
  coast();
  motorA('R');
  motorB('L');
}

void left()
{
  coast();
  motorA('L');
  motorB('R');
}


//MOTOR functions
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
