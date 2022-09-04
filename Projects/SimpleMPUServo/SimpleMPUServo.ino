
/*
    MPU6050 Triple Axis Gyroscope & Accelerometer. Pitch & Roll & Yaw Gyroscope Example.
    Read more: http://www.jarzebski.pl/arduino/czujniki-i-sensory/3-osiowy-zyroskop-i-akcelerometr-mpu6050.html
    GIT: https://github.com/jarzebski/Arduino-MPU6050
    Web: http://www.jarzebski.pl
    (c) 2014 by Korneliusz Jarzebski
*/

//#include <Adafruit_PWMServoDriver.h>
#define SERVOMIN  125 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  575 // this is the 'maximum' pulse length count (out of 4096)
//Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

#include <Wire.h>
#include <MPU6050.h>
#include <Servo.h> 

MPU6050 mpu;

// Timers
unsigned long timer = 0;
float timeStep = 0.01;

// Pitch, Roll and Yaw values
float pitch = 0;
float roll = 0;
float yaw = 0;
int mouthPin = 4;
int yesPin = 5;
int nodPin = 6;
Servo mouth; 
Servo yes; 
Servo nod; 

void setup() 
{
  Serial.begin(115200);

  // Initialize MPU6050
  while(!mpu.begin(MPU6050_SCALE_2000DPS, MPU6050_RANGE_2G))
  {
    Serial.println("Could not find a valid MPU6050 sensor, check wiring!");
    delay(500);
  }
  //pwm.begin();
  //pwm.setPWMFreq(60);
  mouth.attach(mouthPin); 
  yes.attach(yesPin);   
  nod.attach(nodPin); 
  // Calibrate gyroscope. The calibration must be at rest.
  // If you don't want calibrate, comment this line.
  mpu.calibrateGyro();

  // Set threshold sensivty. Default 3.
  // If you don't want use threshold, comment this line or set 0.
  mpu.setThreshold(0);
}

void loop()
{
  timer = millis();

  // Read normalized values
  Vector norm = mpu.readNormalizeGyro();

  // Calculate Pitch, Roll and Yaw
  pitch = pitch + norm.YAxis * timeStep;
  roll = roll + norm.XAxis * timeStep;
  yaw = yaw + norm.ZAxis * timeStep;

  // Output raw
  Serial.print(" Pitch = ");
  Serial.print(pitch);
  Serial.print(" Roll = ");
  Serial.print(roll);  
  Serial.print(" Yaw = ");
  Serial.println(yaw);
  if(roll<=0 && roll>=-30)
    mouth.write(roll+30);
    //pwm.setPWM(0, 0, angleToPulse(roll+90));
  if(pitch<=45 && pitch>=-45)
    yes.write(pitch+45);//angleToPulse(pitch+90));
  if(yaw<=45 && yaw>=-45)
    nod.write(yaw+45);
    //pwm.setPWM(2, 0, angleToPulse(yaw+90));
  // Wait to full timeStep period
  delay((timeStep*1000) - (millis() - timer));
}

int angleToPulse(int ang){
   int pulse = map(ang,0, 180, SERVOMIN,SERVOMAX);// map angle of 0 to 180 to Servo min and Servo max
   return pulse;
}
