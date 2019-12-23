#include <Servo.h>

#include <boarddefs.h>
#include <IRremote.h>
#include <IRremoteInt.h>
#include <ir_Lego_PF_BitStreamEncoder.h>

/**IR Receiver
 * Connect IR receiver signal to pin 8
 * when it receives a signal the program generates the code for a case to put into a switch and waits 500ms,
 * case integer and code hex are handled automatically
 * if it stops sending outputs reopen the serial monitor
 */


const int irReceiverPin = 8; //receiver module S pin is connected to arduino D8
int num = 0;
IRrecv irrecv(irReceiverPin);  
decode_results results;                          
Servo steer;
Servo power;
int angle = 90;
boolean toggle = false;


void setup()
{
  Serial.begin(9600);
  irrecv.enableIRIn();  
  power.attach(9);
  power.write(90);
  steer.attach(11);
  steer.write(105);
}
void loop(){
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
          steer.write(angle+=20);
          break;
          case 0xFF28D7:  // RX
          steer.write(angle-=20);
          break;
          case 0xFF48B7:  //CENTER
          angle=105;
          steer.write(angle);
          break;
          case 0xFF6897:  //THROTTLE TOGGLE
            toggle = !toggle;
            if(!toggle)
              power.write(90);
            else
              power.write(180);
          break;
    }
  }   
  if(Serial.available()){
      int a = Serial.parseInt();
      steer.write(a);
      Serial.parseInt();
      Serial.println(a, DEC);
    }
}
