// ============================================================================
// F8620 USB Transmitter — Step 2: Multi-Protocol Bind Test
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Try multiple toy-drone protocols to find which one the C3-7-RX uses.
//          Sends bind packets for the selected protocol when drone powers on.
//
// [SAFETY] REMOVE PROPELLERS before testing.
// [SAFETY] Do NOT power the original remote while this is running.
// [SAFETY] Throttle is always 0 during bind testing.
//
// USAGE:
//   1. Upload this sketch
//   2. Open Serial Monitor @ 115200
//   3. Type protocol number (1–6) and press Enter to select
//   4. Power OFF the drone
//   5. Press Enter to start binding
//   6. Power ON the drone within 2 seconds
//   7. Watch drone LED: blinking → solid = BOUND
//   8. If no bind after 5 seconds, power-cycle drone and try next protocol
//
// PROTOCOL LIST:
//   1 = Bayang (most likely for Chinese educational quads)
//   2 = E010 / JJRC H36
//   3 = CX-10
//   4 = Syma X5C
//   5 = H8 mini / H20
//   6 = MJX
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE = D9, CSN = D10

// ============================================================================
//  PROTOCOL DEFINITIONS
// ============================================================================

enum Protocol : uint8_t {
  PROTO_NONE    = 0,
  PROTO_BAYANG  = 1,
  PROTO_E010    = 2,
  PROTO_CX10    = 3,
  PROTO_SYMA    = 4,
  PROTO_H8MINI  = 5,
  PROTO_MJX     = 6,
  PROTO_COUNT   = 7
};

static const char* const proto_names[] = {
  "None",
  "Bayang",
  "E010/JJRC H36",
  "CX-10",
  "Syma X5C",
  "H8 mini/H20",
  "MJX"
};

static Protocol current_proto = PROTO_NONE;
static bool binding = false;
static bool bound = false;
static uint32_t bind_start_ms = 0;
static uint32_t last_packet_us = 0;

// TX ID (random, generated at startup)
static uint8_t tx_id[4];

// RF hopping channels (protocol-specific)
static uint8_t rf_channels[4];
static uint8_t rf_chan_idx = 0;

// Packet buffer
static uint8_t packet[32];
static uint8_t packet_len = 0;
static uint16_t packet_interval_us = 3000;

// Bind packet counter
static uint16_t bind_counter = 0;
static const uint16_t BIND_PACKET_COUNT = 500;

// Channel values (all zero for bind test — no throttle!)
static int16_t ch_throttle = 0;
static int16_t ch_yaw      = 0;
static int16_t ch_pitch    = 0;
static int16_t ch_roll     = 0;

// ============================================================================
//  ID GENERATION
// ============================================================================
static void generate_tx_id() {
  randomSeed(analogRead(A0) ^ (analogRead(A1) << 8) ^
             (analogRead(A2) << 4) ^ micros());
  for (uint8_t i = 0; i < 4; i++) {
    tx_id[i] = random(256);
  }
}

// ============================================================================
//  BAYANG PROTOCOL
// ============================================================================
static void bayang_init() {
  radio.setDataRate(RF24_1MBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);

  // Bind address
  uint8_t bind_addr[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0);
  radio.stopListening();

  // Generate hop channels from TX ID
  rf_channels[0] = (tx_id[0] & 0x1F) + 0x10;
  rf_channels[1] = rf_channels[0] + 0x20;
  rf_channels[2] = rf_channels[0] + 0x40;
  rf_channels[3] = rf_channels[0] + 0x42;
  for (uint8_t i = 0; i < 4; i++) {
    if (rf_channels[i] > 83) rf_channels[i] = 83;
  }

  packet_len = 15;
  packet_interval_us = 3000;
}

static void bayang_bind_packet() {
  memset(packet, 0, 15);
  packet[0] = 0xA4;  // Bind marker
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  packet[3] = tx_id[2];
  packet[4] = tx_id[3];
  packet[5] = rf_channels[0];
  packet[6] = rf_channels[1];
  packet[7] = rf_channels[2];
  packet[8] = rf_channels[3];
  packet[9]  = tx_id[0];  // TX addr
  packet[10] = tx_id[1];
  packet[11] = tx_id[2];
  packet[12] = tx_id[3];

  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;
}

