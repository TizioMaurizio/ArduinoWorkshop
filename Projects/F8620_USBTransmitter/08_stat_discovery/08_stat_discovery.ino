// ============================================================================
// F8620 USB Transmitter — Statistical Address Discovery
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Discover the unknown TX address by statistical analysis.
//          Captures many packets with minimal filtering and finds byte
//          positions that have consistent values (= real address/header).
//
// METHOD:
//   - Listen on channel 75 (strongest from scan) with 3-byte addr width
//   - Use address {0xAA, 0xAA, 0xAA} (preamble continuation, max catch rate)
//   - Capture N packets, track first-8-byte value frequencies
//   - Report which byte positions have a dominant value
//
// With nRF24 addr={0xAA,0xAA,0xAA} (3-byte), after the real preamble+3xAA
// match, the "payload" bytes 0-1 are actually the remaining 2 address bytes,
// and bytes 2+ are the real payload.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// Configuration
static const uint8_t LISTEN_CHANNEL = 75;   // strongest from scan
static const uint8_t NUM_POSITIONS = 10;    // analyze first 10 bytes
static const uint16_t CAPTURE_COUNT = 200;  // packets per analysis round

// For each byte position, track the top-3 most common values
// (can't afford full 256-entry histogram on Uno)
struct ByteStat {
  uint8_t top_val[4];
  uint8_t top_count[4];
  uint16_t total;
};

static ByteStat stats[NUM_POSITIONS];
static uint16_t captured = 0;
static uint8_t phase = 0;  // 0=AA addr, 1=55 addr, 2=try 1-byte offsets
static uint8_t current_addr[3] = {0xAA, 0xAA, 0xAA};

void reset_stats() {
  for (uint8_t i = 0; i < NUM_POSITIONS; i++) {
    for (uint8_t j = 0; j < 4; j++) {
      stats[i].top_val[j] = 0;
      stats[i].top_count[j] = 0;
    }
    stats[i].total = 0;
  }
  captured = 0;
}

void update_stats(uint8_t* buf) {
  for (uint8_t pos = 0; pos < NUM_POSITIONS; pos++) {
    uint8_t val = buf[pos];
    stats[pos].total++;
    
    // Check if this value is already in top-4
    bool found = false;
    for (uint8_t j = 0; j < 4; j++) {
      if (stats[pos].top_val[j] == val && stats[pos].top_count[j] > 0) {
        stats[pos].top_count[j]++;
        found = true;
        // Bubble up if needed
        if (j > 0 && stats[pos].top_count[j] > stats[pos].top_count[j-1]) {
          uint8_t tv = stats[pos].top_val[j-1];
          uint8_t tc = stats[pos].top_count[j-1];
          stats[pos].top_val[j-1] = stats[pos].top_val[j];
          stats[pos].top_count[j-1] = stats[pos].top_count[j];
          stats[pos].top_val[j] = tv;
          stats[pos].top_count[j] = tc;
        }
        break;
      }
    }
    
    if (!found) {
      // Replace lowest entry if count >= lowest
      if (stats[pos].top_count[3] == 0) {
        stats[pos].top_val[3] = val;
        stats[pos].top_count[3] = 1;
      } else {
        // Just increment a general counter (we lose precision for rare values)
        // Replace slot 3 if current count = 1 (tie-break with new value)
        if (stats[pos].top_count[3] <= 1) {
          stats[pos].top_val[3] = val;
          stats[pos].top_count[3] = 1;
        }
      }
    }
  }
}

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

void print_stats() {
  Serial.println(F("\n--- Byte Position Analysis ---"));
  Serial.println(F("Pos | Top1 (cnt) | Top2 (cnt) | Top3 (cnt) | Confidence"));
  
  for (uint8_t pos = 0; pos < NUM_POSITIONS; pos++) {
    Serial.print(F("  "));
    Serial.print(pos);
    Serial.print(F(" | "));
    
    for (uint8_t j = 0; j < 3; j++) {
      Serial.print(F("0x"));
      print_hex(stats[pos].top_val[j]);
      Serial.print(F(" ("));
      Serial.print(stats[pos].top_count[j]);
      Serial.print(F(") | "));
    }
    
    // Confidence: if top value dominates, it's likely part of fixed structure
    uint16_t total = stats[pos].total;
    if (total > 0 && stats[pos].top_count[0] > 0) {
      uint8_t pct = (uint16_t)stats[pos].top_count[0] * 100 / total;
      Serial.print(pct);
      Serial.print(F("%"));
      if (pct > 30) Serial.print(F(" <<<"));  // flag promising positions
      if (pct > 50) Serial.print(F(" STRONG"));
    }
    Serial.println();
  }
}

