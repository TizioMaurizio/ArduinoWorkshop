#include "SoftwareSerial.h"
#include "DFRobotDFPlayerMini.h"

// Use pins 2 and 3 to communicate with DFPlayer Mini
static const uint8_t PIN_MP3_TX = 2; // Connects to module's RX 
static const uint8_t PIN_MP3_RX = 3; // Connects to module's TX 
SoftwareSerial softwareSerial(PIN_MP3_RX, PIN_MP3_TX);

// Create the Player object
DFRobotDFPlayerMini player;

void setup() {
  // Init USB serial port for debugging
  Serial.begin(9600);
  // Init serial port for DFPlayer Mini
  softwareSerial.begin(9600);

  // Start communication with DFPlayer Mini
  if (player.begin(softwareSerial)) {
   Serial.println("OK");

    // Set volume to maximum (0 to 30).
    player.volume(30);
    // Play the first MP3 file on the SD card
  } else {
    Serial.println("Connecting to DFPlayer Mini failed!");
  }
}
int vol=0;
int i = 0;
int k = 0;
int threshold = 10;
void loop() {
  if(Serial.available()){
    player.next();
    threshold = Serial.read();
    Serial.read();
    Serial.println("Next sound");
  }
  vol = analogRead (0);
  if(abs(vol-315)>threshold*10)
    Serial.println (vol-315);
  else
    Serial.println (0);
  delay(5);
  i++;
  if(i%200==0){
    k++;
    if(k%2)
      Serial.println (1000);
    else
      Serial.println (0);
  }
}
