// ============================================================================
// F8620 USB Transmitter — RF Sniffer
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Capture packets from the original F8620 transmitter to identify
//          the protocol, data rate, address, channel, and packet format.
//
// USAGE:
//   1. Upload this sketch
//   2. Open Serial Monitor @ 115200
//   3. Power ON the original F8620 transmitter
//   4. The sniffer scans all channels and data rates
//   5. When packets are found, it prints the raw data
//
// The sniffer tries:
//   - 1Mbps and 250kbps data rates
//   - Channels 0–83
//   - Multiple common bind addresses (including XN297 scrambled)
//   - Promiscuous mode (short address) to catch anything
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE = D9, CSN = D10

// Common bind addresses used by toy drone protocols
static const uint8_t NUM_ADDRESSES = 8;
static const uint8_t addresses[][5] = {
  {0x00, 0x00, 0x00, 0x00, 0x00},  // Bayang / E010
  {0xCC, 0xCC, 0xCC, 0xCC, 0xCC},  // CX-10
  {0xC4, 0xC4, 0xC4, 0xC4, 0xC4},  // H8 mini
  {0x06, 0x06, 0x06, 0x06, 0x06},  // Syma
  {0x6D, 0x6A, 0x73, 0x73, 0x73},  // MJX
  {0xA1, 0xA1, 0xA1, 0xA1, 0xA1},  // Some XN297 variants
  {0x55, 0x55, 0x55, 0x55, 0x55},  // Generic
  {0xAA, 0xAA, 0xAA, 0xAA, 0xAA},  // Generic alt
};

// XN297 address scramble table (first 5 bytes)
static const uint8_t xn297_scramble[] = {
  0xE3, 0xB1, 0x4B, 0xEA, 0x85
};

// Descramble XN297 address
static void xn297_descramble_addr(const uint8_t *in, uint8_t *out, uint8_t len) {
  for (uint8_t i = 0; i < len; i++) {
    out[i] = in[i] ^ xn297_scramble[i];
  }
}

// State
static uint8_t current_channel = 0;
static uint8_t current_rate = 0;  // 0=1Mbps, 1=250kbps, 2=2Mbps
static uint8_t current_addr_idx = 0;
static uint32_t scan_start_ms = 0;
static uint32_t packets_found = 0;
static uint8_t found_channel = 0;
static uint8_t found_rate = 0;
static uint8_t found_addr_idx = 0;
static bool locked = false;

// Channel scan range
static const uint8_t CH_MIN = 0;
static const uint8_t CH_MAX = 84;
static const uint8_t DWELL_MS = 2;  // ms per channel during scan

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("=== F8620 RF Sniffer ==="));
  Serial.println(F("Scanning for transmitter packets..."));
  Serial.println(F("Power ON the original F8620 remote now."));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }

  // Start scanning
  radio.setAutoAck(false);
  radio.setPayloadSize(32);  // max payload to capture everything
  radio.setAddressWidth(5);
  radio.setCRCLength(RF24_CRC_DISABLED);  // disable CRC for promiscuous capture
  radio.setPALevel(RF24_PA_LOW);

  // Start with first address at 1Mbps
  set_scan_config();
  radio.startListening();

  scan_start_ms = millis();
  Serial.println(F("Scanning... (this takes ~30 seconds for full sweep)"));
  Serial.println(F("If transmitter is ON, packets should appear below."));
  Serial.println();
}

void set_scan_config() {
  radio.stopListening();

  // Set data rate
  switch (current_rate) {
    case 0: radio.setDataRate(RF24_1MBPS); break;
    case 1: radio.setDataRate(RF24_250KBPS); break;
    case 2: radio.setDataRate(RF24_2MBPS); break;
  }

  // Set address
  radio.openReadingPipe(0, addresses[current_addr_idx]);

  // Also try XN297-scrambled version of current address on pipe 1
  uint8_t scrambled[5];
  xn297_descramble_addr(addresses[current_addr_idx], scrambled, 5);
  radio.openReadingPipe(1, scrambled);

  // Set channel
  radio.setChannel(current_channel);
  radio.startListening();
}

