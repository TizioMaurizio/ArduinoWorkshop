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

char receivedChar;
boolean newData = false;
boolean incoming = false;


const int A1A = 2;//define pin 2 for A1A
const int A1B = 3;//define pin 3 for A1B

const int B1A = 8;//define pin 8 for B1A
const int B1B = 9;//define pin 10 for B1B

void setup() {
  // initialize serial:
  Serial.begin(115200);
  pinMode(B1A,OUTPUT);// define pin as output
  pinMode(B1B,OUTPUT);
  
  pinMode(A1A,OUTPUT);
  pinMode(A1B,OUTPUT);  
}

void loop() {
 recvOneChar();
 showNewData();
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
