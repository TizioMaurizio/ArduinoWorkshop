// ============================================================================
// F8620 Quadcopter Drone — Flight Controller
// Target board: Arduino Nano (ATmega328P)
// RAM budget: ~1.2 KB used of 2 KB available
// Compile with: -Wall -Wextra
//
// Hardware: F8620 coreless motor quadcopter kit
//   - 4x brushed coreless motors 8.6mm x 20mm via MOSFET drivers
//   - C3-7-RX 2.4 GHz receiver (4-channel: throttle, yaw, pitch, roll)
//   - 145mm wheelbase, 64mm propellers
//
// Control modes:
//   1. RECEIVER MODE — reads PWM/PPM from C3-7-RX receiver
//   2. SERIAL MODE   — reads commands from Serial at 115200 baud
//      Format: "T<throttle> Y<yaw> P<pitch> R<roll>\n"
//      Example: "T500 Y0 P0 R0\n" (half throttle, no yaw/pitch/roll)
//
// Arming:  throttle low + yaw right for 1 second
// Disarm:  throttle low + yaw left  for 1 second
//
// [SAFETY] Motors will NOT spin unless armed.
// [SAFETY] Signal loss for >500ms → immediate motor kill (failsafe).
// [SAFETY] Throttle must be at minimum to arm.
// ============================================================================

#include "config.h"
#include "receiver.h"
#include "mixer.h"

// ============================================================================
//  STATE MACHINE
// ============================================================================
enum FlightState : uint8_t {
  STATE_DISARMED,
  STATE_ARMING,
  STATE_ARMED,
  STATE_DISARMING,
  STATE_FAILSAFE
};

static FlightState flight_state = STATE_DISARMED;
static uint32_t arm_timer_start = 0;
static uint32_t last_loop_us = 0;

// Serial control buffer
static char serial_buf[64];
static uint8_t serial_buf_pos = 0;
static uint32_t serial_last_cmd_ms = 0;
static bool serial_active = false;

// ============================================================================
//  LED STATUS PATTERNS
// ============================================================================
static uint32_t led_last_toggle_ms = 0;

static void led_update() {
  uint32_t now = millis();
  uint16_t interval;

  switch (flight_state) {
    case STATE_DISARMED:  interval = 1000; break;  // slow blink
    case STATE_ARMING:    interval = 100;  break;  // fast blink
    case STATE_ARMED:     interval = 0;    break;  // solid on
    case STATE_DISARMING: interval = 100;  break;  // fast blink
    case STATE_FAILSAFE:  interval = 200;  break;  // medium blink
    default:              interval = 500;  break;
  }

  if (interval == 0) {
    digitalWrite(PIN_LED, HIGH);
  } else if (now - led_last_toggle_ms >= interval) {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    led_last_toggle_ms = now;
  }
}

// ============================================================================
//  SERIAL COMMAND PARSER
// ============================================================================
static bool serial_parse(int16_t &throttle, int16_t &yaw,
                          int16_t &pitch, int16_t &roll) {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serial_buf_pos > 0) {
        serial_buf[serial_buf_pos] = '\0';

        // Parse "T<val> Y<val> P<val> R<val>"
        int t = 0, y = 0, p = 0, r = 0;
        if (sscanf(serial_buf, "T%d Y%d P%d R%d", &t, &y, &p, &r) == 4) {
          throttle = constrain(t, 0, 1000);
          yaw      = constrain(y, -500, 500);
          pitch    = constrain(p, -500, 500);
          roll     = constrain(r, -500, 500);
          serial_last_cmd_ms = millis();
          serial_active = true;
          serial_buf_pos = 0;
          return true;
        }

        // Also accept "ARM" and "DISARM" commands
        if (strncmp(serial_buf, "ARM", 3) == 0) {
          if (flight_state == STATE_DISARMED) {
            flight_state = STATE_ARMED;
            Serial.println(F("ARMED"));
          }
          serial_buf_pos = 0;
          serial_last_cmd_ms = millis();
          serial_active = true;
          return false;
        }
        if (strncmp(serial_buf, "DISARM", 6) == 0) {
          flight_state = STATE_DISARMED;
          mixer_kill();
          Serial.println(F("DISARMED"));
          serial_buf_pos = 0;
          serial_last_cmd_ms = millis();
          serial_active = true;
          return false;
        }

        serial_buf_pos = 0;
      }
    } else if (serial_buf_pos < sizeof(serial_buf) - 1) {
      serial_buf[serial_buf_pos++] = c;
    } else {
      // Buffer overflow — discard
      serial_buf_pos = 0;
    }
  }
  return false;
}

