// ============================================================================
// F8620 USB Transmitter — Step 3: PC Serial Control
// Target board: Arduino Uno (Elegoo)
// Library required: RF24 by TMRh20
//
// PURPOSE: Full PC → Arduino → nRF24L01+ → drone control.
//          Upload AFTER you found the working protocol in step 2.
//          Set ACTIVE_PROTOCOL below to the protocol that worked.
//
// [SAFETY] REMOVE PROPELLERS until you are confident in control.
// [SAFETY] If no serial command for 500ms → throttle = 0.
// [SAFETY] Throttle must be 0 to start binding.
//
// SERIAL COMMANDS (115200 baud):
//   T<thr> Y<yaw> P<pitch> R<roll>  — control (T:0–1000, Y/P/R:-500..500)
//   BIND                             — restart binding
//   STOP                             — zero all channels
//   STATUS                           — print state
//
// PYTHON EXAMPLE:
//   import serial, time
//   ser = serial.Serial('COM3', 115200)  # adjust port
//   time.sleep(2)  # wait for Arduino reset
//   ser.write(b'T0 Y0 P0 R0\n')  # neutral
//   time.sleep(3)  # wait for bind
//   ser.write(b'T200 Y0 P0 R0\n')  # gentle throttle (PROPS OFF!)
// ============================================================================

#include <SPI.h>
#include <RF24.h>

RF24 radio(9, 10);  // CE = D9, CSN = D10

// ============================================================================
//  >>> SET THIS TO THE PROTOCOL THAT WORKED IN STEP 2 <<<
// ============================================================================
#define ACTIVE_PROTOCOL  1  // 1=Bayang, 2=E010, 3=CX10, 4=Syma, 5=H8mini, 6=MJX

// ============================================================================
//  STATE
// ============================================================================
static uint8_t tx_id[4];
static uint8_t rf_channels[4];
static uint8_t rf_chan_idx = 0;
static uint8_t packet[32];
static uint8_t packet_len = 15;
static uint16_t packet_interval_us = 3000;

static bool bound = false;
static uint16_t bind_counter = 0;
static const uint16_t BIND_PACKET_COUNT = 500;

static int16_t ch_throttle = 0;
static int16_t ch_yaw      = 0;
static int16_t ch_pitch    = 0;
static int16_t ch_roll     = 0;

static uint32_t last_packet_us = 0;
static uint32_t last_cmd_ms = 0;
static const uint16_t CMD_TIMEOUT_MS = 500;

// Serial buffer
static char cmd_buf[64];
static uint8_t cmd_pos = 0;

// ============================================================================
//  PROTOCOL INIT (same as step 2, but only the active protocol)
// ============================================================================
static void generate_tx_id() {
  randomSeed(analogRead(A0) ^ (analogRead(A1) << 8) ^
             (analogRead(A2) << 4) ^ micros());
  for (uint8_t i = 0; i < 4; i++) {
    tx_id[i] = random(256);
  }
}

static void init_protocol() {
  radio.setAutoAck(false);
  radio.setPALevel(RF24_PA_MAX);
  radio.stopListening();

#if ACTIVE_PROTOCOL == 1  // Bayang
  radio.setDataRate(RF24_1MBPS);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  uint8_t bind_addr[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0);
  rf_channels[0] = (tx_id[0] & 0x1F) + 0x10;
  rf_channels[1] = rf_channels[0] + 0x20;
  rf_channels[2] = rf_channels[0] + 0x40;
  rf_channels[3] = rf_channels[0] + 0x42;
  for (uint8_t i = 0; i < 4; i++) if (rf_channels[i] > 83) rf_channels[i] = 83;
  packet_len = 15;
  packet_interval_us = 3000;

#elif ACTIVE_PROTOCOL == 2  // E010
  radio.setDataRate(RF24_1MBPS);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  uint8_t bind_addr[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0);
  rf_channels[0] = (tx_id[0] & 0x0F) + 0x24;
  rf_channels[1] = rf_channels[0] + 0x14;
  rf_channels[2] = rf_channels[0] + 0x28;
  rf_channels[3] = rf_channels[0] + 0x3C;
  for (uint8_t i = 0; i < 4; i++) if (rf_channels[i] > 83) rf_channels[i] = 83;
  packet_len = 15;
  packet_interval_us = 4000;

#elif ACTIVE_PROTOCOL == 3  // CX-10
  radio.setDataRate(RF24_1MBPS);
  radio.setPayloadSize(15);
  radio.setAddressWidth(5);
  radio.setCRCLength(RF24_CRC_16);
  uint8_t bind_addr[5] = {0xCC, 0xCC, 0xCC, 0xCC, 0xCC};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x02);
  rf_channels[0] = 0x03;
  rf_channels[1] = 0x16;
  rf_channels[2] = 0x2E;
  rf_channels[3] = 0x46;
  packet_len = 15;
  packet_interval_us = 6000;