static void bayang_data_packet() {
  memset(packet, 0, 15);
  packet[0] = 0xA5;  // Data marker
  packet[1] = 0x00;  // No flags
  packet[2] = tx_id[0];
  packet[3] = tx_id[1];

  // Throttle (10-bit: 0–1023)
  uint16_t thr = (uint16_t)((int32_t)ch_throttle * 1023 / 1000);
  packet[4] = (thr >> 8) & 0x03;
  packet[5] = thr & 0xFF;

  // Yaw (10-bit: 512 = center)
  uint16_t rud = (uint16_t)((int32_t)ch_yaw * 511 / 500 + 512);
  packet[6] = (rud >> 8) & 0x03;
  packet[7] = rud & 0xFF;

  // Pitch (10-bit: 512 = center)
  uint16_t ele = (uint16_t)((int32_t)ch_pitch * 511 / 500 + 512);
  packet[8] = (ele >> 8) & 0x03;
  packet[9] = ele & 0xFF;

  // Roll (10-bit: 512 = center)
  uint16_t ail = (uint16_t)((int32_t)ch_roll * 511 / 500 + 512);
  packet[10] = (ail >> 8) & 0x03;
  packet[11] = ail & 0xFF;

  packet[12] = 0x00;  // Trims
  packet[13] = 0x00;

  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;
}

static void bayang_switch_to_data() {
  uint8_t tx_addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x00};
  radio.openWritingPipe(tx_addr);
}

// ============================================================================
//  E010 / JJRC H36 PROTOCOL
// ============================================================================
static void e010_init() {
  radio.setDataRate(RF24_1MBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);

  // E010 uses same structure as Bayang with slight differences
  uint8_t bind_addr[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0);
  radio.stopListening();

  rf_channels[0] = (tx_id[0] & 0x0F) + 0x24;
  rf_channels[1] = rf_channels[0] + 0x14;
  rf_channels[2] = rf_channels[0] + 0x28;
  rf_channels[3] = rf_channels[0] + 0x3C;
  for (uint8_t i = 0; i < 4; i++) {
    if (rf_channels[i] > 83) rf_channels[i] = 83;
  }

  packet_len = 15;
  packet_interval_us = 4000;
}

static void e010_bind_packet() {
  // E010 bind is very similar to Bayang
  bayang_bind_packet();
  packet[0] = 0xA4;  // Same bind marker
}

static void e010_data_packet() {
  bayang_data_packet();
}

static void e010_switch_to_data() {
  bayang_switch_to_data();
}

// ============================================================================
//  CX-10 PROTOCOL
// ============================================================================
static void cx10_init() {
  radio.setDataRate(RF24_1MBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);
  radio.setCRCLength(RF24_CRC_16);

  uint8_t bind_addr[5] = {0xCC, 0xCC, 0xCC, 0xCC, 0xCC};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x02);
  radio.stopListening();

  rf_channels[0] = 0x03;
  rf_channels[1] = 0x16;
  rf_channels[2] = 0x2E;
  rf_channels[3] = 0x46;

  packet_len = 15;
  packet_interval_us = 6000;
}

static void cx10_bind_packet() {
  memset(packet, 0, 15);
  packet[0] = 0x55;  // CX-10 bind marker
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  packet[3] = tx_id[2];
  packet[4] = tx_id[3];

  // Channels at center (neutral)
  packet[5] = 0x00;
  packet[6] = 0x80;  // throttle low
  packet[7] = 0x00;
  packet[8] = 0x80;  // yaw center
  packet[9] = 0x00;
  packet[10] = 0x80; // pitch center
  packet[11] = 0x00;
  packet[12] = 0x80; // roll center
  packet[13] = 0x00; // flags

  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;
}

static void cx10_data_packet() {
  cx10_bind_packet();
  packet[0] = 0xAA;  // Data marker instead of bind
}

static void cx10_switch_to_data() {
  uint8_t tx_addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0xCC};
  radio.openWritingPipe(tx_addr);
}

// ============================================================================
//  SYMA X5C PROTOCOL
// ============================================================================
static void syma_init() {
  radio.setDataRate(RF24_250KBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(10);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);

  uint8_t bind_addr[5] = {0x06, 0x06, 0x06, 0x06, 0x06};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x08);
  radio.stopListening();

  rf_channels[0] = 0x08;
  rf_channels[1] = 0x1E;
  rf_channels[2] = 0x34;
  rf_channels[3] = 0x4A;

  packet_len = 10;
  packet_interval_us = 8000;
}

static void syma_bind_packet() {
  memset(packet, 0, 10);
  packet[0] = tx_id[0];
  packet[1] = tx_id[1];
  packet[2] = tx_id[2];
  packet[3] = tx_id[3];
  packet[4] = 0x80;  // throttle = 0
  packet[5] = 0x80;  // yaw center
  packet[6] = 0x80;  // pitch center
  packet[7] = 0x80;  // roll center
  packet[8] = 0x00;  // flags (bind)
  packet[9] = 0x00;  // checksum
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;
}

