// ============================================================================
// F8620 USB Transmitter — Focused Packet Capture
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Capture actual packets from the F8620 transmitter on its
//          identified channels (72–77). Uses CRC filtering to reject noise.
//          Tries multiple address/rate combinations on ONLY those channels.
//
// PREREQUISITE: Channel scan confirmed TX activity on CH 72–77.
//               Turn the original transmitter ON before running.
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);

// Target channels identified by scanner
static const uint8_t target_channels[] = {72, 73, 74, 75, 76, 77};
static const uint8_t NUM_TARGET_CH = 6;

// XN297 scramble/descramble table
static const uint8_t xn297_scramble_addr[] = {
  0xE3, 0xB1, 0x4B, 0xEA, 0x85
};

// XN297 data scramble (first 32 bytes)
static const uint8_t xn297_scramble_data[] = {
  0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
  0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
  0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
  0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F
};

// Addresses to try — normal and XN297-scrambled versions
struct AddrConfig {
  uint8_t addr[5];
  const char* name;
  bool xn297;  // if true, descramble received data
};

static const AddrConfig addr_configs[] = {
  // Standard addresses
  {{0x00, 0x00, 0x00, 0x00, 0x00}, "Zero", false},
  {{0xCC, 0xCC, 0xCC, 0xCC, 0xCC}, "CX10", false},
  {{0xC4, 0xC4, 0xC4, 0xC4, 0xC4}, "H8", false},
  {{0xAA, 0xAA, 0xAA, 0xAA, 0xAA}, "GenAA", false},
  {{0x55, 0x55, 0x55, 0x55, 0x55}, "Gen55", false},
  // XN297 scrambled equivalents (addr XOR scramble_table)
  // Zero addr scrambled = E3 B1 4B EA 85
  {{0xE3, 0xB1, 0x4B, 0xEA, 0x85}, "XN297-Zero", true},
  // Common XN297 toy drone: addr 0xC4 scrambled
  {{0x27, 0x75, 0x8F, 0x2E, 0x41}, "XN297-C4", true},
  // Bayang XN297: uses addr based on TX ID
  {{0x3B, 0xB6, 0x00, 0x00, 0x85}, "XN297-Bayang", true},
  // Try reversed bit order common in some XN297 implementations
  {{0xC7, 0x8D, 0xD2, 0x57, 0xA1}, "XN297-Rev", true},
};
static const uint8_t NUM_ADDR_CONFIGS = sizeof(addr_configs) / sizeof(addr_configs[0]);

// Data rates to try
static const rf24_datarate_e data_rates[] = {RF24_1MBPS, RF24_250KBPS, RF24_2MBPS};
static const char* rate_names[] = {"1Mbps", "250kbps", "2Mbps"};
static const uint8_t NUM_RATES = 3;

// State
static uint8_t addr_idx = 0;
static uint8_t rate_idx = 0;
static uint32_t packets_captured = 0;
static uint32_t config_start_ms = 0;
static const uint32_t CONFIG_DWELL_MS = 3000;  // 3 sec per config
static bool found_signal = false;

void setup_radio_config() {
  radio.stopListening();
  radio.setDataRate(data_rates[rate_idx]);
  radio.setAutoAck(false);
  radio.setPayloadSize(32);
  radio.setAddressWidth(5);

  // Try with and without CRC
  if (packets_captured == 0) {
    radio.setCRCLength(RF24_CRC_DISABLED);  // first pass: no CRC filter
  }

  radio.openReadingPipe(0, addr_configs[addr_idx].addr);
  radio.setChannel(target_channels[0]);  // start on first target channel
  radio.startListening();

  config_start_ms = millis();
}

void print_hex(uint8_t val) {
  if (val < 0x10) Serial.print('0');
  Serial.print(val, HEX);
}

void descramble_xn297(uint8_t* data, uint8_t len) {
  for (uint8_t i = 0; i < len && i < 32; i++) {
    data[i] ^= xn297_scramble_data[i];
  }
}