#elif ACTIVE_PROTOCOL == 4  // Syma
  radio.setDataRate(RF24_250KBPS);
  radio.setPayloadSize(10);
  radio.setAddressWidth(5);
  uint8_t bind_addr[5] = {0x06, 0x06, 0x06, 0x06, 0x06};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x08);
  rf_channels[0] = 0x08;
  rf_channels[1] = 0x1E;
  rf_channels[2] = 0x34;
  rf_channels[3] = 0x4A;
  packet_len = 10;
  packet_interval_us = 8000;

#elif ACTIVE_PROTOCOL == 5  // H8 mini
  radio.setDataRate(RF24_1MBPS);
  radio.setPayloadSize(10);
  radio.setAddressWidth(5);
  uint8_t bind_addr[5] = {0xC4, 0xC4, 0xC4, 0xC4, 0xC4};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x06);
  rf_channels[0] = 0x06;
  rf_channels[1] = 0x19;
  rf_channels[2] = 0x2C;
  rf_channels[3] = 0x3F;
  packet_len = 10;
  packet_interval_us = 7000;

#elif ACTIVE_PROTOCOL == 6  // MJX
  radio.setDataRate(RF24_1MBPS);
  radio.setPayloadSize(16);
  radio.setAddressWidth(5);
  uint8_t bind_addr[5] = {0x6D, 0x6A, 0x73, 0x73, 0x73};
  radio.openWritingPipe(bind_addr);
  radio.setChannel(0x0A);
  rf_channels[0] = 0x0A;
  rf_channels[1] = 0x23;
  rf_channels[2] = 0x3C;
  rf_channels[3] = 0x50;
  packet_len = 16;
  packet_interval_us = 5000;
#endif
}

// ============================================================================
//  PACKET BUILDERS (Bayang-style — adjust if different protocol)
// ============================================================================
static void build_bind_packet() {
#if ACTIVE_PROTOCOL == 1 || ACTIVE_PROTOCOL == 2
  memset(packet, 0, packet_len);
  packet[0] = 0xA4;
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  packet[3] = tx_id[2];
  packet[4] = tx_id[3];
  packet[5] = rf_channels[0];
  packet[6] = rf_channels[1];
  packet[7] = rf_channels[2];
  packet[8] = rf_channels[3];
  packet[9]  = tx_id[0];
  packet[10] = tx_id[1];
  packet[11] = tx_id[2];
  packet[12] = tx_id[3];
  uint8_t sum = 0;
  for (uint8_t i = 0; i < packet_len - 1; i++) sum += packet[i];
  packet[packet_len - 1] = sum;

#elif ACTIVE_PROTOCOL == 3
  memset(packet, 0, packet_len);
  packet[0] = 0x55;
  packet[1] = tx_id[0];
  packet[2] = tx_id[1];
  packet[3] = tx_id[2];
  packet[4] = tx_id[3];
  packet[5] = 0x00; packet[6] = 0x80;
  packet[7] = 0x00; packet[8] = 0x80;
  packet[9] = 0x00; packet[10] = 0x80;
  packet[11] = 0x00; packet[12] = 0x80;
  packet[13] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;

#elif ACTIVE_PROTOCOL == 4
  memset(packet, 0, packet_len);
  packet[0] = tx_id[0]; packet[1] = tx_id[1];
  packet[2] = tx_id[2]; packet[3] = tx_id[3];
  packet[4] = 0x80; packet[5] = 0x80;
  packet[6] = 0x80; packet[7] = 0x80;
  packet[8] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;

#elif ACTIVE_PROTOCOL == 5
  memset(packet, 0, packet_len);
  packet[0] = tx_id[0]; packet[1] = tx_id[1];
  packet[2] = tx_id[2]; packet[3] = tx_id[3];
  packet[4] = 0x00; packet[5] = 0x80;
  packet[6] = 0x80; packet[7] = 0x80;
  packet[8] = 0x80;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;

#elif ACTIVE_PROTOCOL == 6
  memset(packet, 0, packet_len);
  packet[0] = 0x20;
  packet[1] = tx_id[0]; packet[2] = tx_id[1];
  packet[3] = tx_id[2]; packet[4] = tx_id[3];
  packet[5] = rf_channels[0]; packet[6] = rf_channels[1];
  packet[7] = rf_channels[2]; packet[8] = rf_channels[3];
  uint8_t sum = 0;
  for (uint8_t i = 0; i < packet_len - 1; i++) sum += packet[i];
  packet[packet_len - 1] = sum;
#endif
}