static void syma_data_packet() {
  syma_bind_packet();
  packet[8] = 0x01;  // flags (data, not bind)
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;
}

static void syma_switch_to_data() {
  uint8_t tx_addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x06};
  radio.openWritingPipe(tx_addr);
}

// ============================================================================
//  H8 MINI / H20 PROTOCOL
// ============================================================================
static void h8mini_init() {
  radio.setDataRate(RF24_1MBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(10);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);

  uint8_t bind_addr[5] = {0xC4, 0xC4, 0xC4, 0xC4, 0xC4};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x06);
  radio.stopListening();

  rf_channels[0] = 0x06;
  rf_channels[1] = 0x19;
  rf_channels[2] = 0x2C;
  rf_channels[3] = 0x3F;

  packet_len = 10;
  packet_interval_us = 7000;
}

static void h8mini_bind_packet() {
  memset(packet, 0, 10);
  packet[0] = tx_id[0];
  packet[1] = tx_id[1];
  packet[2] = tx_id[2];
  packet[3] = tx_id[3];
  packet[4] = 0x00;  // throttle
  packet[5] = 0x80;  // yaw center
  packet[6] = 0x80;  // pitch center
  packet[7] = 0x80;  // roll center
  packet[8] = 0x80;  // bind flag
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;
}

static void h8mini_data_packet() {
  h8mini_bind_packet();
  packet[8] = 0x00;  // data flag (not bind)
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;
}

static void h8mini_switch_to_data() {
  uint8_t tx_addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0xC4};
  radio.openWritingPipe(tx_addr);
}

// ============================================================================
//  MJX PROTOCOL
// ============================================================================
static void mjx_init() {
  radio.setDataRate(RF24_1MBPS);
  radio.setAutoAck(false);
  radio.setPayloadSize(16);
  radio.setAddressWidth(5);
  radio.setPALevel(RF24_PA_MAX);

  uint8_t bind_addr[5] = {0x6D, 0x6A, 0x73, 0x73, 0x73};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x0A);
  radio.stopListening();

  rf_channels[0] = 0x0A;
  rf_channels[1] = 0x23;
  rf_channels[2] = 0x3C;
  rf_channels[3] = 0x50;

  packet_len = 16;
  packet_interval_us = 5000;
}

static void mjx_bind_packet() {
  memset(packet, 0, 16);
  packet[0] = 0x20;  // MJX bind marker
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  packet[3] = tx_id[2];
  packet[4] = tx_id[3];
  packet[5] = rf_channels[0];
  packet[6] = rf_channels[1];
  packet[7] = rf_channels[2];
  packet[8] = rf_channels[3];
  // Rest is zeros
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 15; i++) sum += packet[i];
  packet[15] = sum;
}

static void mjx_data_packet() {
  memset(packet, 0, 16);
  packet[0] = 0x21;  // Data marker
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  // Channels at center
  packet[3] = 0x00;
  packet[4] = 0x80;  // throttle
  packet[5] = 0x00;
  packet[6] = 0x80;  // yaw
  packet[7] = 0x00;
  packet[8] = 0x80;  // pitch
  packet[9] = 0x00;
  packet[10] = 0x80; // roll
  // Flags
  packet[11] = 0x00;
  packet[12] = 0x00;
  packet[13] = 0x00;
  packet[14] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 15; i++) sum += packet[i];
  packet[15] = sum;
}

static void mjx_switch_to_data() {
  uint8_t tx_addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x6D};
  radio.openWritingPipe(tx_addr);
}

// ============================================================================
//  PROTOCOL DISPATCHER
// ============================================================================
static void proto_init(Protocol p) {
  switch (p) {
    case PROTO_BAYANG:  bayang_init();  break;
    case PROTO_E010:    e010_init();    break;
    case PROTO_CX10:    cx10_init();    break;
    case PROTO_SYMA:    syma_init();    break;
    case PROTO_H8MINI:  h8mini_init();  break;
    case PROTO_MJX:     mjx_init();     break;
    default: break;
  }
}

static void proto_build_bind_packet(Protocol p) {
  switch (p) {
    case PROTO_BAYANG:  bayang_bind_packet();  break;
    case PROTO_E010:    e010_bind_packet();    break;
    case PROTO_CX10:    cx10_bind_packet();    break;
    case PROTO_SYMA:    syma_bind_packet();    break;
    case PROTO_H8MINI:  h8mini_bind_packet();  break;
    case PROTO_MJX:     mjx_bind_packet();     break;
    default: break;
  }
}

