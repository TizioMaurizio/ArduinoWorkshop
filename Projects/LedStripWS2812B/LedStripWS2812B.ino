#include <FastLED.h>
#define LED_PIN     7
#define NUM_LEDS    240
int colors[3]  = {125,255,125};
String str[3];
String serialResponse = "";

CRGB leds[NUM_LEDS];
void setup() {
  Serial.begin(9600);
  Serial.setTimeout(5);
  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS);
}
void loop() {
  if(Serial.available()){
    serialResponse = Serial.readString();
    Serial.println(serialResponse);
    for(int i=0; i<3; i++){
      str[i] = "";
      for(int j=0; j<3; j++){
        str[i].concat(serialResponse[i*3+j]);
      }
      colors[i] = str[i].toInt();
    }
    for (int i = 50; i <= 150; i+=1) {
      leds[i] = CRGB ( int(colors[0]), int(colors[1]), int(colors[2]));
      //leds[i+1] = CRGB ( 255, 255, 255);
      
      //delay(40);
    } 
    FastLED.show();
  }
  
  /*leds[i] = CRGB ( int(colors[0]), int(colors[1]), int(colors[2]));
  for (int i = 19; i >= 0; i--) {
    leds[i] = CRGB ( 255, 0, 0);
    FastLED.show();
    delay(40);
  }*/
}