static void build_data_packet() {
#if ACTIVE_PROTOCOL == 1 || ACTIVE_PROTOCOL == 2
  memset(packet, 0, packet_len);
  packet[0] = 0xA5;
  packet[1] = 0x00;  // flags
  packet[2] = tx_id[0];
  packet[3] = tx_id[1];

  uint16_t thr = (uint16_t)((int32_t)constrain(ch_throttle, 0, 1000) * 1023 / 1000);
  uint16_t rud = (uint16_t)((int32_t)constrain(ch_yaw, -500, 500) * 511 / 500 + 512);
  uint16_t ele = (uint16_t)((int32_t)constrain(ch_pitch, -500, 500) * 511 / 500 + 512);
  uint16_t ail = (uint16_t)((int32_t)constrain(ch_roll, -500, 500) * 511 / 500 + 512);

  packet[4] = (thr >> 8) & 0x03; packet[5] = thr & 0xFF;
  packet[6] = (rud >> 8) & 0x03; packet[7] = rud & 0xFF;
  packet[8] = (ele >> 8) & 0x03; packet[9] = ele & 0xFF;
  packet[10] = (ail >> 8) & 0x03; packet[11] = ail & 0xFF;
  packet[12] = 0x00; packet[13] = 0x00;

  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;

#elif ACTIVE_PROTOCOL == 3
  memset(packet, 0, packet_len);
  packet[0] = 0xAA;
  packet[1] = tx_id[0]; packet[2] = tx_id[1];
  packet[3] = tx_id[2]; packet[4] = tx_id[3];
  // Simplified: 8-bit channels
  packet[5] = 0x00; packet[6] = (uint8_t)(ch_throttle * 255 / 1000);
  packet[7] = 0x00; packet[8] = (uint8_t)((ch_yaw + 500) * 255 / 1000);
  packet[9] = 0x00; packet[10] = (uint8_t)((ch_pitch + 500) * 255 / 1000);
  packet[11] = 0x00; packet[12] = (uint8_t)((ch_roll + 500) * 255 / 1000);
  packet[13] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 14; i++) sum += packet[i];
  packet[14] = sum;

#elif ACTIVE_PROTOCOL == 4
  memset(packet, 0, packet_len);
  packet[0] = tx_id[0]; packet[1] = tx_id[1];
  packet[2] = tx_id[2]; packet[3] = tx_id[3];
  packet[4] = (uint8_t)(ch_throttle * 255 / 1000);
  packet[5] = (uint8_t)((ch_yaw + 500) * 255 / 1000);
  packet[6] = (uint8_t)((ch_pitch + 500) * 255 / 1000);
  packet[7] = (uint8_t)((ch_roll + 500) * 255 / 1000);
  packet[8] = 0x01;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;

#elif ACTIVE_PROTOCOL == 5
  memset(packet, 0, packet_len);
  packet[0] = tx_id[0]; packet[1] = tx_id[1];
  packet[2] = tx_id[2]; packet[3] = tx_id[3];
  packet[4] = (uint8_t)(ch_throttle * 255 / 1000);
  packet[5] = (uint8_t)((ch_yaw + 500) * 255 / 1000);
  packet[6] = (uint8_t)((ch_pitch + 500) * 255 / 1000);
  packet[7] = (uint8_t)((ch_roll + 500) * 255 / 1000);
  packet[8] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 9; i++) sum += packet[i];
  packet[9] = sum;

#elif ACTIVE_PROTOCOL == 6
  memset(packet, 0, packet_len);
  packet[0] = 0x21;
  packet[1] = tx_id[0]; packet[2] = tx_id[1];
  packet[3] = 0x00; packet[4] = (uint8_t)(ch_throttle * 255 / 1000);
  packet[5] = 0x00; packet[6] = (uint8_t)((ch_yaw + 500) * 255 / 1000);
  packet[7] = 0x00; packet[8] = (uint8_t)((ch_pitch + 500) * 255 / 1000);
  packet[9] = 0x00; packet[10] = (uint8_t)((ch_roll + 500) * 255 / 1000);
  packet[11] = 0x00; packet[12] = 0x00;
  packet[13] = 0x00; packet[14] = 0x00;
  uint8_t sum = 0;
  for (uint8_t i = 0; i < 15; i++) sum += packet[i];
  packet[15] = sum;
#endif
}

static void switch_to_data_address() {
#if ACTIVE_PROTOCOL == 1 || ACTIVE_PROTOCOL == 2
  uint8_t addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x00};
  radio.openWritingPipe(addr);
