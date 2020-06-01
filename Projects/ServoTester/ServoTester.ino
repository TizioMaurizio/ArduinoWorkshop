/*
 Control various servos one at a time using a potentiometer or serial input angle
*/

#include <Servo.h>

Servo myservo;  // create servo object to control a servo

int potpin = 0;  // analog pin used to connect the potentiometer
int val=0;    // variable to read the value from the analog pin
int angle=-1;
int check;
String buf;
char motor[1] = "a";

void setup() {
  myservo.attach(9);  // attaches the servo on pin 9 to the servo object
  Serial.begin(9600);
  Serial.setTimeout(10); // readString reads until this timeout
  Serial.println("Servo controller: input -1 to use potentiometer, -2 to print current angle");
  Serial.println("else input a letter to choose the motor and an int to set angle");
}

void loop() {
  if(Serial.available()){
    buf = Serial.readString();
    check = buf.toInt();
    
    if(check==0 && buf[0]!='0'){  // if input was a char (clamps strings)
      motor[0]=buf[0];
      Serial.print("Now using ");
      Serial.println(motor[0]);
    }
    else{ // if input was integer
      angle = check;
      if(check>=0){
        Serial.print("Motor ");
        Serial.print(motor[0]);
        Serial.print(" -> ");
        Serial.println(angle);
      }
      Serial.read();
    }
  }
  
  if(angle>=0 && angle<=180){ // set servo angle
    val = angle;
    myservo.write(val);
  }
  if(angle<0){
    if(angle==-1){
      val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
      val = map(val, 0, 1023, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
      myservo.write(val);                  // sets the servo position according to the scaled value
      //Serial.println(val);
    }
    if(angle==-2){  // print potentiometer angle
      Serial.print("Motor ");
      Serial.print(motor[0]);
      Serial.print(" -> ");
      Serial.println(val);
      angle=-1;
    }
  }
  delay(15);                           // waits for the servo to get there
}
