// Simple ESP8266 serial test
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("=== ESP8266 ALIVE ===");
  Serial.print("Chip ID: ");
  Serial.println(ESP.getChipId(), HEX);
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
  Serial.println("Looping...");
}

void loop() {
  Serial.print("tick ");
  Serial.println(millis() / 1000);
  delay(1000);
}