#elif ACTIVE_PROTOCOL == 3
  uint8_t addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0xCC};
  radio.openWritingPipe(addr);
#elif ACTIVE_PROTOCOL == 4
  uint8_t addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x06};
  radio.openWritingPipe(addr);
#elif ACTIVE_PROTOCOL == 5
  uint8_t addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0xC4};
  radio.openWritingPipe(addr);
#elif ACTIVE_PROTOCOL == 6
  uint8_t addr[5] = {tx_id[0], tx_id[1], tx_id[2], tx_id[3], 0x6D};
  radio.openWritingPipe(addr);
#endif
}

// ============================================================================
//  SERIAL PARSER
// ============================================================================
static void process_serial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_pos > 0) {
        cmd_buf[cmd_pos] = '\0';

        int t, y, p, r;
        if (sscanf(cmd_buf, "T%d Y%d P%d R%d", &t, &y, &p, &r) == 4) {
          ch_throttle = constrain(t, 0, 1000);
          ch_yaw      = constrain(y, -500, 500);
          ch_pitch    = constrain(p, -500, 500);
          ch_roll     = constrain(r, -500, 500);
          last_cmd_ms = millis();
        } else if (strncmp(cmd_buf, "BIND", 4) == 0) {
          bound = false;
          bind_counter = 0;
          init_protocol();
          Serial.println(F("REBINDING — power-cycle drone now"));
        } else if (strncmp(cmd_buf, "STOP", 4) == 0) {
          ch_throttle = 0;
          ch_yaw = 0;
          ch_pitch = 0;
          ch_roll = 0;
          last_cmd_ms = millis();
          Serial.println(F("STOPPED"));
        } else if (strncmp(cmd_buf, "STATUS", 6) == 0) {
          Serial.print(F("Bound: ")); Serial.println(bound ? "YES" : "NO");
          Serial.print(F("T=")); Serial.print(ch_throttle);
          Serial.print(F(" Y=")); Serial.print(ch_yaw);
          Serial.print(F(" P=")); Serial.print(ch_pitch);
          Serial.print(F(" R=")); Serial.println(ch_roll);
        } else {
          Serial.println(F("? T<thr> Y<yaw> P<pitch> R<roll> | BIND | STOP | STATUS"));
        }
        cmd_pos = 0;
      }
    } else if (cmd_pos < sizeof(cmd_buf) - 1) {
      cmd_buf[cmd_pos++] = c;
    } else {
      cmd_pos = 0;
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

  Serial.println(F("=== F8620 PC Control Transmitter ==="));
  Serial.print(F("Protocol: "));
  const char* names[] = {"?", "Bayang", "E010", "CX-10", "Syma", "H8mini", "MJX"};
  Serial.println(names[ACTIVE_PROTOCOL]);
  Serial.println(F("[SAFETY] Props removed? Original TX off?"));
  Serial.println();

  if (!radio.begin()) {
    Serial.println(F("[FAIL] nRF24 not found!"));
    while (1) { delay(1000); }
  }
  Serial.println(F("nRF24 OK"));

  generate_tx_id();
  init_protocol();

  Serial.println(F("Binding... power ON drone now."));
  Serial.println(F("Commands: T<thr> Y<yaw> P<pitch> R<roll> | BIND | STOP | STATUS"));

  last_cmd_ms = millis();
  last_packet_us = micros();
}

// ============================================================================
//  MAIN LOOP
// ============================================================================
void loop() {
  process_serial();

  // Failsafe: no serial command → throttle to 0
  if (millis() - last_cmd_ms > CMD_TIMEOUT_MS) {
    if (ch_throttle > 0) {
      ch_throttle = 0;
      ch_yaw = 0;
      ch_pitch = 0;
      ch_roll = 0;
    }
  }

  // Transmit at protocol rate
  uint32_t now_us = micros();
  if (now_us - last_packet_us < packet_interval_us) {
    return;
  }
  last_packet_us = now_us;

  if (!bound) {
    // Bind phase
    build_bind_packet();
    radio.write(packet, packet_len);
    bind_counter++;
    digitalWrite(LED_BUILTIN, (bind_counter / 50) & 1);

    if (bind_counter >= BIND_PACKET_COUNT) {
      bound = true;
      switch_to_data_address();
      Serial.println(F("BOUND — sending data. Watch drone LED."));
      digitalWrite(LED_BUILTIN, HIGH);
    }
  } else {
    // Data phase with frequency hopping
    build_data_packet();
    radio.setChannel(rf_channels[rf_chan_idx]);
    radio.write(packet, packet_len);
    rf_chan_idx = (rf_chan_idx + 1) % 4;
  }
}