void setup_listen() {
  radio.stopListening();
  radio.setChannel(LISTEN_CHANNEL);
  radio.setDataRate(RF24_1MBPS);
  radio.setCRCLength(RF24_CRC_DISABLED);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(3);
  radio.openReadingPipe(0, current_addr);
  radio.startListening();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println(F("=== F8620 Statistical Address Discovery ==="));
  Serial.println(F("Captures packets and finds repeating byte patterns."));
  Serial.println(F("Repeating bytes = address/header of real TX signal."));
  Serial.println(F("Turn ON the F8620 transmitter."));
  Serial.println();
  
  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }
  
  Serial.println(F("nRF24 OK."));
  reset_stats();
  setup_listen();
  
  Serial.print(F("Phase 0: addr={AA,AA,AA} ch="));
  Serial.println(LISTEN_CHANNEL);
  Serial.println(F("Capturing..."));
}

void loop() {
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);
    
    // Basic noise filter: not all same byte
    bool valid = false;
    uint8_t first = buf[0];
    for (uint8_t i = 1; i < 10; i++) {
      if (buf[i] != first) { valid = true; break; }
    }
    
    if (valid) {
      update_stats(buf);
      captured++;
      
      // Print first few raw captures for visual inspection
      if (captured <= 5 || captured % 50 == 0) {
        Serial.print(F("#"));
        Serial.print(captured);
        Serial.print(F(": "));
        for (uint8_t i = 0; i < 16; i++) {
          print_hex(buf[i]);
          Serial.print(' ');
        }
        Serial.println();
      }
      
      if (captured >= CAPTURE_COUNT) {
        print_stats();
        
        // Move to next phase
        phase++;
        reset_stats();
        
        if (phase == 1) {
          // Try with 0x55 address (other preamble polarity)
          current_addr[0] = 0x55;
          current_addr[1] = 0x55;
          current_addr[2] = 0x55;
          setup_listen();
          Serial.print(F("\nPhase 1: addr={55,55,55} ch="));
          Serial.println(LISTEN_CHANNEL);
        } else if (phase == 2) {
          // Try hopping all target channels with AA addr
          current_addr[0] = 0xAA;
          current_addr[1] = 0xAA;
          current_addr[2] = 0xAA;
          setup_listen();
          Serial.println(F("\nPhase 2: addr={AA,AA,AA} hopping ch72-77"));
        } else if (phase == 3) {
          // Try with 2-byte continuation + likely first byte from phase 0
          Serial.println(F("\nPhase 3: Using discovered byte patterns..."));
          // Use the most common byte[0] from phase 0 as part of addr
          current_addr[0] = 0xAA;
          current_addr[1] = 0xAA;
          current_addr[2] = stats[0].top_val[0]; // most common first payload byte
          setup_listen();
        } else {
          Serial.println(F("\n=== All phases complete. ==="));
          Serial.println(F("Look for byte positions with >30% confidence."));
          Serial.println(F("Those values form the TX address."));
          phase = 0;
          current_addr[0] = 0xAA;
          current_addr[1] = 0xAA;
          current_addr[2] = 0xAA;
          setup_listen();
        }
      }
    }
  }
  
  // Channel hopping in phase 2
  if (phase == 2) {
    static uint32_t last_hop = 0;
    static uint8_t ch_idx = 0;
    if (millis() - last_hop > 3) {
      ch_idx = (ch_idx + 1) % 6;
      static const uint8_t chs[] = {72, 73, 74, 75, 76, 77};
      radio.stopListening();
      radio.setChannel(chs[ch_idx]);
      radio.startListening();
      last_hop = millis();
    }
  }
}
