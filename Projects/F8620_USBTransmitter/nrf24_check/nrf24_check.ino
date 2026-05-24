// ============================================================================
// nRF24L01+ Hardware Check
// Verifies SPI communication with the radio module.
// Does NOT transmit any drone-control packets.
//
// Wiring:
//   CE  = D9
//   CSN = D10
//   MOSI = D11
//   MISO = D12
//   SCK  = D13
//   VCC  = 3.3V (use adapter/regulator; 5V will damage the module!)
//   GND  = GND
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE=D9, CSN=D10

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("=== nRF24L01+ HARDWARE CHECK ==="));
  Serial.println(F("CE=D9  CSN=D10  MOSI=D11  MISO=D12  SCK=D13"));
  Serial.println();

  bool ok = radio.begin();
  Serial.print(F("radio.begin(): "));
  Serial.println(ok ? F("OK") : F("FAILED"));

  bool connected = radio.isChipConnected();
  Serial.print(F("isChipConnected(): "));
  Serial.println(connected ? F("YES") : F("NO"));

  if (!ok || !connected) {
    Serial.println();
    Serial.println(F("*** RADIO NOT DETECTED ***"));
    Serial.println(F("Check wiring:"));
    Serial.println(F("  - VCC must be 3.3V (NOT 5V directly)"));
    Serial.println(F("  - GND connected"));
    Serial.println(F("  - CE  -> D9"));
    Serial.println(F("  - CSN -> D10"));
    Serial.println(F("  - SCK -> D13"));
    Serial.println(F("  - MOSI-> D11"));
    Serial.println(F("  - MISO-> D12"));
    Serial.println(F("  - Try adding 10uF capacitor across VCC/GND"));
    Serial.println(F("  - Try shorter wires"));
    while (1) { delay(1000); }
  }

  // Configure for basic test
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_LOW);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setChannel(76);

  Serial.println();
  Serial.println(F("--- Radio Details ---"));
  radio.printPrettyDetails();

  Serial.println();
  Serial.println(F("=== HARDWARE CHECK PASSED ==="));
  Serial.println(F("Radio is responding on SPI. Wiring is correct."));
  Serial.println(F("You can now upload f8620_usb_tx.ino"));
}

void loop() {
  // Nothing to do. Hardware check is one-shot.
  delay(5000);
  Serial.println(F("[idle - radio OK]"));
}
