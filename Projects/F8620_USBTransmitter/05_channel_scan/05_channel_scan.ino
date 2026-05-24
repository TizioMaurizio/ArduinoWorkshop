// ============================================================================
// F8620 USB Transmitter — Channel Scanner (RF Power Detector)
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Find which 2.4 GHz channels have RF activity from the transmitter.
//          Uses the nRF24L01+ RPD (Received Power Detector) to measure signal
//          strength on each channel without needing to know the address.
//
// USAGE:
//   1. Upload this sketch
//   2. Open Serial Monitor @ 115200
//   3. FIRST: run with transmitter OFF to get a noise baseline
//   4. THEN: power ON the transmitter and see which channels light up
//
// The output shows a heatmap of channel activity. Channels with the
// transmitter's signal will show significantly more hits than noise floor.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE = D9, CSN = D10

static const uint8_t NUM_CHANNELS = 84;  // 2400–2483 MHz
static uint16_t channel_hits[NUM_CHANNELS];
static uint8_t scan_count = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("=== F8620 Channel Scanner ==="));
  Serial.println(F("Scanning 2400-2483 MHz for RF activity."));
  Serial.println(F(""));
  Serial.println(F("1. First scan: keep TX OFF (baseline)"));
  Serial.println(F("2. Second scan: turn TX ON"));
  Serial.println(F("3. Compare: new peaks = transmitter channels"));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }

  radio.setAutoAck(false);
  radio.stopListening();
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_MIN);

  memset(channel_hits, 0, sizeof(channel_hits));
}

void do_scan(uint16_t num_sweeps) {
  memset(channel_hits, 0, sizeof(channel_hits));

  for (uint16_t sweep = 0; sweep < num_sweeps; sweep++) {
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
      radio.setChannel(ch);
      radio.startListening();
      delayMicroseconds(170);  // needs 170us to detect signal
      radio.stopListening();

      if (radio.testRPD()) {  // Received Power Detector
        channel_hits[ch]++;
      }
    }
  }
}

void print_results(const char* label) {
  Serial.println();
  Serial.print(F("=== "));
  Serial.print(label);
  Serial.println(F(" ==="));
  Serial.println(F("Ch  MHz   Hits  Bar"));
  Serial.println(F("--- ----- ----- ----------------------------------------"));

  // Find max for scaling
  uint16_t max_hits = 1;
  for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
    if (channel_hits[ch] > max_hits) max_hits = channel_hits[ch];
  }

  // Only print channels with activity
  bool any_activity = false;
  for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
    if (channel_hits[ch] > 0) {
      any_activity = true;
      Serial.print(ch < 10 ? "  " : (ch < 100 ? " " : ""));
      Serial.print(ch);
      Serial.print(F("  "));
      Serial.print(2400 + ch);
      Serial.print(F("  "));
      Serial.print(channel_hits[ch] < 10 ? "    " :
                   (channel_hits[ch] < 100 ? "   " :
                   (channel_hits[ch] < 1000 ? "  " : " ")));
      Serial.print(channel_hits[ch]);
      Serial.print(F("  "));

      // Draw bar
      uint8_t bar_len = (uint32_t)channel_hits[ch] * 40 / max_hits;
      for (uint8_t i = 0; i < bar_len; i++) {
        Serial.print('#');
      }
      Serial.println();
    }
  }

  if (!any_activity) {
    Serial.println(F("  (no activity detected)"));
  }

  Serial.println();

  // Also print top 10 channels
  Serial.println(F("Top active channels:"));
  for (uint8_t rank = 0; rank < 10; rank++) {
    uint16_t best = 0;
    uint8_t best_ch = 0;
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
      if (channel_hits[ch] > best) {
        // Check not already printed
        bool already = false;
        // Simple approach: just find the max each time and zero it
        best = channel_hits[ch];
        best_ch = ch;
      }
    }
    if (best == 0) break;
    Serial.print(F("  #"));
    Serial.print(rank + 1);
    Serial.print(F(": CH"));
    Serial.print(best_ch);
    Serial.print(F(" ("));
    Serial.print(2400 + best_ch);
    Serial.print(F(" MHz) = "));
    Serial.print(best);
    Serial.println(F(" hits"));
    channel_hits[best_ch] = 0;  // remove for next iteration
  }
}

void loop() {
  scan_count++;

  Serial.print(F("Scan #"));
  Serial.print(scan_count);
  Serial.print(F(" — running 200 sweeps (takes ~3 sec)..."));

  do_scan(200);

  Serial.println(F(" done."));

  char label[32];
  snprintf(label, sizeof(label), "Scan #%d", scan_count);
  print_results(label);

  Serial.println();
  Serial.println(F("Next scan in 5 seconds..."));
  Serial.println(F("(Turn TX ON/OFF between scans to compare)"));
  delay(5000);
}
