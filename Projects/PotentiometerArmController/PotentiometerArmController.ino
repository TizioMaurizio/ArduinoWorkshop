/*
 Reads a SERVONUM sequence of 3 digits integers starting with s and ending with \n (like S090180150090090\n) and sets the angles on the servo drive (SDA -> A4, SCL -> A5)
 Message is received on softSerial on pins 10(RX) and 11(TX)
*/
#include <Servo.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <SoftwareSerial.h>

#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)
#define NONE -99
#define CW_START_CLK 0
#define CW_START_DT 0
#define CW_END_CLK 1
#define CW_END_DT 1
#define CCW_START_CLK 0
#define CCW_START_DT 1
#define CCW_END_CLK 1
#define CCW_END_DT 0

int SERVONUM = 16;
int RECLEN = SERVONUM*3+1; //account for \n
SoftwareSerial linkSerial(10, 11); // RX, TX
Servo myservo;  // for use without drive, signal on pin 9
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// MOTOR STARTING POSITIONS
int servos[16] = {90, 102, 121, 91, 80, 90, 90, 90, 90, 90, 90, 104, 95, 72, 73, 90};
//SERVO ARM
//Hand 'a' >=30
//Swing 'd' >=80

// Potentiometer variables
int potpin = 0;  // analog pin used to connect the potentiometer
int offset = 0;  // motor - potpin
int offpot = 0;  // potpin + offset
int val = 0;    // variable to read the value from the analog pin

//Encoder variables
//int CLK = 2;//CLK->D2
//int DT = 3;//DT->D3
//int SW = 4;//SW->D4
//const int interrupt0 = 0;
//int count = 18;
//int lastCLK = 0;
//int stage = -1; 
//int encAngle = 90;
//int precValue = 0;

// General variables
int angle = NONE;
int input;
String buf;
char motor = NONE;
bool potMode = true;
int newline = 0;
unsigned long previousCycle = 0;
unsigned long cycleTime = 0;

//Potentiometer variables
int potentiometers[16] = {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1}; //from hand to swing, initial value must be invalid
int correction[16] = {0, -10, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}; //
bool activated[16] = {false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false}; //all potentiometers do not control motors on start
//potentiometer pins: A0 hand, A1 writst, A2 elbow, A3 shoulder, A6 rotate (A4 and A5 used by Servo drive)
int LINK_THRESHOLD = 5; //soglia di agganciamento 5 gradi
unsigned long previousMillisPot = 0;

//Motor variables
int targetPoses[16] = {90, 102, 121, 91, 80, 90, 90, 90, 90, 90, 90, 104, 95, 72, 73, 90}; //from hand to swing
unsigned long previousMillis = 0;
const long INTERVAL = 14; //1 degree every 17ms (about 60 degrees per second) --NOTE one cycle seems to take around 10ms, lowering the value under that is harmful for performance
int increment = 2; //change this to speed up movement once interval is minimized
unsigned long currentMillis = millis();
int deltaMove;
bool speedSet = false;

void setup() {
  //myservo.attach(9);  // attaches the single servo on pin 9 to the servo object
  val = analogRead(potpin);            // reads the value of the potentiometer (value between 0 and 1023)
  val = map(val, 200, 800, 0, 180);     // scale it to use it with the servo (value between 0 and 180)
  /*myservo.write(encAngle);
  pinMode(SW, INPUT);
  digitalWrite(SW, HIGH);
  pinMode(CLK, INPUT);
  pinMode(DT, INPUT);
  attachInterrupt(interrupt0, ClockChanged, CHANGE);*/
  pwm.begin();
  pwm.setPWMFreq(60);  // Analog servos run at ~60 Hz updates
  Serial.begin(115200);
  linkSerial.begin(115200);
  Serial.setTimeout(5);
  linkSerial.setTimeout(10);
  //linkSerial.setTimeout(5);
  /*
  Serial.setTimeout(10); // readString reads until this timeout
  Serial.println("Servo controller: input -1 to use encoder, -2 to print current angle");
  Serial.println("else input a letter to choose the motor and an int to set angle");
  Serial.println("signal D9 is for use without servo drive (motor q)");
  Serial.println("Initializing motors to values ");*/
  for(int i=0; i<16; i++){  // power motors to starting position
    /*Serial.print((char)(97+i));
    Serial.print(":");
    Serial.print(servos[i]);
    Serial.print(' ');*/
    pwm.setPWM(i, 0, angleToPulse(servos[i]));
    targetPoses[i] = servos[i];
  }
  //Serial.println("start");
}

