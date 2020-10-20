#define CW_START_CLK 0
#define CW_START_DT 0
#define CW_END_CLK 1
#define CW_END_DT 1
#define CCW_START_CLK 0
#define CCW_START_DT 1
#define CCW_END_CLK 1
#define CCW_END_DT 0

int CLK = 2;//CLK->D2
int DT = 3;//DT->D3
int SW = 4;//SW->D4
const int interrupt0 = 0;
int count = 0;
int lastCLK = 0;

int stage = -1; 

void setup()
{
pinMode(SW, INPUT);
digitalWrite(SW, HIGH);
pinMode(CLK, INPUT);
pinMode(DT, INPUT);
attachInterrupt(interrupt0, ClockChanged, CHANGE);
Serial.begin(9600);
}

void loop()
{
if (!digitalRead(SW) && count != 0) 
{
count = 0;
Serial.print("count:");
Serial.println(count);
}
}


void ClockChanged()
{
int clkValue = digitalRead(CLK);
int dtValue = digitalRead(DT);

if ((clkValue == CW_START_CLK) && (dtValue == CW_START_DT))
{
if (stage == -1)
{
stage = 0;
}
else if (stage == 1)
{
stage = 0;
count++;
Serial.print("count:");
Serial.println(count);
}
}
else if ((clkValue == CW_END_CLK) && (dtValue == CW_END_DT))
{
if (stage == 0)
{
stage = 1;
}
}
else if ((clkValue == CW_START_CLK) && (dtValue == CCW_START_DT))
{
if (stage == -1)
{
stage = 0;
}
else if (stage == 1)
{
stage = 0;
count--;
Serial.print("count:");
Serial.println(count);
}
}
else if ((clkValue == CCW_END_CLK) && (dtValue == CCW_END_DT))
{
if (stage == 0)
{
stage = 1;
}
}
}