void advance_scan() {
  if (locked) return;  // stay on found channel

  current_channel++;
  if (current_channel >= CH_MAX) {
    current_channel = CH_MIN;
    current_addr_idx++;
    if (current_addr_idx >= NUM_ADDRESSES) {
      current_addr_idx = 0;
      current_rate++;
      if (current_rate > 2) {
        current_rate = 0;
        // Full sweep done
        static uint8_t sweeps = 0;
        sweeps++;
        if (sweeps % 3 == 0 && packets_found == 0) {
          Serial.println(F("Still scanning... make sure TX is ON and close to the nRF24."));
        }
      }
      const char* rates[] = {"1Mbps", "250kbps", "2Mbps"};
      Serial.print(F("  Scanning: "));
      Serial.print(rates[current_rate]);
      Serial.print(F(", addr #"));
      Serial.println(current_addr_idx);
    }
  }
  set_scan_config();
}

void print_packet(uint8_t *buf, uint8_t len, uint8_t pipe) {
  packets_found++;

  Serial.println(F("╔══════════════════════════════════════╗"));
  Serial.println(F("║        PACKET CAPTURED!              ║"));
  Serial.println(F("╚══════════════════════════════════════╝"));

  const char* rates[] = {"1Mbps", "250kbps", "2Mbps"};
  Serial.print(F("Channel: "));
  Serial.print(current_channel);
  Serial.print(F("  ("));
  Serial.print(2400 + current_channel);
  Serial.println(F(" MHz)"));

  Serial.print(F("Data rate: "));
  Serial.println(rates[current_rate]);

  Serial.print(F("Address: "));
  for (uint8_t i = 0; i < 5; i++) {
    if (addresses[current_addr_idx][i] < 0x10) Serial.print('0');
    Serial.print(addresses[current_addr_idx][i], HEX);
    Serial.print(' ');
  }
  Serial.print(F(" (pipe "));
  Serial.print(pipe);
  if (pipe == 1) Serial.print(F(" = XN297 scrambled"));
  Serial.println(F(")"));

  Serial.print(F("Payload ("));
  Serial.print(len);
  Serial.print(F(" bytes): "));
  for (uint8_t i = 0; i < len; i++) {
    if (buf[i] < 0x10) Serial.print('0');
    Serial.print(buf[i], HEX);
    Serial.print(' ');
  }
  Serial.println();

  // Try to identify protocol from first byte
  Serial.print(F("First byte: 0x"));
  Serial.print(buf[0], HEX);
  Serial.print(F(" -> "));
  switch (buf[0]) {
    case 0xA4: Serial.println(F("Bayang/E010 BIND packet")); break;
    case 0xA5: Serial.println(F("Bayang/E010 DATA packet")); break;
    case 0x55: Serial.println(F("CX-10 BIND packet")); break;
    case 0xAA: Serial.println(F("CX-10 DATA packet")); break;
    case 0x20: Serial.println(F("MJX BIND packet")); break;
    case 0x21: Serial.println(F("MJX DATA packet")); break;
    default:   Serial.println(F("Unknown (check raw data)")); break;
  }
  Serial.println();

  // Lock onto this channel/rate for more captures
  if (!locked) {
    locked = true;
    found_channel = current_channel;
    found_rate = current_rate;
    found_addr_idx = current_addr_idx;
    Serial.println(F(">>> LOCKED onto signal. Capturing more packets... <<<"));
    Serial.println();
  }
}

void loop() {
  // Check for received packets
  uint8_t pipe;
  if (radio.available(&pipe)) {
    uint8_t buf[32];
    uint8_t len = radio.getPayloadSize();
    radio.read(buf, len);

    // Filter out noise (all zeros or all FFs)
    bool all_zero = true, all_ff = true;
    for (uint8_t i = 0; i < len; i++) {
      if (buf[i] != 0x00) all_zero = false;
      if (buf[i] != 0xFF) all_ff = false;
    }
    if (!all_zero && !all_ff) {
      print_packet(buf, len, pipe);
    }
  }

  // Advance scan every DWELL_MS
  if (!locked) {
    static uint32_t last_advance = 0;
    if (millis() - last_advance >= DWELL_MS) {
      advance_scan();
      last_advance = millis();
    }
  }

  // Print summary every 10 seconds
  static uint32_t last_summary = 0;
  if (millis() - last_summary >= 10000) {
    last_summary = millis();
    uint32_t elapsed = (millis() - scan_start_ms) / 1000;
    Serial.print(F("["));
    Serial.print(elapsed);
    Serial.print(F("s] Packets captured: "));
    Serial.println(packets_found);
  }
}
