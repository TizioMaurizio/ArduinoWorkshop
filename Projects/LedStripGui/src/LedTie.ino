#include <Arduino.h>
#include <FastLED.h>

#define LED_PIN 7
#define NUM_LEDS 30

//communicate with this pythjon gui:
/*  
    def send_color(self, event):
        color = "r" + str(self.r.get()) + "g" + str(self.g.get()) + "b" + str(self.b.get())
        self.serial.write(color.encode())

    def receive_ack(self):
        if self.serial.in_waiting:
            self.ack.config(text=self.serial.readline().decode())
        self.root.after(100, self.receive_ack)
        */

CRGB leds[NUM_LEDS];
//prevtime
unsigned long prevtime = 0;

void setup()
{
  Serial.begin(9600);
  Serial.setTimeout(5);
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
}

void loop()
{
  if (Serial.available())
  {
    //read everything
    String input = Serial.readString();
    
    //Serial.println(input);
    //set color to last r0g120b154 in input
    int r = input.substring(input.lastIndexOf("r") + 1, input.lastIndexOf("g")).toInt();
    int g = input.substring(input.lastIndexOf("g") + 1, input.lastIndexOf("b")).toInt();
    int b = input.substring(input.lastIndexOf("b") + 1).toInt();
    //print input
    //if input length is more than 6
    if (input.length() > 6)
    {
      //serial print if 100ms have passed
      if (millis() - prevtime > 100)
      {
        Serial.print("r");
        Serial.print(r);
        Serial.print("g");
        Serial.print(g);
        Serial.print("b");
        Serial.println(b);
        prevtime = millis();

        for (int i = 0; i < NUM_LEDS; i++)
        {
          leds[i] = CRGB(r, g, b);
        }
        FastLED.show();
      }
    }
  }
}