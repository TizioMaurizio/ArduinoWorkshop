int redPin = 6;
int greenPin = 5;
int bluePin = 3;

void setup()
{
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin, OUTPUT);  
}
 
void loop()
{
  setColor(0,255,0);
  delay(1000);
  setColor(0,255,128);
  delay(1000);
  setColor(0,255,255);
  delay(1000);
  setColor(0,128,255);
  delay(1000);
  setColor(0,0,255);
  delay(1000);
  setColor(128,0,255);
  delay(1000);
  setColor(255,0,255);
  delay(1000);
  setColor(255,0,128);
  delay(1000);
  setColor(255,0,0);
  delay(1000);
  setColor(255,128,0);
  delay(1000);
  setColor(255,255,0);
  delay(1000);
  setColor(128,255,0);
  delay(1000);
}
 
void setColor(int red, int green, int blue)
{
  analogWrite(redPin, 255-red);
  analogWrite(greenPin, 255-green);
  analogWrite(bluePin, 255-blue);  
}
