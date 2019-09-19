/**IR Blaster
 * Connect signal to pin 3
 * reads an int from serial input and sends an hex code via IR 
 * you can generate the switch cases' code with IR Receiver
 */

#include <IRremote.h> //adds the library code to the sketch
long color=255;      
IRsend irsend;                         

void setup()
{
  Serial.begin(9600);
  pinMode(3, OUTPUT); 
}
void loop(){
  if(Serial.available()) {
    color = Serial.parseInt();
    Serial.read();
    Serial.print("SendIR: ");
    Serial.println(color);
  }   
  
  switch(color){
    case 0:  // 
      irsend.sendNEC(0xFF609F, 32);
      break;
    case 1:  // 
      irsend.sendNEC(0xFFE01F, 32);
      break;
    case 2:  // 
      irsend.sendNEC(0xFF10EF, 32);
      break;
    case 3:  // 
      irsend.sendNEC(0xFF30CF, 32);
      break;
    case 4:  // 
      irsend.sendNEC(0xFF08F7, 32);
      break;
    case 5:  // 
      irsend.sendNEC(0xFF28D7, 32);
      break;
    case 6:  // 
      irsend.sendNEC(0xFF18E7, 32);
      break;
    case 7:  // 
      irsend.sendNEC(0xFF906F, 32);
      break;
    case 8:  // 
      irsend.sendNEC(0xFFB04F, 32);
      break;
    case 9:  // 
      irsend.sendNEC(0xFF8877, 32);
      break;
    case 10:  // 
      irsend.sendNEC(0xFFA857, 32);
      break;
    case 11:  // 
      irsend.sendNEC(0xFF9867, 32);
      break;
    case 12:  // 
      irsend.sendNEC(0xFF50AF, 32);
      break;
    case 13:  // 
      irsend.sendNEC(0xFF708F, 32);
      break;
    case 14:  // 
      irsend.sendNEC(0xFF48B7, 32);
      break;
    case 15:  // 
      irsend.sendNEC(0xFF6897, 32);
      break;
    case 16:  // 
      irsend.sendNEC(0xFF58A7, 32);
      break;
    case 17:  // 
      irsend.sendNEC(0xFFC03F, 32);
      break;
    default:
      break;
  }
  color = 255;
}
