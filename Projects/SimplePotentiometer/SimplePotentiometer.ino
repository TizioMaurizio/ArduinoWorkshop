float potValue = 0;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  Serial.println("begin");
  potValue = analogRead(A0);
}

void loop() {
  // put your main code here, to run repeatedly:
  Serial.println(int(potValue/1024*290));
  potValue = analogRead(A0);
  delay(40);
}
