#include <Servo.h> 

Servo motor1;
int motor1Pin = 6;

void setup(){
  Serial.begin(9600);
  motor1.attach(motor1Pin); 
  Serial.println("begin");
}

void loop(){
  float value = analogRead(A0);
  int pot = analogRead(A1);
  Serial.print(value);
  Serial.print(",");
  pot = int(float(float(pot)*180)/1024);
  Serial.println(pot);
  motor1.write(pot); 
  
}