//All'avvio il controller viene ignorato se è in una posizione diversa da quella iniziale del braccio 
//per attivare il braccio occorre muovere ogni sua articolazione (potenziometro) finche essa non si raggiunge o supera l'angolo iniziale del rispettivo motore, 
//soddisfatta questa condizione il potenziometro legato a tale articolazione inizia a controllare il rispettivo motore (tolleranza +-5gradi)
void loop() {
  currentMillis = millis();
  
  //read angles every INTERVAL milliseconds
  previousMillisPot = currentMillis;
  //if(linkSerial.available()){
  if(Serial.available()){
    //if(linkSerial.read() != 's')
    if(Serial.read() != 's')
      return 0;
    //String serialResponse = linkSerial.readString();
    String serialResponse = Serial.readString();
    Serial.println(serialResponse);
    if(serialResponse.length() != RECLEN || serialResponse[RECLEN-1] != '\n'){
      //Serial.print(serialResponse);
      //Serial.print(serialResponse.length());
      //Serial.println(" Invalid string");
      Serial.println("Invalid string");
      return 0;
    }
    String str[SERVONUM] = {"","",""};
    for(int i=0; i<SERVONUM; i++){
      str[i] = "";
      for(int j=0; j<3; j++){
        str[i].concat(serialResponse[i*3+j]);
      }
    }
    for(int i=0; i<SERVONUM; i++){
      targetPoses[i] = str[i].toInt();
      //Serial.print(str[i]);
    }
    //Serial.print(str[1]);
    //Serial.println(str[2]);
    //Serial.println();
    //Serial.println("RECEIVED\n");
  }
  for(int i=0; i<5; i++){
    if(i == 4) i = 6;//l' ultimo pin analog è dopo la servo drive  ##################HARDCODED##################
    if(0 == 1);//i <= 3) i=i;
    else{
      //if(i==2){//i != 6 && i!= 0 && i!= 1
        val = analogRead(i);            // reads the value of the potentiometer (value between 0 and 1023)
        val = map(val, 0+171, 1023-170, 0, 180) + correction[i];     // scale it to use it with the servo (value between 0 and 180)
        potentiometers[i] = val + correction[i];
        if(val>=0 && val<=180){
            if(activated[i] == false){
              if(val >= servos[i] - LINK_THRESHOLD && val <= servos[i] + LINK_THRESHOLD) //range di agganciamento
                activated[i] = true; //attiva il potenziometro i
            }
            if(activated[i] == true){
              if(i == 6) i = 4;
              targetPoses[i] = val; //==potentiometers[i]
            }
         }
      //}
      //Serial.print(" p"); Serial.print(i); Serial.print(": ");  Serial.print(val); Serial.print(" "); Serial.print(activated[i]); Serial.print("  |"); if(i==4 || i==6) Serial.println();
    }
  }
  
  //update motor pose every INTERVAL milliseconds
  unsigned long deltaT = currentMillis - previousMillis;
  if (deltaT >= INTERVAL) {
    previousMillis = currentMillis;
    if(deltaT - INTERVAL > 3)
      Serial.println(deltaT);
    for(int i=0; i<16; i++){
      if(servos[i] != targetPoses[i]){
        deltaMove = targetPoses[i] - servos[i];
        if(abs(deltaMove) <= increment)
          servos[i] = targetPoses[i];
        else 
          servos[i] += increment * sign(deltaMove);
        pwm.setPWM(i, 0, angleToPulse(servos[i]));
      }
    }
  }
  /*cycleTime = currentMillis - previousCycle;
  if(currentMillis - previousCycle < INTERVAL)
    delay(INTERVAL - cycleTime);*/
}



int sign(int x){
  if (x > 0) return 1;
  if (x < 0) return -1;
  return 0;
}


/*
 * angleToPulse(int ang)
 * gets angle in degree and returns the pulse width
 * also prints the value on seial monitor
 * written by Ahmad Nejrabi for Robojax, Robojax.com
 */
int angleToPulse(int ang){
   int pulse = map(ang,0, 180, SERVOMIN,SERVOMAX);// map angle of 0 to 180 to Servo min and Servo max
   return pulse;
}
