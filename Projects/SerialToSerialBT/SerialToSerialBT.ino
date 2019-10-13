#include "IRremote.h"
#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run `make menuconfig` to and enable it
#endif

//  BT variables
BluetoothSerial SerialBT;
const long interval = 500;   
unsigned long previousMillis = 0;
const int btPin = 13;

//  IR variables
//const int irReceiverPin = 2;
const int irPin = 15; //receiver module S pin is connected to arduino D8
//int num = 0;
long color=255;  
IRsend irsend;
//IRrecv irrecv(irReceiverPin);  
//decode_results results;   


//  SETUP
void setup() {
  Serial.begin(115200);
  SerialBT.begin("ESP32test"); //Bluetooth device name
  Serial.println("The device started, now you can pair it with bluetooth!");
  pinMode(btPin, OUTPUT);
  pinMode(irPin, OUTPUT);
  //irrecv.enableIRIn(); 
}


//  LOOP
void loop() {
  unsigned long currentMillis = millis();
  
  /*if (irrecv.decode(&results) && results.value != 0xFFFFFFFF) {
    Serial.print("IR Code: ");
    Serial.print(results.value, HEX);
    SerialBT.println();
    SerialBT.print("IR Code: ");
    SerialBT.print(results.value);
    SerialBT.println();
    previousMillis = currentMillis;
  }*/
  
  if (Serial.available()) {
    color = SerialBT.parseInt();
    SerialBT.write(Serial.read());
    digitalWrite(btPin, HIGH);
    previousMillis = currentMillis;
    switch(color){
      case 0:  // OFF
        irsend.sendNEC(0xFF609F, 32);
        break;
      case 1:  // ON
        irsend.sendNEC(0xFFE01F, 32);
        break;
      case 2:  // RED
        irsend.sendNEC(0xFF10EF, 32);
        break;
      case 3:  // R1
        irsend.sendNEC(0xFF30CF, 32);
        break;
      case 4:  // R2
        irsend.sendNEC(0xFF08F7, 32);
        break;
      case 5:  // R4
        irsend.sendNEC(0xFF28D7, 32);
        break;
      case 6:  // R5
        irsend.sendNEC(0xFF18E7, 32);
        break;
      case 7:  // GREEN
        irsend.sendNEC(0xFF906F, 32);
        break;
      case 8:  // G1
        irsend.sendNEC(0xFFB04F, 32);
        break;
      case 9:  // G2
        irsend.sendNEC(0xFF8877, 32);
        break;
      case 10:  // G3
        irsend.sendNEC(0xFFA857, 32);
        break;
      case 11:  // G4
        irsend.sendNEC(0xFF9867, 32);
        break;
      case 12:  // BLUE
        irsend.sendNEC(0xFF50AF, 32);
        break;
      case 13:  // B1
        irsend.sendNEC(0xFF708F, 32);
        break;
      case 14:  // B2
        irsend.sendNEC(0xFF48B7, 32);
        break;
      case 15:  // B3
        irsend.sendNEC(0xFF6897, 32);
        break;
      case 16:  // B4
        irsend.sendNEC(0xFF58A7, 32);
        break;
      case 17:  // WHITE
        irsend.sendNEC(0xFFC03F, 32);
        break;
      default:
        break;
    }
  }

  if (SerialBT.available()) {
    color = SerialBT.parseInt();
    SerialBT.read();
    Serial.print("Bluetooth SendIR: ");
    Serial.println(color);
    digitalWrite(btPin, HIGH);
    previousMillis = currentMillis;
    switch(color){
      case 0:  // OFF
        irsend.sendNEC(0xFF609F, 32);
        break;
      case 1:  // ON
        irsend.sendNEC(0xFFE01F, 32);
        break;
      case 2:  // RED
        irsend.sendNEC(0xFF10EF, 32);
        break;
      case 3:  // R1
        irsend.sendNEC(0xFF30CF, 32);
        break;
      case 4:  // R2
        irsend.sendNEC(0xFF08F7, 32);
        break;
      case 5:  // R4
        irsend.sendNEC(0xFF28D7, 32);
        break;
      case 6:  // R5
        irsend.sendNEC(0xFF18E7, 32);
        break;
      case 7:  // GREEN
        irsend.sendNEC(0xFF906F, 32);
        break;
      case 8:  // G1
        irsend.sendNEC(0xFFB04F, 32);
        break;
      case 9:  // G2
        irsend.sendNEC(0xFF8877, 32);
        break;
      case 10:  // G3
        irsend.sendNEC(0xFFA857, 32);
        break;
      case 11:  // G4
        irsend.sendNEC(0xFF9867, 32);
        break;
      case 12:  // BLUE
        irsend.sendNEC(0xFF50AF, 32);
        break;
      case 13:  // B1
        irsend.sendNEC(0xFF708F, 32);
        break;
      case 14:  // B2
        irsend.sendNEC(0xFF48B7, 32);
        break;
      case 15:  // B3
        irsend.sendNEC(0xFF6897, 32);
        break;
      case 16:  // B4
        irsend.sendNEC(0xFF58A7, 32);
        break;
      case 17:  // WHITE
        irsend.sendNEC(0xFFC03F, 32);
        break;
      default:
        break;
    }
  }   
  color = 255;
  
  if (currentMillis - previousMillis >= interval) {
    digitalWrite(btPin, LOW);
    //irsend.sendNEC(0xFF906F, 32);
    //irrecv.resume();
  }

  
  delay(20);
}


void send(long value){
  switch(value){
      case 0:  // OFF
        irsend.sendNEC(0xFF609F, 32);
        break;
      case 1:  // ON
        irsend.sendNEC(0xFFE01F, 32);
        break;
      case 2:  // RED
        irsend.sendNEC(0xFF10EF, 32);
        break;
      case 3:  // R1
        irsend.sendNEC(0xFF30CF, 32);
        break;
      case 4:  // R2
        irsend.sendNEC(0xFF08F7, 32);
        break;
      case 5:  // R4
        irsend.sendNEC(0xFF28D7, 32);
        break;
      case 6:  // R5
        irsend.sendNEC(0xFF18E7, 32);
        break;
      case 7:  // GREEN
        irsend.sendNEC(0xFF906F, 32);
        break;
      case 8:  // G1
        irsend.sendNEC(0xFFB04F, 32);
        break;
      case 9:  // G2
        irsend.sendNEC(0xFF8877, 32);
        break;
      case 10:  // G3
        irsend.sendNEC(0xFFA857, 32);
        break;
      case 11:  // G4
        irsend.sendNEC(0xFF9867, 32);
        break;
      case 12:  // BLUE
        irsend.sendNEC(0xFF50AF, 32);
        break;
      case 13:  // B1
        irsend.sendNEC(0xFF708F, 32);
        break;
      case 14:  // B2
        irsend.sendNEC(0xFF48B7, 32);
        break;
      case 15:  // B3
        irsend.sendNEC(0xFF6897, 32);
        break;
      case 16:  // B4
        irsend.sendNEC(0xFF58A7, 32);
        break;
      case 17:  // WHITE
        irsend.sendNEC(0xFFC03F, 32);
        break;
      default:
        break;
    }
}
