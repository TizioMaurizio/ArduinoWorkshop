
void setup()
{
  Serial.begin(9600);
  pinMode(13, OUTPUT);
}
void loop(){
  if(Serial.available()) {
    int letter = Serial.read();
    if(letter == 'a'){
      Serial.print(letter);
      digitalWrite(13, HIGH);
      delay(500);
      digitalWrite(13, LOW);
    }
  }
}
