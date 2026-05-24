// ============================================================================
// F8620 USB Transmitter — Step 1: nRF24L01+ Hardware Check
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20 (install via Library Manager)
//
// PURPOSE: Verify the nRF24L01+ module is correctly wired and responding.
//          Do NOT proceed to protocol testing until this prints "nRF24 detected OK".
//
// WIRING (with adapter board — adapter handles 5V→3.3V regulation):
//   Arduino Uno        nRF24 Adapter Board
//   ──────────         ───────────────────
//   5V              →  VCC
//   GND             →  GND
//   D9              →  CE
//   D10             →  CSN / CS
//   D13             →  SCK
//   D11             →  MOSI
//   D12             →  MISO
//   (not connected) →  IRQ
//
// WIRING (bare nRF24 module — NO adapter):
//   [SAFETY] VCC must be 3.3V, NOT 5V! (nRF24L01+ max is 3.6V)
//   Arduino Uno        nRF24L01+ bare module
//   ──────────         ─────────────────────
//   3.3V            →  VCC  (+ 10µF cap across VCC-GND on module)
//   GND             →  GND
//   D9              →  CE
//   D10             →  CSN
//   D13             →  SCK
//   D11             →  MOSI
//   D12             →  MISO
//   (not connected) →  IRQ
//
// EXPECTED OUTPUT (Serial Monitor @ 115200):
//   nRF24 hardware check...
//   nRF24 detected OK
//   Data rate: 1MBPS
//   PA level: LOW
//   Channel: 2
//   Done. Ready for protocol testing.
//
// IF YOU SEE "nRF24 NOT detected" — DO NOT CONTINUE. Fix wiring first.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE = D9, CSN = D10

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("=== nRF24L01+ Hardware Check ==="));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("[FAIL] radio.begin() failed!"));
    Serial.println(F(""));
    Serial.println(F("Troubleshooting:"));
    Serial.println(F("  1. Check VCC: adapter=5V, bare module=3.3V"));
    Serial.println(F("  2. Check GND is connected"));
    Serial.println(F("  3. Check SPI: SCK=D13, MOSI=D11, MISO=D12"));
    Serial.println(F("  4. Check CE=D9, CSN=D10"));
    Serial.println(F("  5. Add 10uF cap across VCC-GND on module"));
    Serial.println(F("  6. Try a different nRF24 module (they can be DOA)"));
    while (1) {
      delay(1000);
    }
  }

  if (radio.isChipConnected()) {
    Serial.println(F("[OK] nRF24 detected OK"));
  } else {
    Serial.println(F("[FAIL] nRF24 NOT detected — chip not responding"));
    Serial.println(F("  SPI communication failed. Check wiring."));
    while (1) {
      delay(1000);
    }
  }

  // Configure for basic test
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(2);
  radio.stopListening();

  // Print configuration
  Serial.println();
  Serial.print(F("Data rate: "));
  switch (radio.getDataRate()) {
    case RF24_250KBPS: Serial.println(F("250KBPS")); break;
    case RF24_1MBPS:   Serial.println(F("1MBPS"));   break;
    case RF24_2MBPS:   Serial.println(F("2MBPS"));   break;
  }

  Serial.print(F("PA level: "));
  switch (radio.getPALevel()) {
    case RF24_PA_MIN:  Serial.println(F("MIN (-18dBm)"));  break;
    case RF24_PA_LOW:  Serial.println(F("LOW (-12dBm)"));  break;
    case RF24_PA_HIGH: Serial.println(F("HIGH (-6dBm)"));  break;
    case RF24_PA_MAX:  Serial.println(F("MAX (0dBm)"));    break;
  }

  Serial.print(F("Channel: "));
  Serial.println(radio.getChannel());

  Serial.println();
  Serial.println(F("Done. Ready for protocol testing."));
  Serial.println(F("Next step: upload the multi-protocol sketch."));
}

void loop() {
  // Nothing to do — hardware check is one-shot
}
