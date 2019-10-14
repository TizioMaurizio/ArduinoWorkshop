/**IR Blaster
 * Connect signal to pin 3
 * reads an int from serial input and sends an hex code via IR 
 * you can generate the switch cases' code with IR Receiver
 */

#include <IRremote.h> //adds the library code to the sketch
char color=255, prev_color=255;      
IRsend irsend;                         
bool fire = false;
bool rdy = false;
const long interval = 100;
unsigned long currentMillis = 0, previousMillis = 0; 

void setup()
{
  Serial.begin(9600);
  pinMode(13, OUTPUT); 
}

void loop()
{
  currentMillis = millis();
  if(Serial.available()) {
    color = Serial.read();
    //Serial.print("SendIR: ");
    //Serial.print(color);
    fire = (color != prev_color) && (currentMillis - previousMillis >= interval);
  }
  if(fire){  // 8 9 : ; < = > ? @ A B (...)
    previousMillis = currentMillis;
    switch(color){
      case 90:  // OFF (enable with code 8)
        irsend.sendNEC(0xFF609F, 32);
        break;
      case 91:  // ON
        irsend.sendNEC(0xFFE01F, 32);
        break;
      case '0':  // RED
        irsend.sendNEC(0xFF10EF, 32);
        //Serial.print("Red");
        break;
      case 93:  // R1
        irsend.sendNEC(0xFF30CF, 32);
        break;
      case '7':  // R2
        irsend.sendNEC(0xFF08F7, 32);
        break;
      case 95:  // R4
        irsend.sendNEC(0xFF28D7, 32);
        break;
      case '3':  // YELLOW
        irsend.sendNEC(0xFF18E7, 32);
        //Serial.print("Yellow");
        break;
      case '2':  // GREEN
        irsend.sendNEC(0xFF906F, 32);
        //Serial.print("Green");
        break;
      case '8':  // G1
        irsend.sendNEC(0xFFB04F, 32);
        break;
      case 9:  // G2
        irsend.sendNEC(0xFF8877, 32);
        break;
      case 10:  // G3
        irsend.sendNEC(0xFFA857, 32);
        break;
      case '4':  // CYAN
        irsend.sendNEC(0xFF9867, 32);
        //Serial.print("Cyan");
        break;
      case '1':  // BLUE
        irsend.sendNEC(0xFF50AF, 32);
        //Serial.print("Blue");
        break;
      case 13:  // B1
        irsend.sendNEC(0xFF708F, 32);
        break;
      case '9':  // B2
        irsend.sendNEC(0xFF48B7, 32);
        break;
      case 15:  // B3
        irsend.sendNEC(0xFF6897, 32);
        break;
      case '5':  // PINK
        irsend.sendNEC(0xFF58A7, 32);
        //Serial.print("Pink");
        break;
      case '6':  // WHITE
        irsend.sendNEC(0xFFC03F, 32);
        //Serial.print("White");
        break;
      default:
        irsend.sendNEC(0xFFB04F, 32);
        break;
    }
  }
  prev_color = color;
  fire = false;
}
