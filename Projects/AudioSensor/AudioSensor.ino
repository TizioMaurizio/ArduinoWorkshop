int vol=0;
void setup () {
  Serial.begin (115200);
}
int i = 0;
int k = 0;
void loop () {
  vol = analogRead (0);
  if(abs(vol-315)>100)
    Serial.println (vol-315);
  else
    Serial.println (0);
  delay(5);
  i++;
  if(i%200==0){
    k++;
    if(k%2)
      Serial.println (1000);
    else
      Serial.println (0);
  }
}