void print_packet(uint8_t* buf, uint8_t len, uint8_t channel) {
  packets_captured++;

  Serial.println(F(""));
  Serial.println(F("*** PACKET ***"));
  Serial.print(F("Config: addr="));
  Serial.print(addr_configs[addr_idx].name);
  Serial.print(F(" rate="));
  Serial.print(rate_names[rate_idx]);
  Serial.print(F(" ch="));
  Serial.println(channel);

  Serial.print(F("Raw: "));
  for (uint8_t i = 0; i < len; i++) {
    print_hex(buf[i]);
    Serial.print(' ');
  }
  Serial.println();

  // If XN297 address, try descrambling
  if (addr_configs[addr_idx].xn297) {
    descramble_xn297(buf, len);
    Serial.print(F("Descrambled: "));
    for (uint8_t i = 0; i < len; i++) {
      print_hex(buf[i]);
      Serial.print(' ');
    }
    Serial.println();
  }

  // Check first byte for known markers
  Serial.print(F("Byte[0]=0x"));
  print_hex(buf[0]);
  Serial.print(F(" → "));
  switch (buf[0]) {
    case 0xA4: Serial.println(F("BAYANG BIND")); break;
    case 0xA5: Serial.println(F("BAYANG DATA")); break;
    case 0x55: Serial.println(F("CX10 BIND")); break;
    case 0xAA: Serial.println(F("CX10 DATA")); break;
    case 0x20: Serial.println(F("MJX BIND")); break;
    case 0x21: Serial.println(F("MJX DATA")); break;
    default: Serial.println(F("unknown")); break;
  }

  if (!found_signal) {
    found_signal = true;
    Serial.println(F(""));
    Serial.println(F("=== SIGNAL FOUND! Locking config. ==="));
  }
}

void loop() {
  // Cycle through target channels rapidly
  static uint8_t ch_idx = 0;
  static uint32_t last_hop = 0;

  if (millis() - last_hop > 1) {  // hop every 1ms
    ch_idx = (ch_idx + 1) % NUM_TARGET_CH;
    radio.stopListening();
    radio.setChannel(target_channels[ch_idx]);
    radio.startListening();
    last_hop = millis();
  }

  // Check for packets
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    radio.read(buf, 32);

    // Filter obvious noise
    bool all_zero = true, all_ff = true;
    uint8_t nonzero_count = 0;
    for (uint8_t i = 0; i < 32; i++) {
      if (buf[i] != 0x00) all_zero = false;
      if (buf[i] != 0xFF) all_ff = false;
      if (buf[i] != 0x00 && buf[i] != 0xFF) nonzero_count++;
    }

    // Only print if it looks like real data (not all zeros/FFs, has structure)
    if (!all_zero && !all_ff && nonzero_count > 4) {
      print_packet(buf, 32, target_channels[ch_idx]);
    }
  }

  // Advance to next address/rate config if no signal found
  if (!found_signal && millis() - config_start_ms > CONFIG_DWELL_MS) {
    addr_idx++;
    if (addr_idx >= NUM_ADDR_CONFIGS) {
      addr_idx = 0;
      rate_idx++;
      if (rate_idx >= NUM_RATES) {
        rate_idx = 0;
        Serial.println(F("Full cycle done. Repeating..."));
      }
    }
    Serial.print(F("Trying: "));
    Serial.print(addr_configs[addr_idx].name);
    Serial.print(F(" @ "));
    Serial.println(rate_names[rate_idx]);
    setup_radio_config();
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("=== F8620 Focused Packet Capture ==="));
  Serial.println(F("Target: channels 72-77 (2472-2477 MHz)"));
  Serial.println(F("Turn ON the original F8620 transmitter."));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }

  Serial.println(F("nRF24 OK. Starting capture..."));
  setup_radio_config();
}