static void proto_build_data_packet(Protocol p) {
  switch (p) {
    case PROTO_BAYANG:  bayang_data_packet();  break;
    case PROTO_E010:    e010_data_packet();    break;
    case PROTO_CX10:    cx10_data_packet();    break;
    case PROTO_SYMA:    syma_data_packet();    break;
    case PROTO_H8MINI:  h8mini_data_packet();  break;
    case PROTO_MJX:     mjx_data_packet();     break;
    default: break;
  }
}

static void proto_switch_to_data(Protocol p) {
  switch (p) {
    case PROTO_BAYANG:  bayang_switch_to_data();  break;
    case PROTO_E010:    e010_switch_to_data();    break;
    case PROTO_CX10:    cx10_switch_to_data();    break;
    case PROTO_SYMA:    syma_switch_to_data();    break;
    case PROTO_H8MINI:  h8mini_switch_to_data();  break;
    case PROTO_MJX:     mjx_switch_to_data();     break;
    default: break;
  }
}

// ============================================================================
//  SERIAL INTERFACE
// ============================================================================
static char cmd_buf[32];
static uint8_t cmd_pos = 0;

static void print_menu() {
  Serial.println();
  Serial.println(F("=== F8620 Protocol Bind Test ==="));
  Serial.println(F("[SAFETY] Props removed? Original TX off?"));
  Serial.println();
  Serial.println(F("Select protocol:"));
  Serial.println(F("  1 = Bayang (try first)"));
  Serial.println(F("  2 = E010 / JJRC H36"));
  Serial.println(F("  3 = CX-10"));
  Serial.println(F("  4 = Syma X5C"));
  Serial.println(F("  5 = H8 mini / H20"));
  Serial.println(F("  6 = MJX"));
  Serial.println();
  Serial.println(F("Type number and press Enter."));
  Serial.println(F("Then power-cycle the drone to bind."));
}

static void start_bind(Protocol p) {
  current_proto = p;
  binding = true;
  bound = false;
  bind_counter = 0;
  rf_chan_idx = 0;

  generate_tx_id();
  proto_init(p);

  Serial.print(F("Starting bind: "));
  Serial.println(proto_names[p]);
  Serial.println(F("Power ON the drone NOW..."));
  Serial.println(F("(Sending bind packets for ~2 seconds)"));

  bind_start_ms = millis();
}

static void process_serial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_pos > 0) {
        cmd_buf[cmd_pos] = '\0';

        // Parse protocol number
        uint8_t proto_num = atoi(cmd_buf);
        if (proto_num >= 1 && proto_num <= 6) {
          start_bind((Protocol)proto_num);
        } else if (cmd_buf[0] == 'S' || cmd_buf[0] == 's') {
          // STOP
          binding = false;
          bound = false;
          Serial.println(F("STOPPED."));
          print_menu();
        } else {
          Serial.println(F("Invalid. Type 1–6 or S to stop."));
        }
        cmd_pos = 0;
      }
    } else if (cmd_pos < sizeof(cmd_buf) - 1) {
      cmd_buf[cmd_pos++] = c;
    }
  }
}

// ============================================================================
//  SETUP
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found! Run hardware check first."));
    while (1) { delay(1000); }
  }

  Serial.println(F("nRF24 OK."));
  print_menu();
}

// ============================================================================
//  MAIN LOOP
// ============================================================================
void loop() {
  process_serial();

  if (!binding && !bound) {
    return;
  }

  // Transmit at protocol rate
  uint32_t now_us = micros();
  if (now_us - last_packet_us < packet_interval_us) {
    return;
  }
  last_packet_us = now_us;

  if (binding) {
    // Send bind packets
    proto_build_bind_packet(current_proto);
    radio.write(packet, packet_len);
    bind_counter++;

    // Blink LED during binding
    digitalWrite(LED_BUILTIN, (bind_counter / 50) & 1);

    if (bind_counter >= BIND_PACKET_COUNT) {
      // Switch to data mode
      binding = false;
      bound = true;
      proto_switch_to_data(current_proto);
      Serial.println();
      Serial.println(F("Bind phase complete — now sending data packets."));
      Serial.println(F("If drone LED is solid: SUCCESS! Protocol found."));
      Serial.println(F("If drone LED still blinking: try next protocol."));
      Serial.println(F("Type S to stop, or 1–6 for another protocol."));
      digitalWrite(LED_BUILTIN, HIGH);
    }
  } else if (bound) {
    // Send data packets (throttle = 0, all centered)
    proto_build_data_packet(current_proto);

    // Frequency hop
    radio.setChannel(rf_channels[rf_chan_idx]);
    radio.write(packet, packet_len);
    rf_chan_idx = (rf_chan_idx + 1) % 4;
  }
}