// ============================================================================
//  ARMING STATE MACHINE (receiver stick-based)
// ============================================================================
static void arming_update(int16_t throttle, int16_t yaw) {
  uint32_t now = millis();
  bool throttle_low = (throttle < MOTOR_ARM_THRESHOLD);
  bool yaw_right    = (yaw > 400);
  bool yaw_left     = (yaw < -400);

  switch (flight_state) {
    case STATE_DISARMED:
      if (throttle_low && yaw_right) {
        flight_state = STATE_ARMING;
        arm_timer_start = now;
      }
      break;

    case STATE_ARMING:
      if (!throttle_low || !yaw_right) {
        flight_state = STATE_DISARMED;
      } else if (now - arm_timer_start >= ARM_HOLD_MS) {
        flight_state = STATE_ARMED;
        Serial.println(F("ARMED"));
      }
      break;

    case STATE_ARMED:
      if (throttle_low && yaw_left) {
        flight_state = STATE_DISARMING;
        arm_timer_start = now;
      }
      break;

    case STATE_DISARMING:
      if (!throttle_low || !yaw_left) {
        flight_state = STATE_ARMED;
      } else if (now - arm_timer_start >= ARM_HOLD_MS) {
        flight_state = STATE_DISARMED;
        mixer_kill();
        Serial.println(F("DISARMED"));
      }
      break;

    case STATE_FAILSAFE:
      // Stay in failsafe until signal returns and throttle is low
      if (throttle_low) {
        flight_state = STATE_DISARMED;
        Serial.println(F("FAILSAFE CLEARED"));
      }
      break;
  }
}

// ============================================================================
//  SETUP
// ============================================================================
void setup() {
  Serial.begin(SERIAL_BAUD);
  Serial.println(F("F8620 Drone Controller v1.0"));
  Serial.println(F("Status: DISARMED"));
  Serial.println(F("Commands: ARM | DISARM | T<thr> Y<yaw> P<pitch> R<roll>"));

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  mixer_init();
  rx_init();

  last_loop_us = micros();
}

// ============================================================================
//  MAIN LOOP — 250 Hz control loop
// ============================================================================
void loop() {
  // Enforce loop timing
  uint32_t now_us = micros();
  if (now_us - last_loop_us < LOOP_INTERVAL_US) {
    return;
  }
  last_loop_us = now_us;

  // --- Read inputs ---
  int16_t throttle = 0;
  int16_t yaw      = 0;
  int16_t pitch    = 0;
  int16_t roll     = 0;
  bool have_signal = false;

  // Try receiver first
  uint16_t rx_channels[CH_COUNT];
  bool rx_valid;
  rx_read(rx_channels, rx_valid);

  if (rx_valid) {
    throttle    = rx_to_throttle(rx_channels[CH_THROTTLE]);
    yaw         = rx_to_signed(rx_channels[CH_YAW]);
    pitch       = rx_to_signed(rx_channels[CH_PITCH]);
    roll        = rx_to_signed(rx_channels[CH_ROLL]);
    have_signal = true;
    serial_active = false;
  }

  // Fall back to serial commands if no receiver signal
  if (!have_signal) {
    if (serial_parse(throttle, yaw, pitch, roll)) {
      have_signal = true;
    } else if (serial_active) {
      // Check serial timeout
      if (millis() - serial_last_cmd_ms < SERIAL_TIMEOUT_MS) {
        have_signal = true;
        // Keep last values (throttle etc. retain their previous parse)
        throttle = 0; // safe default — caller must send continuous commands
      }
    }
  }

  // --- Failsafe check ---
  if (!have_signal && flight_state == STATE_ARMED) {
    flight_state = STATE_FAILSAFE;
    mixer_kill();
    Serial.println(F("[SAFETY] FAILSAFE — signal lost, motors killed"));
  }

  // --- Arming state machine ---
  if (!serial_active) {
    arming_update(throttle, yaw);
  }

  // --- Motor output ---
  if (flight_state == STATE_ARMED && have_signal) {
    uint8_t motor_out[MOTOR_COUNT];
    mixer_compute(throttle, yaw, pitch, roll, motor_out);
    mixer_write(motor_out);
  } else {
    mixer_kill();
  }

  // --- LED status ---
  led_update();
}
