#include <FastLED.h>
#define LED_PIN     7
#define NUM_LEDS    240
int colors[3]  = {255,0,255};
int originalColors[3]  = {255,0,255};
String str[3];
String serialResponse = "";
bool smooth = false;

int changingColor = 0;
int fixedColor = 2;
int colorChange = -1;

int colorButtonPin = 12;
int intensityButtonPin = 13;

float intensity = 1; 
float intensityDelta = -0.04;
bool changeIntensity = false;

CRGB leds[NUM_LEDS];
void setup() {
  Serial.begin(9600);
  Serial.setTimeout(5);
  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS);
  pinMode(colorButtonPin, INPUT_PULLUP);
  pinMode(intensityButtonPin, INPUT_PULLUP);
}
void loop() {
  // Read the value of the input. It can either be 1 or 0
  int colorValue = digitalRead(colorButtonPin);
  int intensityValue = digitalRead(intensityButtonPin);
  
  if (colorValue == LOW){
    // If button pushed, turn LED on
    smooth = true;
    changeIntensity = false;
    Serial.println("color");
  }
  else{
    smooth = false;
  }
  
  if (intensityValue == LOW){
    // If button pushed, turn LED on
    changeIntensity = true;
    smooth = false;
    Serial.println("intensity");
  }
  else{
    changeIntensity = false;
  }
  /*if (colorValue == HIGH){
    // If button pushed, turn LED on
    smooth = true;
    changeIntensity = false;
  }
  else{
    smooth = false;
  }
  if (intensityValue == HIGH){
    // If button pushed, turn LED on
    changeIntensity = true;
    smooth = false;
  }
  else{
    changeIntensity = false;
    intensity = 0.99;
  }*/
  
  if(false && Serial.available()){
    char charInput = Serial.read();
    Serial.readString();
    if(charInput=='a'){
      smooth = true;
    }
    if(charInput=='b'){
      smooth = false;
    }
    if(charInput=='i'){
      changeIntensity = true;
      intensity = 0.99;
    }
    if(charInput=='0'){
      changeIntensity = false;
      smooth = false;
      intensity = 1;
    }
    //b 255, scende r [- 0 1]
    //b 255, cresce g [0 + 1]
    //g 255, scende b [0 1 -]
    //g 255, cresce r [+ 1 0]
    //r 255, scende g [1 - 0]
    //r 255, cresce b [1 0 +]
    
  }
  if(smooth){
      changeIntensity = false;
      if(colorChange<0 && colors[changingColor]<=0){
        changingColor++;
        changingColor=changingColor%3;
        colorChange = +5;
      }
      if(colorChange>0 && colors[changingColor]>=255){
        changingColor++;
        changingColor=changingColor%3;
        colorChange = -5;
        fixedColor--;
        fixedColor=fixedColor%3;
        colors[fixedColor] = 255;
      }
      colors[changingColor] += colorChange;
      Serial.print(colors[0]);
      Serial.print(",");
      Serial.print(colors[1]);
      Serial.print(",");
      Serial.println(colors[2]);
      originalColors[0] = colors[0];
      originalColors[1] = colors[1];
      originalColors[2] = colors[2];
    }
    if(changeIntensity){
      smooth = false;
      if(intensity <= 0){
        intensityDelta = 0.04;
      }
      if(intensity >= 1){
        intensityDelta = -0.04;
      }
      colors[0] = originalColors[0]*intensity;
      colors[1] = originalColors[1]*intensity;
      colors[2] = originalColors[2]*intensity;
      intensity += intensityDelta;
      Serial.print(colors[0]);
      Serial.print(",");
      Serial.print(colors[1]);
      Serial.print(",");
      Serial.println(colors[2]);
      delay(25);
    }
    
    delay(1);
    for (int i = 0; i <= 28; i+=1) {
      leds[i] = CRGB ( int(colors[0]), int(colors[1]), int(colors[2]));
      //leds[i+1] = CRGB ( 255, 255, 255);
      
      //delay(40);
    } 
    FastLED.show();
  /*leds[i] = CRGB ( int(colors[0]), int(colors[1]), int(colors[2]));
  for (int i = 19; i >= 0; i--) {
    leds[i] = CRGB ( 255, 0, 0);
    FastLED.show();
    delay(40);
  }*/
}
