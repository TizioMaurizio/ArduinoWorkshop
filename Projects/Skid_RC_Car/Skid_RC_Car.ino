#include <boarddefs.h>
#include <IRremote.h>
#include <IRremoteInt.h>
#include <ir_Lego_PF_BitStreamEncoder.h>
/*
 * Display number on seven segment display with Arduino
 * Written by Ahmad Shamshiri for Robojax.com
Date modified: Jun 11, 2018 at 17:20 at Ajax, Ontario, Canada
watch video instruction for this code:https://youtu.be/-g6Q9lSHDzg

Code is provided for free AS IS without warranty. 
You can share this acode as long as you keep the above note intact.
 */

const int A1A = 2;//define pin 2 for A1A
const int A1B = 3;//define pin 3 for A1B

const int B1A = 8;//define pin 8 for B1A
const int B1B = 9;//define pin 10 for B1B

const int irReceiverPin = 10; //receiver module S pin is connected to arduino D8
int num = 0;
boolean toggle = false;

IRrecv irrecv(irReceiverPin);  
decode_results results;  

void setup() {
  Serial.begin(9600);
  irrecv.enableIRIn(); 
  pinMode(B1A,OUTPUT);// define pin as output
  pinMode(B1B,OUTPUT);
  
  pinMode(A1A,OUTPUT);
  pinMode(A1B,OUTPUT);   
}

void loop() {
    if(Serial.available()){
      char a = (char)Serial.read();
      if(a == 'L' || a == 'R' || a == 'O'){
        Serial.print(a);  
        motorA(a);
        motorB(a);
      }
      Serial.flush();
    }
    if (irrecv.decode(&results) && results.value != 0xFFFFFFFF) {
    Serial.print("    case ");
    Serial.print(num, DEC);
    Serial.print(":  // ");
    Serial.println();
    Serial.print("      irsend.sendNEC(0x");
    Serial.print(results.value, HEX);
    Serial.print(", 32);");
    Serial.println();
    Serial.print("      break;");
    Serial.println();
    num++;
    delay(100);
    irrecv.resume();
    switch(results.value){
          case 0xFFA857:  // DX
          motorA('R');
          motorB('L');
          toggle = false;
          break;
          case 0xFF28D7:  // RX
          motorA('L');
          motorB('R');
          toggle = false;
          break;
          case 0xFFC837:  //CENTER (back)
          motorA('O');
          motorB('O');
          toggle = false;
          break;
          case 0xFF6897:  //THROTTLE TOGGLE
            toggle = !toggle;
            if(!toggle){
              motorA('O');
              motorB('O');
            }
            else{
              motorA('L');
              motorB('L');
            }
          break;
    }
  }
    /*motorA('R');// Turn motor A to RIGHT
    delay(2000);
     motorA('L');// Turn motor A to LEFT
    delay(2000);   
    motorA('O');// Turn motor A OFF
    delay(2000); 
     
    motorA('R');// Turn motor A to RIGHT
    motorB('R'); // Turn motor A to RIGHT 
    delay(2000);
    motorA('L');// Turn motor A to LEFT
    motorB('L');// Turn motor B to LEFT     
    delay(3000);
    motorA('O');// Turn motor A OFF
    motorB('O');// Turn motor B OFF
    delay(5000);*/
   
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
