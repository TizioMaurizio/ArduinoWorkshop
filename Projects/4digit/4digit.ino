int a = 13;
  int b = 2;
  int c = 3;
  int d = 4;
  int e = 5;
  int f = 6;
  int g = 7;
  int dp = 8;
  //Set anode interface
  int d4 = 9;
  int d3 = 10;
  int d2 = 11;
  int d1 = 12;
  //Set variable
  long n = 1230;
  int x = 100;
  int del = 55;  //Here to fine tune the clock   
  void setup()
  {
    Serial.begin(9600);
    pinMode(d1, OUTPUT);
    pinMode(d2, OUTPUT);
    pinMode(d3, OUTPUT);
    pinMode(d4, OUTPUT);
    pinMode(a, OUTPUT);
    pinMode(b, OUTPUT);
    pinMode(c, OUTPUT);
    pinMode(d, OUTPUT);
    pinMode(e, OUTPUT);
    pinMode(f, OUTPUT);
    pinMode(g, OUTPUT);
    pinMode(dp, OUTPUT);
  }
/////////////////////////////////////////////////////////////
/*
 *   1 
 * 6   2
 *   7
 * 5   3
 *   4  8
 */

    int input=4;
    int showing=0;
    unsigned long previousMillis = 0;
    
void loop()
{ 
  unsigned long currentMillis = millis();  
  show(showing);
  if(Serial.available()){
    showing=Serial.parseInt();
    Serial.read();
  }
  /*if (currentMillis - previousMillis >= 1000) {
    previousMillis = currentMillis;
    showing++;
  }*/
}
///////////////////////////////////////////////////////////////
void show(int n){
    int m=0,c=0,d=0,u=0;
    m=n/1000;
    if(m>0)
      Display(1,m);
    c=(n-m*1000)/100;
    if(c>0||m>0)
      Display(2,c);
    d=(n-m*1000-c*100)/10;
    if(d>0||c>0||m>0)
      Display(3,d);
    u=(n-m*1000-c*100-d*10);
    Display(4,u);
}
void WeiXuan(unsigned char n)//
{
    switch(n)
     {
  case 1: 
    digitalWrite(d1,LOW);
    digitalWrite(d2, HIGH);
    digitalWrite(d3, HIGH);
    digitalWrite(d4, HIGH);   
   break;
   case 2: 
    digitalWrite(d1, HIGH);
    digitalWrite(d2, LOW);
    digitalWrite(d3, HIGH);
    digitalWrite(d4, HIGH); 
      break;
    case 3: 
      digitalWrite(d1,HIGH);
     digitalWrite(d2, HIGH);
     digitalWrite(d3, LOW);
     digitalWrite(d4, HIGH); 
      break;
    case 4: 
     digitalWrite(d1, HIGH);
     digitalWrite(d2, HIGH);
     digitalWrite(d3, HIGH);
     digitalWrite(d4, LOW); 
      break;
        default :
           digitalWrite(d1, HIGH);
     digitalWrite(d2, HIGH);
     digitalWrite(d3, HIGH);
     digitalWrite(d4, HIGH);
        break;
    }
}
void Num_0()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, HIGH);
  digitalWrite(f, HIGH);
  digitalWrite(g, LOW);
  digitalWrite(dp,LOW);
}
void Num_1()
{
  digitalWrite(a, LOW);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, LOW);
  digitalWrite(e, LOW);
  digitalWrite(f, LOW);
  digitalWrite(g, LOW);
  digitalWrite(dp,LOW);
}
void Num_2()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, LOW);
  digitalWrite(d, HIGH);
  digitalWrite(e, HIGH);
  digitalWrite(f, LOW);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_3()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, LOW);
  digitalWrite(f, LOW);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_4()
{
  digitalWrite(a, LOW);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, LOW);
  digitalWrite(e, LOW);
  digitalWrite(f, HIGH);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_5()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, LOW);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, LOW);
  digitalWrite(f, HIGH);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_6()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, LOW);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, HIGH);
  digitalWrite(f, HIGH);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_7()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, LOW);
  digitalWrite(e, LOW);
  digitalWrite(f, LOW);
  digitalWrite(g, LOW);
  digitalWrite(dp,LOW);
}
void Num_8()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, HIGH);
  digitalWrite(f, HIGH);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Num_9()
{
  digitalWrite(a, HIGH);
  digitalWrite(b, HIGH);
  digitalWrite(c, HIGH);
  digitalWrite(d, HIGH);
  digitalWrite(e, LOW);
  digitalWrite(f, HIGH);
  digitalWrite(g, HIGH);
  digitalWrite(dp,LOW);
}
void Clear()  // Clear the screen
{
  digitalWrite(a, LOW);
  digitalWrite(b, LOW);
  digitalWrite(c, LOW);
  digitalWrite(d, LOW);
  digitalWrite(e, LOW);
  digitalWrite(f, LOW);
  digitalWrite(g, LOW);
  digitalWrite(dp,LOW);
}
void pickNumber(unsigned char n)//Choose the number of
{
  switch(n)
  {
   case 0:Num_0();
   break;
   case 1:Num_1();
   break;
   case 2:Num_2();
   break;
   case 3:Num_3();
   break;
   case 4:Num_4();
   break;
   case 5:Num_5();
   break;
   case 6:Num_6();
   break;
   case 7:Num_7();
   break;
   case 8:Num_8();
   break;
   case 9:Num_9();
   break;
   default:Clear();
   break; 
  }
}
void Display(unsigned char x, unsigned char Number)//Show that x is the coordinate, Number is the number
{
  WeiXuan(x);
  pickNumber(Number);
 delay(1);
 Clear() ; //Vanishing
}
