#include <FastLED.h>
#define LED_PIN     7 //signal pin IMPORTANT PUT 330Ω BETWEEN THIS PIN AND LED STRIP SIGNAL
#define NUM_LEDS    240 //how many leds to account for
CRGB leds[NUM_LEDS];
int color[3] = {102, 51, 0}; //set the color here
void setup() {
  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS);
}
void loop() {
  for (int i = 80; i <= 120; i++) {
    leds[i] = CRGB ( color[0], color[1], color[2]);
    FastLED.show();
    delay(10);
  }
  for (int i = 20; i <= 60; i++) {
    leds[i] = CRGB ( color[0], color[1], color[2]);
    FastLED.show();
    delay(10);
  }/*
  for (int i = 360; i >= 0; i--) {
    leds[i] = CRGB ( 0, 0, 0);
    FastLED.show();
    delay(10);
  }*/
}
